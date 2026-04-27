"""
承富 Orchestrator · 主管家跨 Agent 呼叫
==============================================
v2.0 關鍵:主管家不再只「建議」,而是**真的呼叫**其他 Agent 並整合結果。

運作:
  使用者 → 主管家 → 識別需求 → 呼叫多個子 Agent(序列 or 併發) → 整合回應

實作策略:
  主管家透過 Action 呼叫此服務 · 此服務用 LibreChat API 以使用者身份建 conversation。
  子 Agent 回應後,結果回流給主管家作為 tool_result。

注意:
  需要 LibreChat JWT token 才能以使用者身份呼叫。
  透過 reverse proxy 從主管家對話傳遞 cookie / Authorization header。
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional
import os
import httpx
import json
import uuid
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId
from routers._deps import _is_admin_user, require_user_dep


router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])

LIBRECHAT_INTERNAL = os.getenv("LIBRECHAT_INTERNAL_URL", "http://librechat:3080")

AGENT_NUM_TO_NAME = {
    "00": "主管家",
    "01": "投標顧問",
    "02": "活動規劃師",
    "03": "設計夥伴",
    "04": "公關寫手",
    "05": "會議速記",
    "06": "知識庫查詢",
    "07": "財務試算",
    "08": "合約法務",
    "09": "結案營運",
}


class AgentInvokeRequest(BaseModel):
    agent_id: str
    input: str
    conversation_id: Optional[str] = None  # 若串在現有對話
    stream: bool = False


class WorkflowStep(BaseModel):
    agent_id: str
    prompt_template: str
    depends_on: list[str] = Field(default_factory=list)  # 依賴前面哪些 step 的結果
    # v1.6.0 #2 · WorkflowContext · 結構化 handoff
    # 該 step 把哪些「key」寫進 context · 下一個 step 透過 {context.<key>} 引用
    # 比 {step_0} 整段塞 prompt 更精準 · token 省 50-70%
    extracts: dict[str, str] = Field(
        default_factory=dict,
        description="從 response 抽哪些 key · 例:{'tender_subject': 'regex:案名:(.+?)\\n'}",
    )


class WorkflowRequest(BaseModel):
    name: str
    description: Optional[str] = None
    steps: list[WorkflowStep]
    initial_input: str
    # v1.6.0 #2 · 跨 step 共享 context · 第一步可直接訪問 initial_input
    # 後續 step 用 {context.<key>} 引用前 step extract 出來的結構化資料
    initial_context: dict = Field(default_factory=dict)


class PresetPrepareRequest(BaseModel):
    initial_input: str
    project_id: Optional[str] = None


class WorkflowAdoptionRequest(BaseModel):
    preset_id: str
    preset_name: Optional[str] = None
    status: str = Field(pattern="^(adopted|modified_adopted|rejected)$")
    project_id: Optional[str] = None
    note: Optional[str] = None


def _project_oid(project_id: str) -> ObjectId:
    try:
        return ObjectId(project_id)
    except (InvalidId, TypeError):
        raise HTTPException(400, "project_id 格式錯誤")


def _project_access_query(project_id: str, user_email: str) -> dict:
    q = {"_id": _project_oid(project_id)}
    if not _is_admin_user(user_email):
        q["$or"] = [
            {"owner": user_email},
            {"collaborators": user_email},
            {"next_owner": user_email},
        ]
    return q


def _ensure_project_access(project_id: str, user_email: str) -> None:
    from main import db
    q = _project_access_query(project_id, user_email)
    if db.projects.find_one(q, {"_id": 1}):
        return
    if db.projects.find_one({"_id": q["_id"]}, {"_id": 1}):
        raise HTTPException(403, "只能使用自己負責或協作中的專案")
    raise HTTPException(404, "project 不存在")


def _extract_agent_text(raw: str) -> str:
    """LibreChat v0.8 /api/agents/chat returns SSE; keep a JSON fallback for tests/upgrades."""
    accumulated = ""
    for line in raw.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if data.get("text") is not None:
            accumulated = data["text"]
        elif data.get("message", {}).get("text"):
            accumulated = data["message"]["text"]
        elif data.get("delta", {}).get("content"):
            accumulated += data["delta"]["content"]
    if accumulated:
        return accumulated

    try:
        data = json.loads(raw)
        return data.get("text") or data.get("response") or data.get("message", {}).get("text") or raw
    except json.JSONDecodeError:
        return raw.strip()


def _workflow_execution_enabled() -> bool:
    """v1.54 啟用 · 仍受 daily quota / kill switch / per-user 額度共同限制"""
    if os.getenv("ORCHESTRATOR_EXECUTION_ENABLED", "0").strip() != "1":
        return False
    # 全局 kill switch · admin 從 mongo 設 paused=true 即停所有 workflow
    try:
        from main import db
        flag = db.settings.find_one({"_id": "orchestrator_kill_switch"})
        if flag and flag.get("paused"):
            return False
    except Exception:
        pass
    return True


# v1.54 · daily quota · 防失控 · 每 user 每日 5 個 workflow 預設
def _daily_quota_check(user_email: str) -> tuple[bool, int, int]:
    """回 (允許, 已用, 上限)"""
    cap = int(os.getenv("ORCHESTRATOR_DAILY_PER_USER", "5"))
    try:
        from main import db
        from datetime import timedelta
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        used = db.workflow_runs.count_documents({
            "user_email": user_email,
            "started_at": {"$gte": since},
        })
        return (used < cap, used, cap)
    except Exception:
        return (True, 0, cap)


def _audit_workflow_run(user_email: str, preset_id: str, status: str, **extra) -> str:
    """記 workflow_runs · 回 mongo _id 讓 caller 可後續更新"""
    try:
        from main import db
        doc = {
            "user_email": user_email,
            "preset_id": preset_id,
            "status": status,
            "started_at": datetime.now(timezone.utc),
            **extra,
        }
        return str(db.workflow_runs.insert_one(doc).inserted_id)
    except Exception:
        return ""


def _audit_update(run_id: str, **fields) -> None:
    if not run_id:
        return
    try:
        from main import db
        db.workflow_runs.update_one({"_id": ObjectId(run_id)}, {"$set": fields})
    except Exception:
        pass


async def _resolve_agent_id(
    client: httpx.AsyncClient,
    authorization: str,
    agent_ref: str,
) -> str:
    """Resolve core agent numbers like '01' to real LibreChat agent ids."""
    if not (agent_ref.isdigit() and len(agent_ref) == 2):
        return agent_ref

    agents_r = await client.get(
        f"{LIBRECHAT_INTERNAL}/api/agents",
        headers={"Authorization": authorization},
    )
    if agents_r.status_code != 200:
        raise HTTPException(502, f"查 Agent 清單失敗:{agents_r.text[:200]}")

    data = agents_r.json()
    agents = data if isinstance(data, list) else data.get("data") or data.get("agents") or []
    target_name = AGENT_NUM_TO_NAME.get(agent_ref, "")
    for agent in agents:
        meta = agent.get("metadata") or {}
        name = agent.get("name") or ""
        if meta.get("number") == agent_ref or (target_name and target_name in name):
            resolved = agent.get("id") or agent.get("_id")
            if resolved:
                return resolved

    raise HTTPException(404, f"找不到核心 Agent #{agent_ref} · 請先建立 Agents")


# ============================================================
# 呼叫單一 Agent
# ============================================================
@router.post("/invoke")
async def invoke_agent(
    req: AgentInvokeRequest,
    authorization: Optional[str] = Header(None),
):
    """以使用者身份(透過 Authorization header 傳 JWT)呼叫指定 Agent。"""
    if not authorization:
        raise HTTPException(401, "需 Authorization header(從 LibreChat 登入後 JWT)")

    async with httpx.AsyncClient(timeout=120) as client:
        agent_id = await _resolve_agent_id(client, authorization, req.agent_id)

        # 1. 建 conversation(若沒有)
        if not req.conversation_id:
            convo_r = await client.post(
                f"{LIBRECHAT_INTERNAL}/api/convos/new",
                headers={"Authorization": authorization},
                json={"endpoint": "agents", "agent_id": agent_id},
            )
            if convo_r.status_code != 200:
                raise HTTPException(502, f"建 conversation 失敗:{convo_r.text[:200]}")
            convo = convo_r.json()
            conversation_id = convo.get("conversationId") or convo.get("id")
        else:
            conversation_id = req.conversation_id

        # 2. 送訊息
        message_id = str(uuid.uuid4())
        msg_r = await client.post(
            f"{LIBRECHAT_INTERNAL}/api/agents/chat",
            headers={"Authorization": authorization},
            json={
                "agent_id": agent_id,
                "conversationId": conversation_id,
                "parentMessageId": "00000000-0000-0000-0000-000000000000",
                "text": req.input,
                "endpoint": "agents",
                "isContinued": False,
                "isTemporary": False,
                "messageId": message_id,
            },
        )
        if msg_r.status_code != 200:
            raise HTTPException(502, f"送訊息失敗:{msg_r.text[:200]}")

        return {
            "conversation_id": conversation_id,
            "agent_ref": req.agent_id,
            "agent_id": agent_id,
            "response": _extract_agent_text(msg_r.text),
            "raw": msg_r.text,
        }


# ============================================================
# v1.7.0 D3 · 主管家 → 專家 真實 tool delegation
# 主管家透過 OpenAI function-calling 呼叫此 endpoint · AI 動態派工
# ============================================================
class DelegateRequest(BaseModel):
    target_agent: str = Field(
        ...,
        description="專家編號 01-09 或角色名(投標顧問/活動規劃師/...)",
    )
    task: str = Field(..., description="要交辦的具體任務 · 主管家用人話寫")
    context_summary: Optional[str] = Field(
        None, description="主管家整理的相關背景(目前對話 / project / 既定條件)",
    )
    expected_format: Optional[str] = Field(
        None, description="希望專家回什麼格式(JSON / 列表 / 簡報大綱 / ...)",
    )


# 角色名 → agent num 反查
_AGENT_NAME_TO_NUM = {v: k for k, v in AGENT_NUM_TO_NAME.items()}

# 防失控:單次主管家對話內最多 delegate 次數
DELEGATION_DEPTH_LIMIT = int(os.getenv("ORCHESTRATOR_DELEGATION_MAX", "5"))
# 防遞迴:不允許 delegate 到 router 自己
_FORBIDDEN_TARGETS = {"00", "主管家"}

_delegation_counter: dict[str, int] = {}  # by user_email


@router.post("/delegate")
async def delegate_to_agent(
    req: DelegateRequest,
    authorization: Optional[str] = Header(None),
    user_email: str = require_user_dep(),
):
    """主管家 → 專家 真實 tool 派工 · v1.7.0 D3
    使用情境:主管家不知該怎麼答某個專業問題 → 直接呼叫對應專家
    回流:專家完整 response · 主管家整合後回給同事

    安全:
    · 不接受 internal:cron(workflow 走另一條 path)
    · 單一 user 同對話最多 N 次 delegate(防失控)
    · 不允許 delegate 到主管家自己(防無限遞迴)
    · 與 workflow 共用 daily quota
    """
    if not _workflow_execution_enabled():
        raise HTTPException(403, "workflow / delegation 目前停用")
    if user_email.startswith("internal:"):
        raise HTTPException(403, "delegation 不接受 internal token 觸發")
    if not authorization:
        raise HTTPException(401, "需 Authorization header")

    # 解析 target_agent (allow num or name)
    target = req.target_agent.strip()
    if target in _AGENT_NAME_TO_NUM:
        target = _AGENT_NAME_TO_NUM[target]
    if target in _FORBIDDEN_TARGETS:
        raise HTTPException(400, "不可以 delegate 到主管家自己 · 直接回答即可")
    if target not in AGENT_NUM_TO_NAME:
        raise HTTPException(
            400, f"unknown agent: {req.target_agent} · 接受 01-09 或角色名稱",
        )

    # depth limit
    used = _delegation_counter.get(user_email, 0)
    if used >= DELEGATION_DEPTH_LIMIT:
        raise HTTPException(
            429,
            f"主管家本對話 delegate 次數已達 {used}/{DELEGATION_DEPTH_LIMIT} 上限 · "
            "建議直接回給同事或 reset 對話",
        )
    _delegation_counter[user_email] = used + 1

    # 組 prompt 給專家
    prompt_parts = [f"【主管家轉介】\n\n任務:{req.task}"]
    if req.context_summary:
        prompt_parts.append(f"\n\n背景:\n{req.context_summary}")
    if req.expected_format:
        prompt_parts.append(f"\n\n期望格式:{req.expected_format}")
    prompt_parts.append(
        "\n\n請以你的專業回應 · 主管家會把你的回應整合給同事 · 不必再寒暄。",
    )
    prompt = "".join(prompt_parts)

    # audit
    audit_id = _audit_workflow_run(
        user_email=user_email,
        preset_id="delegation",
        status="running",
        preset_name=f"delegate→{AGENT_NUM_TO_NAME.get(target, target)}",
        target_agent=target,
        delegation_depth=used + 1,
    )

    try:
        invoke_r = await invoke_agent(
            AgentInvokeRequest(agent_id=target, input=prompt),
            authorization,
        )
        _audit_update(
            audit_id,
            status="completed",
            completed_at=datetime.now(timezone.utc),
            final_preview=(invoke_r.get("response") or "")[:300],
        )
        return {
            "delegated_to": AGENT_NUM_TO_NAME.get(target, target),
            "agent_num": target,
            "response": invoke_r.get("response", ""),
            "delegation_count": used + 1,
            "limit": DELEGATION_DEPTH_LIMIT,
        }
    except HTTPException as e:
        _audit_update(audit_id, status="failed", error=str(e.detail)[:300])
        raise
    except Exception as e:
        _audit_update(audit_id, status="failed", error=str(e)[:300])
        raise HTTPException(500, f"delegation failed: {e}")


# ============================================================
# 執行 Workflow(多步 Agent 串接)
# ============================================================
@router.post("/workflow/run")
async def run_workflow(
    req: WorkflowRequest,
    authorization: Optional[str] = Header(None),
):
    """執行預定義 workflow。

    範例 · 完整投標閉環:
      step 1: 01 投標顧問 - PDF 結構化
      step 2: 01 投標顧問 - Go/No-Go(依賴 step 1)
      step 3: 03 設計夥伴 - KV 發想(並行)
      step 4: 07 財務試算 - 預算試算(依賴 step 1, 2)
      step 5: 01 投標顧問 - 建議書整合(依賴全部)
    """
    if not _workflow_execution_enabled():
        raise HTTPException(
            403,
            "workflow execution disabled · Phase E 請使用 /workflow/prepare-preset 產生人審草稿",
        )
    if not authorization:
        raise HTTPException(401, "需 Authorization header")

    import asyncio
    import re as _re
    results: dict[str, dict] = {}
    executed_steps: list[dict] = []
    # v1.6.0 #2 · WorkflowContext · 跨 step 結構化資料(取代 raw {step_0} 整段塞)
    workflow_context: dict[str, str] = dict(req.initial_context or {})

    def _extract_from_response(response: str, extracts: dict[str, str]) -> dict[str, str]:
        """從 response text 用指定規則抽 key
        支援:
          · 'regex:模式'  → 用 regex 抽 group 1
          · 'json:path'   → 從 ```json ... ``` 區塊抽 path(簡易)
          · 'first_line' → 第一行
          · 其他 → 取 response 前 200 字"""
        out = {}
        for key, rule in extracts.items():
            try:
                if rule.startswith("regex:"):
                    pat = rule[6:]
                    m = _re.search(pat, response)
                    out[key] = m.group(1).strip() if m else ""
                elif rule.startswith("json:"):
                    path = rule[5:]
                    m = _re.search(r"```json\s*(\{.+?\})\s*```", response, _re.DOTALL)
                    if m:
                        import json as _j
                        d = _j.loads(m.group(1))
                        for p in path.split("."):
                            d = d.get(p, "") if isinstance(d, dict) else ""
                        out[key] = str(d)
                    else: out[key] = ""
                elif rule == "first_line":
                    out[key] = response.split("\n", 1)[0].strip()[:200]
                else:
                    out[key] = response[:200]
            except Exception:
                out[key] = ""
        return out

    async with httpx.AsyncClient(timeout=300) as client:
        # v1.57 perf P0-3 · 一次 resolve 所有 agent_ref
        agent_id_cache: dict[str, str] = {}
        for step in req.steps:
            ref = step.agent_id
            if ref not in agent_id_cache:
                agent_id_cache[ref] = await _resolve_agent_id(client, authorization, ref)

        # v1.59 perf P0-5 · DAG 並行 · 沒依賴的 step 同 batch asyncio.gather
        # event-planning step_0 (場景 Brief) + step_1 (主視覺) 同時跑 · 省 ~10s
        # 規則:每 round 找出 depends_on 全部已完成的 pending step · 並行執行
        pending = list(enumerate(req.steps))
        round_no = 0
        while pending:
            round_no += 1
            ready = [
                (i, s) for i, s in pending
                if all(f"step_{j}" in results for j in [int(d.split("_")[1]) for d in s.depends_on if d.startswith("step_")])
            ]
            if not ready:
                missing = [(i, s.depends_on) for i, s in pending]
                raise HTTPException(
                    400, f"workflow DAG 解不開:剩 {missing} · 可能有 circular dependency",
                )

            async def _run_one(idx: int, step) -> tuple[int, dict]:
                # v1.6.0 #2 · prompt template 支援:
                #   · {initial_input} 原始輸入
                #   · {step_N} 完整 response (legacy · 仍支援)
                #   · {context.key} 結構化抽出的 key (新 · token 省 50-70%)
                fmt_kwargs = {
                    "initial_input": req.initial_input,
                    **{k: v.get("response", "") for k, v in results.items()},
                }
                # context.* placeholders 替換
                prompt = step.prompt_template
                for ck, cv in workflow_context.items():
                    prompt = prompt.replace(f"{{context.{ck}}}", str(cv))
                prompt = prompt.format(**fmt_kwargs)
                invoke_r = await invoke_agent(
                    AgentInvokeRequest(
                        agent_id=agent_id_cache[step.agent_id], input=prompt,
                    ),
                    authorization,
                )
                # extract structured keys 寫回 workflow_context
                if step.extracts:
                    extracted = _extract_from_response(
                        invoke_r.get("response", ""), step.extracts,
                    )
                    workflow_context.update(extracted)
                    invoke_r["_extracted_keys"] = list(extracted.keys())
                return idx, invoke_r

            batch_results = await asyncio.gather(
                *(_run_one(i, s) for i, s in ready),
                return_exceptions=False,
            )
            for idx, invoke_r in batch_results:
                step = req.steps[idx]
                step_id = f"step_{idx}"
                results[step_id] = invoke_r
                executed_steps.append({
                    "step_id": step_id,
                    "agent_id": step.agent_id,
                    "round": round_no,
                    "output_preview": (invoke_r.get("response") or "")[:300],
                })
            # 從 pending 移除已完成
            done_indices = {idx for idx, _ in batch_results}
            pending = [(i, s) for i, s in pending if i not in done_indices]

    # 排序回原 step 順序(asyncio.gather 不保序 · 但用 idx sort)
    executed_steps.sort(key=lambda x: int(x["step_id"].split("_")[1]))
    return {
        "workflow": req.name,
        "steps_executed": len(executed_steps),
        "rounds": round_no,
        "results": executed_steps,
        "context": workflow_context,  # v1.6.0 #2 · 暴露累積 context 給 caller
        "final_output": executed_steps[-1]["output_preview"] if executed_steps else None,
    }


# ============================================================
# 預設 Workflows(承富業務閉環)
# ============================================================
PRESET_WORKFLOWS = {
    "tender-full": {
        "name": "投標完整閉環",
        "description": "從招標 PDF 一路到建議書 + 報價 + Email 送件準備",
        "steps": [
            {
                "agent_id": "01",  # 投標顧問
                "prompt_template": "分析此招標 PDF 的 9 欄結構:{initial_input}",
                "depends_on": [],
            },
            {
                "agent_id": "01",
                "prompt_template": "基於以下結構化分析做 Go/No-Go 評估:\n\n{step_0}",
                "depends_on": ["step_0"],
            },
            {
                "agent_id": "07",  # 財務試算
                "prompt_template": "依據招標分析做毛利試算:\n\n{step_0}",
                "depends_on": ["step_0"],
            },
            {
                "agent_id": "01",
                "prompt_template": "整合以下資訊產建議書大綱:\n\n招標分析:{step_0}\nGo/No-Go:{step_1}\n預算:{step_2}",
                "depends_on": ["step_0", "step_1", "step_2"],
            },
        ],
    },
    "event-planning": {
        "name": "活動完整企劃",
        "description": "從活動主題 → 場地 Brief + 主視覺 + 廠商比價 + 預算",
        "steps": [
            {"agent_id": "02", "prompt_template": "為此活動產 3D 場景 Brief + 動線規劃:{initial_input}", "depends_on": []},
            {"agent_id": "03", "prompt_template": "為此活動產主視覺 3 個方向:{initial_input}", "depends_on": []},
            {"agent_id": "07", "prompt_template": "活動預算分配建議:{initial_input}\n場地 Brief:{step_0}", "depends_on": ["step_0"]},
        ],
    },
    "news-release": {
        "name": "新聞發布閉環",
        "description": "事實整理 → 新聞稿 → 媒體 Email 邀請",
        "steps": [
            {"agent_id": "04", "prompt_template": "寫新聞稿 · AP Style:{initial_input}", "depends_on": []},
            {"agent_id": "04", "prompt_template": "寫媒體邀請 Email · 附上稿件內容:{step_0}", "depends_on": ["step_0"]},
        ],
    },
}


@router.get("/workflow/presets")
def list_preset_workflows(_user: str = require_user_dep()):
    """列出承富預設的 workflow。"""
    return [
        {"id": k, "name": v["name"], "description": v["description"], "step_count": len(v["steps"])}
        for k, v in PRESET_WORKFLOWS.items()
    ]


@router.get("/workflow/presets/{preset_id}")
def get_preset_workflow(preset_id: str, _user: str = require_user_dep()):
    """回傳 workflow step 明細 · 給 Launcher 做人工確認 UI。"""
    if preset_id not in PRESET_WORKFLOWS:
        raise HTTPException(404, f"Unknown preset: {preset_id}")
    preset = PRESET_WORKFLOWS[preset_id]
    return {
        "id": preset_id,
        "name": preset["name"],
        "description": preset["description"],
        "mode": "draft_first",
        "requires_human_review": True,
        "steps": [
            {
                "id": f"step_{i}",
                "agent_id": step["agent_id"],
                "depends_on": step.get("depends_on", []),
                "prompt_template": step["prompt_template"],
            }
            for i, step in enumerate(preset["steps"])
        ],
    }


@router.post("/workflow/prepare-preset/{preset_id}")
def prepare_preset_workflow(
    preset_id: str,
    payload: PresetPrepareRequest,
    _user: str = require_user_dep(),
):
    """產生半自動 workflow 草稿。

    Phase E 先不直接多 Agent 送出；回傳給主管家的人審 prompt,由使用者確認後再送。
    """
    if preset_id not in PRESET_WORKFLOWS:
        raise HTTPException(404, f"Unknown preset: {preset_id}")
    preset = PRESET_WORKFLOWS[preset_id]
    steps = []
    for i, step in enumerate(preset["steps"]):
        steps.append({
            "id": f"step_{i}",
            "agent_id": step["agent_id"],
            "depends_on": step.get("depends_on", []),
            "prompt_preview": step["prompt_template"].replace("{initial_input}", payload.initial_input)[:500],
            "expected_output": _expected_output_for_step(preset_id, i),
            "human_review": True,
        })

    supervisor_prompt = _build_supervisor_prompt(preset_id, preset, payload.initial_input, steps)
    result = {
        "id": preset_id,
        "name": preset["name"],
        "description": preset["description"],
        "mode": "draft_first",
        "requires_human_review": True,
        "steps": steps,
        "supervisor_prompt": supervisor_prompt,
    }
    if payload.project_id:
        result["saved_to_project"] = _save_workflow_draft_to_project(
            payload.project_id,
            _user,
            preset_id,
            preset,
            steps,
            supervisor_prompt,
        )
    return result


@router.post("/workflow/adoptions")
def record_workflow_adoption(
    payload: WorkflowAdoptionRequest,
    user_email: str = require_user_dep(),
):
    """Record workflow draft adoption so Level 4 monthly reports can learn what works."""
    from main import db
    now = datetime.now(timezone.utc)
    if payload.project_id:
        _ensure_project_access(payload.project_id, user_email)
    data = {
        "preset_id": payload.preset_id,
        "preset_name": payload.preset_name or PRESET_WORKFLOWS.get(payload.preset_id, {}).get("name", payload.preset_id),
        "status": payload.status,
        "project_id": payload.project_id,
        "note": payload.note,
        "user": user_email,
        "created_at": now,
    }
    db.workflow_adoptions.insert_one(data)
    try:
        db.audit_log.insert_one({
            "action": "workflow_adoption",
            "user": user_email,
            "resource": payload.project_id or payload.preset_id,
            "details": {
                "preset_id": payload.preset_id,
                "preset_name": data["preset_name"],
                "status": payload.status,
            },
            "created_at": now,
        })
    except Exception:
        pass
    return {"ok": True, "status": payload.status, "created_at": now.isoformat()}


@router.post("/workflow/run-preset/{preset_id}")
async def run_preset_workflow(
    preset_id: str,
    payload: PresetPrepareRequest,
    authorization: Optional[str] = Header(None),
    user_email: str = require_user_dep(),
):
    """v1.54 · 執行預設 workflow · 全套 safety guards
    · 全局 kill switch
    · 每 user 每日 quota
    · audit log 寫 mongo workflow_runs
    """
    if preset_id not in PRESET_WORKFLOWS:
        raise HTTPException(404, f"Unknown preset: {preset_id}")
    if not _workflow_execution_enabled():
        raise HTTPException(403, "workflow 執行目前停用 · admin 可從中控解除 kill switch")
    if not authorization:
        raise HTTPException(401, "需 Authorization header")
    # v1.57 安全 · 防 internal:cron 用無人 quota 跑爆 · workflow 必須是真實使用者
    if user_email.startswith("internal:"):
        raise HTTPException(403, "workflow 不接受 internal token 觸發 · 必須真實使用者")

    allowed, used, cap = _daily_quota_check(user_email)
    if not allowed:
        raise HTTPException(
            429,
            f"今日已執行 {used}/{cap} 個 workflow · 預防失控 · 24h 後重置",
        )

    preset = PRESET_WORKFLOWS[preset_id]
    run_id = _audit_workflow_run(
        user_email=user_email,
        preset_id=preset_id,
        status="running",
        preset_name=preset["name"],
        step_count=len(preset["steps"]),
        initial_input_preview=(payload.initial_input or "")[:200],
    )

    req = WorkflowRequest(
        name=preset["name"],
        description=preset["description"],
        steps=[WorkflowStep(**s) for s in preset["steps"]],
        initial_input=payload.initial_input,
    )
    try:
        result = await run_workflow(req, authorization)
        _audit_update(
            run_id,
            status="completed",
            completed_at=datetime.now(timezone.utc),
            steps_executed=result.get("steps_executed", 0),
            final_preview=(result.get("final_output") or "")[:300],
        )
        result["run_id"] = run_id
        result["quota"] = {"used": used + 1, "cap": cap}
        return result
    except HTTPException as e:
        _audit_update(run_id, status="failed", error=str(e.detail)[:300])
        raise
    except Exception as e:
        _audit_update(run_id, status="failed", error=str(e)[:300])
        raise HTTPException(500, f"workflow 執行失敗:{e}")


def _expected_output_for_step(preset_id: str, index: int) -> str:
    outputs = {
        "tender-full": ["招標 9 欄摘要", "Go/No-Go 評估", "毛利與預算風險", "建議書大綱"],
        "event-planning": ["場景與動線 Brief", "主視覺方向", "預算分配建議"],
        "news-release": ["新聞稿草稿", "媒體邀請 Email"],
    }
    return outputs.get(preset_id, [])[index] if index < len(outputs.get(preset_id, [])) else "步驟產出"


def _build_supervisor_prompt(
    preset_id: str,
    preset: dict,
    initial_input: str,
    steps: list[dict],
) -> str:
    step_lines = "\n".join(
        f"{s['id']} · Agent {s['agent_id']} · 產出:{s['expected_output']} · 依賴:{', '.join(s['depends_on']) or '無'}"
        for s in steps
    )
    return (
        f"請以主管家身份執行「{preset['name']}」半自動工作流。\n\n"
        "執行規則:\n"
        "1. 每一步先說明你要做什麼,再產出草稿。\n"
        "2. 涉及報價、對外文字、客戶承諾或機敏資料時,必須標記「需人工確認」。\n"
        "3. 不確定資訊請列為待補,不要自行假設。\n"
        "4. 最後整理一份可交付清單與下一步。\n\n"
        f"Workflow ID:{preset_id}\n"
        f"流程說明:{preset['description']}\n\n"
        f"步驟:\n{step_lines}\n\n"
        f"初始輸入:\n{initial_input}"
    )


def _save_workflow_draft_to_project(
    project_id: str,
    user_email: str,
    preset_id: str,
    preset: dict,
    steps: list[dict],
    supervisor_prompt: str,
) -> dict:
    """Persist workflow draft into project.handoff without overwriting human fields."""
    from main import db
    now = datetime.now(timezone.utc)
    draft = {
        "preset_id": preset_id,
        "name": preset["name"],
        "mode": "draft_first",
        "step_count": len(steps),
        "steps": steps,
        "supervisor_prompt": supervisor_prompt,
        "created_by": user_email,
        "created_at": now,
    }
    q = _project_access_query(project_id, user_email)
    r = db.projects.update_one(
        q,
        {"$set": {
            "handoff.workflow_draft": draft,
            "handoff.updated_by": user_email,
            "handoff.updated_at": now,
            "updated_at": now,
        }},
    )
    if r.matched_count == 0:
        if db.projects.find_one({"_id": q["_id"]}, {"_id": 1}):
            raise HTTPException(403, "只能把 workflow 草稿寫入自己負責或協作中的專案")
        raise HTTPException(404, "project 不存在")

    try:
        db.audit_log.insert_one({
            "action": "workflow_prepare_preset",
            "user": user_email,
            "resource": project_id,
            "details": {
                "preset_id": preset_id,
                "preset_name": preset["name"],
                "step_count": len(steps),
            },
            "created_at": now,
        })
    except Exception:
        pass

    return {"project_id": project_id, "handoff_field": "workflow_draft"}


# ============================================================
# v1.54 · admin kill switch + runs history
# ============================================================
@router.get("/workflow/runs")
def list_workflow_runs(
    user_email: str = require_user_dep(),
    limit: int = 20,
):
    """回最近的 workflow 執行紀錄 · 自己看自己 · admin 可看全部"""
    from main import db
    q = {} if _is_admin_user(user_email) else {"user_email": user_email}
    cursor = db.workflow_runs.find(q).sort("started_at", -1).limit(min(100, max(1, limit)))
    runs = []
    for r in cursor:
        runs.append({
            "id": str(r["_id"]),
            "user_email": r.get("user_email"),
            "preset_id": r.get("preset_id"),
            "preset_name": r.get("preset_name"),
            "status": r.get("status"),
            "step_count": r.get("step_count"),
            "steps_executed": r.get("steps_executed"),
            "started_at": r.get("started_at").isoformat() if r.get("started_at") else None,
            "completed_at": r.get("completed_at").isoformat() if r.get("completed_at") else None,
            "error": r.get("error"),
        })
    return {"runs": runs}


@router.get("/workflow/kill-switch")
def get_kill_switch(_user: str = require_user_dep()):
    """所有人可查 · 知道現在可不可以執行"""
    from main import db
    flag = db.settings.find_one({"_id": "orchestrator_kill_switch"}) or {}
    enabled_env = os.getenv("ORCHESTRATOR_EXECUTION_ENABLED", "0").strip() == "1"
    return {
        "execution_enabled": enabled_env and not flag.get("paused"),
        "env_enabled": enabled_env,
        "paused_by_admin": bool(flag.get("paused")),
        "paused_at": flag.get("paused_at").isoformat() if flag.get("paused_at") else None,
        "paused_reason": flag.get("reason"),
        "daily_per_user_cap": int(os.getenv("ORCHESTRATOR_DAILY_PER_USER", "5")),
    }


class KillSwitchToggle(BaseModel):
    paused: bool
    reason: Optional[str] = None


@router.post("/workflow/kill-switch")
def set_kill_switch(
    payload: KillSwitchToggle,
    user_email: str = require_user_dep(),
):
    """admin only · 緊急時 paused=true 可瞬間停所有 workflow 執行"""
    if not _is_admin_user(user_email):
        raise HTTPException(403, "只有管理員可切 kill switch")
    from main import db
    db.settings.update_one(
        {"_id": "orchestrator_kill_switch"},
        {"$set": {
            "paused": payload.paused,
            "reason": payload.reason or "",
            "paused_at": datetime.now(timezone.utc) if payload.paused else None,
            "updated_by": user_email,
        }},
        upsert=True,
    )
    return {"ok": True, "paused": payload.paused}

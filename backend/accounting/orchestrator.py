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
from pydantic import BaseModel
from typing import Optional
import os
import httpx
from datetime import datetime


router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])

LIBRECHAT_INTERNAL = os.getenv("LIBRECHAT_INTERNAL_URL", "http://librechat:3080")


class AgentInvokeRequest(BaseModel):
    agent_id: str
    input: str
    conversation_id: Optional[str] = None  # 若串在現有對話
    stream: bool = False


class WorkflowStep(BaseModel):
    agent_id: str
    prompt_template: str
    depends_on: list[str] = []  # 依賴前面哪些 step 的結果


class WorkflowRequest(BaseModel):
    name: str
    description: Optional[str] = None
    steps: list[WorkflowStep]
    initial_input: str


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
        # 1. 建 conversation(若沒有)
        if not req.conversation_id:
            convo_r = await client.post(
                f"{LIBRECHAT_INTERNAL}/api/convos/new",
                headers={"Authorization": authorization},
                json={"endpoint": "agents", "agent_id": req.agent_id},
            )
            if convo_r.status_code != 200:
                raise HTTPException(502, f"建 conversation 失敗:{convo_r.text[:200]}")
            convo = convo_r.json()
            conversation_id = convo.get("conversationId") or convo.get("id")
        else:
            conversation_id = req.conversation_id

        # 2. 送訊息
        msg_r = await client.post(
            f"{LIBRECHAT_INTERNAL}/api/ask/agents",
            headers={"Authorization": authorization},
            json={
                "agent_id": req.agent_id,
                "conversationId": conversation_id,
                "text": req.input,
            },
        )
        if msg_r.status_code != 200:
            raise HTTPException(502, f"送訊息失敗:{msg_r.text[:200]}")

        result = msg_r.json()
        return {
            "conversation_id": conversation_id,
            "agent_id": req.agent_id,
            "response": result.get("text") or result.get("response"),
            "raw": result,
        }


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
    if not authorization:
        raise HTTPException(401, "需 Authorization header")

    results = {}
    executed_steps = []

    async with httpx.AsyncClient(timeout=300) as client:
        for i, step in enumerate(req.steps):
            # 檢查依賴
            for dep in step.depends_on:
                if dep not in results:
                    raise HTTPException(400, f"Step {i} 依賴 {dep} 但尚未執行")

            # 組合 prompt(用前面結果)
            prompt = step.prompt_template.format(
                initial_input=req.initial_input,
                **{k: v.get("response", "") for k, v in results.items()},
            )

            # 呼叫 Agent
            step_id = f"step_{i}"
            invoke_r = await invoke_agent(
                AgentInvokeRequest(agent_id=step.agent_id, input=prompt),
                authorization,
            )
            results[step_id] = invoke_r
            executed_steps.append({
                "step_id": step_id,
                "agent_id": step.agent_id,
                "output_preview": (invoke_r.get("response") or "")[:300],
            })

    return {
        "workflow": req.name,
        "steps_executed": len(executed_steps),
        "results": executed_steps,
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
def list_preset_workflows():
    """列出承富預設的 workflow。"""
    return [
        {"id": k, "name": v["name"], "description": v["description"], "step_count": len(v["steps"])}
        for k, v in PRESET_WORKFLOWS.items()
    ]


@router.post("/workflow/run-preset/{preset_id}")
async def run_preset_workflow(
    preset_id: str,
    initial_input: str,
    authorization: Optional[str] = Header(None),
):
    """執行預設 workflow。"""
    if preset_id not in PRESET_WORKFLOWS:
        raise HTTPException(404, f"Unknown preset: {preset_id}")
    preset = PRESET_WORKFLOWS[preset_id]
    req = WorkflowRequest(
        name=preset["name"],
        description=preset["description"],
        steps=[WorkflowStep(**s) for s in preset["steps"]],
        initial_input=initial_input,
    )
    return await run_workflow(req, authorization)

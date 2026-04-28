#!/usr/bin/env python3
"""
智慧助理 · Agent 批次建立(主管家 + 9 專家,可選延伸)

讀取 config-templates/presets/*.json,透過 LibreChat API 建立對應 Agent。
Agent 名稱會自動加上 Workspace emoji prefix 與 AI 引擎尾綴(OpenAI / Claude)。
主管家(00)單獨以「✨ 主管家」標示。

Agent 分層:
  - core(v1.0 預設)   : 主管家 + 9 個職能專家(共 10 個)
  - extended(v1.1 啟用): legacy/reference prompt,視需求再建

前置:
  1. LibreChat 已啟動
  2. Admin 帳號已建立(首位註冊者自動為 admin)

使用:
  # v1.0 預設(只建 core 10 個 · OpenAI + Claude 雙版本)
  LIBRECHAT_ADMIN_EMAIL=... LIBRECHAT_ADMIN_PASSWORD=... python3 scripts/create-agents.py

  # 只建 OpenAI 版
  python3 scripts/create-agents.py --provider openai

  # v1.1 升級:加 extended
  python3 scripts/create-agents.py --tier extended

  # 全部 production + extended 參考 prompt
  python3 scripts/create-agents.py --tier all

  # 乾跑(不實際建立)
  python3 scripts/create-agents.py --dry-run

  # 只建指定編號
  python3 scripts/create-agents.py --only 00,01

注意:
  - 重複執行會依 Agent name PATCH 更新,不會重複建立同名 Agent
  - OpenAI 是新版主力;Claude 是備援 / 長文件既有工作流
  - Prompt Caching 透過 .env 的 ANTHROPIC_ENABLE_PROMPT_CACHE=true 啟用(Claude 版)
"""
from __future__ import annotations  # Python 3.9 以下相容

import argparse
import glob
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request


BASE = os.environ.get("LIBRECHAT_URL", "http://localhost:3080")
PROJECT_ROOT = pathlib.Path(__file__).parent.parent
PRESETS_DIR = PROJECT_ROOT / "config-templates" / "presets"


# ========================================================
# 2026-04-19 重構:29 Agent 精簡 → 10 職能 Agent(Router + 9 專家)
# ========================================================
# 原 29 個 Agent 因職能高度重疊,精簡為 10 個。
# 每個新 Agent 內化原本 2-5 個 Agent 的職能,靠場景判斷切換角色。
# 完整涵蓋 PDF 提案的所有功能承諾(Module 01-07 + Part A/B/D)。

# Workspace 分組(新 · 10 Agent)
WORKSPACE = {
    "✨ 主管家": {"00"},
    "🎯 投標": {"01"},      # 招標解析+Go/NoGo+建議書+簡報架構+競品
    "🎪 活動": {"02"},      # 3D Brief+舞台+動線+現場+廠商比價
    "🎨 設計": {"03"},      # KV+Brief+生圖+多渠道+活動視覺系統
    "📣 公關": {"04"},      # 新聞稿+社群+月計劃+Email
    "🎙️ 會議": {"05"},      # 會議速記
    "📚 知識": {"06"},      # 知識庫查詢(RAG)
    "💰 財務": {"07"},      # 毛利+報價+比價+預算
    "⚖️ 法務": {"08"},      # 合約+NDA+稅務+法規
    "📊 營運": {"09"},      # 結案+里程碑+CRM+Onboarding
}

# Core = 全部 10 個(v1.0 必建)
CORE_SET = {"00", "01", "02", "03", "04", "05", "06", "07", "08", "09"}
# 舊的 legacy/ 下還有 29 個原始 JSON 可參考,但 v1.0 不再建立它們為獨立 Agent

PROVIDER_CONFIG = {
    "openai": {
        "api_provider": "openAI",
        "label": "OpenAI",
        # v1.54 · GPT-5.5 為主力 · 增強推理 + 原生多模態 + 強化 function calling + 更大 context
        "high_model": os.environ.get("CHENGFU_OPENAI_HIGH_MODEL", "gpt-5.5"),
        "standard_model": os.environ.get("CHENGFU_OPENAI_STANDARD_MODEL", "gpt-5.5-mini"),
        "fast_model": os.environ.get("CHENGFU_OPENAI_FAST_MODEL", "gpt-5.5-nano"),
    },
    "anthropic": {
        "api_provider": "anthropic",
        "label": "Claude",
        "high_model": os.environ.get("CHENGFU_ANTHROPIC_HIGH_MODEL", "claude-opus-4-7"),
        "standard_model": os.environ.get("CHENGFU_ANTHROPIC_STANDARD_MODEL", "claude-sonnet-4-6"),
        "fast_model": os.environ.get("CHENGFU_ANTHROPIC_FAST_MODEL", "claude-haiku-4-5"),
    },
}

HIGH_REASONING_SET = {"00", "01", "03", "08"}
FAST_SET = {"05"}


def find_workspace(num: str) -> str:
    for ws, nums in WORKSPACE.items():
        if num in nums:
            return ws
    return "📎 其他"


def get_tier(num: str) -> str:
    return "core" if num in CORE_SET else "extended"


# LibreChat v0.8.4 的 uaParser middleware 會拒絕非瀏覽器 UA
# (ua-parser-js 解析不出 browser.name → 回 "Illegal request")
# Python-urllib 預設 UA 會被擋,必須假扮成瀏覽器
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def api(method: str, path: str, token: str | None = None, data: dict | None = None) -> dict:
    url = f"{BASE}{path}"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": _BROWSER_UA,  # LibreChat uaParser 必須
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode()) if resp.length else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:500]
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {err_body}") from e


def login() -> str:
    token = os.environ.get("LIBRECHAT_JWT")
    if token:
        return token
    email = os.environ.get("LIBRECHAT_ADMIN_EMAIL")
    password = os.environ.get("LIBRECHAT_ADMIN_PASSWORD")
    if not (email and password):
        sys.exit(
            "❌ 請設定 LIBRECHAT_JWT,\n"
            "   或 LIBRECHAT_ADMIN_EMAIL + LIBRECHAT_ADMIN_PASSWORD"
        )
    try:
        resp = api("POST", "/api/auth/login", data={"email": email, "password": password})
    except Exception as e:
        sys.exit(f"❌ 登入失敗:{e}")
    if "token" not in resp:
        sys.exit(f"❌ 登入回應缺 token:{resp}")
    return resp["token"]


# LibreChat v0.8.4 agentCreateSchema 允許的 tools(filterAuthorizedTools 白名單)
# 其他值(artifacts / web_search / ocr / context / chain)會被靜默剔除,
# 所以不要送 · 只保留會被接受的 · 避免 schema 欺騙式成功
_SAFE_TOOLS = {"file_search", "execute_code"}


def select_model(num: str, provider: str, data: dict) -> str:
    cfg = PROVIDER_CONFIG[provider]
    if provider == "anthropic":
        return data.get("model") or (cfg["high_model"] if num in HIGH_REASONING_SET else cfg["standard_model"])
    if num in HIGH_REASONING_SET:
        return cfg["high_model"]
    if num in FAST_SET:
        return cfg["fast_model"]
    return cfg["standard_model"]


def provider_instructions(provider: str, instructions: str) -> str:
    if provider != "openai":
        return instructions
    note = (
        "【AI 引擎說明】\n"
        "你目前在智慧助理內使用 OpenAI 模型。若下方舊版 prompt 提到 Claude、Claude Skills 或 Anthropic,請理解為平台技能庫與既有工作流名稱,不要自稱 Claude。"
        "回答一律使用繁體中文、台灣用語與公司品牌語氣。\n\n"
    )
    return note + instructions


NOTEBOOKLM_AGENT_POLICY = """

## NotebookLM 深讀副知識庫(v1.7.1)
- 本地資料庫 / 工作包 / 檔案索引永遠是主資料來源；NotebookLM 只讀 Source Pack 快照,不得視為正式資料庫。
- 需要長文件深讀、跨來源比較、教學素材、簡報/播客草稿時,可使用 NotebookLM Source Pack 工具。
- 操作順序:previewNotebookLMSourcePack → 確認內容範圍正確 → createNotebookLMSourcePack → 由管理員或主管家 syncNotebookLMSourcePack。
- 資料等級只作標記,不阻擋 NotebookLM 建立或同步；功能最大化優先,但仍要回報官方格式/大小/API 限制。
- NotebookLM 產出的洞察若要成為正式紀錄,必須回寫到本地工作包、會議、商機、會計或知識庫模組。
"""


def append_notebooklm_policy(instructions: str) -> str:
    if "## NotebookLM 深讀副知識庫" in instructions:
        return instructions
    return instructions.rstrip() + NOTEBOOKLM_AGENT_POLICY


def preset_json_to_agent(data: dict, provider: str = "openai") -> dict:
    """Convert 1 個 preset JSON → LibreChat v0.8.4 Agent payload."""
    if provider not in PROVIDER_CONFIG:
        raise ValueError(f"Unsupported provider:{provider}")
    preset_id = data["presetId"]
    num = preset_id.split("-")[1].zfill(2) if "-" in preset_id else "00"
    ws = find_workspace(num)
    provider_cfg = PROVIDER_CONFIG[provider]
    model = select_model(num, provider, data)

    # 移除舊品牌前綴,因為 workspace emoji 已替代
    legacy_brand_prefix = "\u627f\u5bcc · "
    bare_title = data["title"].replace(legacy_brand_prefix, "").strip()
    if bare_title in ws:
        agent_name = f"{ws} · {provider_cfg['label']}"
    else:
        agent_name = f"{ws} · {bare_title} · {provider_cfg['label']}"

    # tools · 只送白名單內的 · 其他被 filterAuthorizedTools 靜默過濾
    raw_tools = data.get("capabilities") or ["file_search", "execute_code"]
    tools = [t for t in raw_tools if t in _SAFE_TOOLS]
    if not tools:
        tools = ["file_search", "execute_code"]

    # 在 description 尾端保留 preset metadata(zod schema 沒這欄位,會被 strip)
    desc_with_meta = (
        f"{data.get('description', '')}\n\n"
        f"— {ws} · #{num} · preset={preset_id} · tier={get_tier(num)} · "
        f"provider={provider} · model={model}"
    )

    # LibreChat v0.8.4 agentCreateSchema 允許的欄位:
    #   provider / model / name / description / instructions /
    #   avatar / model_parameters / tools / tool_resources / tool_options /
    #   conversation_starters / support_contact / category / artifacts /
    #   recursion_limit / end_after_tools / hide_sequential_outputs / edges
    # 不允許 · 會被 zod 靜默 strip:isCollaborative / metadata / projectIds
    # (全公司共享要用 PATCH 設 projectIds · 見 share_agent_globally)
    payload = {
        "provider": provider_cfg["api_provider"],
        "model": model,
        "name": agent_name,
        "description": desc_with_meta,
        "instructions": provider_instructions(provider, append_notebooklm_policy(data["promptPrefix"])),
        "model_parameters": {
            "temperature": data.get("temperature", 0.7),
            "maxOutputTokens": data.get("max_tokens", 4096),
            "topP": data.get("top_p", 0.95),
        },
        "tools": tools,
    }
    return payload


_CACHED_GLOBAL_PROJECT_ID: str | None = None


def get_global_project_id(token: str) -> str | None:
    """
    取 LibreChat 的 global project(name = Constants.GLOBAL_PROJECT_NAME = 'instance')。
    沒 HTTP endpoint 可列 projects · 從 /api/roles 側邊拿不到。
    改走:/api/roles/:role 含 permissions,再 fallback 到 mongo(需要 docker exec)。
    若都失敗 · 返回 None 讓呼叫端略過共享。
    """
    global _CACHED_GLOBAL_PROJECT_ID
    if _CACHED_GLOBAL_PROJECT_ID:
        return _CACHED_GLOBAL_PROJECT_ID

    # 方法 1:環境變數(最快 · 最可靠)
    env_id = os.environ.get("LIBRECHAT_INSTANCE_PROJECT_ID")
    if env_id:
        _CACHED_GLOBAL_PROJECT_ID = env_id
        return env_id

    # 方法 2:透過 /api/config 拿(若有暴露)
    try:
        cfg = api("GET", "/api/config", token=token)
        # v0.8.4 的 config response 有時會帶 instanceProjectId
        pid = cfg.get("instanceProjectId") or cfg.get("instance_project_id")
        if pid:
            _CACHED_GLOBAL_PROJECT_ID = pid
            return pid
    except Exception:
        pass

    return None


def share_agent_globally(token: str, agent_id: str) -> bool:
    """
    建立後 PATCH projectIds 讓全公司可用。
    提示:若沒設 LIBRECHAT_INSTANCE_PROJECT_ID,跑完後用 mongo 手動批次 patch:
      docker exec chengfu-mongo mongosh chengfu --eval '
        const id = db.projects.findOne({name:"instance"})._id;
        db.agents.updateMany({}, {$set:{projectIds:[id]}})'
    """
    proj_id = get_global_project_id(token)
    if not proj_id:
        return False
    try:
        api("PATCH", f"/api/agents/{agent_id}", token=token,
            data={"projectIds": [proj_id]})
        return True
    except Exception as e:
        print(f"   ⚠ 共享失敗(略過):{e}")
        return False


def load_presets(
    only: set[str] | None = None,
    tier: str = "core",
) -> list[tuple[pathlib.Path, dict]]:
    """
    載入 preset JSON。
    tier: core | extended | all
    only: 指定編號(優先於 tier)
    """
    files = sorted(PRESETS_DIR.glob("*.json"))
    result = []
    for f in files:
        num = f.stem.split("-")[0]

        if only:
            if num not in only:
                continue
        else:
            current_tier = get_tier(num)
            if tier == "core" and current_tier != "core":
                continue
            elif tier == "extended" and current_tier != "extended":
                continue
            # tier == "all" 不過濾

        with open(f, encoding="utf-8") as fp:
            result.append((f, json.load(fp)))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="只印要建立的內容,不實際呼叫 API")
    parser.add_argument("--only", type=str, help="只建指定編號(逗號分隔,如 00,01,25)")
    parser.add_argument(
        "--tier",
        type=str,
        choices=["core", "extended", "all"],
        default="core",
        help="建哪一層 Agent(預設 core = 主管家 + 9 專家)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["openai", "anthropic", "both"],
        default=os.environ.get("CHENGFU_AGENT_PROVIDER", "both"),
        help="建立哪個 AI 引擎版本(預設 both = OpenAI + Claude,供前端切換)",
    )
    args = parser.parse_args()

    only = set(s.strip().zfill(2) for s in args.only.split(",")) if args.only else None
    provider_ids = ["openai", "anthropic"] if args.provider == "both" else [args.provider]

    presets = load_presets(only=only, tier=args.tier)
    if not presets:
        sys.exit(f"❌ 找不到符合條件的 preset JSON(tier={args.tier}, only={only})")

    print(f"📋 tier={args.tier} · provider={args.provider} · 找到 {len(presets)} 個 preset:")
    for f, data in presets:
        num = f.stem.split("-")[0]
        print(f"   [{get_tier(num):8s}] {f.stem}")
    print(f"   將建立/更新 {len(presets) * len(provider_ids)} 個 Agent 版本")
    print()

    if not args.dry_run:
        print("🔐 登入 LibreChat...")
        token = login()
        print(f"   Base URL: {BASE}")
        print()

        # Codex R3.9 · idempotent · 先取現有 agents · 存在就 skip 或 PATCH
        # 原行為:每次跑都 POST · 跑 2 次會建 2 組 · 管理員會看到 20 個助手
        print("🔍 取現有 agents 清單...")
        try:
            existing = api("GET", "/api/agents", token=token)
            # LibreChat 回 {"data": [...]} 或直接 list
            existing_list = existing.get("data") if isinstance(existing, dict) else existing
            existing_by_name = {a.get("name"): a for a in (existing_list or [])}
            print(f"   已存在 {len(existing_by_name)} 個 agents")
        except Exception as e:
            print(f"   ⚠ 無法取現有 · 繼續但可能建重複: {e}")
            existing_by_name = {}

    success, fail, skipped = 0, 0, 0
    for f, data in presets:
        for provider in provider_ids:
            agent = preset_json_to_agent(data, provider=provider)
            if args.dry_run:
                print(f"[DRY-RUN] {agent['name']}")
                print(f"          provider={provider} api_provider={agent['provider']}")
                print(f"          model={agent['model']} temp={agent['model_parameters']['temperature']}")
                print(f"          instructions 長度={len(agent['instructions'])} 字")
                success += 1
                continue

            # Codex R3.9 · 已存在 · 走 PATCH 更新而非 POST 新建
            existing_agent = existing_by_name.get(agent["name"])
            if existing_agent:
                agent_id = existing_agent.get("id") or existing_agent.get("_id")
                try:
                    api("PATCH", f"/api/agents/{agent_id}", token=token, data=agent)
                    print(f"🔄 更新現有 {agent['name']} (id={agent_id})")
                    # 不重共享 · 沿用舊 projectIds
                    success += 1
                    continue
                except Exception as e:
                    print(f"⚠ PATCH {agent['name']} 失敗 · skip: {e}")
                    skipped += 1
                    continue

            try:
                resp = api("POST", "/api/agents", token=token, data=agent)
                agent_id = resp.get("id") or resp.get("_id") or "unknown"
                print(f"✅ 新建 {agent['name']}")
                print(f"   agent_id={agent_id}")
                # 建立後 · 共享給全公司 · v4.4 起 · 共享失敗視為錯誤(避免表面成功實質沒共享)
                if agent_id != "unknown":
                    if share_agent_globally(token, agent_id):
                        print("   🌐 已共享給全公司")
                    else:
                        # 若要停掉 hard-fail(某些 LibreChat 升版 projectIds 改變),
                        # 設環境變數 CHENGFU_SHARE_SOFT_FAIL=1
                        if os.environ.get("CHENGFU_SHARE_SOFT_FAIL") != "1":
                            print(f"❌ {agent['name']} 共享失敗 · agent 已建但未對全公司可見")
                            print("   原因通常是:instance project id 找不到 · 或 Mongo 手動加 projectIds")
                            print("   請見 docs/LIBRECHAT-UPGRADE-CHECKLIST.md 第 5a 步")
                            fail += 1
                            continue
                        else:
                            print("   ⚠ 共享失敗但 SOFT_FAIL=1 · 略過")
                success += 1
            except Exception as e:
                print(f"❌ {agent['name']}")
                print(f"   {e}")
                fail += 1

    print()
    print("=" * 44)
    print(f"  結果:{success} 成功 / {fail} 失敗" +
          (f" / {skipped} 略過(Codex R3.9 · 重跑保留既有)" if not args.dry_run and skipped else ""))
    print("=" * 44)

    if not args.dry_run and fail == 0:
        print()
        print("下一步:")
        print("  1. 登入 LibreChat,到「Agents」頁面確認 10 個職能 Agent 版本都在")
        print("  2. 編輯 config-templates/librechat.yaml 的 modelSpecs.list")
        print("     把 agent_id 填入,讓 5 Workspace 分組入口生效")
        print("  3. 上傳公司知識庫:./scripts/upload-knowledge-base.py")

    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

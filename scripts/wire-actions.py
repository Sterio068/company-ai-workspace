#!/usr/bin/env python3
"""
智慧助理 · 把 config-templates/actions/*.json 掛到指定 Agent (v1.51)

LibreChat v0.8.4 Action API:
  POST /api/agents/actions/:agent_id
  Body: { functions: FunctionTool[], action_id?: str, metadata: {raw_spec, domain, api_key?} }

Mapping(預設):
  fal-ai-image-gen.json    → 🎨 設計 · 設計夥伴(OpenAI + Claude)+ ✨ 主管家
  pcc-tender.json          → 🎯 投標 · 投標顧問(OpenAI + Claude)+ ✨ 主管家
  accounting-internal.json → 💰 財務 · 財務試算(OpenAI + Claude)+ ✨ 主管家

Idempotency:
  · POST /actions/:agent_id 用同一個 action_id 會更新而非重複
  · 我們用 action 檔名 hash 做為 action_id · 重跑不會疊

前置:
  LIBRECHAT_ADMIN_EMAIL / LIBRECHAT_ADMIN_PASSWORD(或 LIBRECHAT_JWT)
  ACTION_BRIDGE_TOKEN(內部 Actions 專用 · 不可用 ECC_INTERNAL_TOKEN 代替)
  ALLOW_LIBRECHAT_ACTION_SECRET_PERSISTENCE=1(才允許把外部 vendor key 寫進 LibreChat metadata)

用法:
  python3 scripts/wire-actions.py                  # 全部 mapping
  python3 scripts/wire-actions.py --only pcc       # 只接 pcc
  python3 scripts/wire-actions.py --agent-pattern "投標"  # 只接 name 含「投標」的 agent
  python3 scripts/wire-actions.py --dry-run        # 不送 · 印出計畫
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse

BASE = os.environ.get("LIBRECHAT_URL", "http://localhost:3080")
PROJECT_ROOT = pathlib.Path(__file__).parent.parent
ACTIONS_DIR = PROJECT_ROOT / "config-templates" / "actions"
ACTION_REGISTRY_PATH = ACTIONS_DIR / "registry.json"

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def load_action_agent_map() -> list[tuple[str, list[str]]]:
    """從 registry.json 讀取唯一接線清單,避免 legacy spec 被誤掛。"""
    if not ACTION_REGISTRY_PATH.exists():
        sys.exit(f"❌ 找不到 action registry:{ACTION_REGISTRY_PATH}")
    registry = json.loads(ACTION_REGISTRY_PATH.read_text())
    selected: list[tuple[str, list[str]]] = []
    for item in registry.get("actions", []):
        if not item.get("wire"):
            continue
        patterns = item.get("agent_patterns") or []
        if not patterns:
            sys.exit(f"❌ action registry 缺 agent_patterns:{item.get('file')}")
        selected.append((item["file"], patterns))
    return selected


ACTION_AGENT_MAP = load_action_agent_map()


def api(method: str, path: str, token: str | None = None, data: dict | None = None) -> dict:
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json", "User-Agent": _BROWSER_UA}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:600]
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {err_body}") from e


def login() -> str:
    token = os.environ.get("LIBRECHAT_JWT")
    if token:
        return token
    email = os.environ.get("LIBRECHAT_ADMIN_EMAIL")
    password = os.environ.get("LIBRECHAT_ADMIN_PASSWORD")
    if not (email and password):
        sys.exit("❌ 請設 LIBRECHAT_JWT 或 LIBRECHAT_ADMIN_EMAIL/PASSWORD")
    resp = api("POST", "/api/auth/login", data={"email": email, "password": password})
    if "token" not in resp:
        sys.exit(f"❌ 登入失敗:{resp}")
    return resp["token"]


def list_agents(token: str) -> list[dict]:
    resp = api("GET", "/api/agents", token=token)
    return resp.get("data") or resp.get("agents") or (resp if isinstance(resp, list) else [])


def extract_functions(spec: dict) -> list[dict]:
    """從 OpenAPI spec 抽出 OpenAI function-calling 格式的 functions[]"""
    funcs: list[dict] = []
    paths = spec.get("paths", {})
    for path, methods in paths.items():
        for method, op in methods.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            op_id = op.get("operationId")
            if not op_id:
                continue
            # 組 parameters JSON Schema
            properties: dict = {}
            required: list[str] = []
            # query / path params
            for p in op.get("parameters", []):
                schema = p.get("schema") or {}
                desc = p.get("description", "")
                properties[p["name"]] = {**schema, "description": desc}
                if p.get("required"):
                    required.append(p["name"])
            # request body
            body = op.get("requestBody", {})
            if body:
                content = body.get("content", {}).get("application/json", {})
                body_schema = content.get("schema", {})
                if body_schema.get("type") == "object":
                    for k, v in (body_schema.get("properties") or {}).items():
                        properties[k] = v
                    for k in (body_schema.get("required") or []):
                        if k not in required:
                            required.append(k)
            funcs.append({
                "function": {
                    "name": op_id,
                    "description": op.get("summary", "") or op.get("description", ""),
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            })
    return funcs


def spec_domain(spec: dict) -> str:
    """LibreChat validateActionDomain 強制 client domain 預設 https · 若 spec 是 http
    必須在 domain 帶 scheme 顯式覆蓋 · 否則 normalize 後 scheme 不對 reject"""
    servers = spec.get("servers", [])
    if not servers:
        raise ValueError("OpenAPI spec missing servers[]")
    url = servers[0]["url"]
    parsed = urlparse(url)
    netloc = parsed.netloc or parsed.path.split("/")[0]
    if parsed.scheme == "http":
        # 內部 HTTP 服務(accounting 等)· 帶 http:// scheme 否則 mismatch
        return f"http://{netloc}"
    return netloc


def stable_action_id(filename: str, agent_id: str) -> str:
    """穩定的 action_id · 每個 agent 獨立(LibreChat 限 action 與 agent 1:1)
    重跑同一個 (檔, agent) 對不會疊 · 換 agent 會建新 action"""
    base = filename.replace(".json", "").replace("-", "")[:8]
    # 取 agent_id 後 12 字 · 確保 OAuth/per-agent 配對唯一
    suffix = agent_id.replace("agent_", "").replace("-", "").replace("_", "")[:12]
    out = f"{base}{suffix}"
    return (out + "abcdefghijklmnopqrstu")[:21]


def needs_api_key(spec: dict) -> bool:
    return bool(spec.get("security"))


INTERNAL_ACTION_SPECS = ("accounting", "vision", "delegate", "internal-services", "notebooklm-bridge")


def is_internal_action_spec(spec_filename: str) -> bool:
    return any(k in spec_filename for k in INTERNAL_ACTION_SPECS)


def allow_vendor_secret_persistence() -> bool:
    """LibreChat 目前會把 action api_key 放進 action metadata。

    內部服務改用低權限 ACTION_BRIDGE_TOKEN；外部供應商 key(OpenAI/Fal)
    預設不寫入 LibreChat DB,除非部署者明確 opt-in。
    """
    return os.getenv("ALLOW_LIBRECHAT_ACTION_SECRET_PERSISTENCE", "").strip() == "1"


def get_api_key_for(spec_filename: str) -> str | None:
    if is_internal_action_spec(spec_filename):
        # 不再把全域 ECC_INTERNAL_TOKEN 寫入 LibreChat action metadata。
        # 這顆 token 只可走 action allowlist endpoint,且必須搭配 X-Acting-User。
        return os.environ.get("ACTION_BRIDGE_TOKEN")
    if "fal-ai" in spec_filename:
        if not allow_vendor_secret_persistence():
            return None
        return os.environ.get("FAL_KEY")
    if "openai-image" in spec_filename:
        if not allow_vendor_secret_persistence():
            return None
        # 用既有 OPENAI_API_KEY · 不用業主再開新帳戶
        return os.environ.get("OPENAI_API_KEY")
    return None


def needs_api_key_strict(spec: dict, spec_filename: str) -> bool:
    """spec 沒宣告 security 但內部服務要 X-Internal-Token"""
    if spec.get("security"): return True
    if is_internal_action_spec(spec_filename): return True
    return False


def required_env_for(spec_filename: str) -> str:
    if "fal-ai" in spec_filename:
        return "FAL_KEY + ALLOW_LIBRECHAT_ACTION_SECRET_PERSISTENCE=1"
    if "openai-image" in spec_filename:
        return "OPENAI_API_KEY + ALLOW_LIBRECHAT_ACTION_SECRET_PERSISTENCE=1"
    if is_internal_action_spec(spec_filename):
        return "ACTION_BRIDGE_TOKEN"
    return "API_KEY"


def wire_action(
    token: str,
    agent: dict,
    spec_path: pathlib.Path,
    *,
    dry_run: bool = False,
) -> tuple[str, str]:
    """掛一個 action 到一個 agent · 回 (status, msg)"""
    spec = json.loads(spec_path.read_text())
    domain = spec_domain(spec)
    funcs = extract_functions(spec)
    if not funcs:
        return ("skip", "spec 沒有可抽出的 operation")
    api_key = None
    if needs_api_key_strict(spec, spec_path.name):
        api_key = get_api_key_for(spec_path.name)
        if not api_key:
            envname = required_env_for(spec_path.name)
            return ("skip", f"需要 api_key 但 ${envname} 沒設 · 跳過 {spec_path.name}")

    agent_id = agent.get("id")
    if not agent_id:
        return ("error", "agent 沒 id")

    action_id = stable_action_id(spec_path.name, agent_id)
    metadata: dict = {
        "raw_spec": json.dumps(spec),  # LibreChat 接 JSON 或 YAML 字串
        "domain": domain,
        "api_key_id": (
            "action-bridge-token" if is_internal_action_spec(spec_path.name)
            else "vendor-secret-explicit-opt-in" if api_key else None
        ),
    }
    if api_key:
        metadata["api_key"] = api_key
        # 解析 spec 的 securityScheme · 決定 bearer vs custom header
        schemes = (spec.get("components") or {}).get("securitySchemes") or {}
        if schemes:
            scheme = next(iter(schemes.values()))
            if scheme.get("type") == "apiKey" and scheme.get("in") == "header":
                metadata["auth"] = {
                    "type": "service_http",
                    "authorization_type": "custom",
                    "custom_auth_header": scheme.get("name", "X-API-Key"),
                }
            else:
                metadata["auth"] = {"type": "service_http", "authorization_type": "bearer"}
        else:
            metadata["auth"] = {"type": "service_http", "authorization_type": "bearer"}

    body = {"functions": funcs, "action_id": action_id, "metadata": metadata}

    if dry_run:
        return ("plan", f"會 POST {len(funcs)} 個 function 到 agent={agent.get('name')[:30]}")

    try:
        resp = api("POST", f"/api/agents/actions/{agent_id}", token=token, data=body)
        return ("ok", f"接上 {len(funcs)} 個 function · action_id={action_id}")
    except RuntimeError as e:
        return ("error", str(e)[:200])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="逗號分隔的 action 子字串 · e.g. 'pcc' 'accounting,fal'")
    parser.add_argument("--agent-pattern", help="只接 name 含此字串的 agent")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    token = login()
    print(f"✓ 登入成功 · {BASE}")

    agents = list_agents(token)
    print(f"✓ 取得 {len(agents)} 個 agent")

    selected = ACTION_AGENT_MAP
    if args.only:
        keys = [k.strip() for k in args.only.split(",")]
        selected = [(f, ws) for f, ws in ACTION_AGENT_MAP if any(k in f for k in keys)]

    total_ok = total_skip = total_error = 0
    for spec_filename, ws_list in selected:
        spec_path = ACTIONS_DIR / spec_filename
        if not spec_path.exists():
            print(f"⚠ 跳過 · {spec_filename} 不存在")
            continue
        print(f"\n=== {spec_filename} → {ws_list} ===")
        for agent in agents:
            name = agent.get("name", "")
            if not any(ws in name for ws in ws_list):
                continue
            if args.agent_pattern and args.agent_pattern not in name:
                continue
            status, msg = wire_action(token, agent, spec_path, dry_run=args.dry_run)
            mark = {"ok": "✓", "plan": "▶", "skip": "—", "error": "✗"}.get(status, "?")
            print(f"  {mark} {name[:35]:35s} {msg}")
            if status == "ok": total_ok += 1
            elif status == "skip": total_skip += 1
            elif status == "error": total_error += 1

    print(f"\n--- 結果:✓ {total_ok}  — {total_skip}  ✗ {total_error} ---")
    if total_error:
        sys.exit(1)


if __name__ == "__main__":
    main()

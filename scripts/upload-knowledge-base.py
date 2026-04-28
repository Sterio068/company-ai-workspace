#!/usr/bin/env python3
"""
承富 AI 系統 · 公司知識庫批次上傳

將 knowledge-base/ 下的檔案上傳到 LibreChat,
並附加到「07 公司知識庫查詢」Agent,啟用 file_search 原生 RAG。

前置:
  1. LibreChat 已啟動
  2. 29 個 Agent 已建立(尤其 #07 公司知識庫查詢)
  3. knowledge-base/ 內已放置去識別化後的檔案

支援格式:.pdf .docx .txt .md(見 librechat.yaml fileConfig)

使用:
  LIBRECHAT_ADMIN_EMAIL=... LIBRECHAT_ADMIN_PASSWORD=... \\
    python3 scripts/upload-knowledge-base.py

  # 只上傳特定檔案
  python3 scripts/upload-knowledge-base.py --files "knowledge-base/建議書*"

  # 指定要附加到哪個 Agent(預設找名稱含「公司知識庫查詢」)
  python3 scripts/upload-knowledge-base.py --agent-id=agent_abc123
"""
import argparse
import glob
import json
import mimetypes
import os
import pathlib
import sys
import urllib.error
import urllib.request
import uuid


BASE = os.environ.get("LIBRECHAT_URL", "http://localhost:3080")
PROJECT_ROOT = pathlib.Path(__file__).parent.parent
KB_DIR = PROJECT_ROOT / "knowledge-base"

SUPPORTED_EXT = {".pdf", ".docx", ".txt", ".md", ".xlsx", ".pptx"}


def api(method, path, token=None, data=None, multipart=None):
    url = f"{BASE}{path}"
    headers = {
        # LibreChat rejects generic script clients through ua-parser in some routes.
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if multipart:
        # 手動組 multipart/form-data
        boundary = f"----{uuid.uuid4().hex}"
        body = b""
        for name, (filename, content, ctype) in multipart.items():
            body += f"--{boundary}\r\n".encode()
            if filename is None:
                body += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
            else:
                body += f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
                body += f"Content-Type: {ctype}\r\n\r\n".encode()
            body += content
            body += b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif data:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode()
    else:
        body = None

    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            if not raw:
                return {}
            return json.loads(raw.decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:500]}") from e


def login():
    token = os.environ.get("LIBRECHAT_JWT")
    if token:
        return token
    email = os.environ.get("LIBRECHAT_ADMIN_EMAIL")
    password = os.environ.get("LIBRECHAT_ADMIN_PASSWORD")
    if not (email and password):
        sys.exit("❌ 需設 LIBRECHAT_JWT 或 LIBRECHAT_ADMIN_EMAIL+PASSWORD")
    resp = api("POST", "/api/auth/login", data={"email": email, "password": password})
    return resp["token"]


def find_kb_agent(token, expected_name):
    """Find the production knowledge Agent by exact name.

    Avoid fuzzy matching here: attaching company files to the wrong Agent is a
    real data-boundary bug. Use --agent-id when the production Agent was renamed.
    """
    resp = api("GET", "/api/agents", token=token)
    if isinstance(resp, dict):
        agents = resp.get("agents") or resp.get("data") or resp.get("results") or []
    else:
        agents = resp
    agents = agents or []
    for a in agents:
        name = a.get("name", "")
        provider = (a.get("provider") or a.get("endpoint") or "").lower()
        if name == expected_name and ("openai" in provider or "openai" in name.lower()):
            return a.get("id") or a.get("_id")
    return None


def gather_files(pattern=None):
    if pattern:
        files = [pathlib.Path(p).resolve() for p in glob.glob(pattern)]
    else:
        files = []
        for ext in SUPPORTED_EXT:
            files.extend(path.resolve() for path in KB_DIR.rglob(f"*{ext}"))
    return sorted(files)


def upload_file(token, path, agent_id):
    ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    with open(path, "rb") as f:
        content = f.read()
    # LibreChat v0.8+ file_search agent resource upload.
    # The upload route attaches the file to the agent automatically when
    # agent_id + tool_resource=file_search are present.
    file_id = str(uuid.uuid4())
    resp = api("POST", "/api/files", token=token, multipart={
        "endpoint": (None, b"agents", "text/plain"),
        "endpointType": (None, b"agents", "text/plain"),
        "agent_id": (None, agent_id.encode(), "text/plain"),
        "tool_resource": (None, b"file_search", "text/plain"),
        "file_id": (None, file_id.encode(), "text/plain"),
        "file": (path.name, content, ctype),
    })
    return resp.get("file_id") or resp.get("id") or resp.get("_id") or file_id


def attach_to_agent(token, agent_id, file_ids):
    # v0.7+ PATCH /api/agents/:id 更新 attached files
    resp = api("PATCH", f"/api/agents/{agent_id}", token=token, data={
        "attached_file_ids": file_ids,
    })
    return resp


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--files", help="glob pattern 指定要上傳的檔案")
    parser.add_argument("--agent-id", help="指定要附加到的 Agent ID")
    parser.add_argument(
        "--agent-name",
        default="📚 知識 · 知識庫查詢 · OpenAI",
        help="要附加的知識庫 Agent 精確名稱(預設 OpenAI production 知識庫 Agent)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = gather_files(args.files)
    if not files:
        sys.exit(f"❌ 找不到要上傳的檔案(在 {KB_DIR}/)")

    total_size = sum(f.stat().st_size for f in files) / 1024 / 1024
    print(f"📂 找到 {len(files)} 個檔案,總 {total_size:.1f} MB")
    for f in files:
        size_mb = f.stat().st_size / 1024 / 1024
        try:
            display_path = f.relative_to(PROJECT_ROOT)
        except ValueError:
            display_path = f
        print(f"   {display_path}  ({size_mb:.2f} MB)")
    print()

    if args.dry_run:
        print("[DRY-RUN] 不會實際上傳")
        return 0

    token = login()
    print("🔐 已登入")

    # 找目標 Agent
    agent_id = args.agent_id or find_kb_agent(token, args.agent_name)
    if not agent_id:
        sys.exit(
            f"❌ 找不到精確名稱為「{args.agent_name}」的 OpenAI 知識庫 Agent。"
            "請先執行 create-agents.py,或明確使用 --agent-id=agent_xxx,避免檔案掛到錯誤 Agent。"
        )
    print(f"🎯 目標 Agent: {agent_id}")
    print()

    # 逐檔上傳 · v0.8+ 會自動掛到 Agent tool_resources.file_search
    file_ids = []
    for f in files:
        print(f"📤 上傳 {f.name}...", end=" ", flush=True)
        try:
            fid = upload_file(token, f, agent_id)
            file_ids.append(fid)
            print(f"✅ file_id={fid}")
        except Exception as e:
            print(f"❌ {e}")

    if not file_ids:
        sys.exit("❌ 沒有檔案成功上傳")

    print()
    print("下一步驗證:")
    print("  1. 登入 LibreChat,開啟「公司知識庫查詢」Agent")
    print("  2. 問:「去年環保局案的預算結構大概怎麼配?」")
    print("  3. 預期:Agent 引用你剛上傳的結案報告並回答")


if __name__ == "__main__":
    sys.exit(main() or 0)

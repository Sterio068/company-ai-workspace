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
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if multipart:
        # 手動組 multipart/form-data
        boundary = f"----{uuid.uuid4().hex}"
        body = b""
        for name, (filename, content, ctype) in multipart.items():
            body += f"--{boundary}\r\n".encode()
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
            return json.loads(resp.read().decode()) if resp.length else {}
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


def find_kb_agent(token):
    """Find the 07 公司知識庫查詢 Agent by name."""
    resp = api("GET", "/api/agents", token=token)
    agents = resp.get("agents", resp) if isinstance(resp, dict) else resp
    for a in agents:
        name = a.get("name", "")
        if "知識庫查詢" in name or "知識庫" in name and "查詢" in name:
            return a.get("id") or a.get("_id")
    return None


def gather_files(pattern=None):
    if pattern:
        files = [pathlib.Path(p) for p in glob.glob(pattern)]
    else:
        files = []
        for ext in SUPPORTED_EXT:
            files.extend(KB_DIR.rglob(f"*{ext}"))
    return sorted(files)


def upload_file(token, path):
    ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    with open(path, "rb") as f:
        content = f.read()
    # LibreChat 的上傳 endpoint(v0.7+)
    resp = api("POST", "/api/files", token=token, multipart={
        "file": (path.name, content, ctype),
    })
    return resp.get("file_id") or resp.get("id") or resp.get("_id")


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
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = gather_files(args.files)
    if not files:
        sys.exit(f"❌ 找不到要上傳的檔案(在 {KB_DIR}/)")

    total_size = sum(f.stat().st_size for f in files) / 1024 / 1024
    print(f"📂 找到 {len(files)} 個檔案,總 {total_size:.1f} MB")
    for f in files:
        size_mb = f.stat().st_size / 1024 / 1024
        print(f"   {f.relative_to(PROJECT_ROOT)}  ({size_mb:.2f} MB)")
    print()

    if args.dry_run:
        print("[DRY-RUN] 不會實際上傳")
        return 0

    token = login()
    print("🔐 已登入")

    # 找目標 Agent
    agent_id = args.agent_id or find_kb_agent(token)
    if not agent_id:
        sys.exit("❌ 找不到「公司知識庫查詢」Agent,請先執行 create-agents.py,或用 --agent-id=...")
    print(f"🎯 目標 Agent: {agent_id}")
    print()

    # 逐檔上傳
    file_ids = []
    for f in files:
        print(f"📤 上傳 {f.name}...", end=" ", flush=True)
        try:
            fid = upload_file(token, f)
            file_ids.append(fid)
            print(f"✅ file_id={fid}")
        except Exception as e:
            print(f"❌ {e}")

    if not file_ids:
        sys.exit("❌ 沒有檔案成功上傳")

    # 附加到 Agent
    print()
    print(f"🔗 附加 {len(file_ids)} 個檔案到 Agent {agent_id}...", end=" ")
    try:
        attach_to_agent(token, agent_id, file_ids)
        print("✅")
    except Exception as e:
        print(f"❌ {e}")
        print("   已上傳但未附加,請到 LibreChat UI 手動關聯")

    print()
    print("下一步驗證:")
    print("  1. 登入 LibreChat,開啟「公司知識庫查詢」Agent")
    print("  2. 問:「去年環保局案的預算結構大概怎麼配?」")
    print("  3. 預期:Agent 引用你剛上傳的結案報告並回答")


if __name__ == "__main__":
    sys.exit(main() or 0)

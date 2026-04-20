#!/usr/bin/env python3
"""
承富 AI 系統 · 10 同仁帳號批次建立

讀取 config-templates/users.json,透過 LibreChat API 建立對應使用者。
自動產生強隨機密碼,寫入 scripts/passwords.txt(分發完畢請刪除)。

前置:
  1. LibreChat 已啟動
  2. 已經由 UI 建立第一位 admin(首位註冊者),或已有 LIBRECHAT_JWT token
  3. config-templates/users.json 已建立(見範例)

users.json 範例:
[
  {"email": "alice@chengfu.com",   "name": "王小明", "role": "USER"},
  {"email": "bob@chengfu.com",     "name": "李小華", "role": "USER"},
  {"email": "sterio@chengfu.com",  "name": "Sterio", "role": "ADMIN"}
]

使用:
  LIBRECHAT_ADMIN_EMAIL=sterio@... LIBRECHAT_ADMIN_PASSWORD=... \\
    python3 scripts/create-users.py
"""
import argparse
import json
import os
import pathlib
import secrets
import string
import sys
import urllib.error
import urllib.request
from datetime import datetime


BASE = os.environ.get("LIBRECHAT_URL", "http://localhost:3080")
PROJECT_ROOT = pathlib.Path(__file__).parent.parent
USER_FILE = PROJECT_ROOT / "config-templates" / "users.json"
PASSWORD_FILE = PROJECT_ROOT / "scripts" / "passwords.txt"


def gen_password(n: int = 14) -> str:
    """產生人類可讀但強度足夠的密碼。"""
    # 避免易混淆字元 0/O/I/l/1
    alphabet = "".join(c for c in (string.ascii_letters + string.digits) if c not in "0OIl1")
    symbols = "!@#$%&*-_+="
    # 至少 1 個符號 + 1 個數字
    body = [secrets.choice(string.ascii_lowercase) for _ in range(n - 3)]
    body.append(secrets.choice(string.ascii_uppercase))
    body.append(secrets.choice(string.digits))
    body.append(secrets.choice(symbols))
    secrets.SystemRandom().shuffle(body)
    return "".join(body)


def api(method, path, token=None, data=None):
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
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


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not USER_FILE.exists():
        sys.exit(f"❌ 找不到 {USER_FILE}\n   建立範例後再執行(見 script 開頭註解)")

    with open(USER_FILE, encoding="utf-8") as f:
        users = json.load(f)

    print(f"📋 {USER_FILE} 列出 {len(users)} 個使用者")
    for u in users:
        role = u.get("role", "USER")
        print(f"   {u['email']}  ({u.get('name', '無名')}, {role})")
    print()

    if args.dry_run:
        print("[DRY-RUN] 不會實際建立,也不會產生密碼")
        return 0

    token = login()
    print("🔐 已登入")

    results = []
    for u in users:
        password = gen_password()
        payload = {
            "email": u["email"],
            "name": u.get("name", u["email"].split("@")[0]),
            "username": u["email"].split("@")[0],
            "password": password,
            "role": u.get("role", "USER"),
        }
        try:
            resp = api("POST", "/api/user", token=token, data=payload)
            print(f"✅ {u['email']} 建立成功")
            results.append({**u, "password": password, "status": "ok"})
        except Exception as e:
            print(f"❌ {u['email']}: {e}")
            results.append({**u, "password": "", "status": f"failed: {e}"})

    # 寫密碼檔
    with open(PASSWORD_FILE, "w", encoding="utf-8") as f:
        f.write(f"# 承富 AI 系統 · 初始密碼表\n")
        f.write(f"# 建立時間:{datetime.now().isoformat()}\n")
        f.write(f"# ⚠ 分發完畢請 shred -u scripts/passwords.txt 安全刪除\n\n")
        for r in results:
            if r["status"] == "ok":
                f.write(f"{r['email']:30s}  {r['password']}\n")
            else:
                f.write(f"# {r['email']:30s}  FAILED: {r['status']}\n")

    os.chmod(PASSWORD_FILE, 0o600)
    print()
    print(f"📝 密碼表已寫入 {PASSWORD_FILE}(權限 600,僅本人可讀)")
    print("   請分發後執行:shred -u scripts/passwords.txt")


if __name__ == "__main__":
    sys.exit(main() or 0)

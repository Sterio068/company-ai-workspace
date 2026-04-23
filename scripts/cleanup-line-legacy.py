#!/usr/bin/env python3
"""
技術債#4(2026-04-23)· cleanup db.user_preferences 內舊 line_token

R26#2 · LINE Notify 已停服 2025-03-31 · 既有 line_token 全失效
此 script 把舊 line_token 全清掉(寫 audit log) · 並提示同事改設 webhook

用法:
    python3 scripts/cleanup-line-legacy.py             # dry-run · 只列數量
    python3 scripts/cleanup-line-legacy.py --execute   # 真刪 + audit
"""
import sys
import os
from datetime import datetime, timezone

# 連 Mongo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "accounting"))

try:
    from pymongo import MongoClient
except ImportError:
    print("缺 pymongo · 請 `pip install pymongo`", file=sys.stderr)
    sys.exit(1)


def main(execute: bool = False):
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB_NAME", "chengfu_ai")
    db = MongoClient(mongo_url)[db_name]

    q = {"key": "line_token"}
    n = db.user_preferences.count_documents(q)
    print(f"找到 {n} 筆 line_token(已停服 · 不再有效)")

    if n == 0:
        print("✅ DB 內無 line_token · 不用清")
        return

    affected_emails = sorted({
        p["user_email"] for p in db.user_preferences.find(q, {"user_email": 1})
    })
    print(f"影響同事:{len(affected_emails)} 位")
    for e in affected_emails:
        print(f"  - {e}")

    if not execute:
        print("\n[dry-run] 加 --execute 真刪")
        return

    r = db.user_preferences.delete_many(q)
    db.knowledge_audit.insert_one({
        "action": "cleanup_line_legacy",
        "user": "scripts/cleanup-line-legacy.py",
        "resource": "user_preferences.line_token",
        "details": {"deleted": r.deleted_count, "affected_emails": affected_emails},
        "created_at": datetime.now(timezone.utc),
    })
    print(f"\n✅ 刪 {r.deleted_count} 筆 · audit 已紀錄")
    print("⚠️ 提醒這 {} 位改 webhook(launcher → 使用教學 → webhook URL)".format(
        len(affected_emails)))


if __name__ == "__main__":
    execute = "--execute" in sys.argv
    main(execute=execute)

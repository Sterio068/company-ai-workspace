#!/usr/bin/env python3
"""
承富 AI · 政府電子採購網每日監測
==========================================================

每日抓 g0v PCC API 看承富有興趣的關鍵字是否有新標案,
發現新標案 → 寫入 MongoDB(Launcher 會看到)+ optional Slack/Email。

用法:
  python3 scripts/tender-monitor.py

cron(每日早上 9 點):
  0 9 * * * cd /Users/chengfu-admin/ChengFu && /usr/bin/python3 scripts/tender-monitor.py

環境變數(選配):
  TENDER_MONITOR_KEYWORDS='環保,文化,觀光,宣導,AI,永續'  # 逗號分隔
  TENDER_SLACK_WEBHOOK=https://hooks.slack.com/...       # Slack 通知
"""
import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime

try:
    from pymongo import MongoClient
except ImportError:
    sys.exit("pip install pymongo")


MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/chengfu")
KEYWORDS = [k.strip() for k in os.environ.get(
    "TENDER_MONITOR_KEYWORDS",
    "環保,文化,觀光,宣導,AI,永續,行銷,公關,活動策劃"
).split(",")]
SLACK_WEBHOOK = os.environ.get("TENDER_SLACK_WEBHOOK")

PCC_API = "https://pcc.g0v.ronny.tw/api"


def search_tenders(keyword: str, page: int = 1) -> list:
    url = f"{PCC_API}/searchbytitle?{urllib.parse.urlencode({'query': keyword, 'page': page})}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read().decode())
            return data.get("records", [])
    except Exception as e:
        print(f"  ⚠ {keyword} 查詢失敗: {e}", file=sys.stderr)
        return []


def send_slack(text: str):
    if not SLACK_WEBHOOK:
        return
    try:
        req = urllib.request.Request(
            SLACK_WEBHOOK,
            data=json.dumps({"text": text}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"  ⚠ Slack 通知失敗: {e}", file=sys.stderr)


def main():
    client = MongoClient(MONGO_URI)
    db = client.get_default_database()
    alerts = db.tender_alerts
    alerts.create_index("tender_key", unique=True)

    now = datetime.utcnow().isoformat()
    new_count = 0
    total_scanned = 0

    print(f"[{now}] 承富標案監測啟動 · 關鍵字 {len(KEYWORDS)} 個")
    print(f"   {', '.join(KEYWORDS)}")
    print()

    for kw in KEYWORDS:
        print(f"🔍 {kw}")
        records = search_tenders(kw, page=1)
        print(f"   找到 {len(records)} 筆")
        total_scanned += len(records)

        for rec in records:
            brief = rec.get("brief", {})
            title = brief.get("title") or rec.get("title", "")
            unit = rec.get("unit_name", "")
            job_no = rec.get("job_number", "")
            tender_key = f"{unit}:{job_no}"

            # 只記新標案(避免重複)
            existing = alerts.find_one({"tender_key": tender_key})
            if existing:
                continue

            # 寫入 MongoDB
            alerts.insert_one({
                "tender_key": tender_key,
                "keyword": kw,
                "title": title,
                "unit_name": unit,
                "job_number": job_no,
                "brief_type": brief.get("type", ""),
                "date": rec.get("date"),
                "raw": rec,
                "discovered_at": datetime.utcnow(),
                "status": "new",
            })
            new_count += 1
            print(f"   ✨ 新標案: {title[:60]} · {unit}")

    # Slack 通知
    if new_count > 0 and SLACK_WEBHOOK:
        send_slack(
            f"📢 承富標案監測 · {datetime.now():%Y-%m-%d}\n"
            f"發現 {new_count} 個新標案(掃描 {total_scanned} 筆 · {len(KEYWORDS)} 關鍵字)\n"
            f"打開承富 AI Launcher 看詳情。"
        )

    print()
    print("=" * 40)
    print(f"✅ 完成 · 新發現 {new_count} 筆 / 掃描 {total_scanned} 筆")
    print("=" * 40)


if __name__ == "__main__":
    main()

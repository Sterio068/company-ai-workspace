#!/usr/bin/env python3
"""
承富 AI · 每日晨間 Digest
==========================================================

每天早上 8:30 自動產:
  - 昨日承富對話活動摘要(誰用了什麼 Agent)
  - 今日待辦(從承富專案 · 截止日近的)
  - 今日新標案 alerts
  - 今日關鍵日期(合約到期 / 繳稅 / 驗收)
  - Claude 產出「給承富團隊的今日 3 個建議」

寄送 email 給 ADMIN_EMAIL + 所有 ACTIVE 使用者(可選)。

cron:
  30 8 * * 1-5 cd /path/to/ChengFu && python3 scripts/daily-digest.py
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta

try:
    from pymongo import MongoClient
    import anthropic
except ImportError:
    sys.exit("pip install pymongo anthropic")


MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/chengfu")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "sterio@chengfu.local")
ACCOUNTING_BASE = os.environ.get("ACCOUNTING_BASE", "http://localhost/api-accounting")


def collect_yesterday_activity(db):
    """抓昨日對話 + 回饋。"""
    yesterday = datetime.utcnow() - timedelta(days=1)
    try:
        convos = list(db.conversations.find({
            "createdAt": {"$gte": yesterday.replace(hour=0, minute=0, second=0)}
        }).limit(50))
    except Exception:
        convos = []

    feedbacks = list(db.feedback.find({
        "created_at": {"$gte": yesterday.replace(hour=0, minute=0, second=0)}
    }))

    by_agent = {}
    for c in convos:
        agent = c.get("title", "unknown")[:50]
        by_agent[agent] = by_agent.get(agent, 0) + 1

    return {
        "total_convos": len(convos),
        "top_agents": sorted(by_agent.items(), key=lambda x: -x[1])[:5],
        "feedback_count": len(feedbacks),
        "positive": sum(1 for f in feedbacks if f.get("verdict") == "up"),
    }


def collect_today_priorities(db):
    """今日截止 / 7 天內截止專案 + 標案 + 合約。"""
    today = datetime.utcnow().date()
    next_week = today + timedelta(days=7)

    # 近期截止專案
    upcoming_projects = []
    for p in db.projects.find({"status": "active"}):
        deadline = p.get("deadline")
        if deadline and today.isoformat() <= deadline <= next_week.isoformat():
            upcoming_projects.append({
                "name": p["name"],
                "client": p.get("client", ""),
                "deadline": deadline,
                "days_left": (datetime.fromisoformat(deadline).date() - today).days,
            })
    upcoming_projects.sort(key=lambda x: x["days_left"])

    # 新標案
    new_tenders = list(db.tender_alerts.find({
        "status": "new"
    }).sort("discovered_at", -1).limit(5))

    return {
        "upcoming_projects": upcoming_projects[:5],
        "new_tenders": [{"title": t["title"][:80], "unit": t["unit_name"]} for t in new_tenders],
    }


def generate_ai_advice(activity: dict, priorities: dict) -> str:
    """用 Claude 產今日 3 個建議。"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "(未設 ANTHROPIC_API_KEY · 跳過 AI 建議)"

    client = anthropic.Anthropic()
    prompt = f"""承富創意整合行銷的 10 人團隊 · 今日晨會資料:

昨日活動:
- 總對話數:{activity['total_convos']}
- 主要 Agent:{activity['top_agents'][:3]}
- 👍 回饋:{activity['positive']} / {activity['feedback_count']}

今日重點:
- 近期截止專案:{[p['name'] + f" ({p['days_left']}天)" for p in priorities['upcoming_projects'][:3]]}
- 新標案 alerts:{[t['title'] for t in priorities['new_tenders'][:3]]}

請給承富團隊「今日 3 個具體建議」(每個 1-2 句,繁中,不超過 100 字)。
風格:精簡 · 可行動 · 承富老闆風。"""

    resp = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def send_digest_email(activity, priorities, advice):
    """透過 accounting API 的 /admin/email/send 寄送。"""
    body = f"""<html><body style="font-family: -apple-system, 'PingFang TC', sans-serif; max-width: 600px; margin: 0 auto; color: #1D1D1F;">

<div style="background: linear-gradient(135deg, #0F2340, #2D4268); color: white; padding: 24px; border-radius: 12px;">
  <h1 style="margin: 0;">早安,承富 👋</h1>
  <p style="margin: 8px 0 0 0; opacity: 0.9;">{datetime.now().strftime("%Y 年 %m 月 %d 日 · %A")}</p>
</div>

<h2>📊 昨日活動</h2>
<ul>
  <li>AI 對話:{activity['total_convos']} 次</li>
  <li>👍 回饋:{activity['positive']} / {activity['feedback_count']} 筆</li>
  <li>熱門 Agent:{', '.join([f"{a[0]}({a[1]})" for a in activity['top_agents'][:3]])}</li>
</ul>

<h2>⏰ 近期截止</h2>
{''.join([f"<li><b>{p['name']}</b> · {p['client']} · 剩 {p['days_left']} 天</li>" for p in priorities['upcoming_projects'][:5]]) or '<li>無近 7 天截止事項</li>'}

<h2>🔍 新標案(值得關注)</h2>
<ul>
{''.join([f"<li><b>{t['title']}</b><br><small>{t['unit']}</small></li>" for t in priorities['new_tenders']]) or '<li>今日無新發現</li>'}
</ul>

<h2>💡 AI 給今日的 3 個建議</h2>
<div style="background: #F5F5F7; padding: 16px; border-radius: 8px; border-left: 3px solid #0F2340;">
{advice.replace(chr(10), '<br>')}
</div>

<hr style="margin: 32px 0; border: none; border-top: 1px solid #E5E5EA;">
<p style="color: #8E8E93; font-size: 12px; text-align: center;">
  承富 AI 系統自動產出 · <a href="http://localhost/">打開平台</a>
</p>
</body></html>"""

    # ROADMAP §11.8 · 加 X-User-Email · 通過 require_admin
    # ADMIN_EMAIL 預設 sterio068@gmail.com · env 可覆蓋
    req = urllib.request.Request(
        f"{ACCOUNTING_BASE}/admin/email/send",
        data=json.dumps({
            "to": ADMIN_EMAIL,
            "subject": f"承富 AI · 今日 digest · {datetime.now():%m/%d}",
            "body": body,
            "body_type": "html",
        }).encode(),
        headers={
            "Content-Type": "application/json",
            "X-User-Email": ADMIN_EMAIL,  # cron 走 admin 身分
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"✅ 已寄 digest 到 {ADMIN_EMAIL}")
    except Exception as e:
        print(f"⚠ Email 寄送失敗(可能 SMTP 未設): {e}")
        # 若沒設 email,印出來也好
        print()
        print("========== DIGEST ==========")
        print(body)


def main():
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 承富 AI 今日 digest 產生中...")
    client = MongoClient(MONGO_URI)
    db = client.get_default_database()

    activity = collect_yesterday_activity(db)
    priorities = collect_today_priorities(db)
    advice = generate_ai_advice(activity, priorities)

    print(f"  昨日:{activity['total_convos']} 對話")
    print(f"  今日截止:{len(priorities['upcoming_projects'])}")
    print(f"  新標案:{len(priorities['new_tenders'])}")
    print()

    send_digest_email(activity, priorities, advice)


if __name__ == "__main__":
    main()

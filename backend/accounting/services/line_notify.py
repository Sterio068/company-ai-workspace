"""
LINE Notify · Feature #2 · 推播通知

每位同事在 launcher「使用教學 → API Key」綁自己 LINE Notify token
觸發場景:
  - tender-monitor cron(每日)· 新標案符合關鍵字 → LINE
  - quota 80% / 95% 觸發(scripts/quota-watch · v1.3)· admin LINE
  - 月報寄出時 → LINE summary
  - 社群排程失敗 3 次 → admin LINE

LINE Notify 是免費官方服務 · https://notify-bot.line.me/
- 每 token 1000 msg/hour 限速
- 簡單 POST 即可發

import:
  from services.line_notify import notify_user, notify_admin
"""
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger("chengfu")

LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"


def send(token: str, message: str, *, timeout: int = 10) -> bool:
    """送一則 LINE · 成功 True · 失敗 False(log warn)
    · 不 raise · 通知是 best-effort · 主流程不擋"""
    if not token:
        return False
    try:
        data = urllib.parse.urlencode({"message": message[:1000]}).encode()
        req = urllib.request.Request(
            LINE_NOTIFY_URL, data=data,
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ok = 200 <= r.status < 300
            if not ok:
                logger.warning("[line] send fail status=%d", r.status)
            return ok
    except Exception as e:
        logger.warning("[line] send exception: %s", str(e)[:100])
        return False


def notify_user(db, email: str, message: str) -> bool:
    """從 db.user_preferences 拿 line_token · 沒設則跳過"""
    pref = db.user_preferences.find_one({"user_email": email, "key": "line_token"})
    if not pref or not pref.get("value"):
        return False
    return send(pref["value"], message)


def notify_admin(db, message: str) -> int:
    """所有 admin 都收 · 回成功數"""
    from main import _admin_allowlist
    count = 0
    for email in _admin_allowlist:
        if notify_user(db, email, message):
            count += 1
    return count

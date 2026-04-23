"""
Webhook Notify · v1.2 Day 3 R26#2 修(取代 LINE Notify · 已停服 2025-03-31)

承富同事可選任一 webhook(Slack / Discord / Telegram bot / Mattermost / 自架)
而非綁死 LINE Notify(LINE Notify 2025-03-31 已停服 · 官方公告 notify-bot.line.me)

webhook URL 通常長這樣:
- Slack:https://hooks.slack.com/services/T.../B.../...
- Discord:https://discord.com/api/webhooks/.../...
- Telegram bot:https://api.telegram.org/bot{TOKEN}/sendMessage(需 chat_id 在 query)
- Mattermost:https://mm.example.com/hooks/...

不同平台 payload 格式略不同 · 我們用「猜」:
- 含 'slack' / 'discord' / 'mattermost' → JSON {"text": ...}
- 含 'telegram' → query string sendMessage
- 其他 → JSON {"text": ...} 預設

best-effort · 失敗不擋主流程
"""
import ipaddress
import json
import logging
import socket
import urllib.parse
import urllib.request

logger = logging.getLogger("chengfu")


# R27#4 · SSRF 防護 · webhook URL user-supplied · 立刻 server-side fetch
# 沒護欄 → 同仁可探內網(librechat/mongodb/meili/localhost/admin endpoint)
# 白名單也行 · 但承富 user 自架 webhook(Mattermost on-prem)合法 · 改 IP block
_BLOCKED_HOSTS = {"localhost", "metadata.google.internal"}


class WebhookValidationError(ValueError):
    """webhook URL 不合法 · raise 在 set_webhook 時擋下"""


def validate_webhook_url(url: str) -> str:
    """R27#4 · 防 SSRF · raise WebhookValidationError 若不合法
    1. 必須 https:// 起頭(telegram bot / mattermost / slack / discord 都支援)
    2. host 解析後 IP 不可是 private/loopback/link-local/reserved
    3. 阻擋 metadata service hostname
    """
    if not url:
        raise WebhookValidationError("webhook URL 不可為空")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise WebhookValidationError("webhook 必須 https://")
    host = (parsed.hostname or "").lower()
    if not host or host in _BLOCKED_HOSTS:
        raise WebhookValidationError(f"webhook host 不允許:{host or '(空)'}")
    # 解析 DNS · 拒絕內網 IP(防 attacker 用 evil.com → CNAME → 10.0.0.1)
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise WebhookValidationError(f"webhook host DNS 解析失敗:{e}")
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved \
                or ip.is_multicast or ip.is_unspecified:
            raise WebhookValidationError(
                f"webhook 拒絕指向內網/loopback IP:{host} → {ip}"
            )
    return url


def send(webhook_url: str, message: str, *, timeout: int = 10) -> bool:
    """Generic webhook · 自動偵測 platform 用對應 payload
    R27#4 · send 時 best-effort 不 raise · 但設定時透過 validate_webhook_url 把關
    """
    if not webhook_url:
        return False
    try:
        url = webhook_url.strip()
        # send 時再驗一次 · 防 DB 內既有舊 URL 是內網
        try:
            validate_webhook_url(url)
        except WebhookValidationError as e:
            logger.warning("[webhook] blocked by SSRF guard: %s", e)
            return False
        is_telegram = "telegram.org" in url
        if is_telegram:
            # Telegram bot · message 進 query string sendMessage
            # webhook_url 需含 ?chat_id=xxx · text 由我們加
            sep = "&" if "?" in url else "?"
            full_url = f"{url}{sep}text={urllib.parse.quote(message[:4096])}"
            req = urllib.request.Request(full_url, method="GET")
        else:
            # Slack / Discord / Mattermost / 通用 · JSON {"text": ...}
            payload = json.dumps({"text": message[:2000]}).encode()
            req = urllib.request.Request(
                url, data=payload, method="POST",
                headers={"Content-Type": "application/json"},
            )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ok = 200 <= r.status < 300
            if not ok:
                logger.warning("[webhook] send fail status=%d", r.status)
            return ok
    except Exception as e:
        logger.warning("[webhook] send exception: %s", str(e)[:100])
        return False


def notify_user(db, email: str, message: str) -> bool:
    """從 db.user_preferences 拿 webhook_url
    技術債#4(2026-04-23)· 移除 line_token fallback · 已 cleanup-line-legacy.py 清過
    """
    pref = db.user_preferences.find_one({"user_email": email, "key": "webhook_url"})
    if pref and pref.get("value"):
        return send(pref["value"], message)
    return False


def notify_admin(db, message: str) -> int:
    """所有 admin 都收 · 回成功數"""
    from main import _admin_allowlist
    count = 0
    for email in _admin_allowlist:
        if notify_user(db, email, message):
            count += 1
    return count

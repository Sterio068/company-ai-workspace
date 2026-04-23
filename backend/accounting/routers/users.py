"""
Users router · 跨 Agent 使用者偏好(Level 4 Learning 核心)

ROADMAP §11.1 B-3 · 從 main.py 抽出
- D-009 · 跨 Agent 「記住 user 偏好正式語氣」
- 安全:Codex sec F-2 · 同人或 admin 才可改 · 防 prompt injection
v1.2 §11.1 B-1.5 · 改用 routers/_deps.py 共用 helper
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from ._deps import current_user_email_dep, get_db


router = APIRouter(tags=["users"])


class UserPreference(BaseModel):
    key: str
    value: str
    learned_from: Optional[str] = None
    confidence: float = 1.0


def _require_self_or_admin(user_email: str, caller: Optional[str]) -> str:
    """Audit sec F-2 · 同人或 admin 才可改/讀偏好"""
    from main import _admin_allowlist
    if not caller:
        raise HTTPException(403, "未識別呼叫者 · 請從 launcher 進入")
    caller_lc = caller.lower()
    if caller_lc == user_email.lower() or caller_lc in _admin_allowlist:
        return caller_lc
    raise HTTPException(403, f"只能讀/改自己的偏好(您:{caller_lc} · 對象:{user_email})")


@router.get("/users/{user_email}/preferences")
def get_user_prefs(user_email: str,
                   caller: Optional[str] = current_user_email_dep()):
    db = get_db()
    _require_self_or_admin(user_email, caller)
    prefs = list(db.user_preferences.find({"user_email": user_email}))
    # R25#1 + R27#3 · 敏感欄位(line_token / webhook_url / api_keys)只回 configured + last4 · 不回原值
    # webhook_url 含 Slack/Discord/Telegram 整段 secret · 同等敏感
    SENSITIVE = {"line_token", "webhook_url"}
    out = {}
    for p in prefs:
        k, v = p.get("key"), p.get("value", "")
        if k in SENSITIVE:
            out[k] = {
                "configured": bool(v),
                "preview": (v[-4:] if v and len(v) > 4 else "***"),
            }
        else:
            out[k] = v
    return {
        "user_email": user_email,
        "preferences": out,
        "count": len(prefs),
    }


@router.post("/users/{user_email}/preferences")
def save_user_pref(user_email: str, pref: UserPreference,
                   caller: Optional[str] = current_user_email_dep()):
    db = get_db()
    _require_self_or_admin(user_email, caller)
    db.user_preferences.update_one(
        {"user_email": user_email, "key": pref.key},
        {"$set": {
            "user_email": user_email,
            "key": pref.key,
            "value": pref.value,
            "learned_from": pref.learned_from,
            "confidence": pref.confidence,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return {"saved": True}


@router.delete("/users/{user_email}/preferences/{key}")
def delete_user_pref(user_email: str, key: str,
                     caller: Optional[str] = current_user_email_dep()):
    db = get_db()
    _require_self_or_admin(user_email, caller)
    r = db.user_preferences.delete_one({"user_email": user_email, "key": key})
    return {"deleted": r.deleted_count}


# ============================================================
# Feature #2 · Webhook Notify(R26#2 · LINE Notify 已停服 · 改 generic webhook)
# 支援:Slack / Discord / Telegram bot / Mattermost / 任何 POST {"text"} webhook
# ============================================================
class WebhookSetup(BaseModel):
    url: str  # Slack/Discord/Telegram/Mattermost webhook URL


@router.post("/users/{user_email}/webhook")
def set_webhook(user_email: str, payload: WebhookSetup,
                caller: Optional[str] = current_user_email_dep()):
    """同事自設 webhook URL · 支援 Slack/Discord/Telegram/Mattermost
    R26#2 · 取代 LINE Notify(已停服 2025-03-31)
    R27#4 · 必驗 SSRF(必 https · 不指內網 IP)
    """
    _require_self_or_admin(user_email, caller)
    from services.webhook_notify import send, validate_webhook_url, WebhookValidationError
    url = payload.url.strip()
    try:
        validate_webhook_url(url)
    except WebhookValidationError as e:
        raise HTTPException(400, str(e))
    db = get_db()
    db.user_preferences.update_one(
        {"user_email": user_email, "key": "webhook_url"},
        {"$set": {
            "user_email": user_email,
            "key": "webhook_url",
            "value": url,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    # 立刻送測試訊息
    ok = send(url, "✅ 承富 AI · webhook 綁定成功 · 之後重要事件會推這")
    return {"saved": True, "test_sent": ok}


@router.delete("/users/{user_email}/webhook")
def delete_webhook(user_email: str,
                   caller: Optional[str] = current_user_email_dep()):
    _require_self_or_admin(user_email, caller)
    db = get_db()
    r = db.user_preferences.delete_one({"user_email": user_email, "key": "webhook_url"})
    return {"deleted": r.deleted_count}


# ============================================================
# [DEPRECATED] LINE Notify · 留 backward compat · 提示停服
# ============================================================
class LineTokenSetup(BaseModel):
    token: str


@router.post("/users/{user_email}/line-token")
def set_line_token_deprecated(user_email: str, payload: LineTokenSetup,
                              caller: Optional[str] = current_user_email_dep()):
    """[DEPRECATED] R26#2 · LINE Notify 已停服 2025-03-31 · 請改 /users/{email}/webhook"""
    raise HTTPException(
        410,  # Gone
        "LINE Notify 已於 2025-03-31 停服 · 請改用 /users/{email}/webhook"
        "(支援 Slack/Discord/Telegram/Mattermost)",
    )

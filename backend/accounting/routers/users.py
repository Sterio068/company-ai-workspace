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
from datetime import datetime

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
    # R25#1 · 敏感欄位(line_token / api_keys)只回 configured + last4 · 不回原值
    SENSITIVE = {"line_token"}
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
            "updated_at": datetime.utcnow(),
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
# Feature #2 · LINE Notify token 設定 + 測試送
# ============================================================
class LineTokenSetup(BaseModel):
    token: str  # LINE Notify token


@router.post("/users/{user_email}/line-token")
def set_line_token(user_email: str, payload: LineTokenSetup,
                   caller: Optional[str] = current_user_email_dep()):
    """同事自設 LINE Notify token · /users/me 也走此(email = caller)"""
    _require_self_or_admin(user_email, caller)
    db = get_db()
    db.user_preferences.update_one(
        {"user_email": user_email, "key": "line_token"},
        {"$set": {
            "user_email": user_email,
            "key": "line_token",
            "value": payload.token.strip(),
            "updated_at": datetime.utcnow(),
        }},
        upsert=True,
    )
    # 立刻送測試訊息
    from services.line_notify import send
    ok = send(payload.token.strip(), "✅ 承富 AI · LINE Notify 綁定成功 · 之後重要事件會推這")
    return {"saved": True, "test_sent": ok}


@router.delete("/users/{user_email}/line-token")
def delete_line_token(user_email: str,
                      caller: Optional[str] = current_user_email_dep()):
    _require_self_or_admin(user_email, caller)
    db = get_db()
    r = db.user_preferences.delete_one({"user_email": user_email, "key": "line_token"})
    return {"deleted": r.deleted_count}

"""
Users router · 跨 Agent 使用者偏好(Level 4 Learning 核心)

ROADMAP §11.1 B-3 · 從 main.py 抽出
- D-009 · 跨 Agent 「記住 user 偏好正式語氣」
- 安全:Codex sec F-2 · 同人或 admin 才可改 · 防 prompt injection
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


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


def _caller_email_dep():
    """Lazy import current_user_email · 避免 circular"""
    from main import current_user_email
    return Depends(current_user_email)


@router.get("/users/{user_email}/preferences")
def get_user_prefs(user_email: str,
                   caller: Optional[str] = _caller_email_dep()):
    from main import db
    _require_self_or_admin(user_email, caller)
    prefs = list(db.user_preferences.find({"user_email": user_email}))
    return {
        "user_email": user_email,
        "preferences": {p["key"]: p["value"] for p in prefs},
        "count": len(prefs),
    }


@router.post("/users/{user_email}/preferences")
def save_user_pref(user_email: str, pref: UserPreference,
                   caller: Optional[str] = _caller_email_dep()):
    from main import db
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
                     caller: Optional[str] = _caller_email_dep()):
    from main import db
    _require_self_or_admin(user_email, caller)
    r = db.user_preferences.delete_one({"user_email": user_email, "key": key})
    return {"deleted": r.deleted_count}

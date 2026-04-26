"""
v1.7 · AI Suggestions endpoint(真實作)
=====================================
從 LibreChat 對話算 metadata · 跑 3 detector · 回給前端 dashboard-fpp Inbox

Endpoints:
  GET  /admin/ai-suggestions                · 列當前建議(讀 cache or 即時算)
  POST /admin/ai-suggestions/scan           · 強制觸發掃描(忽略 cache)
  POST /admin/ai-suggestions/{id}/dismiss   · 「之後再說」(暫隱 24h)
  POST /admin/ai-suggestions/suppress       · 「不再提示這類」(寫 user prefs)
  GET  /admin/ai-suggestions/suppressed     · 看當前已關類型
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .._deps import require_admin_dep

logger = logging.getLogger("chengfu")
router = APIRouter(tags=["admin"])

# Cache TTL · 30 分鐘 · 對齊「掃描頻率」承諾
CACHE_TTL_SECONDS = 30 * 60

# ============================================================
# Models
# ============================================================
class SuppressRequest(BaseModel):
    type: str  # deadline / reply / stale


class DismissRequest(BaseModel):
    hours: int = 24  # 隱多久


# ============================================================
# Internal · get / set cache · per-user
# ============================================================
def _get_cache(db, user_email: str) -> Optional[dict]:
    doc = db.ai_suggestions_cache.find_one({"user_email": user_email.lower()})
    if not doc:
        return None
    age = (datetime.now(timezone.utc) - doc["scanned_at"]).total_seconds()
    if age > CACHE_TTL_SECONDS:
        return None
    return doc


def _set_cache(db, user_email: str, suggestions: list):
    now = datetime.now(timezone.utc)
    db.ai_suggestions_cache.update_one(
        {"user_email": user_email.lower()},
        {"$set": {
            "user_email": user_email.lower(),
            "scanned_at": now,
            "suggestions": suggestions,
        }},
        upsert=True,
    )


def _get_suppressed_types(db, user_email: str) -> set:
    doc = db.ai_suppressions.find_one({"user_email": user_email.lower()})
    return set(doc.get("types", []) if doc else [])


def _get_dismissed_ids(db, user_email: str) -> set:
    """還在 dismiss 期內的 suggestion id set"""
    now = datetime.now(timezone.utc)
    docs = db.ai_dismissed.find({
        "user_email": user_email.lower(),
        "until": {"$gt": now},
    })
    return set(d["suggestion_id"] for d in docs)


# ============================================================
# Run scan(算建議)· 寫 cache + 回結果
# ============================================================
def _run_scan(db, user_email: str) -> list:
    """主流程 · LibreChat conversations → metadata → 3 detector → 過濾 → 排序"""
    from services.conversation_meta import get_recent_metas
    from services.ai_detectors import detect_all
    from services.librechat_admin import find_librechat_user_id

    user_id = find_librechat_user_id(db, user_email)
    if not user_id:
        return []

    metas = get_recent_metas(db, user_email, user_id, limit=80)
    suppressed = _get_suppressed_types(db, user_email)
    suggestions = detect_all(db, metas, suppressed_types=suppressed)
    _set_cache(db, user_email, suggestions)
    return suggestions


# ============================================================
# Endpoints
# ============================================================
@router.get("/admin/ai-suggestions")
def list_ai_suggestions(_admin: str = require_admin_dep()):
    """讀 cache · 沒就掃 · 自動過濾 dismissed"""
    from main import db
    cache = _get_cache(db, _admin)
    if cache:
        suggestions = cache["suggestions"]
        scanned_at = cache["scanned_at"]
    else:
        suggestions = _run_scan(db, _admin)
        scanned_at = datetime.now(timezone.utc)

    dismissed = _get_dismissed_ids(db, _admin)
    suggestions = [s for s in suggestions if s.get("id") not in dismissed]

    return {
        "suggestions": suggestions,
        "scanned_at": scanned_at.isoformat() if hasattr(scanned_at, "isoformat") else str(scanned_at),
        "next_scan_at": (datetime.now(timezone.utc) + timedelta(seconds=CACHE_TTL_SECONDS)).isoformat(),
        "stub": False,
    }


@router.post("/admin/ai-suggestions/scan")
def force_scan(_admin: str = require_admin_dep()):
    """強制重掃 · 忽略 cache"""
    from main import db
    suggestions = _run_scan(db, _admin)
    return {"scanned": True, "count": len(suggestions), "suggestions": suggestions}


@router.post("/admin/ai-suggestions/{suggestion_id}/dismiss")
def dismiss_suggestion(suggestion_id: int, payload: DismissRequest, _admin: str = require_admin_dep()):
    """暫隱 · 預設 24 小時"""
    from main import db
    until = datetime.now(timezone.utc) + timedelta(hours=payload.hours)
    db.ai_dismissed.update_one(
        {"user_email": _admin.lower(), "suggestion_id": suggestion_id},
        {"$set": {
            "user_email": _admin.lower(),
            "suggestion_id": suggestion_id,
            "until": until,
        }},
        upsert=True,
    )
    return {"dismissed_until": until.isoformat()}


@router.post("/admin/ai-suggestions/suppress")
def suppress_type(payload: SuppressRequest, _admin: str = require_admin_dep()):
    """「不再提示這類」 · 寫 user prefs"""
    if payload.type not in ("deadline", "reply", "stale"):
        raise HTTPException(400, "type must be deadline / reply / stale")
    from main import db
    db.ai_suppressions.update_one(
        {"user_email": _admin.lower()},
        {"$addToSet": {"types": payload.type}, "$set": {"updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"suppressed_types": list(_get_suppressed_types(db, _admin))}


@router.delete("/admin/ai-suggestions/suppress/{type_name}")
def unsuppress_type(type_name: str, _admin: str = require_admin_dep()):
    """重新接收某類提示"""
    from main import db
    db.ai_suppressions.update_one(
        {"user_email": _admin.lower()},
        {"$pull": {"types": type_name}, "$set": {"updated_at": datetime.now(timezone.utc)}},
    )
    return {"suppressed_types": list(_get_suppressed_types(db, _admin))}


@router.get("/admin/ai-suggestions/suppressed")
def get_suppressed(_admin: str = require_admin_dep()):
    from main import db
    return {"types": list(_get_suppressed_types(db, _admin))}

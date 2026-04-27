"""
v1.7 · AI Suggestions endpoint(真實作)
=====================================
從 LibreChat 對話算 metadata · 跑 3 detector · 回給前端 dashboard-fpp Inbox

Endpoints:
  GET  /admin/ai-suggestions                · 列當前建議(讀 cache or 即時算)
  POST /admin/ai-suggestions/scan           · 強制觸發掃描(忽略 cache)
  POST /admin/ai-suggestions/scan-all       · 一次掃所有 admin(cron 用)
  POST /admin/ai-suggestions/{id}/dismiss   · 「之後再說」(暫隱 24h)
  POST /admin/ai-suggestions/suppress       · 「不再提示這類」(寫 user prefs)
  GET  /admin/ai-suggestions/suppressed     · 看當前已關類型

v1.8 hardening:
  - cron 不再對每個 admin 單獨打 endpoint(舊方式 _admin 解析為 "internal:cron"
    導致掃描永遠空陣列)· 改為 backend 自己列 admin 並逐一 scan
  - 加 hashlib.sha256 stable id(取代 Python hash())· 跨重啟 dismiss 仍有效
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict
import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .._deps import require_admin_dep

logger = logging.getLogger("chengfu")
router = APIRouter(tags=["admin"])

# Cache TTL · 30 分鐘 · 對齊「掃描頻率」承諾
CACHE_TTL_SECONDS = 30 * 60

# v1.10 perf · per-user scan lock · 防 thundering herd
# 10 admin 同時 cache miss → 全部撞 _run_scan → 80 conv × 3 query × 10 = 大量 query
# 加 lock 後同 user 同時只跑一個 scan · 後到的 cooperate cache
_scan_locks: Dict[str, asyncio.Lock] = {}


def _get_scan_lock(user_email: str) -> asyncio.Lock:
    if user_email not in _scan_locks:
        _scan_locks[user_email] = asyncio.Lock()
    return _scan_locks[user_email]

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
    scanned_at = doc.get("scanned_at")
    # Mongo 回 naive datetime · 視為 UTC 避免 tz mismatch
    if scanned_at and scanned_at.tzinfo is None:
        scanned_at = scanned_at.replace(tzinfo=timezone.utc)
        doc["scanned_at"] = scanned_at
    if not scanned_at:
        return None
    age = (datetime.now(timezone.utc) - scanned_at).total_seconds()
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
async def list_ai_suggestions(request: Request, _admin: str = require_admin_dep()):
    """讀 cache · 沒就掃 · 自動過濾 dismissed · cron 路徑解 X-User-Email

    v1.10 perf · async + per-user scan lock(防 thundering herd)
    cache miss 時 · 同 user 同時只一個 scan · 其餘等 lock 後讀 cache
    """
    from main import db
    _admin = _resolve_admin_email(request, _admin)
    cache = _get_cache(db, _admin)

    if cache:
        suggestions = cache["suggestions"]
        scanned_at = cache["scanned_at"]
    else:
        # cache miss · 走 lock · 防 N 個並發 request 撞同一掃描
        lock = _get_scan_lock(_admin)
        async with lock:
            # 拿 lock 後再 check cache · 前一個 holder 可能已寫入
            cache = _get_cache(db, _admin)
            if cache:
                suggestions = cache["suggestions"]
                scanned_at = cache["scanned_at"]
            else:
                # v1.44 perf F-10 修 · get_event_loop deprecated in 3.12
                # 改 get_running_loop · async context 內安全
                # sync 函式放 thread pool · 不阻塞 event loop
                loop = asyncio.get_running_loop()
                suggestions = await loop.run_in_executor(
                    None, _run_scan, db, _admin
                )
                scanned_at = datetime.now(timezone.utc)

    dismissed = _get_dismissed_ids(db, _admin)
    suggestions = [s for s in suggestions if s.get("id") not in dismissed]

    return {
        "suggestions": suggestions,
        "scanned_at": scanned_at.isoformat() if hasattr(scanned_at, "isoformat") else str(scanned_at),
        "next_scan_at": (datetime.now(timezone.utc) + timedelta(seconds=CACHE_TTL_SECONDS)).isoformat(),
        "stub": False,
    }


def _resolve_admin_email(request: Request, _admin: str) -> str:
    """v1.8 · cron(internal token)路徑下 _admin = "internal:cron" · 解 X-User-Email
    讓 cron 可以代特定 admin 掃 · 否則 cache 永遠寫到 internal:cron key 結果無效
    """
    if _admin == "internal:cron":
        for_user = (request.headers.get("X-User-Email") or "").strip().lower()
        if for_user:
            return for_user
    return _admin


@router.post("/admin/ai-suggestions/scan")
def force_scan(request: Request, _admin: str = require_admin_dep()):
    """強制重掃 · 忽略 cache · cron 路徑會解 X-User-Email 拿真 email"""
    from main import db
    target = _resolve_admin_email(request, _admin)
    suggestions = _run_scan(db, target)
    return {"scanned": True, "count": len(suggestions), "user": target,
            "suggestions": suggestions}


@router.post("/admin/ai-suggestions/scan-all")
def scan_all_admins(_admin: str = require_admin_dep()):
    """v1.8 · cron 用 · 一次掃所有 admin · backend 自己列 user"""
    from main import db, _users_col
    admins = list(_users_col.find(
        {"role": "ADMIN"}, {"email": 1}
    ))
    results = []
    for u in admins:
        email = u.get("email", "").strip().lower()
        if not email:
            continue
        try:
            suggestions = _run_scan(db, email)
            results.append({"email": email, "count": len(suggestions)})
        except Exception as e:
            logger.warning("[ai-scan] %s fail: %s", email, e)
            results.append({"email": email, "error": str(e)[:80]})
    return {"scanned_admins": len(results), "results": results}


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

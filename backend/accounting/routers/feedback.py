"""
Feedback router · 👍👎 集中收集 + stats(per-agent 滿意率)

ROADMAP §11.1 B-2 · 從 main.py 抽出
Codex R6#4 · list/stats 改 admin-only · create 用 trusted email
Codex R7#4 · create 完全不信 fb.user_email · 必 trusted_email
v1.2 §11.1 B-1.5 · 改用 routers/_deps.py 共用 helper
"""
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime, timezone

from ._deps import _serialize, require_admin_dep


router = APIRouter(tags=["feedback"])


class Feedback(BaseModel):
    message_id: str
    conversation_id: Optional[str] = None
    agent_name: Optional[str] = None
    verdict: Literal["up", "down"]
    note: Optional[str] = None
    user_email: Optional[str] = None


@router.post("/feedback")
def create_feedback(fb: Feedback, request: Request):
    """R6#4 + R7#4 · user_email 從 trusted identity 取 · 完全不信前端 body
    R7#4 抓:R6#4 fallback fb.user_email 仍可偽造他人回饋
    修正:無 trusted_email 直接 403 · feedback 必須登入"""
    from main import feedback_col, current_user_email
    trusted_email = current_user_email(request, request.headers.get("X-User-Email"))
    if not trusted_email:
        raise HTTPException(403, "未識別使用者 · feedback 必須登入(R7#4)")
    data = fb.model_dump()
    data["user_email"] = trusted_email  # 覆蓋 body · 防偽造
    data["created_at"] = datetime.now(timezone.utc)
    feedback_col.update_one(
        {"message_id": fb.message_id, "user_email": trusted_email},
        {"$set": data},
        upsert=True,
    )
    return {"ok": True}


@router.get("/feedback")
def list_feedback(
    verdict: Optional[str] = None,
    agent: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),  # R14#1 · 預設 50 · 上限 500
    skip: int = Query(default=0, ge=0),
    _admin: str = require_admin_dep(),  # R6#4 · admin-only · v1.2 用 _deps.py
):
    """R6#4 · admin-only · 防匿名讀全部 user_email/note
    R14#1 · 加 pagination(skip/limit) + 封頂 500 · 防爬蟲發 ?limit=10000 打爆
    · 用 projection 只撈必要欄位 · 減少 network + memory
    """
    from main import feedback_col
    q = {}
    if verdict:
        q["verdict"] = verdict
    if agent:
        q["agent_name"] = {"$regex": agent, "$options": "i"}
    cursor = feedback_col.find(
        q,
        # R14#1 · projection · 不撈 prompt raw / note 全文(Day 0 後改 admin 看需求加)
        {"_id": 1, "message_id": 1, "conversation_id": 1, "agent_name": 1,
         "verdict": 1, "note": 1, "user_email": 1, "created_at": 1},
    ).sort("created_at", -1).skip(skip).limit(limit)
    items = _serialize(list(cursor))
    total = feedback_col.count_documents(q)
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": (skip + len(items)) < total,
    }


def _compute_feedback_stats():
    """純資料 helper · 給內部 admin_dashboard 用 · 不過 Depends"""
    from main import feedback_col
    pipeline = [
        {"$group": {
            "_id": "$agent_name",
            "up":    {"$sum": {"$cond": [{"$eq": ["$verdict", "up"]}, 1, 0]}},
            "down":  {"$sum": {"$cond": [{"$eq": ["$verdict", "down"]}, 1, 0]}},
            "total": {"$sum": 1},
        }},
    ]
    stats = list(feedback_col.aggregate(pipeline))
    return [
        {"agent": s["_id"] or "unknown",
         "up": s["up"], "down": s["down"], "total": s["total"],
         "score": round(s["up"] / s["total"] * 100, 1) if s["total"] > 0 else 0}
        for s in stats
    ]


@router.get("/feedback/stats")
def feedback_stats(_admin: str = require_admin_dep()):
    """R6#4 · admin-only endpoint wrapper · v1.2 用 _deps.py"""
    return _compute_feedback_stats()


# 向後相容(main.py 的 admin_dashboard / monthly_report 透過 import 直接呼叫)
feedback_stats_internal = _compute_feedback_stats

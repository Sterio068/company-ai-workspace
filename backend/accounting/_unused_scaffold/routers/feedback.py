"""👍👎 回饋集中收集 + Agent 品質分析。"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


router = APIRouter(prefix="/feedback", tags=["feedback"])


class Feedback(BaseModel):
    message_id: str
    conversation_id: Optional[str] = None
    agent_name: Optional[str] = None
    verdict: Literal["up", "down"]
    note: Optional[str] = None
    user_email: Optional[str] = None


def get_db():
    from main import db
    return db


def serialize(doc):
    from bson import ObjectId
    if isinstance(doc, list):  return [serialize(d) for d in doc]
    if isinstance(doc, dict):
        return {k: (str(v) if isinstance(v, ObjectId) else serialize(v) if isinstance(v, (dict, list)) else v)
                for k, v in doc.items()}
    return doc


@router.post("")
def create_feedback(fb: Feedback):
    db = get_db()
    data = fb.dict(); data["created_at"] = datetime.utcnow()
    db.feedback.update_one(
        {"message_id": fb.message_id, "user_email": fb.user_email},
        {"$set": data}, upsert=True,
    )
    return {"ok": True}


@router.get("")
def list_feedback(verdict: Optional[str] = None, agent: Optional[str] = None, limit: int = 100):
    db = get_db()
    q = {}
    if verdict: q["verdict"] = verdict
    if agent:   q["agent_name"] = {"$regex": agent, "$options": "i"}
    return serialize(list(db.feedback.find(q).sort("created_at", -1).limit(limit)))


@router.get("/stats")
def feedback_stats():
    db = get_db()
    pipeline = [{"$group": {
        "_id": "$agent_name",
        "up":    {"$sum": {"$cond": [{"$eq": ["$verdict", "up"]}, 1, 0]}},
        "down":  {"$sum": {"$cond": [{"$eq": ["$verdict", "down"]}, 1, 0]}},
        "total": {"$sum": 1},
    }}]
    stats = list(db.feedback.aggregate(pipeline))
    return [
        {"agent": s["_id"] or "unknown", "up": s["up"], "down": s["down"], "total": s["total"],
         "score": round(s["up"] / s["total"] * 100, 1) if s["total"] > 0 else 0}
        for s in stats
    ]

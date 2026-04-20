"""記憶層 · Context Summary + User Preferences(Level 4 Learning 核心)。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


router = APIRouter(prefix="", tags=["memory"])


class SummarizeRequest(BaseModel):
    conversation_id: str
    keep_recent: int = 10
    force: bool = False


class UserPreference(BaseModel):
    key: str
    value: str
    learned_from: Optional[str] = None
    confidence: float = 1.0


def get_db():
    from main import db
    return db


# ==================== Context Summary ====================
@router.post("/memory/summarize-conversation")
def summarize_conversation(req: SummarizeRequest):
    db = get_db()
    try:
        messages = list(db.messages.find({"conversationId": req.conversation_id}).sort("createdAt", 1))
    except Exception as e:
        raise HTTPException(500, f"MongoDB 查詢失敗: {e}")

    if len(messages) <= req.keep_recent and not req.force:
        return {"summarized": False, "reason": f"對話僅 {len(messages)} 輪,未達門檻"}

    to_summarize = messages[:-req.keep_recent] if not req.force else messages
    if not to_summarize:
        return {"summarized": False, "reason": "無可摘要訊息"}

    try:
        import anthropic
        client = anthropic.Anthropic()
        dialogue = "\n\n".join([
            f"{m.get('sender', m.get('role', 'user'))}: {(m.get('text') or '')[:500]}"
            for m in to_summarize
        ])
        resp = client.messages.create(
            model="claude-haiku-4-5", max_tokens=1000,
            messages=[{"role": "user",
                       "content": f"把以下承富 AI 對話摘要成 200-400 字 · 保留關鍵事實/決議/待辦 · 繁中 · 台灣用語:\n\n{dialogue}"}]
        )
        summary_text = resp.content[0].text
        db.conversations.update_one(
            {"conversationId": req.conversation_id},
            {"$set": {"chengfu_summary": summary_text,
                      "chengfu_summarized_at": datetime.utcnow(),
                      "chengfu_summarized_messages": len(to_summarize)}}
        )
        return {"summarized": True, "messages_summarized": len(to_summarize),
                "summary_length": len(summary_text), "kept_recent": req.keep_recent,
                "estimated_tokens_saved": sum(len(m.get("text", "")) for m in to_summarize) // 4}
    except Exception as e:
        raise HTTPException(500, f"摘要失敗: {e}")


# ==================== User Preferences ====================
@router.get("/users/{user_email}/preferences")
def get_user_prefs(user_email: str):
    db = get_db()
    prefs = list(db.user_preferences.find({"user_email": user_email}))
    return {"user_email": user_email,
            "preferences": {p["key"]: p["value"] for p in prefs},
            "count": len(prefs)}


@router.post("/users/{user_email}/preferences")
def save_user_pref(user_email: str, pref: UserPreference):
    db = get_db()
    db.user_preferences.update_one(
        {"user_email": user_email, "key": pref.key},
        {"$set": {**pref.dict(), "user_email": user_email, "updated_at": datetime.utcnow()}},
        upsert=True
    )
    return {"saved": True}


@router.delete("/users/{user_email}/preferences/{key}")
def delete_user_pref(user_email: str, key: str):
    db = get_db()
    r = db.user_preferences.delete_one({"user_email": user_email, "key": key})
    return {"deleted": r.deleted_count}

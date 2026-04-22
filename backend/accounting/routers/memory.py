"""
Memory router · v1.3 §11.1 B-11 · 從 main.py 抽出

Context Summary Middleware · 對話超長自動摘要 · 省 token

涵蓋:
- /memory/summarize-conversation POST(用 Haiku 4.5 摘要前面對話 · 存回 conversation metadata)

省 token 邏輯:
- 20 輪對話 × 平均 1500 tokens = 30k tokens context
- 摘要成 2k tokens + 保留最近 10 輪(10k) = 12k tokens
- 每次呼叫省約 60% context

依賴:
- anthropic SDK
- main.py 的 db.messages / db.conversations(LibreChat 私有 schema)
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter(tags=["memory"])
logger = logging.getLogger("chengfu")


class SummarizeRequest(BaseModel):
    conversation_id: str
    keep_recent: int = 10  # 保留最近 N 輪不摘要
    force: bool = False    # 強制摘要(即使未達門檻)


@router.post("/memory/summarize-conversation")
def summarize_conversation(req: SummarizeRequest):
    """對話超過 N 輪時用 Haiku 摘要前面的 · 存回 conversation metadata

    節省邏輯:
      - 20 輪對話 × 平均 1500 tokens = 30k tokens context
      - 摘要成 2k tokens + 保留最近 10 輪(10k) = 12k tokens
      - 每次呼叫省約 60% context
    """
    from main import db
    msgs_col = db.messages
    try:
        messages = list(msgs_col.find(
            {"conversationId": req.conversation_id}
        ).sort("createdAt", 1))
    except Exception as e:
        raise HTTPException(500, f"MongoDB 查詢失敗: {e}")

    if len(messages) <= req.keep_recent and not req.force:
        return {"summarized": False, "reason": f"對話僅 {len(messages)} 輪,未達門檻"}

    to_summarize = messages[:-req.keep_recent] if not req.force else messages
    if not to_summarize:
        return {"summarized": False, "reason": "無可摘要訊息"}

    # 用 Anthropic Haiku 摘要
    try:
        import anthropic
        client = anthropic.Anthropic()

        dialogue = "\n\n".join([
            f"{m.get('sender', m.get('role', 'user'))}: {(m.get('text') or '')[:500]}"
            for m in to_summarize
        ])

        summary_resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""把以下承富 AI 對話摘要成 200-400 字 · 保留關鍵事實 / 決議 / 待辦 · 繁中 · 台灣用語:\n\n{dialogue}"""
            }]
        )
        summary_text = summary_resp.content[0].text

        db.conversations.update_one(
            {"conversationId": req.conversation_id},
            {"$set": {
                "chengfu_summary": summary_text,
                "chengfu_summary_up_to": str(to_summarize[-1].get("_id", "")),
                "chengfu_summarized_at": datetime.utcnow(),
                "chengfu_summarized_messages": len(to_summarize),
            }}
        )

        return {
            "summarized": True,
            "messages_summarized": len(to_summarize),
            "summary_length": len(summary_text),
            "kept_recent": req.keep_recent,
            "estimated_tokens_saved": sum(len(m.get("text", "")) for m in to_summarize) // 4,
        }
    except Exception as e:
        raise HTTPException(500, f"摘要失敗: {e}")

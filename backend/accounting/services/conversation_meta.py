"""
v1.7 · Conversation Metadata 計算
=====================================
從 LibreChat conversations + messages collection 推導 metadata · 給:
  - Smart Folder 條件查詢(workspace / 回應狀態 / 上次活動 / 未讀數 / @我)
  - AI 觸發管線(deadline / reply / stale)

Schema(計算 · 不寫獨立 collection · 即時 aggregate):
  {
    conversation_id: str,
    title: str,
    workspace: str | None,        # 投標 / 活動 / ...
    project_id: str | None,        # 從 user_preferences 推
    last_activity_at: datetime,
    last_user_msg_at: datetime,
    last_assistant_msg_at: datetime,
    response_status: "waiting" | "answered",  # last_user > last_asst → waiting
    unread_count: int,
    mentions: [str],               # @username · 從訊息抽
    agent_id: str | None,          # 對話用的 agent
  }

設計決策:
  - LibreChat conversations collection 已有 updatedAt
  - 對話 last 訊息可從 messages collection 拿(min/max by createdAt)
  - workspace 從 conversation.title 或 metadata 推 · MVP 用標題關鍵字
  - 未讀:用 user_preferences.last_seen_msg[conv_id] 比對 last_msg_id
"""
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional
import re
import logging

logger = logging.getLogger("chengfu")

# Workspace 關鍵字推導(MVP · v1.8 改用真標籤)
WS_KEYWORDS = {
    "投標": ["投標", "標案", "RFP", "建議書", "提案"],
    "活動": ["活動", "場勘", "現場", "舞台", "預算"],
    "設計": ["設計", "Logo", "視覺", "Brief", "排版"],
    "公關": ["公關", "新聞稿", "媒體", "採訪", "Email"],
    "營運": ["結案", "報表", "合約", "財報", "客戶"],
}


def _detect_workspace(title: str, recent_text: str = "") -> Optional[str]:
    """從對話標題 + 最近文字推 workspace"""
    text = (title + " " + recent_text).lower()
    for ws, keywords in WS_KEYWORDS.items():
        if any(k.lower() in text for k in keywords):
            return ws
    return None


def _extract_mentions(text: str) -> list:
    """抽 @mentions(含中英文)"""
    return list(set(re.findall(r"@([A-Za-z0-9_一-鿿]+)", text or "")))


def _ensure_aware(dt):
    """將 naive datetime 視為 UTC · 避免 ai_detectors 比較時 TypeError

    MongoDB 預設回 naive datetime(雖然存的是 UTC)· 與 datetime.now(timezone.utc) 比較會炸
    """
    if dt is None:
        return None
    if isinstance(dt, datetime) and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def compute_meta(db, conv: dict, last_seen: Optional[datetime] = None,
                 _msgs: Optional[list] = None) -> dict:
    """從 conversation doc + messages 計算單一對話 meta

    Args:
        db: pymongo db
        conv: conversation doc(LibreChat conversations collection)
        last_seen: user 最後看 conversation 的時間(算未讀)
        _msgs: v1.10 perf · 由 caller 預先批次查好的 messages list
              (避免 N+1 · get_recent_metas 改 $in batch query)
              不傳則 fallback 走原本 per-conv query
    """
    conv_id = conv.get("conversationId") or str(conv.get("_id"))
    title = conv.get("title") or "(無標題)"

    # 拿最近 20 訊 · 算 last_user / last_assistant / mentions
    if _msgs is not None:
        # batch 模式 · _msgs 已經是這個 conv 的訊息 · 已 sort
        msgs = _msgs[:20]
    else:
        # legacy 單筆模式 · per-conv query(N+1 · 不建議)
        msgs = list(db.messages.find(
            {"conversationId": conv_id}
        ).sort("createdAt", -1).limit(20))

    last_user = None
    last_asst = None
    mentions = set()
    recent_text_parts = []
    unread = 0

    last_seen_aware = _ensure_aware(last_seen)

    for m in msgs:
        role = m.get("sender") or m.get("isCreatedByUser")  # LibreChat 不同版本欄位名
        is_user = role is True or role == "User" or role == "user"
        ts = _ensure_aware(m.get("createdAt"))  # naive → UTC aware
        if is_user:
            if not last_user or (ts and ts > last_user):
                last_user = ts
        else:
            if not last_asst or (ts and ts > last_asst):
                last_asst = ts
        # 累積最近文字 · 給 workspace 推導
        text = m.get("text") or m.get("content") or ""
        if isinstance(text, str):
            recent_text_parts.append(text[:200])
            mentions.update(_extract_mentions(text))
        # 未讀計算
        if last_seen_aware and ts and ts > last_seen_aware and not is_user:
            unread += 1

    # response_status
    if last_user and last_asst:
        response_status = "waiting" if last_user > last_asst else "answered"
    elif last_user:
        response_status = "waiting"
    else:
        response_status = "answered"

    last_activity = _ensure_aware(
        conv.get("updatedAt") or conv.get("createdAt")
    ) or datetime.now(timezone.utc)
    workspace = _detect_workspace(title, " ".join(recent_text_parts))

    return {
        "conversation_id": conv_id,
        "title": title,
        "workspace": workspace,
        "agent_id": conv.get("agent_id") or conv.get("model"),
        "last_activity_at": last_activity,
        "last_user_msg_at": last_user,
        "last_assistant_msg_at": last_asst,
        "response_status": response_status,
        "unread_count": unread,
        "mentions": list(mentions),
    }


def iter_user_conversations(db, user_id, limit: int = 200) -> Iterator[dict]:
    """列 user 的所有 conversations(最新 N 筆)

    LibreChat conversations.user 在不同版本可能存 ObjectId 或 string · 用 $in 兼容
    """
    user_keys = []
    if user_id is not None:
        user_keys.append(user_id)
        try:
            user_keys.append(str(user_id))
        except Exception:
            pass
    cursor = db.conversations.find(
        {"user": {"$in": user_keys}} if user_keys else {"_id": None}
    ).sort("updatedAt", -1).limit(limit)
    for conv in cursor:
        yield conv


def get_user_last_seen(db, user_email: str) -> dict:
    """讀 user 對各 conversation 最後查看時間 · 算未讀用"""
    pref = db.user_preferences.find_one({"user_email": user_email.lower()}) or {}
    return pref.get("last_seen_per_conv") or {}


def get_recent_metas(db, user_email: str, user_id, limit: int = 100) -> list:
    """一次拿 user 所有最近對話的 metadata · 給 Smart Folder 查詢用

    v1.10 perf · 改 batch query · 從 1+N(82 query)降到 1+1+1=3 query
      1. user_preferences.find_one(last_seen)
      2. conversations.find(user) sorted limit=N
      3. messages.find(conversationId IN [N convs]) sorted

    對應 perf-optimizer 黃 2 修
    """
    last_seen_map = get_user_last_seen(db, user_email)
    convs = list(iter_user_conversations(db, user_id, limit=limit))
    if not convs:
        return []

    # v1.10 batch · 一次拿所有 conv 的 messages · 端 client 分組
    conv_ids = [c.get("conversationId") or str(c.get("_id")) for c in convs]
    # 加 conversationId index 後 · 此 query 走 indexed lookup(v1.8 main.py 加的)
    all_msgs = list(db.messages.find(
        {"conversationId": {"$in": conv_ids}}
    ).sort([("conversationId", 1), ("createdAt", -1)]))
    msgs_by_conv: dict = {}
    for m in all_msgs:
        cid = m.get("conversationId")
        # 每個 conv 只留 20 筆(原 limit)
        if len(msgs_by_conv.setdefault(cid, [])) < 20:
            msgs_by_conv[cid].append(m)

    metas = []
    for conv in convs:
        try:
            cid = conv.get("conversationId") or str(conv.get("_id"))
            last_seen_iso = last_seen_map.get(cid)
            last_seen = (
                datetime.fromisoformat(last_seen_iso)
                if isinstance(last_seen_iso, str) else None
            )
            # 傳預先 batch 好的 _msgs 進去 · compute_meta 不再單獨 query
            cached_msgs = msgs_by_conv.get(cid, [])
            meta = compute_meta(db, conv, last_seen=last_seen, _msgs=cached_msgs)
            # v1.10 · 把 batch 好的 messages 也黏在 meta 上 · 給 detect_deadline 重用
            # 用 _ 前綴避免污染 public schema(API 序列化時前端不會看到)
            meta["_cached_msgs"] = cached_msgs
            metas.append(meta)
        except Exception as e:
            logger.warning("[conv-meta] compute fail %s: %s", conv.get("_id"), e)
    return metas

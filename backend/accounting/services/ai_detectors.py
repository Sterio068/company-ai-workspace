"""
v1.7 · AI 觸發 detectors
=====================================
3 個 detector + 排序去重 · 給 cron 每 30 分掃描 · 寫 ai_suggestions collection

Detectors:
  - deadline_detector(text 找日期 · 比對今日距離)
  - reply_detector(對話 last_user_msg > last_assistant_msg + 超過 N 小時)
  - stale_detector(7 天無動作 + 未結案)

排序:截止日近 > 待回信久 > 停滯久
去重:同 conversation_id × type 只保留最高信心
抑制:user 已標「不再提示這類」全濾掉
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import re
import logging

logger = logging.getLogger("chengfu")

# 日期 regex(覆蓋台灣常用格式 · 寬鬆抓)
# 1) MM/DD or M/D · 5/15 · 12/31
# 2) M月D日 · 5月15日
# 3) YYYY-MM-DD or YYYY/MM/DD
# 4) 「X 月底」「下週」「明天」(MVP 不抓 · 太模糊)
DATE_PATTERNS = [
    # YYYY-MM-DD or YYYY/MM/DD · 強信號
    (r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", "ymd"),
    # M/D 或 M-D(無年)
    (r"(?<!\d)(\d{1,2})[/-](\d{1,2})(?![/-])", "md"),
    # M 月 D 日(中文)
    (r"(\d{1,2})\s*月\s*(\d{1,2})\s*日", "md_zh"),
]


def extract_dates(text: str, base_year: int = None) -> list:
    """從 text 抽日期 · 回 list of (datetime, original_str)

    base_year:推算 M/D 用 · 預設今年
    """
    if not text:
        return []
    if base_year is None:
        base_year = datetime.now().year
    found = []
    for pattern, kind in DATE_PATTERNS:
        for m in re.finditer(pattern, text):
            try:
                if kind == "ymd":
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                else:
                    y, mo, d = base_year, int(m.group(1)), int(m.group(2))
                if not (1 <= mo <= 12 and 1 <= d <= 31):
                    continue
                # 若 M/D 落在過去 · 推下一年
                dt = datetime(y, mo, d, tzinfo=timezone.utc)
                if kind != "ymd" and dt < datetime.now(timezone.utc) - timedelta(days=30):
                    dt = dt.replace(year=y + 1)
                found.append((dt, m.group(0)))
            except (ValueError, IndexError):
                continue
    return found


# ============================================================
# Detector 1 · deadline
# ============================================================
def detect_deadline(db, conv_meta: dict) -> Optional[dict]:
    """掃對話最近 20 訊找日期 · 若有 < 14 天的 deadline 觸發

    Returns:
        suggestion dict or None
    """
    conv_id = conv_meta["conversation_id"]
    msgs = list(db.messages.find({"conversationId": conv_id})
                .sort("createdAt", -1).limit(20))

    all_dates = []
    sample_text = []
    last_msg_time = None
    for m in msgs:
        text = m.get("text") or m.get("content") or ""
        if not isinstance(text, str):
            continue
        ts = m.get("createdAt")
        if not last_msg_time and ts:
            last_msg_time = ts
        dates = extract_dates(text)
        all_dates.extend(dates)
        sample_text.append(text[:80])

    if not all_dates:
        return None

    now = datetime.now(timezone.utc)
    upcoming = [(d, s) for d, s in all_dates if now <= d <= now + timedelta(days=30)]
    if not upcoming:
        return None

    # 多日期 · 顯示前 3
    upcoming.sort(key=lambda x: x[0])
    head = upcoming[0]
    days_left = (head[0] - now).days
    confidence = 0.95 if days_left < 7 else 0.85 if days_left < 14 else 0.72
    date_strs = "、".join(d.strftime("%m/%d") for d, _ in upcoming[:3])
    extra = f"(共 {len(upcoming)} 個)" if len(upcoming) > 3 else ""
    src_label = conv_meta.get("title", "對話")
    src_time = (last_msg_time or now).strftime("%H:%M")

    return {
        "type": "deadline",
        "text": f"{src_label} 提到 {len(upcoming)} 個截止日 ({date_strs}{extra})",
        "cta": "排進日曆",
        "src": f"{src_label} · {src_time}",
        "src_conversation_id": conv_id,
        "confidence": round(confidence, 2),
        "meta": {
            "earliest": head[0].isoformat(),
            "days_left": days_left,
            "count": len(upcoming),
        },
    }


# ============================================================
# Detector 2 · reply(待回信)
# ============================================================
def detect_reply(conv_meta: dict, threshold_hours: int = 24) -> Optional[dict]:
    """user 最後一條訊息超過 N 小時未回 · 觸發"""
    if conv_meta.get("response_status") != "waiting":
        return None
    last_user = conv_meta.get("last_user_msg_at")
    if not last_user:
        return None
    now = datetime.now(timezone.utc)
    hours_waiting = (now - last_user).total_seconds() / 3600
    if hours_waiting < threshold_hours:
        return None

    # 信心 · 等越久越高(但 cap 0.92)
    if hours_waiting < 48:
        confidence = 0.78
        time_label = f"{int(hours_waiting)} 小時"
    elif hours_waiting < 24 * 7:
        confidence = 0.88
        time_label = f"{int(hours_waiting / 24)} 天"
    else:
        confidence = 0.92
        time_label = f"{int(hours_waiting / 24)} 天"

    title = conv_meta.get("title", "對話")
    return {
        "type": "reply",
        "text": f"{title} {time_label}沒回 · 該回信了",
        "cta": "看草稿",
        "src": f"{title} · {time_label}前",
        "src_conversation_id": conv_meta["conversation_id"],
        "confidence": round(confidence, 2),
        "meta": {
            "hours_waiting": int(hours_waiting),
            "last_user_msg_at": last_user.isoformat(),
        },
    }


# ============================================================
# Detector 3 · stale
# ============================================================
def detect_stale(conv_meta: dict, threshold_days: int = 7) -> Optional[dict]:
    """對話超過 N 天無活動 · 提醒結案"""
    last_act = conv_meta.get("last_activity_at")
    if not last_act:
        return None
    now = datetime.now(timezone.utc)
    days_idle = (now - last_act).days
    if days_idle < threshold_days:
        return None

    if days_idle < 14:
        confidence = 0.65
    elif days_idle < 30:
        confidence = 0.75
    else:
        confidence = 0.82

    title = conv_meta.get("title", "對話")
    return {
        "type": "stale",
        "text": f"{title} {days_idle} 天沒動 · 要結案嗎?",
        "cta": "檢視",
        "src": title,
        "src_conversation_id": conv_meta["conversation_id"],
        "confidence": round(confidence, 2),
        "meta": {"days_idle": days_idle},
    }


# ============================================================
# Run all · 對 metas 列表跑 3 detector · 排序去重
# ============================================================
def detect_all(db, metas: list, suppressed_types: set = None) -> list:
    """跑 3 detector × N 對話 · 回排序後 unique 建議

    Args:
        db: pymongo db
        metas: list of conversation meta dicts(來自 conversation_meta.get_recent_metas)
        suppressed_types: user 已關閉的 type set
    """
    suppressed_types = suppressed_types or set()
    results = []

    for meta in metas:
        for detector_fn, name in [
            (lambda m: detect_deadline(db, m), "deadline"),
            (lambda m: detect_reply(m), "reply"),
            (lambda m: detect_stale(m), "stale"),
        ]:
            if name in suppressed_types:
                continue
            try:
                r = detector_fn(meta)
                if r:
                    results.append(r)
            except Exception as e:
                logger.warning("[ai-det] %s on %s fail: %s", name, meta.get("conversation_id"), e)

    # 去重:同 conversation_id × type 取最高信心
    dedup = {}
    for r in results:
        key = (r["src_conversation_id"], r["type"])
        if key not in dedup or r["confidence"] > dedup[key]["confidence"]:
            dedup[key] = r

    # 排序:type priority · deadline > reply > stale · 同 type 內信心高的先
    type_order = {"deadline": 0, "reply": 1, "stale": 2}
    sorted_list = sorted(dedup.values(), key=lambda r: (type_order.get(r["type"], 9), -r["confidence"]))

    # 加 id · v1.8 改 sha256 stable hash · Python hash() 是 process-randomized
    # 跨重啟 dismiss/cache 仍對得上(前面用 hash() · cron 重啟後 id 就變 dismiss 失效)
    import hashlib
    for r in sorted_list:
        h = hashlib.sha256(
            (r["src_conversation_id"] + ":" + r["type"]).encode("utf-8")
        ).digest()
        # 取前 8 bytes 當 int(MongoDB int64 範圍 · 不會溢位)
        r["id"] = int.from_bytes(h[:8], "big") & ((1 << 53) - 1)  # 留 JS Number 安全範圍

    return sorted_list

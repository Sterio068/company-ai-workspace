"""
Safety router · L3 機敏內容分級檢查

ROADMAP §11.1 · 從 main.py 抽出的第一個 router(最孤立 · 證明 pattern)
- 老闆 Q3 答「先不考慮 L3 硬擋」· 但這個 endpoint 仍可用為 prompt 預掃
- 前端 chat.js 在送出前可選擇呼叫 /safety/classify · 跳警告 modal(Playwright §11.13)

v1.3 A3 · CRITICAL C-3 · /safety/l3-preflight server-side wall
- 前端 confirm 可被 curl 繞過 · 此 endpoint 強制 audit 任何 L3 送出嘗試
- L3_HARD_STOP=1 env 開啟強制 block(預設 audit-only)
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime, timezone
import logging
import os
import re

logger = logging.getLogger("chengfu")


router = APIRouter(prefix="/safety", tags=["safety"])


LEVEL_3_PATTERNS = [
    # 選情 / 政治
    r"選情", r"民調", r"政黨內部", r"候選人(策略|規劃)",
    # 未公告標案
    r"未公告.{0,10}標", r"內定.{0,5}廠商", r"評審.{0,5}名單",
    # 個資(強 pattern)
    r"\b[A-Z]\d{9}\b",  # 身份證
    r"\b\d{10}\b",      # 手機號
    r"\b\d{3}-\d{3}-\d{3}\b",
    # 客戶機敏
    r"客戶.{0,5}(帳戶|密碼|財務狀況)",
    # 競爭對手情報
    r"(對手|競品).{0,5}(內部|機密|計畫)",
]


class ContentCheck(BaseModel):
    text: str


@router.post("/classify")
def classify_level(payload: ContentCheck, request: Request):
    """Level 03 keyword classifier · 在 Agent 處理前預掃。

    rate limit 由 main.py app 級別 limiter 套用(SlowAPIMiddleware 自動)

    v1.3 batch6 · M-1 · response 不再回 triggers list
    避免攻擊者用 enumeration 反推 LEVEL_3_PATTERNS · 規避 classifier
    """
    hits = []
    for pattern in LEVEL_3_PATTERNS:
        matches = re.findall(pattern, payload.text)
        if matches:
            hits.extend(matches if isinstance(matches[0], str) else [str(m) for m in matches])
    level = "03" if hits else ("02" if len(payload.text) > 500 else "01")
    return {
        "level": level,
        "hit_count": len(hits),  # 數量公開 OK · 細節不公開
        "recommendation": {
            "01": "可直接處理",
            "02": "建議去識別化(客戶名/金額)後處理",
            "03": "❌ 禁止送 AI,請改人工處理或待階段二本地模型",
        }[level],
    }


# ============================================================
# Feature #3 · PII 偵測(身分證 / 電話 / Email / 信用卡)
# 比 L3 classifier 更精確的「個人識別資訊」偵測
# 法律保險 · PDPA 合規
# ============================================================
PII_PATTERNS = {
    "twid": (r"\b[A-Z][12]\d{8}\b", "身分證(範例 A123456789)"),
    "mobile": (r"\b09\d{2}[-\s]?\d{3}[-\s]?\d{3}\b", "手機(09xx-xxx-xxx)"),
    "phone": (r"\b0\d{1,2}[-\s]\d{6,8}\b", "市話(02-xxxxxxxx)"),
    "email": (r"\b[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "Email"),
    "credit_card": (r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "信用卡 16 位"),
    "tax_id": (r"統編[:\s]*\d{8}\b|\b\d{8}\b(?=.{0,10}統編)", "公司統編"),
    "passport": (r"\b[A-Z]\d{8}\b(?!\d)", "護照"),
}


def _redact_pii(text: str) -> tuple[str, list[dict]]:
    """純 helper · 替每個 PII 用 [類型] 取代 · 回 (打碼後 text, 命中列表)"""
    hits = []
    redacted = text
    for kind, (pattern, label) in PII_PATTERNS.items():
        for m in re.finditer(pattern, text):
            value = m.group(0)
            hits.append({"kind": kind, "label": label, "value_preview": value[:4] + "***"})
            redacted = redacted.replace(value, f"[{label}]")
    return redacted, hits


class PIIDetectRequest(BaseModel):
    text: str


@router.post("/pii-detect")
def detect_pii(payload: PIIDetectRequest):
    """偵測但不打碼 · 前端決定要不要送出 / 用打碼版

    回:
      hits: [{kind, label, value_preview}]
      redacted: 自動打碼後的 text(若 user 選 redact 送出 · 用此)
      total: hit 總數
    """
    redacted, hits = _redact_pii(payload.text or "")
    return {
        "total": len(hits),
        "hits": hits,
        "redacted": redacted,
        "recommendation": (
            "❌ 偵測到 PII · 建議用 redacted 版送出 · 或取消送出"
            if hits else "✅ 沒 PII 風險"
        ),
    }


@router.post("/pii-audit")
def audit_pii(payload: PIIDetectRequest, request: Request):
    """前端送出時 · 寫 audit log 記錄『user 看到 PII 警告但仍送了』
    · 不記 raw value · 只記 hit kind + count + user · PDPA

    R29 修:原 __import__("datetime").datetime.now(timezone.utc) timezone NameError 被
    bare except 吞 · 結果 audit 從未真寫 · 改正規 import + 不吞例外
    """
    redacted, hits = _redact_pii(payload.text or "")
    if hits:
        try:
            from main import audit_col, _verify_librechat_cookie
            # v1.3 batch6 · H-1 · 優先驗 cookie · 避免未驗 header 偽造 audit
            user = _verify_librechat_cookie(request)
            if not user:
                user = (request.headers.get("X-User-Email") or "").strip().lower() or None
                if user:
                    logger.warning("[pii-audit] user from unverified header: %s", user)
            audit_col.insert_one({
                "action": "pii_warning_dismissed",
                "user": user,
                "details": {
                    "hit_count": len(hits),
                    "hit_kinds": list(set(h["kind"] for h in hits)),
                    "text_length": len(payload.text or ""),
                },
                "created_at": datetime.now(timezone.utc),
            })
        except Exception as e:
            logger.warning("[pii-audit] write fail: %s", e)
    return {"audited": True, "hit_count": len(hits)}


# ============================================================
# v1.3 A3 · CRITICAL C-3 · L3 server-side wall · 防 curl 繞前端 confirm
# ============================================================
def _l3_hard_stop_enabled() -> bool:
    """env 開啟才硬擋 L3 · 預設 audit-only(老闆 Q3 答暫不擋)
    當公司資料分級政策正式啟用,設 L3_HARD_STOP=1 強制擋送雲
    """
    return os.getenv("L3_HARD_STOP", "0").lower() in ("1", "true", "yes")


@router.post("/l3-preflight")
def l3_preflight(payload: ContentCheck, request: Request):
    """送雲前 L3 強制 audit · 可選擇硬擋

    流程:
    1. classifier 跑 → 算出 level
    2. 若 L3 · 寫 audit_log(用 verified cookie email · 可追責)
    3. L3_HARD_STOP=1 → 回 403 擋送
    4. L3_HARD_STOP=0 (預設) → 回 200 + warning · 由前端 confirm 流程繼續

    前端 chat.js send() 必呼叫此 endpoint · 若 403 直接擋下
    curl 直接打 /api/ask/agents 不過此 endpoint · 但會留 LibreChat layer audit
    """
    text = payload.text or ""
    hits = []
    for pattern in LEVEL_3_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            hits.extend(matches if isinstance(matches[0], str) else [str(m) for m in matches])
    is_l3 = bool(hits)

    if not is_l3:
        return {"allowed": True, "level": "01_or_02", "hit_count": 0}

    # L3 → audit log(verified cookie 優先 · 不信 X-User-Email)
    try:
        from main import audit_col, _verify_librechat_cookie
        user = _verify_librechat_cookie(request)
        if not user:
            user = (request.headers.get("X-User-Email") or "").strip().lower() or "anonymous"
            logger.warning("[l3-audit] user from unverified source: %s", user)
        audit_col.insert_one({
            "action": "l3_send_attempt",
            "user": user,
            "details": {
                "hit_count": len(hits),
                "text_length": len(text),
                "hard_stop_enforced": _l3_hard_stop_enabled(),
            },
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.error("[l3-audit] write fail: %s", e)

    if _l3_hard_stop_enabled():
        # 硬擋 mode · 回 403 · 前端會看到「機敏內容禁止送雲」
        raise HTTPException(
            403,
            detail={
                "reason": "L3_HARD_STOP_ENABLED",
                "message": "偵測到 L3 機敏內容 · 公司政策禁止送雲 · 請改人工或本地處理",
                "hit_count": len(hits),
            },
        )

    # 預設 audit-only · 由前端 confirm 流程繼續(已 modal 警告)
    return {
        "allowed": True,
        "level": "03",
        "hit_count": len(hits),
        "warning": "L3 機敏內容已記錄 · 請確認再送",
    }

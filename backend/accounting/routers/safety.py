"""
Safety router · L3 機敏內容分級檢查

ROADMAP §11.1 · 從 main.py 抽出的第一個 router(最孤立 · 證明 pattern)
- 老闆 Q3 答「先不考慮 L3 硬擋」· 但這個 endpoint 仍可用為 prompt 預掃
- 前端 chat.js 在送出前可選擇呼叫 /safety/classify · 跳警告 modal(Playwright §11.13)
"""
from fastapi import APIRouter, Request
from pydantic import BaseModel
import re


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
    """
    hits = []
    for pattern in LEVEL_3_PATTERNS:
        matches = re.findall(pattern, payload.text)
        if matches:
            hits.extend(matches if isinstance(matches[0], str) else [str(m) for m in matches])
    level = "03" if hits else ("02" if len(payload.text) > 500 else "01")
    return {
        "level": level,
        "triggers": hits[:10],  # 最多回 10 個命中
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
    · 不記 raw value · 只記 hit kind + count + user · PDPA"""
    redacted, hits = _redact_pii(payload.text or "")
    if hits:
        try:
            from main import audit_col
            user = (request.headers.get("X-User-Email") or "").strip().lower() or None
            audit_col.insert_one({
                "action": "pii_warning_dismissed",
                "user": user,
                "details": {
                    "hit_count": len(hits),
                    "hit_kinds": list(set(h["kind"] for h in hits)),
                    "text_length": len(payload.text or ""),
                },
                "created_at": __import__("datetime").datetime.now(timezone.utc),
            })
        except Exception:
            pass
    return {"audited": True, "hit_count": len(hits)}

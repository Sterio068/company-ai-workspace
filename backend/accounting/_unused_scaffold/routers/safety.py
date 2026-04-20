"""Level 03 內容分級 · 技術性阻擋。"""
import re
from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/safety", tags=["safety"])


LEVEL_3_PATTERNS = [
    r"選情", r"民調", r"政黨內部", r"候選人(策略|規劃)",
    r"未公告.{0,10}標", r"內定.{0,5}廠商", r"評審.{0,5}名單",
    r"\b[A-Z]\d{9}\b",           # 身份證
    r"\b\d{10}\b",               # 手機號
    r"\b\d{3}-\d{3}-\d{3}\b",
    r"客戶.{0,5}(帳戶|密碼|財務狀況)",
    r"(對手|競品).{0,5}(內部|機密|計畫)",
]


class ContentCheck(BaseModel):
    text: str


@router.post("/classify")
def classify_level(payload: ContentCheck):
    hits = []
    for pattern in LEVEL_3_PATTERNS:
        matches = re.findall(pattern, payload.text)
        if matches:
            hits.extend(matches if isinstance(matches[0], str) else [str(m) for m in matches])
    level = "03" if hits else ("02" if len(payload.text) > 500 else "01")
    return {
        "level": level,
        "triggers": hits[:10],
        "recommendation": {
            "01": "可直接處理",
            "02": "建議去識別化(客戶名/金額)後處理",
            "03": "❌ 禁止送 AI · 請改人工處理或待階段二本地模型",
        }[level],
    }

"""
Tenders router · g0v 採購網新標案監測

ROADMAP §11.1 B-4 · 從 main.py 抽出
- list / 標記狀態(new/reviewing/interested/skipped)
- 對應 ROADMAP §11.8 · tender-monitor cron 寫進來
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, Literal
from datetime import datetime
from bson import ObjectId


router = APIRouter(tags=["tenders"])


def _serialize(doc):
    if isinstance(doc, list):
        return [_serialize(d) for d in doc]
    if isinstance(doc, dict):
        return {k: _serialize(v) for k, v in doc.items()}
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc


def _caller_email_dep():
    from main import current_user_email
    return Depends(current_user_email)


def _user_required_dep():
    """R6#4 · 一般 user 必登入"""
    from main import current_user_email
    def _check(caller: Optional[str] = Depends(current_user_email)) -> str:
        if not caller:
            raise HTTPException(403, "未識別使用者 · 請從 launcher 登入")
        return caller
    return Depends(_check)


@router.get("/tender-alerts")
def list_tender_alerts(
    status: Optional[str] = None, keyword: Optional[str] = None, limit: int = 50,
    _user: str = _user_required_dep(),  # R6#4 · 至少要登入
):
    """R6#4 · 標案 list 不再匿名可讀(防外部偵察承富業務興趣)"""
    from main import db
    q = {}
    if status:
        q["status"] = status
    if keyword:
        q["keyword"] = keyword
    return _serialize(list(db.tender_alerts.find(q).sort("discovered_at", -1).limit(limit)))


@router.put("/tender-alerts/{tender_key}")
def update_tender_alert(
    tender_key: str,
    status: Literal["new", "reviewing", "interested", "skipped"],
    caller: Optional[str] = _caller_email_dep(),
):
    """標記標案狀態 · Audit sec F-3 · status 白名單 + 必登入"""
    from main import db
    if not caller:
        raise HTTPException(403, "未識別呼叫者 · 請從 launcher 進入")
    r = db.tender_alerts.update_one(
        {"tender_key": tender_key},
        {"$set": {"status": status, "reviewed_at": datetime.utcnow(), "reviewed_by": caller}},
    )
    return {"updated": r.modified_count}

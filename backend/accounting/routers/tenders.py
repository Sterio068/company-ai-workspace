"""
Tenders router · g0v 採購網新標案監測

ROADMAP §11.1 B-4 · 從 main.py 抽出
- list / 標記狀態(new/reviewing/interested/skipped)
- 對應 ROADMAP §11.8 · tender-monitor cron 寫進來
v1.2 §11.1 B-1.5 · 改用 routers/_deps.py 共用 helper
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, Literal
from datetime import datetime, timezone

from ._deps import _serialize, current_user_email_dep, require_user_dep


router = APIRouter(tags=["tenders"])


@router.get("/tender-alerts")
def list_tender_alerts(
    status: Optional[str] = None, keyword: Optional[str] = None, limit: int = 50,
    _user: str = require_user_dep(),  # R6#4 · 至少要登入 · v1.2 用 _deps.py
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
    caller: Optional[str] = current_user_email_dep(),
):
    """標記標案狀態 · Audit sec F-3 · status 白名單 + 必登入"""
    from main import db
    if not caller:
        raise HTTPException(403, "未識別呼叫者 · 請從 launcher 進入")
    r = db.tender_alerts.update_one(
        {"tender_key": tender_key},
        # R31 修 · email 一律 lower · PDPA exact-match 才不漏
        {"$set": {"status": status, "reviewed_at": datetime.now(timezone.utc),
                  "reviewed_by": caller.strip().lower() if caller else None}},
    )
    return {"updated": r.modified_count}

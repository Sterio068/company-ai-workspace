"""
Tenders router · g0v 採購網新標案監測

ROADMAP §11.1 B-4 · 從 main.py 抽出
- list / 標記狀態(new/reviewing/interested/skipped)
- 對應 ROADMAP §11.8 · tender-monitor cron 寫進來
v1.2 §11.1 B-1.5 · 改用 routers/_deps.py 共用 helper
"""
import json
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Literal
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from ._deps import _serialize, current_user_email_dep, require_user_dep


router = APIRouter(tags=["tenders"])
PCC_API = "https://pcc.g0v.ronny.tw/api"
DEFAULT_KEYWORDS = ["活動", "行銷", "公關", "媒體", "策展"]


class TenderMonitorSettings(BaseModel):
    enabled: bool = True
    keywords: list[str] = Field(default_factory=lambda: DEFAULT_KEYWORDS.copy())
    counties: list[str] = Field(default_factory=list)
    units: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    daily_hour: int = Field(default=6, ge=0, le=23)
    auto_import_interested: bool = False


def _normalize_list(values: list[str]) -> list[str]:
    cleaned = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return cleaned


def _settings_dict(doc: Optional[dict] = None) -> dict:
    base = TenderMonitorSettings().model_dump()
    if doc:
        base.update({k: v for k, v in doc.items() if k in base})
        for key in ("keywords", "counties", "units", "exclude_keywords"):
            base[key] = _normalize_list(base.get(key) or [])
        base["updated_at"] = doc.get("updated_at").isoformat() if doc.get("updated_at") else None
        base["updated_by"] = doc.get("updated_by")
        base["last_run_at"] = doc.get("last_run_at").isoformat() if doc.get("last_run_at") else None
        base["last_run_summary"] = doc.get("last_run_summary")
    return base


def _matches_scope(record: dict, settings: dict) -> tuple[bool, Optional[str], Optional[str]]:
    brief = record.get("brief", {}) or {}
    title = brief.get("title") or record.get("title") or ""
    unit = record.get("unit_name") or ""
    text = f"{title} {unit}"
    counties = _normalize_list(settings.get("counties") or [])
    units = _normalize_list(settings.get("units") or [])
    excludes = _normalize_list(settings.get("exclude_keywords") or [])

    if excludes and any(x in text for x in excludes):
        return False, None, None
    matched_county = next((c for c in counties if c in text), None)
    matched_unit = next((u for u in units if u in text), None)
    if counties and not matched_county:
        return False, None, None
    if units and not matched_unit:
        return False, None, None
    return True, matched_county, matched_unit or unit


def _search_tenders(keyword: str, page: int = 1) -> list[dict]:
    url = f"{PCC_API}/searchbytitle?{urllib.parse.urlencode({'query': keyword, 'page': page})}"
    with urllib.request.urlopen(url, timeout=25) as r:
        data = json.loads(r.read().decode())
    return data.get("records", [])


def _insert_alert(db, rec: dict, keyword: str, settings: dict) -> bool:
    brief = rec.get("brief", {}) or {}
    title = brief.get("title") or rec.get("title") or ""
    unit = rec.get("unit_name") or ""
    job_no = rec.get("job_number") or ""
    tender_key = f"{unit}:{job_no}"
    if not unit or not job_no or db.tender_alerts.find_one({"tender_key": tender_key}):
        return False
    ok, county, matched_unit = _matches_scope(rec, settings)
    if not ok:
        return False
    db.tender_alerts.insert_one({
        "tender_key": tender_key,
        "keyword": keyword,
        "title": title,
        "unit_name": unit,
        "department": matched_unit or unit,
        "county": county,
        "job_number": job_no,
        "brief_type": brief.get("type", ""),
        "date": rec.get("date"),
        "raw": rec,
        "monitor_scope": {
            "counties": settings.get("counties", []),
            "units": settings.get("units", []),
        },
        "discovered_at": datetime.now(timezone.utc),
        "status": "new",
    })
    return True


@router.get("/tender-alerts/settings")
def get_tender_monitor_settings(_user: str = require_user_dep()):
    from main import db
    doc = db.settings.find_one({"_id": "tender_monitor"})
    return _settings_dict(doc)


@router.put("/tender-alerts/settings")
def update_tender_monitor_settings(
    settings: TenderMonitorSettings,
    email: str = require_user_dep(),
):
    from main import db
    data = settings.model_dump()
    for key in ("keywords", "counties", "units", "exclude_keywords"):
        data[key] = _normalize_list(data.get(key) or [])
    if not data["keywords"]:
        raise HTTPException(400, "至少要設定 1 個標案關鍵字")
    data.update({
        "_id": "tender_monitor",
        "updated_at": datetime.now(timezone.utc),
        "updated_by": email,
    })
    db.settings.update_one({"_id": "tender_monitor"}, {"$set": data}, upsert=True)
    return _settings_dict(db.settings.find_one({"_id": "tender_monitor"}))


@router.post("/tender-alerts/run-now")
def run_tender_monitor_now(email: str = require_user_dep()):
    """前端手動觸發一次 g0v PCC 搜尋 · cron 仍由 scripts/tender-monitor.py 每日跑"""
    from main import db
    settings = _settings_dict(db.settings.find_one({"_id": "tender_monitor"}))
    if not settings.get("enabled", True):
        raise HTTPException(400, "標案監測目前已關閉")

    run_doc = {
        "requested_by": email,
        "settings_snapshot": settings,
        "status": "running",
        "started_at": datetime.now(timezone.utc),
    }
    run_id = db.tender_monitor_runs.insert_one(run_doc).inserted_id
    total_scanned = 0
    new_count = 0
    errors = []

    for keyword in settings.get("keywords") or DEFAULT_KEYWORDS:
        try:
            records = _search_tenders(keyword, page=1)
        except Exception as exc:
            errors.append({"keyword": keyword, "error": str(exc)[:160]})
            continue
        total_scanned += len(records)
        for rec in records:
            if _insert_alert(db, rec, keyword, settings):
                new_count += 1

    summary = {
        "new_count": new_count,
        "total_scanned": total_scanned,
        "keyword_count": len(settings.get("keywords") or []),
        "errors": errors,
    }
    db.tender_monitor_runs.update_one(
        {"_id": run_id},
        {"$set": {
            "status": "done" if not errors else "partial",
            "finished_at": datetime.now(timezone.utc),
            "summary": summary,
        }},
    )
    db.settings.update_one(
        {"_id": "tender_monitor"},
        {"$set": {
            "last_run_at": datetime.now(timezone.utc),
            "last_run_summary": summary,
        }},
        upsert=True,
    )
    return {"run_id": str(run_id), **summary}


@router.get("/tender-alerts")
def list_tender_alerts(
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    county: Optional[str] = None,
    unit: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    _user: str = require_user_dep(),  # R6#4 · 至少要登入 · v1.2 用 _deps.py
):
    """R6#4 · 標案 list 不再匿名可讀(防外部偵察承富業務興趣)"""
    from main import db
    q = {}
    if status:
        q["status"] = status
    if keyword:
        q["keyword"] = keyword
    if county:
        q["county"] = county
    if unit:
        q["unit_name"] = {"$regex": unit, "$options": "i"}
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

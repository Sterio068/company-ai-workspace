"""
承富會計 / 統一後端 · CRM Router
==============================================
示範:把 CRM Pipeline 從 main.py 拆出來成獨立 router。

其他模組可依此模式拆:
  - accounts.py
  - transactions.py
  - invoices.py
  - projects.py
  - feedback.py
  - admin.py
  - safety.py
  - tenders.py
  - memory.py(context summary + user preferences)
  - orchestrator.py(已拆)

main.py 只負責 FastAPI 主體 + include_router。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum
from bson import ObjectId


router = APIRouter(prefix="/crm", tags=["crm"])


class LeadStage(str, Enum):
    lead       = "lead"
    qualifying = "qualifying"
    proposing  = "proposing"
    submitted  = "submitted"
    won        = "won"
    lost       = "lost"
    executing  = "executing"
    closed     = "closed"


class Lead(BaseModel):
    title: str
    client: Optional[str] = None
    stage: LeadStage = LeadStage.lead
    source: Optional[str] = None
    budget: Optional[float] = None
    deadline: Optional[str] = None
    owner: Optional[str] = None
    description: Optional[str] = None
    tender_key: Optional[str] = None
    probability: float = 0.0
    notes: list[dict] = []


# ============================================================
# 注入 db(DI pattern · main.py 啟動時 setattr)
# ============================================================
def get_db():
    """由 main.py 在 startup 時 inject · 避免 circular import。"""
    from main import db
    return db


def serialize(doc):
    """ObjectId → str."""
    if not doc:
        return doc
    if isinstance(doc, list):
        return [serialize(d) for d in doc]
    if isinstance(doc, dict):
        return {k: (str(v) if isinstance(v, ObjectId) else
                    serialize(v) if isinstance(v, (dict, list)) else v)
                for k, v in doc.items()}
    return doc


# ============================================================
# CRUD
# ============================================================
@router.get("/leads")
def list_leads(stage: Optional[str] = None, owner: Optional[str] = None):
    db = get_db()
    q = {}
    if stage: q["stage"] = stage
    if owner: q["owner"] = owner
    return serialize(list(db.crm_leads.find(q).sort("updated_at", -1)))


@router.post("/leads")
def create_lead(lead: Lead):
    db = get_db()
    data = lead.dict()
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()
    r = db.crm_leads.insert_one(data)
    return {"id": str(r.inserted_id)}


@router.put("/leads/{lead_id}")
def update_lead(lead_id: str, updates: dict):
    db = get_db()
    allowed = {"title", "client", "stage", "source", "budget", "deadline",
               "owner", "description", "probability", "notes"}
    update = {k: v for k, v in updates.items() if k in allowed}
    update["updated_at"] = datetime.utcnow()

    if "stage" in update:
        db.crm_stage_history.insert_one({
            "lead_id": lead_id,
            "new_stage": update["stage"],
            "changed_at": datetime.utcnow(),
            "changed_by": updates.get("_by"),
        })

    r = db.crm_leads.update_one({"_id": ObjectId(lead_id)}, {"$set": update})
    return {"updated": r.modified_count}


@router.delete("/leads/{lead_id}")
def delete_lead(lead_id: str):
    db = get_db()
    r = db.crm_leads.delete_one({"_id": ObjectId(lead_id)})
    return {"deleted": r.deleted_count}


@router.post("/leads/{lead_id}/notes")
def add_lead_note(lead_id: str, note: str, by: Optional[str] = None):
    db = get_db()
    db.crm_leads.update_one(
        {"_id": ObjectId(lead_id)},
        {"$push": {"notes": {
            "text": note, "at": datetime.utcnow().isoformat(), "by": by,
        }},
         "$set": {"updated_at": datetime.utcnow()}}
    )
    return {"added": True}


@router.get("/stats")
def crm_stats():
    db = get_db()
    pipeline = [
        {"$group": {"_id": "$stage", "count": {"$sum": 1},
                    "budget_total": {"$sum": "$budget"}}},
    ]
    by_stage = list(db.crm_leads.aggregate(pipeline))
    won = db.crm_leads.count_documents({"stage": "won"})
    lost = db.crm_leads.count_documents({"stage": "lost"})
    win_rate = round(won / (won + lost) * 100, 1) if (won + lost) > 0 else None

    active_leads = list(db.crm_leads.find({
        "stage": {"$in": ["lead", "qualifying", "proposing", "submitted"]}
    }))
    expected_value = sum(
        (l.get("budget") or 0) * (l.get("probability") or 0.5)
        for l in active_leads
    )

    return {
        "by_stage": [{"stage": s["_id"], "count": s["count"],
                      "budget_total": s["budget_total"] or 0} for s in by_stage],
        "win_rate": win_rate,
        "active_pipeline_value": round(expected_value, 0),
        "total_leads": sum(s["count"] for s in by_stage),
    }


@router.post("/import-from-tenders")
def import_leads_from_tenders():
    db = get_db()
    interested = list(db.tender_alerts.find({"status": "interested"}))
    imported = 0
    for t in interested:
        if db.crm_leads.find_one({"tender_key": t.get("tender_key")}):
            continue
        db.crm_leads.insert_one({
            "title": t.get("title"),
            "client": t.get("unit_name"),
            "stage": "lead",
            "source": "tender_alert",
            "tender_key": t.get("tender_key"),
            "description": f"來源:政府電子採購網 · 關鍵字「{t.get('keyword')}」",
            "probability": 0.5,
            "notes": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })
        imported += 1
    return {"imported": imported, "total_interested": len(interested)}

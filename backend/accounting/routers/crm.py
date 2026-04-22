"""
CRM router · v1.3 §11.1 B-9 · 從 main.py 抽出

CRM Pipeline(Kanban · 標案 → 提案 → 得標 → 執行 → 結案)

涵蓋 7 endpoint:
- /crm/leads GET/POST(新增 lead · stage filter)
- /crm/leads/{id} PUT/DELETE(更新 stage 會記 stage_history)
- /crm/leads/{id}/notes POST(觸點 / 會議紀錄)
- /crm/stats GET(漏斗價值 · 勝率 · by_stage 統計)
- /crm/import-from-tenders POST(把 'interested' tender_alerts 轉成 leads)

注意間接耦合(R12 codex 提示):
- db.crm_leads 與 services/admin_metrics tender_funnel 共用 source 欄位
- routers/tenders.py 的 status 與 CRM source 是不同流程 · 不互動
"""
import logging
from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from bson import ObjectId
from bson.errors import InvalidId


router = APIRouter(tags=["crm"])
logger = logging.getLogger("chengfu")


def _lead_oid(lead_id: str) -> ObjectId:
    """R14#2 · 統一 ObjectId 解析 · 不被 Mongo 寫入錯誤誤吞成 400"""
    try:
        return ObjectId(lead_id)
    except (InvalidId, TypeError):
        raise HTTPException(400, "lead_id 格式錯誤")


# ============================================================
# Models
# ============================================================
class LeadStage(str, Enum):
    lead       = "lead"          # 新機會(採購網自動進這)
    qualifying = "qualifying"    # 評估中(Go/No-Go 進行)
    proposing  = "proposing"     # 撰寫提案中
    submitted  = "submitted"     # 已送件等結果
    won        = "won"           # 得標
    lost       = "lost"          # 未得標
    executing  = "executing"     # 執行中(得標後)
    closed     = "closed"        # 結案完成


class Lead(BaseModel):
    title: str
    client: Optional[str] = None
    stage: LeadStage = LeadStage.lead
    source: Optional[str] = None  # tender_alert / manual / referral
    budget: Optional[float] = None
    deadline: Optional[str] = None
    owner: Optional[str] = None
    description: Optional[str] = None
    tender_key: Optional[str] = None  # 若從 tender_alert 來
    probability: float = 0.0  # 0-1
    notes: list[dict] = []  # 觸點 / 會議紀錄


# ============================================================
# Endpoints
# ============================================================
@router.get("/crm/leads")
def list_leads(
    stage: Optional[str] = None,
    owner: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),  # R14#2 · 封頂 500
    skip: int = Query(default=0, ge=0),
):
    """Kanban 讀 leads · 依階段分組
    R14#2 · 加 pagination · 防全撈 1000+ 筆記憶體爆
    """
    from main import db, serialize
    q = {}
    if stage: q["stage"] = stage
    if owner: q["owner"] = owner
    cursor = db.crm_leads.find(q).sort("updated_at", -1).skip(skip).limit(limit)
    leads = serialize(list(cursor))
    total = db.crm_leads.count_documents(q)
    return {
        "items": leads,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": (skip + len(leads)) < total,
    }


@router.post("/crm/leads")
def create_lead(lead: Lead):
    from main import db
    data = lead.model_dump()
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()
    r = db.crm_leads.insert_one(data)
    return {"id": str(r.inserted_id)}


@router.put("/crm/leads/{lead_id}")
def update_lead(lead_id: str, updates: dict):
    """部分更新 · 支援拖動 Kanban(只改 stage)或完整編輯

    R13#1 修:
    - lead_id 格式錯 → 400(原本 raw ObjectId 會 raise 500)
    - lead 不存在 → 404(原本還是先寫 stage_history)
    - stage 非法值 → 400(原本任意字串都進 DB)
    - stage 真改變才寫 history(原本只要有 stage key 就寫)
    """
    from main import db
    allowed = {"title", "client", "stage", "source", "budget", "deadline",
               "owner", "description", "probability", "notes"}
    update = {k: v for k, v in updates.items() if k in allowed}

    # R13#1 · stage 必走 LeadStage enum 驗證
    if "stage" in update:
        try:
            update["stage"] = LeadStage(update["stage"]).value
        except ValueError:
            raise HTTPException(400, f"stage '{update['stage']}' 不在合法集合內")

    update["updated_at"] = datetime.utcnow()

    oid = _lead_oid(lead_id)
    old = db.crm_leads.find_one({"_id": oid}, {"stage": 1})
    if not old:
        raise HTTPException(404, "lead 不存在")

    r = db.crm_leads.update_one({"_id": oid}, {"$set": update})

    # R13#1 · stage 真有改變才寫 stage_history(原本不必變也寫)
    if "stage" in update and old.get("stage") != update["stage"]:
        db.crm_stage_history.insert_one({
            "lead_id": lead_id,
            "old_stage": old.get("stage"),
            "new_stage": update["stage"],
            "changed_at": datetime.utcnow(),
            "changed_by": updates.get("_by"),
        })

    return {"updated": r.modified_count}


@router.delete("/crm/leads/{lead_id}")
def delete_lead(lead_id: str):
    """R14#2 · 用 _lead_oid · 補 404"""
    from main import db
    r = db.crm_leads.delete_one({"_id": _lead_oid(lead_id)})
    if r.deleted_count == 0:
        raise HTTPException(404, "lead 不存在")
    return {"deleted": r.deleted_count}


@router.post("/crm/leads/{lead_id}/notes")
def add_lead_note(lead_id: str, note: str, by: Optional[str] = None):
    """加觸點 · 電話 / 會議 / Email 紀錄
    R14#2 · 用 _lead_oid · 防 lead 不存在仍回 200(false success)
    """
    from main import db
    r = db.crm_leads.update_one(
        {"_id": _lead_oid(lead_id)},
        {"$push": {"notes": {
            "text": note, "at": datetime.utcnow().isoformat(), "by": by,
        }},
         "$set": {"updated_at": datetime.utcnow()}}
    )
    if r.matched_count == 0:
        raise HTTPException(404, "lead 不存在")
    return {"added": True}


@router.get("/crm/stats")
def crm_stats():
    """Kanban 儀表統計 · 漏斗價值 · 勝率 · by_stage

    R14#2 · 原本 active_leads 全撈 Python for-loop 加總(1000+ leads 會慢)
    改 Mongo $match + $group · 單次 aggregate 拿全部 · Python 只整理輸出
    · full-scan 扣掉 · 100 leads × 10 req/min × 8h = 48k 次也可
    """
    from main import db

    # 一次 aggregate 拿 by_stage + by_category(active / won / lost)
    pipeline = [
        {"$group": {
            "_id": "$stage",
            "count": {"$sum": 1},
            "budget_total": {"$sum": {"$ifNull": ["$budget", 0]}},
            # R14#2 · 漏斗期望值 = sum(budget × probability · 只算 active stage)
            "expected_value": {
                "$sum": {
                    "$cond": [
                        {"$in": ["$stage", ["lead", "qualifying", "proposing", "submitted"]]},
                        {"$multiply": [
                            {"$ifNull": ["$budget", 0]},
                            {"$ifNull": ["$probability", 0.5]},
                        ]},
                        0,
                    ]
                }
            },
        }},
    ]
    by_stage = list(db.crm_leads.aggregate(pipeline))

    won = next((s["count"] for s in by_stage if s["_id"] == "won"), 0)
    lost = next((s["count"] for s in by_stage if s["_id"] == "lost"), 0)
    win_rate = round(won / (won + lost) * 100, 1) if (won + lost) > 0 else None
    expected_value = sum(s.get("expected_value", 0) for s in by_stage)

    return {
        "by_stage": [{"stage": s["_id"], "count": s["count"],
                      "budget_total": s.get("budget_total", 0) or 0} for s in by_stage],
        "win_rate": win_rate,
        "active_pipeline_value": round(expected_value, 0),
        "total_leads": sum(s["count"] for s in by_stage),
    }


@router.post("/crm/import-from-tenders")
def import_leads_from_tenders():
    """把標記為 'interested' 的 tender_alerts 轉成 CRM leads"""
    from main import db
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

"""
Projects router · v1.3 §11.1 B-10 · 從 main.py 抽出

涵蓋:
- /projects GET/POST · /projects/{id} PUT/DELETE
- /projects/{id}/handoff GET/PUT(B2 · 4 格卡 跨人 / 跨日交棒 artifact)

依賴:
- main.py(lazy)· projects_col / serialize
- 跟 routers/accounting.py 的 /projects/{id}/finance 共用 projects collection · 不衝突

注意:V1.1-SPEC §C handoff endpoint 獨立於 PUT /projects/{id} · 不全量更新
"""
import logging
from datetime import datetime
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from bson import ObjectId
from bson.errors import InvalidId


router = APIRouter(tags=["projects"])
logger = logging.getLogger("chengfu")


def _project_oid(project_id: str) -> ObjectId:
    """R13#2 · ObjectId 解析統一處理 · 不誤吞 Mongo 寫入錯誤
    原 except Exception 太寬 · update_one 失敗也會誤回 400 'project_id 格式錯誤'
    """
    try:
        return ObjectId(project_id)
    except (InvalidId, TypeError):
        raise HTTPException(400, "project_id 格式錯誤")


# ============================================================
# Models
# ============================================================
class Project(BaseModel):
    name: str
    client: Optional[str] = None
    budget: Optional[float] = None
    deadline: Optional[str] = None
    description: Optional[str] = None
    status: Literal["active", "closed"] = "active"
    owner: Optional[str] = None


class HandoffAssetRef(BaseModel):
    type: Literal["nas", "url", "file", "note"] = "note"
    label: str = ""
    ref: str = ""


class HandoffCard(BaseModel):
    goal: str = ""
    constraints: list[str] = []
    asset_refs: list[HandoffAssetRef] = []
    next_actions: list[str] = []
    source_conversation_id: Optional[str] = None


# ============================================================
# Endpoints · 專案 CRUD
# ============================================================
@router.get("/projects")
def list_projects(status: Optional[str] = None):
    from main import projects_col, serialize
    q = {}
    if status: q["status"] = status
    return serialize(list(projects_col.find(q).sort("updated_at", -1)))


@router.post("/projects")
def create_project(p: Project):
    from main import projects_col
    data = p.model_dump()
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()
    r = projects_col.insert_one(data)
    return {"id": str(r.inserted_id)}


@router.put("/projects/{project_id}")
def update_project(project_id: str, p: Project):
    """R14#1 · 用 _project_oid · 補 404 · bad id 不再 500"""
    from main import projects_col
    data = p.model_dump(exclude_unset=True)  # py-review #1 · pydantic v2 一致
    data["updated_at"] = datetime.utcnow()
    r = projects_col.update_one({"_id": _project_oid(project_id)}, {"$set": data})
    if r.matched_count == 0:
        raise HTTPException(404, "專案不存在")
    return {"updated": r.modified_count}


@router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    """R14#1 · 用 _project_oid · 補 404"""
    from main import projects_col
    r = projects_col.delete_one({"_id": _project_oid(project_id)})
    if r.deleted_count == 0:
        raise HTTPException(404, "專案不存在")
    return {"deleted": r.deleted_count}


# ============================================================
# B2 · Handoff 4 格卡(跨助手 · 跨人 · 跨日的交棒 artifact)
# V1.1-SPEC §C · 獨立 endpoint 不用 PUT /projects/{id} 全量更新
# ============================================================
@router.put("/projects/{project_id}/handoff")
def update_handoff(project_id: str, card: HandoffCard, request: Request):
    """PM 存完 · 多分頁 BroadcastChannel 會通知其他同仁 re-render"""
    from main import projects_col
    email = (request.headers.get("X-User-Email") or "").strip().lower() or None
    payload = {
        **card.model_dump(),
        "updated_by": email,
        "updated_at": datetime.utcnow(),
    }
    # R13#2 · _project_oid raise 400 為唯一 · update_one 失敗 → 真 500(Mongo 異常)
    r = projects_col.update_one(
        {"_id": _project_oid(project_id)},
        {"$set": {"handoff": payload, "updated_at": datetime.utcnow()}},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "專案不存在")
    return {"ok": True, "updated_at": payload["updated_at"].isoformat()}


@router.get("/projects/{project_id}/handoff")
def get_handoff(project_id: str):
    from main import projects_col
    doc = projects_col.find_one(
        {"_id": _project_oid(project_id)}, {"handoff": 1, "name": 1}
    )
    if not doc:
        raise HTTPException(404, "專案不存在")
    h = doc.get("handoff") or {}
    if isinstance(h.get("updated_at"), datetime):
        h["updated_at"] = h["updated_at"].isoformat()
    return {"project_name": doc.get("name", ""), "handoff": h}

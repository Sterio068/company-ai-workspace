"""專案管理 router(取代 Launcher localStorage · 團隊共享)。"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime
from bson import ObjectId


router = APIRouter(prefix="/projects", tags=["projects"])


class Project(BaseModel):
    name: str
    client: Optional[str] = None
    budget: Optional[float] = None
    deadline: Optional[str] = None
    description: Optional[str] = None
    status: Literal["active", "closed"] = "active"
    owner: Optional[str] = None


def get_db():
    from main import db
    return db


def serialize(doc):
    if isinstance(doc, list):  return [serialize(d) for d in doc]
    if isinstance(doc, dict):
        return {k: (str(v) if isinstance(v, ObjectId) else serialize(v) if isinstance(v, (dict, list)) else v)
                for k, v in doc.items()}
    return doc


@router.get("")
def list_projects(status: Optional[str] = None):
    db = get_db()
    q = {}
    if status: q["status"] = status
    return serialize(list(db.projects.find(q).sort("updated_at", -1)))


@router.post("")
def create_project(p: Project):
    db = get_db()
    data = p.dict()
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()
    r = db.projects.insert_one(data)
    return {"id": str(r.inserted_id)}


@router.put("/{project_id}")
def update_project(project_id: str, p: Project):
    db = get_db()
    data = p.dict(exclude_unset=True)
    data["updated_at"] = datetime.utcnow()
    r = db.projects.update_one({"_id": ObjectId(project_id)}, {"$set": data})
    return {"updated": r.modified_count}


@router.delete("/{project_id}")
def delete_project(project_id: str):
    db = get_db()
    r = db.projects.delete_one({"_id": ObjectId(project_id)})
    return {"deleted": r.deleted_count}

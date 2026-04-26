"""
v1.7 · Smart Folders CRUD + preview
=====================================
給 dashboard-fpp.js 的 Smart Folder Builder modal · 真後端

Endpoints:
  GET    /admin/smart-folders             · 列 user 所有 smart folders
  POST   /admin/smart-folders             · 新增
  PUT    /admin/smart-folders/{key}       · 更新
  DELETE /admin/smart-folders/{key}       · 移除
  POST   /admin/smart-folders/preview     · 條件 → 即時 count + 前 3 名

Schema(smart_folders collection):
  {
    user_email: str,                    # owner
    key: str,                           # unique id 例 "custom-1234567890"
    name: str,                          # 顯示名 例「Q1 客戶 · 高優先」
    conditions: [
      { f: str, op: str, v: str },     # 例 { f: "工作區", op: "=", v: "投標" }
    ],
    show_in_segments: bool,
    notify: bool,
    created_at: datetime,
    updated_at: datetime,
  }
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .._deps import require_admin_dep


router = APIRouter(tags=["admin"])

# ============================================================
# Models
# ============================================================
class Condition(BaseModel):
    f: str           # field · 工作區 / 回應狀態 / 上次活動 / ...
    op: str          # = / ≠ / 包含 / > / <
    v: str           # value


class SmartFolderCreate(BaseModel):
    key: Optional[str] = None  # 客戶端建 · 否則自動產
    name: str
    conditions: List[Condition]
    show_in_segments: bool = True
    notify: bool = False


class PreviewRequest(BaseModel):
    conditions: List[Condition]
    # v1.8 · 加 ge/le bound · 防裸 int 探勘大量 LibreChat messages collection
    limit: int = Field(default=3, ge=1, le=20)


# ============================================================
# 條件 → metadata filter(in-memory · MVP · 不 SQL)
# ============================================================
def _matches_condition(meta: dict, cond: dict) -> bool:
    """單一條件對 meta 比對"""
    f, op, v = cond["f"], cond["op"], cond["v"]

    # field 對應 meta key
    field_map = {
        "工作區": "workspace",
        "回應狀態": "response_status",
        "對話標題": "title",
        "未讀數": "unread_count",
        "工作包": "project_id",
        "主管家活動": "agent_id",
    }
    if f == "上次活動":
        # 特殊 · 比較天數
        from datetime import datetime, timezone, timedelta
        last = meta.get("last_activity_at")
        if not last:
            return False
        try:
            days = float(v.replace("天", "").strip())
        except (ValueError, AttributeError):
            return False
        ago = (datetime.now(timezone.utc) - last).days
        if op == "<":
            return ago < days
        if op == ">":
            return ago > days
        if op == "=":
            return ago == int(days)
        return False

    if f == "提及我":
        # v 為 user 識別 · 應在 mentions 內
        return v in (meta.get("mentions") or [])

    meta_key = field_map.get(f)
    if not meta_key:
        return False
    actual = meta.get(meta_key)
    if actual is None:
        return False
    actual_str = str(actual).lower()
    v_str = str(v).lower()

    if op == "=":
        return actual_str == v_str
    if op == "≠":
        return actual_str != v_str
    if op == "包含":
        return v_str in actual_str
    if op == ">":
        try: return float(actual) > float(v)
        except: return False
    if op == "<":
        try: return float(actual) < float(v)
        except: return False
    return False


def _matches_all(meta: dict, conditions: list) -> bool:
    """AND 所有條件"""
    return all(_matches_condition(meta, c) for c in conditions)


def _filter_metas(metas: list, conditions: list) -> list:
    cond_dicts = [c if isinstance(c, dict) else c.dict() for c in conditions]
    return [m for m in metas if _matches_all(m, cond_dicts)]


# ============================================================
# Helpers · get user's metas
# ============================================================
def _get_user_metas(db, user_email: str, limit: int = 100) -> list:
    """從 LibreChat 拿 user 對話 + 算 metadata · 給 preview / 查詢用"""
    from services.conversation_meta import get_recent_metas
    from services.librechat_admin import find_librechat_user_id
    user_id = find_librechat_user_id(db, user_email)
    if not user_id:
        return []
    return get_recent_metas(db, user_email, user_id, limit=limit)


# ============================================================
# Endpoints
# ============================================================
@router.get("/admin/smart-folders")
def list_smart_folders(_admin: str = require_admin_dep()):
    """列 user 自建 smart folders"""
    from main import db
    items = list(db.smart_folders.find({"user_email": _admin.lower()}).sort("created_at", -1))
    for it in items:
        it["_id"] = str(it["_id"])
        for k in ("created_at", "updated_at"):
            if k in it and hasattr(it[k], "isoformat"):
                it[k] = it[k].isoformat()
    return {"items": items}


@router.post("/admin/smart-folders")
def create_smart_folder(payload: SmartFolderCreate, _admin: str = require_admin_dep()):
    from main import db
    now = datetime.now(timezone.utc)
    key = payload.key or f"custom-{int(now.timestamp())}"
    doc = {
        "user_email": _admin.lower(),
        "key": key,
        "name": payload.name,
        "conditions": [c.dict() for c in payload.conditions],
        "show_in_segments": payload.show_in_segments,
        "notify": payload.notify,
        "created_at": now,
        "updated_at": now,
    }
    # upsert · 同 key 覆寫
    db.smart_folders.update_one(
        {"user_email": _admin.lower(), "key": key},
        {"$set": doc},
        upsert=True,
    )
    return {"key": key, "name": payload.name}


@router.put("/admin/smart-folders/{key}")
def update_smart_folder(key: str, payload: SmartFolderCreate, _admin: str = require_admin_dep()):
    from main import db
    r = db.smart_folders.update_one(
        {"user_email": _admin.lower(), "key": key},
        {"$set": {
            "name": payload.name,
            "conditions": [c.dict() for c in payload.conditions],
            "show_in_segments": payload.show_in_segments,
            "notify": payload.notify,
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    if r.matched_count == 0:
        raise HTTPException(404, f"Smart folder {key} not found")
    return {"updated": True, "key": key}


@router.delete("/admin/smart-folders/{key}")
def delete_smart_folder(key: str, _admin: str = require_admin_dep()):
    from main import db
    r = db.smart_folders.delete_one({"user_email": _admin.lower(), "key": key})
    return {"deleted": r.deleted_count > 0, "key": key}


@router.post("/admin/smart-folders/preview")
def preview_smart_folder(payload: PreviewRequest, _admin: str = require_admin_dep()):
    """條件 → 即時計算符合對話 · 給 Builder modal 即時預覽"""
    from main import db
    metas = _get_user_metas(db, _admin)
    matched = _filter_metas(metas, payload.conditions)
    return {
        "count": len(matched),
        "items": [
            {
                "id": m["conversation_id"],
                "title": m["title"],
                "workspace": m.get("workspace"),
                "last_activity_at": m["last_activity_at"].isoformat() if m.get("last_activity_at") else None,
            }
            for m in matched[:payload.limit]
        ],
    }


@router.get("/admin/smart-folders/{key}/items")
def get_smart_folder_items(
    key: str,
    # v1.8 · 加 ge/le bound · 防 ?limit=999999 DoS
    limit: int = Query(default=50, ge=1, le=200),
    _admin: str = require_admin_dep(),
):
    """讀某 smart folder · 拿符合條件對話列表"""
    from main import db
    folder = db.smart_folders.find_one({"user_email": _admin.lower(), "key": key})
    if not folder:
        raise HTTPException(404, f"Smart folder {key} not found")
    metas = _get_user_metas(db, _admin, limit=200)
    matched = _filter_metas(metas, folder["conditions"])
    return {
        "key": key,
        "name": folder["name"],
        "count": len(matched),
        "items": [
            {
                "id": m["conversation_id"],
                "title": m["title"],
                "workspace": m.get("workspace"),
                "last_activity_at": m["last_activity_at"].isoformat() if m.get("last_activity_at") else None,
                "response_status": m.get("response_status"),
                "unread_count": m.get("unread_count", 0),
            }
            for m in matched[:limit]
        ],
    }

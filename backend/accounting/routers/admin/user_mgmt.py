"""
User Management sub-router · admin UI 在前端建同仁帳號

v1.3 feature · 老闆不用 shell · 在 launcher UI 點一點建人

設計:
- 直接用 LibreChat 的 users collection · 不自己 fork schema
- 多存 2 欄:title(自訂頭銜 · 會計/企劃/設計)· permissions(勾選 array)
- 密碼不回傳(bcrypt hash 存 LibreChat)· 建時 admin 看到一次 · 之後只能 reset
- 新建走 LibreChat registerUser service · 讓 LibreChat 該做的都做(hash + verify email 等)

Endpoints:
- POST   /admin/users           · 建新同仁(email + name + password + title + permissions + role)
- GET    /admin/users           · 列所有 user(不含 password)
- PATCH  /admin/users/{email}   · 改 title / permissions / role / active
- DELETE /admin/users/{email}   · 軟停用(active=false)· 真刪走 PDPA flow

Permissions 目前 UI 可勾選 + 存庫 · backend 硬 enforce 逐步展開(先 admin.*)
完整 enforcement 留 v1.4
"""
from datetime import datetime, timezone
from typing import List, Optional

import bcrypt
import re
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from .._deps import require_admin_dep, get_db


router = APIRouter(prefix="/admin", tags=["admin-users"])


# ============================================================
# Permission Catalog · UI 勾選用 · 分 8 群組
# ============================================================
PERMISSION_CATALOG = [
    {
        "group": "🎯 投標",
        "items": [
            {"key": "tender.view", "label": "看政府採購網標案", "default": True},
            {"key": "tender.evaluate", "label": "Go/No-Go 評估", "default": True},
        ],
    },
    {
        "group": "💼 商機 CRM",
        "items": [
            {"key": "crm.view_own", "label": "看自己 owner 的 lead", "default": True},
            {"key": "crm.view_all", "label": "看所有人的 lead", "default": False},
            {"key": "crm.edit_all", "label": "編輯所有 lead", "default": False},
        ],
    },
    {
        "group": "🎪 活動 / 專案",
        "items": [
            {"key": "project.create", "label": "建立專案", "default": True},
            {"key": "project.edit_own", "label": "改自己 owner 的專案", "default": True},
            {"key": "project.edit_all", "label": "改所有專案", "default": False},
        ],
    },
    {
        "group": "🎨 設計 / 素材",
        "items": [
            {"key": "design.generate", "label": "AI 生圖(Fal.ai)", "default": True},
            {"key": "media_assets.manage", "label": "管素材庫", "default": False},
        ],
    },
    {
        "group": "📣 公關 / 社群",
        "items": [
            {"key": "press.draft", "label": "寫新聞稿", "default": True},
            {"key": "social.post_own", "label": "發自己的社群排程", "default": True},
            {"key": "social.post_all", "label": "改所有人的社群排程", "default": False},
            {"key": "media_crm.view", "label": "看媒體記者名單", "default": False},
            {"key": "media_crm.edit", "label": "編輯記者(PDPA 敏感)", "default": False},
            {"key": "media_crm.export", "label": "匯出記者 CSV", "default": False},
        ],
    },
    {
        "group": "🎤 會議 / 場勘",
        "items": [
            {"key": "meeting.upload", "label": "上傳會議錄音", "default": True},
            {"key": "site.survey", "label": "場勘拍照", "default": True},
        ],
    },
    {
        "group": "📊 會計 / 知識",
        "items": [
            {"key": "accounting.view", "label": "看會計報表", "default": False},
            {"key": "accounting.edit", "label": "記會計交易", "default": False},
            {"key": "knowledge.search", "label": "搜知識庫", "default": True},
            {"key": "knowledge.manage", "label": "建 / 改資料源", "default": False},
        ],
    },
    {
        "group": "🔴 Admin(只給信任的人)",
        "items": [
            {"key": "admin.dashboard", "label": "儀表板 + 用量統計", "default": False},
            {"key": "admin.audit", "label": "看 audit log", "default": False},
            {"key": "admin.pdpa", "label": "刪他人資料(PDPA)", "default": False},
        ],
    },
]

# 推薦 preset · 給 UI「套模板」快捷按鈕用
TITLE_PRESETS = {
    "老闆 / Champion": [  # 全部勾
        p["key"]
        for g in PERMISSION_CATALOG for p in g["items"]
    ],
    "企劃 / 專案經理": [
        "tender.view", "tender.evaluate",
        "crm.view_all", "crm.edit_all",
        "project.create", "project.edit_own", "project.edit_all",
        "design.generate", "press.draft",
        "social.post_own", "media_crm.view",
        "meeting.upload", "site.survey",
        "accounting.view", "knowledge.search",
    ],
    "設計師": [
        "project.edit_own",
        "design.generate", "media_assets.manage",
        "meeting.upload", "site.survey",
        "knowledge.search",
    ],
    "公關 / 媒體窗口": [
        "press.draft", "social.post_own",
        "media_crm.view", "media_crm.edit",  # 公關要改記者
        "meeting.upload", "knowledge.search",
    ],
    "會計 / 財務": [
        "accounting.view", "accounting.edit",
        "meeting.upload", "knowledge.search",
    ],
    "業務 / 顧問": [
        "tender.view", "tender.evaluate",
        "crm.view_own",
        "project.create", "project.edit_own",
        "press.draft",
        "meeting.upload", "knowledge.search",
    ],
    "實習生 / 新人": [  # 最小權 · 只能自己看自己玩
        "project.edit_own",
        "design.generate",
        "meeting.upload",
        "knowledge.search",
    ],
}


@router.get("/users/permission-catalog")
def get_permission_catalog(_admin: str = require_admin_dep()):
    """UI 開建 user modal 時拿 · 28 個 permission + 7 個 preset"""
    return {
        "catalog": PERMISSION_CATALOG,
        "presets": TITLE_PRESETS,
    }


# ============================================================
# Pydantic models
# ============================================================
# 簡易 email regex · 不走 EmailStr 避免 email-validator dep
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class UserCreate(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    name: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    title: Optional[str] = Field(None, max_length=50)  # 自訂頭銜(會計 / 企劃 / 設計)
    permissions: List[str] = Field(default_factory=list)
    role: str = Field(default="USER", pattern="^(USER|ADMIN)$")

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("email 格式不對")
        return v


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    title: Optional[str] = Field(None, max_length=50)
    permissions: Optional[List[str]] = None
    role: Optional[str] = Field(None, pattern="^(USER|ADMIN)$")
    active: Optional[bool] = None


# ============================================================
# POST /admin/users · 建新同仁
# ============================================================
@router.post("/users")
def create_user(payload: UserCreate, _admin: str = require_admin_dep()):
    """建新同仁 · 寫 LibreChat users + 承富 meta 欄位

    流程:
    1. check email 沒重複
    2. bcrypt hash 密碼
    3. insert users · 含 title / permissions / 承富自訂 meta
    4. 回 user(不含密碼)

    Note:密碼 admin 看一次後消失 · 同仁要改密碼走 LibreChat 自己的 reset 流程
    """
    db = get_db()
    email_norm = payload.email.strip().lower()

    # 檢查重複
    existing = db.users.find_one({"email": email_norm})
    if existing:
        raise HTTPException(409, f"email {email_norm} 已存在")

    # bcrypt hash(LibreChat 用 10 rounds · 我們對齊)
    pw_hash = bcrypt.hashpw(payload.password.encode("utf-8"), bcrypt.gensalt(10))

    # 驗 permissions 都在 catalog 內 · 防 UI bypass 塞怪字串
    valid_keys = {
        p["key"]
        for g in PERMISSION_CATALOG for p in g["items"]
    }
    invalid = [k for k in payload.permissions if k not in valid_keys]
    if invalid:
        raise HTTPException(400, f"不合法 permission keys: {invalid}")

    # LibreChat 基本 fields + 承富自訂 meta(chengfu_* prefix 不碰 LibreChat 原生)
    doc = {
        "email": email_norm,
        "name": payload.name,
        "username": email_norm.split("@")[0],  # LibreChat 要求
        "password": pw_hash,
        "role": payload.role,
        "emailVerified": True,
        "provider": "local",
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
        # 承富自訂 meta
        "chengfu_title": payload.title or "",
        "chengfu_permissions": payload.permissions,
        "chengfu_active": True,
        "chengfu_created_by": "admin_ui",
    }
    r = db.users.insert_one(doc)

    # audit log
    try:
        db.audit_log.insert_one({
            "action": "admin_create_user",
            "user": _admin,
            "details": {
                "created_email": email_norm,
                "title": payload.title,
                "role": payload.role,
                "permission_count": len(payload.permissions),
            },
            "created_at": datetime.now(timezone.utc),
        })
    except Exception:
        pass

    return {
        "id": str(r.inserted_id),
        "email": email_norm,
        "name": payload.name,
        "title": payload.title,
        "role": payload.role,
        "permissions": payload.permissions,
        "active": True,
        "created_at": doc["createdAt"].isoformat(),
    }


# ============================================================
# GET /admin/users · 列全部
# ============================================================
@router.get("/users")
def list_users(
    include_inactive: bool = Query(default=False),
    _admin: str = require_admin_dep(),
):
    """列所有 user · 不含密碼 hash · 預設只回 active"""
    db = get_db()
    q = {} if include_inactive else {"chengfu_active": {"$ne": False}}

    users = []
    for u in db.users.find(q).sort("createdAt", -1):
        users.append({
            "id": str(u["_id"]),
            "email": u.get("email", ""),
            "name": u.get("name", ""),
            "title": u.get("chengfu_title", ""),
            "role": u.get("role", "USER"),
            "permissions": u.get("chengfu_permissions", []),
            "active": u.get("chengfu_active", True),
            "created_at": (u.get("createdAt") or datetime.now(timezone.utc)).isoformat(),
            "last_login": u.get("lastLogin", "").isoformat() if u.get("lastLogin") else None,
        })
    return {"total": len(users), "items": users}


# ============================================================
# PATCH /admin/users/{email}
# ============================================================
@router.patch("/users/{email}")
def update_user(email: str, payload: UserUpdate, _admin: str = require_admin_dep()):
    """改 title / permissions / role / active

    不改 password · 同仁要改密碼走 LibreChat reset(安全 · admin 看不到舊密碼)
    不改 email · 要改 email 請刪了重建(避免 audit log 斷鏈)
    """
    db = get_db()
    email_norm = email.strip().lower()

    u = db.users.find_one({"email": email_norm})
    if not u:
        raise HTTPException(404, f"user {email_norm} 不存在")

    # admin 不能降自己的 role(防 lockout)
    if payload.role == "USER" and email_norm == _admin:
        raise HTTPException(400, "不能降自己為 USER · 防 admin lockout · 請請其他 admin 做")

    # permissions 驗
    update_fields = {"updatedAt": datetime.now(timezone.utc)}
    if payload.name is not None:
        update_fields["name"] = payload.name
    if payload.title is not None:
        update_fields["chengfu_title"] = payload.title
    if payload.permissions is not None:
        valid_keys = {p["key"] for g in PERMISSION_CATALOG for p in g["items"]}
        invalid = [k for k in payload.permissions if k not in valid_keys]
        if invalid:
            raise HTTPException(400, f"不合法 permission keys: {invalid}")
        update_fields["chengfu_permissions"] = payload.permissions
    if payload.role is not None:
        update_fields["role"] = payload.role
    if payload.active is not None:
        update_fields["chengfu_active"] = payload.active

    db.users.update_one({"email": email_norm}, {"$set": update_fields})

    # audit
    try:
        db.audit_log.insert_one({
            "action": "admin_update_user",
            "user": _admin,
            "details": {
                "target_email": email_norm,
                "fields": list(update_fields.keys()),
            },
            "created_at": datetime.now(timezone.utc),
        })
    except Exception:
        pass

    return {"ok": True, "updated": list(update_fields.keys())}


# ============================================================
# DELETE /admin/users/{email} · 軟停用
# ============================================================
@router.delete("/users/{email}")
def deactivate_user(email: str, _admin: str = require_admin_dep()):
    """軟停用(active=false)· 保留資料 · 未來需走 PDPA delete-all 才真清

    不真刪原因:audit log / 交接 / 誤操作反悔
    真刪:用 POST /admin/users/{email}/delete-all(PDPA)
    """
    db = get_db()
    email_norm = email.strip().lower()

    if email_norm == _admin:
        raise HTTPException(400, "不能停用自己 · 防 admin lockout")

    r = db.users.update_one(
        {"email": email_norm},
        {"$set": {
            "chengfu_active": False,
            "updatedAt": datetime.now(timezone.utc),
        }},
    )
    if r.matched_count == 0:
        raise HTTPException(404, f"user {email_norm} 不存在")

    try:
        db.audit_log.insert_one({
            "action": "admin_deactivate_user",
            "user": _admin,
            "details": {"target_email": email_norm},
            "created_at": datetime.now(timezone.utc),
        })
    except Exception:
        pass

    return {"ok": True, "email": email_norm, "active": False}

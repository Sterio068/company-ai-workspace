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
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional

import bcrypt
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from .._deps import require_admin_dep, get_db

logger = logging.getLogger(__name__)


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


# vNext Phase D · 誠實揭露哪些權限已由 backend 真正擋下
# 其他 permission 目前仍是營運配置 / UI 分流資料,不可誤導 admin 以為已完整 RBAC。
ENFORCEMENT_STATUS = {
    "mode": "progressive",
    "summary": "ADMIN 與高風險資料入口已由後端強制；細部 chengfu_permissions 逐步展開。",
    "enforced_permissions": [
        "admin.dashboard",
        "admin.audit",
        "admin.pdpa",
        "accounting.view",
        "accounting.edit",
        "knowledge.manage",
        "media_crm.edit",
        "media_crm.export",
        "social.post_own",
        "site.survey",
    ],
    "advisory_permissions": [
        "tender.view",
        "tender.evaluate",
        "crm.view_own",
        "crm.view_all",
        "crm.edit_all",
        "project.create",
        "project.edit_own",
        "project.edit_all",
        "design.generate",
        "media_assets.manage",
        "press.draft",
        "social.post_all",
        "media_crm.view",
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
        "enforcement": ENFORCEMENT_STATUS,
    }


# ============================================================
# Pydantic models
# ============================================================
# 簡易 email regex · 不走 EmailStr 避免 email-validator dep
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class UserCreate(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    name: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=10, max_length=128)
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

    @field_validator("password")
    @classmethod
    def _check_strength(cls, v: str) -> str:
        # 套用統一密碼複雜度規則(create + reset 一致)
        return _validate_password_strength(v)


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    title: Optional[str] = Field(None, max_length=50)
    permissions: Optional[List[str]] = None
    role: Optional[str] = Field(None, pattern="^(USER|ADMIN)$")
    active: Optional[bool] = None


def _validate_password_strength(pw: str) -> str:
    """共用密碼複雜度檢查 · admin create + reset 都用這個

    規則(平衡安全 + 老闆好記)·:
    - 長度 ≥ 10
    - 至少含 3 類:大寫字母 / 小寫字母 / 數字 / 符號
    - 禁常見弱密碼(password / 12345678 / qwerty 等 top 12)
    - 不能重複 4 次以上同字元(aaaa / 1111)

    raise ValueError on fail · pydantic field_validator 會轉成 422
    """
    if not pw or len(pw) < 10:
        raise ValueError("密碼至少 10 字 · 防字典攻擊")
    if len(pw) > 128:
        raise ValueError("密碼不可超過 128 字")
    classes = sum([
        any(c.isupper() for c in pw),
        any(c.islower() for c in pw),
        any(c.isdigit() for c in pw),
        any(not c.isalnum() for c in pw),
    ])
    if classes < 3:
        raise ValueError("密碼需含 3 類以上(大寫 / 小寫 / 數字 / 符號)")
    common_weak = {
        "password", "password1", "12345678", "123456789", "qwerty123",
        "letmein123", "admin1234", "iloveyou1", "monkey1234",
        "dragon1234", "111111111", "abcdefgh1",
    }
    if pw.lower() in common_weak:
        raise ValueError("此為常見弱密碼 · 請改")
    # 同字元重複 ≥ 4 次(aaaa / 1111)
    for i in range(len(pw) - 3):
        if pw[i] == pw[i + 1] == pw[i + 2] == pw[i + 3]:
            raise ValueError("密碼不可同字元重複 4 次以上")
    return pw


class PasswordReset(BaseModel):
    """admin 替同仁重設密碼

    - 同仁忘記密碼 / 老闆要硬覆蓋時用
    - 後端 bcrypt re-hash · 不存明文
    - 回傳明文一次給 admin 轉達同仁(同仁登入後可自己改)
    """
    new_password: str = Field(..., min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _check_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


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


# ============================================================
# POST /admin/users/{email}/reset-password · admin 替同仁重設密碼
# ============================================================
@router.post("/users/{email}/reset-password")
def reset_user_password(
    email: str, payload: PasswordReset, _admin: str = require_admin_dep()
) -> dict:
    """admin 替同仁重設密碼

    流程:
    1. bcrypt re-hash 新密碼(LibreChat 同 10 rounds)
    2. update users.password · 檢查 matched_count 防 race
    3. 清掉所有 sessions / refreshTokens 強制踢登入(防舊 token 仍可用)
    4. audit log(只記操作 · 不記密碼)
    5. 回 ok(明文密碼留 frontend closure · 不回傳)

    安全:
    - require_admin
    - 不能改自己(走右上角頭像)
    - 新密碼 Pydantic 驗 ≥ 8 字 · 密碼明文僅 in-flight · server 不留
    """
    db = get_db()
    email_norm = email.strip().lower()

    if email_norm == _admin:
        raise HTTPException(400, "改自己密碼請走右上角頭像 → 個人設定 · 不從這個介面")

    u = db.users.find_one({"email": email_norm})
    if not u:
        raise HTTPException(404, f"user {email_norm} 不存在")

    pw_hash = bcrypt.hashpw(payload.new_password.encode("utf-8"), bcrypt.gensalt(10))
    user_id_str = str(u["_id"])
    r = db.users.update_one(
        {"_id": u["_id"]},
        {"$set": {
            "password": pw_hash,
            "updatedAt": datetime.now(timezone.utc),
        }},
    )
    if r.matched_count == 0:
        # find_one 跟 update_one 之間 user 被刪
        raise HTTPException(404, f"user {email_norm} 已不存在(并發被刪?)")

    # 強制登出所有現有 session · 雙試 ObjectId / str(LibreChat 不同版本 user 欄位型別不一)
    # 防舊 token 在 TTL 內仍可用 + C3 修
    user_id_obj = u["_id"]
    sessions_invalidated = (
        _try_delete_many(db.sessions, [{"user": user_id_str}, {"user": user_id_obj}])
    )
    refresh_invalidated = (
        _try_delete_many(db.refreshtokens, [{"userId": user_id_str}, {"userId": user_id_obj}])
    )

    # C5 · audit fail-loud:destructive admin op 的 audit 失敗 → 503
    # 稽核鏈不能斷 · 業務再成功也要回錯讓 admin 重試
    try:
        db.audit_log.insert_one({
            "action": "admin_reset_password",
            "user": _admin,
            "details": {
                "target_email": email_norm,
                "sessions_invalidated": sessions_invalidated,
                "refresh_invalidated": refresh_invalidated,
            },
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.error(f"[reset_password] audit_log INSERT failed: {e}")
        raise HTTPException(503, "稽核紀錄寫入失敗 · 操作已執行 · 請通知 IT 補登紀錄")

    return {
        "ok": True,
        "email": email_norm,
        "sessions_invalidated": sessions_invalidated,
        "refresh_invalidated": refresh_invalidated,
    }


def _try_delete_many(collection, filters: list) -> int:
    """嘗試多種 filter 都試一遍 · 用 $or 一次刪 · 取最大 deleted_count

    用途:LibreChat 不同版本 sessions.user 可能存 ObjectId 或 str
         (此處不確定型別 · 用 $or 一次刪兩種 · 不浪費 round trip)
    """
    if not filters:
        return 0
    try:
        return collection.delete_many({"$or": filters}).deleted_count
    except Exception as e:
        logger.warning(f"[cleanup] delete_many($or) failed: {e}")
        return 0


# ============================================================
# DELETE /admin/users/{email}/permanent · 硬刪除(PDPA)
# ============================================================
@router.delete("/users/{email}/permanent")
def delete_user_permanent(email: str, _admin: str = require_admin_dep()) -> dict:
    """硬刪除同仁帳號 · PDPA 個資請求 · 永久不可復原

    要求:
    - target user 必須先 deactivate(active=false)· 二段式防誤刪
    - 不能刪自己
    - 連帶清:sessions / refreshTokens / feedback
    - 對話紀錄(conversations)留存:法律抗辯 + 商業機密追溯
      若客戶要求清對話請走 PDPA 完整流程(docs/05-SECURITY.md)

    回:已刪 + 連帶清除集合計數 + 連帶清失敗的集合
    """
    db = get_db()
    email_norm = email.strip().lower()

    if email_norm == _admin:
        raise HTTPException(400, "不能刪自己 · 防 admin lockout")

    u = db.users.find_one({"email": email_norm})
    if not u:
        raise HTTPException(404, f"user {email_norm} 不存在")

    if u.get("chengfu_active") is not False:
        raise HTTPException(
            400,
            "請先 deactivate(停用)後再硬刪 · 二段式防誤操作",
        )

    user_id = u["_id"]
    user_id_str = str(user_id)

    # C6 · cleanup-first guard:任一 sessions/refreshTokens 清失敗 → 中止 · 不留 orphan token
    # 用 $or 雙型別(ObjectId / str)防 LibreChat schema 變動
    related: dict = {}
    failed: list = []
    cleanup_targets = [
        ("sessions", db.sessions, [{"user": user_id_str}, {"user": user_id}]),
        ("refreshTokens", db.refreshtokens, [{"userId": user_id_str}, {"userId": user_id}]),
        ("feedback", db.feedback, [{"user_email": email_norm}]),
    ]
    for key, coll, filters in cleanup_targets:
        try:
            related[key] = coll.delete_many({"$or": filters}).deleted_count
        except Exception as e:
            related[key] = -1
            failed.append(key)
            logger.error(f"[permanent_delete] {key} cleanup failed: {e}")

    # 任一 token 集合清失敗 → fail closed · 不留 session orphan(防離職員工 token 仍可用)
    if any(k in failed for k in ("sessions", "refreshTokens")):
        # audit 記下未刪情況 · 讓 IT 看
        try:
            db.audit_log.insert_one({
                "action": "admin_delete_user_permanent_aborted",
                "user": _admin,
                "details": {
                    "target_email": email_norm,
                    "target_user_id": user_id_str,
                    "related_cleaned": related,
                    "cleanup_failures": failed,
                    "reason": "token_cleanup_failed",
                },
                "created_at": datetime.now(timezone.utc),
            })
        except Exception as e:
            logger.error(f"[permanent_delete] audit_log abort failed: {e}")
        raise HTTPException(
            503,
            f"無法清除登入 token({', '.join(failed)})· 為防止帳號殘留可登入,已中止刪除 · 請聯絡 IT",
        )

    # C7 · CAS guard:filter 強制 chengfu_active=False · 防 admin race(B 在你刪前 reactivate)
    r = db.users.delete_one({"_id": user_id, "chengfu_active": False})
    if r.deleted_count == 0:
        # 兩種狀況:1) 並發被刪  2) 並發被 reactivate
        latest = db.users.find_one({"_id": user_id})
        if not latest:
            raise HTTPException(409, f"user {email_norm} 已被其他流程刪除")
        raise HTTPException(409, f"user {email_norm} 已被其他管理員復用 · 請重新確認後再刪")

    # C5 · audit fail-loud:destructive 操作 audit 失敗 → 503
    try:
        db.audit_log.insert_one({
            "action": "admin_delete_user_permanent",
            "user": _admin,
            "details": {
                "target_email": email_norm,
                "target_user_id": user_id_str,
                "related_cleaned": related,
                "cleanup_failures": failed,
            },
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.error(f"[permanent_delete] audit_log INSERT failed: {e}")
        raise HTTPException(503, "稽核紀錄寫入失敗 · 同仁已刪除 · 請通知 IT 補登紀錄")

    return {
        "ok": True,
        "email": email_norm,
        "deleted": True,
        "related_cleaned": related,
        "cleanup_failures": failed,
    }

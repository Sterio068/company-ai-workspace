"""
Social scheduler router · Feature #5(FEATURE-PROPOSALS v1.2)

FB / IG / LinkedIn 貼文排程 · mock 實作 · 真 API 等 developer app 審核

涵蓋 7 endpoint:
- /social/posts GET · POST · PUT · DELETE
- /social/posts/{id}/publish-now POST(繞過排程立刻發)
- /admin/social/run-queue POST · internal-token · cron 每 5 分鐘掃

Collection · scheduled_posts:
{
  _id, author: email, platform: fb|ig|linkedin,
  content: str, image_url?, schedule_at: UTC datetime,
  status: queued|publishing|published|failed|cancelled,
  attempts: 0, last_error?,
  platform_post_id?, platform_url?,
  created_at, updated_at, dispatched_at?, published_at?
}
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from bson import ObjectId
from bson.errors import InvalidId

from ._deps import require_admin_dep, require_user_dep
from services.social_providers import PublishError, publish


router = APIRouter(tags=["social"])
logger = logging.getLogger("chengfu")

MAX_RETRIES = 3
PLATFORMS = ("facebook", "instagram", "linkedin")

# R22#1 · publishing lease 上限 · 超過視為孤兒可重 dispatch
PUBLISHING_LEASE_MINUTES = 5

# R22#3 · timezone 處理 · naive 視為 Asia/Taipei
TAIPEI_TZ = timezone(timedelta(hours=8))


def _to_utc(dt: datetime) -> datetime:
    """R22#3 · 接收 datetime · 統一轉 aware UTC
    - aware datetime → astimezone UTC
    - naive datetime → 視為台灣時間 → 換成 UTC

    技術債#1(2026-04-23)· 整個系統改用 aware UTC · 配合 datetime.now(timezone.utc)
    Mongo / mongomock 都支援 aware datetime · 比舊 naive 更安全(防 R22 跨時區比較炸)
    """
    if dt.tzinfo is None:
        # 視為台灣時間
        return dt.replace(tzinfo=TAIPEI_TZ).astimezone(timezone.utc)
    return dt.astimezone(timezone.utc)


def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """讀 DB 出來的 naive datetime(舊資料)當 UTC · 回 aware
    新資料寫入時就是 aware · 不需 patch · 只 patch 舊資料"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _oid(post_id: str) -> ObjectId:
    try:
        return ObjectId(post_id)
    except (InvalidId, TypeError):
        raise HTTPException(400, "post_id 格式錯誤")


class ScheduledPost(BaseModel):
    platform: Literal["facebook", "instagram", "linkedin"]
    content: str = Field(min_length=1, max_length=3000)
    schedule_at: datetime  # 接受 ISO · naive 視為 Asia/Taipei · 內部存 UTC
    image_url: Optional[str] = None


class ScheduledPostPatch(BaseModel):
    content: Optional[str] = Field(default=None, min_length=1, max_length=3000)
    schedule_at: Optional[datetime] = None
    image_url: Optional[str] = None


# ============================================================
# CRUD
# ============================================================
@router.post("/social/posts")
def create_post(p: ScheduledPost, email: str = require_user_dep()):
    from main import db

    if p.platform == "instagram" and not p.image_url:
        raise HTTPException(400, "Instagram 需要 image_url(IG 硬規定)")
    # R22#3 · timezone normalize · 不論前端送 naive(視為 TW)或 aware · 統一轉 UTC naive
    schedule_utc = _to_utc(p.schedule_at)
    if schedule_utc < datetime.now(timezone.utc) - timedelta(minutes=5):
        raise HTTPException(400, "schedule_at 不能在過去")

    doc = {
        "author": email,
        "platform": p.platform,
        "content": p.content,
        "image_url": p.image_url,
        "schedule_at": schedule_utc,
        "status": "queued",
        "attempts": 0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    r = db.scheduled_posts.insert_one(doc)
    return {"post_id": str(r.inserted_id), "status": "queued"}


@router.get("/social/posts")
def list_posts(
    status: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
    email: str = require_user_dep(),
):
    """同事只看自己的 · admin 看全部(以後加 /admin/social/posts)"""
    from main import db, serialize
    q = {"author": email}
    if status:
        q["status"] = status
    if platform:
        q["platform"] = platform
    cursor = db.scheduled_posts.find(q).sort("schedule_at", -1).skip(skip).limit(limit)
    items = serialize(list(cursor))
    total = db.scheduled_posts.count_documents(q)
    return {"items": items, "total": total, "skip": skip, "limit": limit,
            "has_more": (skip + len(items)) < total}


@router.get("/social/posts/{post_id}")
def get_post(post_id: str, email: str = require_user_dep()):
    from main import db, serialize
    doc = db.scheduled_posts.find_one({"_id": _oid(post_id)})
    if not doc:
        raise HTTPException(404, "貼文不存在")
    if doc["author"] != email:
        raise HTTPException(403, "只能看自己的貼文")
    return serialize(doc)


@router.put("/social/posts/{post_id}")
def update_post(post_id: str, p: ScheduledPostPatch, email: str = require_user_dep()):
    """只能改 queued 狀態 · 已 publish 過不能改

    R22#2 · CAS update · 用 _id+author+status:queued 條件 · 防 dispatcher 中間 claim
    """
    from main import db
    oid = _oid(post_id)
    updates = {k: v for k, v in p.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        raise HTTPException(400, "沒有可更新欄位")
    if "schedule_at" in updates:
        schedule_utc = _to_utc(updates["schedule_at"])
        if schedule_utc < datetime.now(timezone.utc):
            raise HTTPException(400, "schedule_at 不能在過去")
        updates["schedule_at"] = schedule_utc
    updates["updated_at"] = datetime.now(timezone.utc)

    # CAS · 必須 status=queued + author 是 self
    r = db.scheduled_posts.update_one(
        {"_id": oid, "author": email, "status": "queued"},
        {"$set": updates},
    )
    if r.matched_count == 0:
        # 排錯 · 是不存在 / 非 owner / 已被 dispatcher claim?
        existing = db.scheduled_posts.find_one({"_id": oid})
        if not existing:
            raise HTTPException(404, "貼文不存在")
        if existing.get("author") != email:
            raise HTTPException(403, "只能改自己的貼文")
        raise HTTPException(409, f"狀態 {existing['status']} 不能改 · dispatcher 已開始或已完成")
    return {"updated": True}


@router.delete("/social/posts/{post_id}")
def cancel_post(post_id: str, email: str = require_user_dep()):
    """軟刪 · status=cancelled · 已 publish 或 publishing 中不給刪

    R22#2 · CAS · 防 dispatcher 中間 publish 後使用者來不及看到 status 變
    """
    from main import db
    oid = _oid(post_id)
    # CAS · 只准 queued / failed 狀態 cancel
    r = db.scheduled_posts.update_one(
        {"_id": oid, "author": email, "status": {"$in": ["queued", "failed"]}},
        {"$set": {"status": "cancelled", "updated_at": datetime.now(timezone.utc)}},
    )
    if r.matched_count == 0:
        existing = db.scheduled_posts.find_one({"_id": oid})
        if not existing:
            raise HTTPException(404, "貼文不存在")
        if existing.get("author") != email:
            raise HTTPException(403, "只能改自己的貼文")
        raise HTTPException(409, f"狀態 {existing['status']} 不能 cancel · 已發或處理中")
    return {"cancelled": True}


@router.post("/social/posts/{post_id}/publish-now")
def publish_now(post_id: str, email: str = require_user_dep()):
    """繞過排程立刻發 · 內部呼 provider"""
    from main import db
    oid = _oid(post_id)
    existing = db.scheduled_posts.find_one({"_id": oid})
    if not existing:
        raise HTTPException(404, "貼文不存在")
    if existing["author"] != email:
        raise HTTPException(403, "只能發自己的貼文")
    if existing["status"] not in ("queued", "failed"):
        raise HTTPException(409, f"狀態 {existing['status']} 不能立刻發")

    return _dispatch_one(oid, existing)


# ============================================================
# Dispatcher(cron 呼 admin endpoint · 掃 queue)
# ============================================================
def _dispatch_one(oid: ObjectId, doc: dict) -> dict:
    """把一筆 post 送去 provider · 更新 status · 失敗重排

    R22#1 · publishing_until lease(5 分)· 超過視為孤兒 · 下次 run_queue 重 claim
    R22#2 · CAS atomic claim · 防 race
    """
    from main import db

    # R22#1 · Atomic claim · 加 publishing_until lease
    now = datetime.now(timezone.utc)
    lease_until = now + timedelta(minutes=PUBLISHING_LEASE_MINUTES)
    r = db.scheduled_posts.update_one(
        {
            "_id": oid,
            "$or": [
                {"status": {"$in": ["queued", "failed"]}},
                # R22#1 · 也搶過期 publishing(孤兒)
                {"status": "publishing", "publishing_until": {"$lt": now}},
            ],
        },
        {"$set": {
            "status": "publishing",
            "dispatched_at": now,
            "publishing_until": lease_until,
            "updated_at": now,
        }},
    )
    if r.modified_count == 0:
        return {"skipped": "already dispatched by another worker (or still in lease)"}

    try:
        result = publish(doc["platform"], doc["content"], doc.get("image_url"))
        db.scheduled_posts.update_one(
            {"_id": oid},
            {"$set": {
                "status": "published",
                "platform_post_id": result["post_id"],
                "platform_url": result["url"],
                "published_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "last_error": None,
            },
             "$unset": {"publishing_until": ""}},  # R22#1 · 清 lease
        )
        return {"published": True, **result}
    except Exception as e:
        # R22#1 · 不只 PublishError · 任何 exception(network / provider SDK bug)都 retry
        is_known = isinstance(e, PublishError)
        attempts = doc.get("attempts", 0) + 1
        new_status = "failed" if attempts >= MAX_RETRIES else "queued"
        # Retry 間隔 · exp backoff 寫進 schedule_at
        if new_status == "queued":
            next_try = datetime.now(timezone.utc) + timedelta(minutes=2 ** attempts)
        else:
            next_try = doc["schedule_at"]
        err_msg = ("PublishError: " if is_known else "Exception: ") + str(e)[:280]
        db.scheduled_posts.update_one(
            {"_id": oid},
            {"$set": {
                "status": new_status,
                "attempts": attempts,
                "last_error": err_msg,
                "schedule_at": next_try,
                "updated_at": datetime.now(timezone.utc),
            },
             "$unset": {"publishing_until": ""}},  # R22#1 · 清 lease
        )
        # final fail 通知 admin(audit log)
        if new_status == "failed":
            try:
                db.audit_log.insert_one({
                    "action": "social_publish_fail",
                    "user": doc["author"],
                    "resource": str(oid),
                    "details": {"platform": doc["platform"], "error": str(e)[:300],
                                "attempts": attempts},
                    "created_at": datetime.now(timezone.utc),
                })
            except Exception:
                pass
        return {"published": False, "attempts": attempts, "status": new_status,
                "error": str(e)[:300]}


@router.post("/admin/social/run-queue")
def run_queue(
    x_internal_token: Optional[str] = Header(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """cron 每 5 分鐘打 · 撈 schedule_at <= now 的 queued/failed · 逐筆 dispatch

    走 internal-token · 不走 admin cookie(cron 沒登入)
    """
    import os, hmac
    expected = os.getenv("ECC_INTERNAL_TOKEN", "").strip()
    provided = (x_internal_token or "").strip()
    if not expected or not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(403, "internal token invalid")

    from main import db
    now = datetime.now(timezone.utc)
    # R22#1 · 也撈 publishing 過期的孤兒(container kill / 真 timeout)
    to_dispatch = list(db.scheduled_posts.find(
        {"$or": [
            {"status": {"$in": ["queued", "failed"]},
             "schedule_at": {"$lte": now},
             "attempts": {"$lt": MAX_RETRIES}},
            # publishing 但 lease 過期 = 孤兒
            {"status": "publishing",
             "publishing_until": {"$lt": now}},
        ]},
        sort=[("schedule_at", 1)],
        limit=limit,
    ))

    results = []
    for doc in to_dispatch:
        r = _dispatch_one(doc["_id"], doc)
        results.append({"post_id": str(doc["_id"]), **r})

    return {"dispatched": len(results), "results": results}

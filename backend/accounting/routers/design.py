"""
Design router · Fal.ai Recraft v3 生圖

ROADMAP §11.1 B-5 · 從 main.py 抽出
- POST /design/recraft · async · 12s polling · 三態 done/pending/rejected
- GET /design/recraft/status/{job_id} · pending 後續查詢
- GET /design/history · 給 dropdown 重生用
- _log_design_job · prompt SHA256 + preview · ROADMAP §11.11 PDPA
v1.2 §11.1 B-1.5 · 改用 routers/_deps.py 共用 helper
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import os
import asyncio
import logging
import hashlib
import httpx

from ._deps import get_db, require_user_dep


router = APIRouter(prefix="/design", tags=["design"])
logger = logging.getLogger("chengfu")


FAL_QUEUE_URL = "https://queue.fal.run/fal-ai/recraft-v3"
def _fal_key() -> str:
    """每次讀 env · test 用 monkeypatch.setenv 可控制 · production 啟動後固定"""
    return os.getenv("FAL_API_KEY", "").strip()
FAL_POLL_MAX_SECONDS = int(os.getenv("FAL_POLL_MAX_SECONDS", "12"))
FAL_POLL_INTERVAL = float(os.getenv("FAL_POLL_INTERVAL", "1.0"))


class RecraftRequest(BaseModel):
    project_id: Optional[str] = None
    prompt: str = Field(min_length=4, max_length=2000)
    image_size: Literal["square_hd", "portrait_16_9", "landscape_16_9"] = "square_hd"
    style: str = "realistic_image"
    regenerate_of: Optional[str] = None


def _log_design_job(req_id: str, email: Optional[str], req: RecraftRequest,
                    status: str, n_images: int = 0):
    """ROADMAP §11.11 · prompt SHA256 redact · 不留客戶名/機敏 raw"""
    from main import db
    full_prompt = req.prompt or ""
    prompt_hash = hashlib.sha256(full_prompt.encode("utf-8")).hexdigest()[:16]
    prompt_preview = full_prompt[:50] + ("…" if len(full_prompt) > 50 else "")
    try:
        db.design_jobs.insert_one({
            "request_id": req_id,
            "user": email,
            "project_id": req.project_id,
            "prompt_hash": prompt_hash,
            "prompt_preview": prompt_preview,
            "prompt_len": len(full_prompt),
            "image_size": req.image_size,
            "style": req.style,
            "regenerate_of": req.regenerate_of,
            "status": status,
            "n_images": n_images,
            "created_at": datetime.utcnow(),
        })
    except Exception as e:
        logger.warning("[design] log fail: %s", e)


@router.post("/recraft")
async def design_recraft(req: RecraftRequest, request: Request,
                         email: str = require_user_dep()):
    """生圖主端點 · Q2 決議每次 3 張 · 三態 done/pending/rejected
    rate limit 由 main.py app 級別 limiter 套用(SlowAPIMiddleware)
    Codex R6#3 · 必須登入 · 防匿名爆 Fal 預算
    v1.2 §11.1 B-1.5 · 用 require_user_dep · email 由 dep 保證 non-None
    """
    db = get_db()

    fal_key = _fal_key()
    if not fal_key:
        raise HTTPException(503, detail={
            "friendly_message": "設計助手尚未啟用 · 請管理員設定 FAL_API_KEY",
            "status": "unconfigured",
        })

    headers = {"Authorization": f"Key {fal_key}", "Content-Type": "application/json"}
    payload = {
        "prompt": req.prompt,
        "image_size": req.image_size,
        "style": req.style,
        "num_images": 3,
    }
    if req.regenerate_of:
        prev = db.design_jobs.find_one(
            {"request_id": req.regenerate_of},
            {"image_size": 1, "style": 1},
        )
        if prev:
            payload["prompt"] = (
                f"{req.prompt}\n[Variation of previous concept · "
                f"keep brand spirit but try a different composition · seed change]"
            )
            if req.image_size == "square_hd" and prev.get("image_size"):
                payload["image_size"] = prev["image_size"]

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            q = await client.post(FAL_QUEUE_URL, headers=headers, json=payload)
            q.raise_for_status()
            req_id = q.json().get("request_id")
            if not req_id:
                _log_design_job("(unknown)", email, req, "no_request_id")
                raise HTTPException(502, detail={
                    "friendly_message": "設計服務無回應 · 請稍後重試",
                    "status": "service_error",
                })
        except httpx.HTTPStatusError as e:
            code = e.response.status_code if e.response is not None else 0
            if code in (400, 422):
                _log_design_job("(moderation)", email, req, "rejected")
                return {"status": "rejected",
                        "friendly_message": "描述太像真人、官方標誌或敏感文字 · 請改成抽象視覺描述"}
            if code == 401:
                logger.error("[design] FAL_API_KEY 無效")
                raise HTTPException(503, detail={
                    "friendly_message": "設計助手金鑰失效 · 請管理員檢查",
                    "status": "auth_error",
                })
            _log_design_job("(http_error)", email, req, f"http_{code}")
            raise HTTPException(502, detail={
                "friendly_message": "設計服務忙碌中 · 請稍後重試",
                "status": "service_error",
            })
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError):
            _log_design_job("(timeout)", email, req, "connect_timeout")
            raise HTTPException(502, detail={
                "friendly_message": "設計服務連線逾時 · 請稍後重試",
                "status": "timeout",
            })

        # Poll 結果
        status_url = f"{FAL_QUEUE_URL}/requests/{req_id}/status"
        result_url = f"{FAL_QUEUE_URL}/requests/{req_id}"
        loops = max(1, int(FAL_POLL_MAX_SECONDS / FAL_POLL_INTERVAL))
        for _ in range(loops):
            try:
                s = await client.get(status_url, headers=headers)
                if s.status_code == 200 and s.json().get("status") == "COMPLETED":
                    r = await client.get(result_url, headers=headers)
                    images = r.json().get("images", []) if r.status_code == 200 else []
                    _log_design_job(req_id, email, req, "done", n_images=len(images))
                    return {"job_id": req_id, "status": "done", "images": images, "friendly_message": None}
            except (httpx.TimeoutException, httpx.ConnectError):
                pass
            await asyncio.sleep(FAL_POLL_INTERVAL)

        _log_design_job(req_id, email, req, "pending")
        return {"job_id": req_id, "status": "pending",
                "friendly_message": "生圖中(Fal 目前繁忙)· 可關掉視窗,稍後到「歷史」查看"}


@router.get("/recraft/status/{job_id}")
async def design_recraft_status(job_id: str):
    """Pending 後續查詢 · 查到 done 時 update DB · ROADMAP R5#5"""
    db = get_db()
    fal_key = _fal_key()
    if not fal_key:
        raise HTTPException(503, "Fal.ai 未設定")
    headers = {"Authorization": f"Key {fal_key}"}
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            s = await client.get(f"{FAL_QUEUE_URL}/requests/{job_id}/status", headers=headers)
            if s.status_code == 404:
                raise HTTPException(404, "找不到此生圖任務")
            if s.status_code != 200:
                raise HTTPException(502, "Fal 查詢失敗")
            st = s.json().get("status", "UNKNOWN")
            if st == "COMPLETED":
                r = await client.get(f"{FAL_QUEUE_URL}/requests/{job_id}", headers=headers)
                images = r.json().get("images", []) if r.status_code == 200 else []
                try:
                    db.design_jobs.update_one(
                        {"request_id": job_id},
                        {"$set": {
                            "status": "done", "n_images": len(images),
                            "images": images, "completed_at": datetime.utcnow(),
                        }},
                    )
                except Exception as e:
                    logger.warning("[design] status update DB fail rid=%s · %s", job_id, e)
                return {"job_id": job_id, "status": "done", "images": images}
            return {"job_id": job_id, "status": "pending",
                    "friendly_message": "仍在生成中 · 再等幾秒"}
        except httpx.TimeoutException:
            raise HTTPException(502, "查詢逾時")


@router.get("/history")
def design_history(request: Request, limit: int = 20,
                   email: str = require_user_dep()):
    """設計助手歷史 · 給 dropdown 重生用 · 含舊 doc backfill
    Codex R6#3 · 必須登入 · 防匿名拿全體 history(洩客戶名 / 案件)
    v1.2 §11.1 B-1.5 · email dep 保證 non-None
    """
    db = get_db()
    # R6#3 · 只回自己的 history(admin 看別人改走 admin endpoint · v1.2 加)
    q = {"user": email}
    docs = list(db.design_jobs.find(
        q,
        {"_id": 0, "request_id": 1, "prompt": 1, "prompt_preview": 1, "prompt_hash": 1,
         "prompt_len": 1, "status": 1, "image_size": 1, "style": 1,
         "n_images": 1, "images": 1, "created_at": 1},
    ).sort("created_at", -1).limit(min(100, max(1, limit))))
    for d in docs:
        if isinstance(d.get("created_at"), datetime):
            d["created_at"] = d["created_at"].isoformat()
        if d.get("prompt") and not d.get("prompt_hash"):
            old_prompt = d["prompt"] or ""
            d["prompt_hash"] = hashlib.sha256(old_prompt.encode()).hexdigest()[:16]
            d["prompt_preview"] = old_prompt[:50] + ("…" if len(old_prompt) > 50 else "")
            d["prompt_len"] = len(old_prompt)
            try:
                db.design_jobs.update_one(
                    {"request_id": d["request_id"]},
                    {"$set": {
                        "prompt_hash": d["prompt_hash"],
                        "prompt_preview": d["prompt_preview"],
                        "prompt_len": d["prompt_len"],
                    }, "$unset": {"prompt": ""}},
                )
            except Exception as e:
                logger.warning("[design] backfill fail rid=%s · %s", d.get("request_id"), e)
        d.pop("prompt", None)
    return {"history": docs, "count": len(docs)}

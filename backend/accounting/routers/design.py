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
from datetime import datetime, timezone
import os
import asyncio
import logging
import hashlib
import httpx

from ._deps import get_db, require_user_dep


router = APIRouter(prefix="/design", tags=["design"])
logger = logging.getLogger("chengfu")


FAL_QUEUE_URL = "https://queue.fal.run/fal-ai/recraft-v3"
OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"
OPENAI_IMAGE_MODEL = "gpt-image-2"  # 2026-04-21 release · 取代 gpt-image-1


def _mongo_setting(name: str) -> Optional[str]:
    """讀 Mongo system_settings · 避免每 fn 重複同樣 lazy import"""
    try:
        from main import db
        doc = db.system_settings.find_one({"name": name})
        if doc and doc.get("value"):
            return doc["value"].strip()
    except Exception:
        pass
    return None


def _fal_key() -> str:
    """Fal.ai API Key · 先 Mongo · fallback env"""
    v = _mongo_setting("FAL_API_KEY")
    return v or os.getenv("FAL_API_KEY", "").strip()


def _openai_key() -> str:
    """OpenAI API Key(給 image generation 用 · 不影響 LibreChat STT)
    先 Mongo · fallback env · admin UI 可改 · 跟 FAL 同 pattern"""
    v = _mongo_setting("OPENAI_API_KEY")
    return v or os.getenv("OPENAI_API_KEY", "").strip()


def _image_provider() -> str:
    """選哪個 provider · 'fal' (Recraft v3) 或 'openai' (gpt-image-2)
    · Mongo `IMAGE_PROVIDER` · fallback env · 預設 fal(backwards-compat)"""
    v = _mongo_setting("IMAGE_PROVIDER")
    if v and v.lower() in ("fal", "openai"):
        return v.lower()
    env_v = os.getenv("IMAGE_PROVIDER", "fal").strip().lower()
    return env_v if env_v in ("fal", "openai") else "fal"


FAL_POLL_MAX_SECONDS = int(os.getenv("FAL_POLL_MAX_SECONDS", "12"))
FAL_POLL_INTERVAL = float(os.getenv("FAL_POLL_INTERVAL", "1.0"))


# OpenAI gpt-image-2 size map · 對應 Fal image_size option(UI 語意一致)
_OPENAI_SIZE_MAP = {
    "square_hd": "1024x1024",
    "portrait_16_9": "1024x1792",  # portrait 大圖
    "landscape_16_9": "1792x1024",  # landscape 大圖
}


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
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.warning("[design] log fail: %s", e)


async def _openai_generate(req: "RecraftRequest", email: str) -> dict:
    """OpenAI gpt-image-2 · /v1/images/generations 同步回(不 queue)

    OpenAI 端 n=3 一次 · 不需 polling · 5-30 秒內回
    `b64_json` 格式 · 前端要轉 data URL(或 accounting 存本機 / S3)

    回 contract 跟 Fal 一致:done / rejected / service_error
    regenerate_of 把 prev prompt 連起(跟 Fal 同策略)
    """
    openai_key = _openai_key()
    if not openai_key:
        raise HTTPException(503, detail={
            "friendly_message": "OpenAI 生圖未設定 · 請管理員在「使用教學 → API Key 管理」設 OPENAI_API_KEY",
            "status": "unconfigured",
        })

    db = get_db()
    full_prompt = req.prompt
    if req.regenerate_of:
        prev = db.design_jobs.find_one(
            {"request_id": req.regenerate_of},
            {"image_size": 1, "style": 1},
        )
        if prev:
            full_prompt = (
                f"{req.prompt}\n[Variation of previous concept · "
                f"keep brand spirit but try a different composition]"
            )

    payload = {
        "model": OPENAI_IMAGE_MODEL,
        "prompt": full_prompt,
        "n": 3,  # Q7 承富一次 3 張
        "size": _OPENAI_SIZE_MAP.get(req.image_size, "1024x1024"),
        "quality": "high",  # standard / high / auto · 承富選高品質
        # response_format 在 gpt-image-2 預設 b64_json · 不用顯設
    }
    headers = {
        "Authorization": f"Bearer {openai_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=90.0) as client:  # OpenAI 生圖較慢 · 給 90s
        try:
            r = await client.post(OPENAI_IMAGES_URL, headers=headers, json=payload)
            if r.status_code == 401:
                logger.error("[design] OPENAI_API_KEY 無效")
                raise HTTPException(503, detail={
                    "friendly_message": "OpenAI 金鑰失效 · 請管理員檢查",
                    "status": "auth_error",
                })
            if r.status_code in (400, 422):
                # moderation / input 錯 · 視同 Fal rejected
                logger.info("[design] OpenAI 拒絕 · %s", r.text[:200])
                _log_design_job("(openai_moderation)", email, req, "rejected")
                return {"status": "rejected",
                        "friendly_message": "描述太像真人、官方標誌或敏感文字 · 請改成抽象視覺描述"}
            if r.status_code != 200:
                _log_design_job("(openai_http)", email, req, f"http_{r.status_code}")
                raise HTTPException(502, detail={
                    "friendly_message": f"OpenAI 生圖失敗(HTTP {r.status_code})· 請稍後重試",
                    "status": "service_error",
                })
            data = r.json()
            images_raw = data.get("data", [])
            # OpenAI 回 b64 · 轉成 data URL 給前端直接 <img src>
            images = []
            for img in images_raw:
                if img.get("b64_json"):
                    images.append({
                        "url": f"data:image/png;base64,{img['b64_json']}",
                        "b64": True,
                    })
                elif img.get("url"):
                    images.append({"url": img["url"], "b64": False})
            # OpenAI 無 request_id · 我們自產一個 placeholder(跟 Fal 欄位對齊)
            req_id = f"openai-{data.get('created', int(datetime.now(timezone.utc).timestamp()))}"
            _log_design_job(req_id, email, req, "done", n_images=len(images))
            return {
                "job_id": req_id,
                "status": "done",
                "images": images,
                "provider": "openai",
                "friendly_message": None,
            }
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError):
            _log_design_job("(openai_timeout)", email, req, "connect_timeout")
            raise HTTPException(502, detail={
                "friendly_message": "OpenAI 連線逾時 · 請稍後重試",
                "status": "timeout",
            })


@router.post("/recraft")
async def design_recraft(req: RecraftRequest, request: Request,
                         email: str = require_user_dep()):
    """生圖主端點 · Q2 決議每次 3 張 · 三態 done/pending/rejected
    rate limit 由 main.py app 級別 limiter 套用(SlowAPIMiddleware)
    Codex R6#3 · 必須登入 · 防匿名爆 Fal 預算
    v1.2 §11.1 B-1.5 · 用 require_user_dep · email 由 dep 保證 non-None
    v1.2 多 provider · IMAGE_PROVIDER=fal(Recraft v3)或 openai(gpt-image-2)
    """
    # 選 provider · OpenAI 走同步 · Fal 走 queue polling
    provider = _image_provider()
    if provider == "openai":
        return await _openai_generate(req, email)

    # ---- Fal.ai Recraft v3(原路徑)----
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
                    return {"job_id": req_id, "status": "done", "images": images, "provider": "fal", "friendly_message": None}
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
                            "images": images, "completed_at": datetime.now(timezone.utc),
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

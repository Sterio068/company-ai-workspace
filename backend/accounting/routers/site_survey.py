"""
Site Survey router · Feature #7(FEATURE-PROPOSALS v1.2)

活動 PM iPhone 現場拍照 + GPS + AI 結構化
- 上傳 images[] + audio_note? + gps_json
- Claude Haiku Vision 每張產 caption + 結構化(場地 / 入口 / 洗手間)
- 結果存 project.handoff.asset_refs

Collection · site_surveys:
{
  _id, owner, project_id?,
  location: {gps: {lat,lng,accuracy_m}, address_hint?},
  media: [{media_id, mime, size_bytes, caption_ai, tags}],
  structured: {venue:{width_m?,area_m2?}, entrances, toilets_count, issues},
  status: uploading|processing|done|failed,
  created_at, updated_at
}

限:
- 單張照片 5MB · 5 張上限 per survey · audio 選配(暫不支援)
- require_user_dep(現場 PM 非 admin)
"""
import base64
import logging
import os
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from bson import ObjectId
from bson.errors import InvalidId

from ._deps import require_user_dep


router = APIRouter(tags=["site-survey"])
logger = logging.getLogger("chengfu")

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES_PER_SURVEY = 5
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


def _oid(survey_id: str) -> ObjectId:
    try:
        return ObjectId(survey_id)
    except (InvalidId, TypeError):
        raise HTTPException(400, "survey_id 格式錯誤")


def _anthropic_key() -> str:
    return os.getenv("ANTHROPIC_API_KEY", "").strip()


def _process_survey(survey_id_str: str, image_b64_list: list, mime_list: list):
    """BackgroundTask · 跑 Claude Haiku Vision 逐張產 caption + 結構化整體

    不 raise · 失敗寫 status=failed
    """
    from main import db
    try:
        import anthropic
    except ImportError:
        db.site_surveys.update_one(
            {"_id": ObjectId(survey_id_str)},
            {"$set": {"status": "failed", "error": "Anthropic SDK 未裝",
                      "updated_at": datetime.utcnow()}},
        )
        return

    try:
        client = anthropic.Anthropic(api_key=_anthropic_key())
        captions = []

        # Step 1 · 逐張 caption(並行可以但每張 $0.003 便宜 · 先順序)
        for idx, (b64, mime) in enumerate(zip(image_b64_list, mime_list)):
            try:
                resp = client.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=500,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {
                                "type": "base64", "media_type": mime, "data": b64,
                            }},
                            {"type": "text", "text":
                                "這是活動場勘照片 · 繁中描述 200 字內:場地類型 / 空間大小感 / 入口 / 特殊物件 / 可能的問題"},
                        ],
                    }],
                )
                cap = resp.content[0].text
                captions.append({"index": idx, "caption": cap})
            except Exception as e:
                logger.warning("[site-survey] caption idx=%d 失敗 · %s", idx, e)
                captions.append({"index": idx, "caption": "(AI 無法辨識)", "error": str(e)[:100]})

        # Step 2 · 彙整結構化(把所有 caption 丟給 Haiku JSON output)
        all_caps = "\n\n".join([f"[照片 {c['index']+1}] {c['caption']}" for c in captions])
        try:
            summary_resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=800,
                messages=[{
                    "role": "user",
                    "content": f"""根據以下場勘照片描述 · 彙整成結構化 JSON · 只回 JSON:

{{
  "venue": {{"type": "室內/室外", "size_estimate": "約 X 坪"}},
  "entrances": ["主入口描述"],
  "toilets_count": 數字或 null,
  "power_outlets": "多/少/未見",
  "parking": "有/無/未見",
  "issues": ["可能問題 1", "問題 2"]
}}

場勘描述:
{all_caps[:6000]}"""
                }],
            )
            import re, json
            raw = summary_resp.content[0].text
            m = re.search(r"\{[\s\S]*\}", raw)
            structured = json.loads(m.group(0)) if m else {}
        except Exception as e:
            logger.warning("[site-survey] 彙整失敗 · %s", e)
            structured = {"issues": [f"AI 彙整失敗: {str(e)[:100]}"]}

        db.site_surveys.update_one(
            {"_id": ObjectId(survey_id_str)},
            {"$set": {
                "media": [
                    {
                        "index": c["index"],
                        "mime": mime_list[c["index"]] if c["index"] < len(mime_list) else None,
                        "caption_ai": c["caption"],
                        "error": c.get("error"),
                    } for c in captions
                ],
                "structured": structured,
                "status": "done",
                "updated_at": datetime.utcnow(),
            }},
        )
        logger.info("[site-survey] done id=%s · %d 張 · %d issues",
                    survey_id_str, len(captions),
                    len(structured.get("issues", [])))
    except Exception as e:
        logger.error("[site-survey] 非預期失敗 id=%s · %s", survey_id_str, e)
        db.site_surveys.update_one(
            {"_id": ObjectId(survey_id_str)},
            {"$set": {"status": "failed", "error": str(e)[:200],
                      "updated_at": datetime.utcnow()}},
        )


@router.post("/site-survey")
async def create_survey(
    background: BackgroundTasks,
    images: List[UploadFile] = File(...),
    gps_lat: Optional[float] = Form(default=None),
    gps_lng: Optional[float] = Form(default=None),
    gps_accuracy: Optional[float] = Form(default=None),
    address_hint: Optional[str] = Form(default=None),
    project_id: Optional[str] = Form(default=None),
    email: str = require_user_dep(),
):
    """上傳場勘 · 回 survey_id · 前端 polling /site-survey/{id}"""
    from main import db

    if not images:
        raise HTTPException(400, "至少上傳 1 張照片")
    if len(images) > MAX_IMAGES_PER_SURVEY:
        raise HTTPException(400, f"最多 {MAX_IMAGES_PER_SURVEY} 張 · 目前 {len(images)}")

    # 驗 mime + size · 讀進 memory(小檔案 · 5 張 × 5MB = 25MB OK)
    b64_list = []
    mime_list = []
    total_bytes = 0
    for img in images:
        mime = (img.content_type or "").lower()
        # HEIC/HEIF 常被 iPhone 送但 Haiku Vision 不支援 · 只接受 JPEG/PNG/WebP
        if mime not in ("image/jpeg", "image/png", "image/webp"):
            raise HTTPException(400, f"照片格式不支援:{mime} · 請用 JPEG/PNG/WebP")
        content = await img.read()
        size = len(content)
        if size > MAX_IMAGE_BYTES:
            raise HTTPException(413, f"照片 > {MAX_IMAGE_BYTES // 1024 // 1024}MB · 請先 resize")
        if size < 1024:
            raise HTTPException(400, "照片太小 · 可能空檔")
        total_bytes += size
        b64_list.append(base64.b64encode(content).decode("ascii"))
        mime_list.append(mime)

    location = {}
    if gps_lat is not None and gps_lng is not None:
        location["gps"] = {"lat": gps_lat, "lng": gps_lng,
                           "accuracy_m": gps_accuracy}
    if address_hint:
        location["address_hint"] = address_hint

    doc = {
        "owner": email,
        "project_id": project_id,
        "location": location,
        "media": [],  # _process_survey 填
        "structured": {},
        "image_count": len(images),
        "total_bytes": total_bytes,
        "status": "processing",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    r = db.site_surveys.insert_one(doc)
    sid = str(r.inserted_id)

    background.add_task(_process_survey, sid, b64_list, mime_list)

    return {"survey_id": sid, "status": "processing",
            "image_count": len(images),
            "total_mb": round(total_bytes / 1024 / 1024, 2)}


@router.get("/site-survey/{survey_id}")
def get_survey(survey_id: str, email: str = require_user_dep()):
    from main import db
    doc = db.site_surveys.find_one({"_id": _oid(survey_id)})
    if not doc:
        raise HTTPException(404, "場勘紀錄不存在")
    if doc.get("owner") != email:
        raise HTTPException(403, "只能看自己的場勘")
    return {
        "survey_id": survey_id,
        "status": doc.get("status"),
        "location": doc.get("location", {}),
        "media": doc.get("media", []),
        "structured": doc.get("structured", {}),
        "image_count": doc.get("image_count"),
        "error": doc.get("error"),
        "project_id": doc.get("project_id"),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
    }


@router.get("/site-survey")
def list_surveys(
    project_id: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    email: str = require_user_dep(),
):
    from main import db
    q = {"owner": email}
    if project_id:
        q["project_id"] = project_id
    items = []
    for doc in db.site_surveys.find(q).sort("created_at", -1).limit(limit):
        items.append({
            "survey_id": str(doc["_id"]),
            "status": doc.get("status"),
            "project_id": doc.get("project_id"),
            "image_count": doc.get("image_count", 0),
            "venue_type": (doc.get("structured") or {}).get("venue", {}).get("type"),
            "issues_count": len((doc.get("structured") or {}).get("issues", [])),
            "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        })
    return {"items": items, "count": len(items)}


@router.post("/site-survey/{survey_id}/push-to-handoff")
def push_to_handoff(survey_id: str, email: str = require_user_dep()):
    """場勘結果推進 project.handoff"""
    from main import db
    doc = db.site_surveys.find_one({"_id": _oid(survey_id)})
    if not doc:
        raise HTTPException(404, "場勘不存在")
    if doc.get("owner") != email:
        raise HTTPException(403, "只能推自己的場勘")
    if doc.get("status") != "done":
        raise HTTPException(400, "場勘還沒處理完 · 等 status=done")
    project_id = doc.get("project_id")
    if not project_id:
        raise HTTPException(400, "此場勘沒綁 project_id")

    s = doc.get("structured", {})
    issues = s.get("issues", [])
    venue = s.get("venue", {})
    asset_refs = [
        {"type": "note",
         "label": "場勘彙整",
         "ref": f"{venue.get('type','')} · {venue.get('size_estimate','')} · "
                f"入口 {len(s.get('entrances',[]))} 處 · 洗手間 {s.get('toilets_count','未見')}"}
    ]

    try:
        p_oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(400, "project_id 格式錯")

    r = db.projects.update_one(
        {"_id": p_oid},
        {"$set": {
            "handoff.asset_refs": asset_refs,
            "handoff.constraints": issues,  # 場勘發現的 issues 變 constraints
            "handoff.source_survey_id": survey_id,
            "handoff.updated_by": email,
            "handoff.updated_at": datetime.utcnow(),
        }},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "project 不存在")
    return {"pushed": True, "issues_count": len(issues)}

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
import tempfile
import threading
from datetime import datetime, timedelta, timezone
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

# B4(v1.3)· audio_note 限制
MAX_AUDIO_BYTES = 5 * 1024 * 1024  # 5 MB · 30s opus < 500KB / 30s webm < 1.5MB · 留 buffer
MAX_AUDIO_PER_SURVEY = 10  # 一張 survey 最多 10 個 audio note
ALLOWED_AUDIO_MIMES = {
    "audio/webm", "audio/ogg", "audio/mpeg", "audio/mp4",
    "audio/wav", "audio/x-wav", "audio/m4a", "audio/x-m4a",
}


def _oid(survey_id: str) -> ObjectId:
    try:
        return ObjectId(survey_id)
    except (InvalidId, TypeError):
        raise HTTPException(400, "survey_id 格式錯誤")


def _validate_gps(lat: Optional[float], lng: Optional[float], acc: Optional[float]):
    """R23#3 · GPS 範圍驗證"""
    if lat is None and lng is None:
        return
    if lat is None or lng is None:
        raise HTTPException(400, "GPS lat/lng 要一起給 或都不給")
    if not (-90 <= lat <= 90):
        raise HTTPException(400, f"lat {lat} 超範圍 [-90, 90]")
    if not (-180 <= lng <= 180):
        raise HTTPException(400, f"lng {lng} 超範圍 [-180, 180]")
    if acc is not None and acc < 0:
        raise HTTPException(400, f"accuracy {acc} 不可負")


def recover_stale_surveys(max_stale_minutes: int = 10):
    """R23#2 · startup 時掃 stuck survey · 有 tmp files 則重跑 · 無則 failed"""
    try:
        from main import db
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_stale_minutes)
        q = {"status": "processing", "updated_at": {"$lt": cutoff}}
        stale = list(db.site_surveys.find(q))
        if not stale:
            return
        logger.info("[site-survey] recover %d stale", len(stale))
        for s in stale:
            sid = str(s["_id"])
            tmp_paths = s.get("_tmp_image_paths") or []
            mime_list = s.get("_tmp_mime_list") or []
            if tmp_paths and all(os.path.exists(p) for p in tmp_paths):
                threading.Thread(
                    target=_process_survey_from_files,
                    args=(sid, tmp_paths, mime_list),
                    daemon=True,
                ).start()
            else:
                db.site_surveys.update_one(
                    {"_id": s["_id"]},
                    {"$set": {"status": "failed",
                              "error": "recovery · tmp images missing after restart"}},
                )
    except Exception as e:
        logger.error("[site-survey] recover_stale 失敗: %s", e)


def _cleanup_tmp_files(paths: list):
    """R23#1 · 刪所有 tmp file · 即使失敗"""
    for p in paths or []:
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning("[site-survey] cleanup tmp %s · %s", p, e)


def _process_survey_from_files(survey_id_str: str, tmp_paths: list, mime_list: list):
    """R23#1 · 從 tmp 檔讀 · 不 hold 5 × 5MB b64 在 memory
    · 每張讀一次 · 讀完可以丟 · 只 peak 1 張 worth"""
    from main import db
    import base64 as _b64
    try:
        b64_list = []
        for p in tmp_paths:
            if not os.path.exists(p):
                logger.error("[site-survey] tmp missing %s · skip", p)
                b64_list.append(None)
                continue
            with open(p, "rb") as f:
                b64_list.append(_b64.b64encode(f.read()).decode("ascii"))
        _process_survey(survey_id_str, b64_list, mime_list)
    finally:
        _cleanup_tmp_files(tmp_paths)
        # 清 DB 的 tmp refs
        try:
            db.site_surveys.update_one(
                {"_id": ObjectId(survey_id_str)},
                {"$unset": {"_tmp_image_paths": "", "_tmp_mime_list": ""}},
            )
        except Exception:
            pass


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
                      "updated_at": datetime.now(timezone.utc)}},
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
                "updated_at": datetime.now(timezone.utc),
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
                      "updated_at": datetime.now(timezone.utc)}},
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
    """上傳場勘 · 回 survey_id · 前端 polling /site-survey/{id}

    R23#1 · 照片寫 tmp file(不一次 hold 全在 memory) · background worker 逐張讀
    R23#2 · DB 存 _tmp_image_paths · container restart 可 recover
    R23#3 · GPS 範圍驗證
    """
    from main import db

    if not images:
        raise HTTPException(400, "至少上傳 1 張照片")
    if len(images) > MAX_IMAGES_PER_SURVEY:
        raise HTTPException(400, f"最多 {MAX_IMAGES_PER_SURVEY} 張 · 目前 {len(images)}")

    _validate_gps(gps_lat, gps_lng, gps_accuracy)

    # R23#1 · 驗 + 落 tmp file · 不一次全塞 memory
    # Day 2.3 · HEIC 自動轉 JPEG(用 Pillow + pillow-heif · iPhone 友好)
    tmp_paths = []
    mime_list = []
    total_bytes = 0
    try:
        for img in images:
            mime = (img.content_type or "").lower()
            is_heic = (mime in ("image/heic", "image/heif")
                       or (img.filename or "").lower().endswith((".heic", ".heif")))

            # R25#2 · 先寫 tmp · raw size cap · 不全部 read 進 memory
            # FastAPI UploadFile 內部已 spool 到 tmp file · 直接 chunked copy
            fd_raw, raw_path = tempfile.mkstemp(
                prefix="chengfu-survey-raw-",
                suffix=".heic" if is_heic else f".{mime.split('/')[-1]}",
            )
            raw_size = 0
            try:
                while True:
                    chunk = await img.read(64 * 1024)  # 64KB chunk
                    if not chunk:
                        break
                    raw_size += len(chunk)
                    if raw_size > MAX_IMAGE_BYTES * 2:  # HEIC 比 JPEG 約大 2x · 容忍
                        os.close(fd_raw)
                        os.remove(raw_path)
                        _cleanup_tmp_files(tmp_paths)
                        raise HTTPException(413, f"照片 raw > {MAX_IMAGE_BYTES * 2 // 1024 // 1024}MB · 請先 resize")
                    os.write(fd_raw, chunk)
            finally:
                os.close(fd_raw)

            if raw_size < 1024:
                os.remove(raw_path)
                _cleanup_tmp_files(tmp_paths)
                raise HTTPException(400, "照片太小 · 可能空檔")

            # 若 HEIC 則轉 JPEG · 否則直接驗 mime + size
            if is_heic:
                try:
                    from PIL import Image
                    import pillow_heif
                    pillow_heif.register_heif_opener()
                    fd_jpg, jpg_path = tempfile.mkstemp(prefix="chengfu-survey-", suffix=".jpg")
                    os.close(fd_jpg)
                    # 從 file path 開 · Pillow 內部 stream(不全載 memory)
                    img_pil = Image.open(raw_path)
                    img_pil.convert("RGB").save(jpg_path, format="JPEG", quality=85)
                    img_pil.close()
                    os.remove(raw_path)  # 刪 raw heic
                    final_size = os.path.getsize(jpg_path)
                    if final_size > MAX_IMAGE_BYTES:
                        os.remove(jpg_path)
                        _cleanup_tmp_files(tmp_paths)
                        raise HTTPException(413, f"HEIC 轉 JPEG 後仍 > {MAX_IMAGE_BYTES // 1024 // 1024}MB")
                    tmp_paths.append(jpg_path)
                    mime_list.append("image/jpeg")
                    total_bytes += final_size
                    logger.info("[site-survey] HEIC → JPEG · %s · raw %d → jpg %d",
                                img.filename, raw_size, final_size)
                except ImportError:
                    os.remove(raw_path)
                    _cleanup_tmp_files(tmp_paths)
                    raise HTTPException(400, "HEIC 需 pillow-heif · 或 iPhone 設定 → 相機 → 最相容")
                except Exception as e:
                    if os.path.exists(raw_path):
                        os.remove(raw_path)
                    _cleanup_tmp_files(tmp_paths)
                    raise HTTPException(400, f"HEIC 轉檔失敗: {str(e)[:100]}")
            else:
                if mime not in ("image/jpeg", "image/png", "image/webp"):
                    os.remove(raw_path)
                    _cleanup_tmp_files(tmp_paths)
                    raise HTTPException(400, f"照片格式不支援:{mime} · 請用 JPEG/PNG/WebP")
                if raw_size > MAX_IMAGE_BYTES:
                    os.remove(raw_path)
                    _cleanup_tmp_files(tmp_paths)
                    raise HTTPException(413, f"照片 > {MAX_IMAGE_BYTES // 1024 // 1024}MB · 請先 resize")
                tmp_paths.append(raw_path)
                mime_list.append(mime)
                total_bytes += raw_size
    except HTTPException:
        raise
    except Exception as e:
        _cleanup_tmp_files(tmp_paths)
        raise HTTPException(500, f"上傳處理失敗: {str(e)[:200]}")

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
        "media": [],
        "structured": {},
        "image_count": len(images),
        "total_bytes": total_bytes,
        "status": "processing",
        "_tmp_image_paths": tmp_paths,  # R23#2 · recovery 用
        "_tmp_mime_list": mime_list,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    r = db.site_surveys.insert_one(doc)
    sid = str(r.inserted_id)

    background.add_task(_process_survey_from_files, sid, tmp_paths, mime_list)

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
    survey_note = {
        "type": "note",
        "label": "場勘彙整 · " + datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "ref": f"{venue.get('type','')} · {venue.get('size_estimate','')} · "
               f"入口 {len(s.get('entrances',[]))} 處 · 洗手間 {s.get('toilets_count','未見')}",
    }

    try:
        p_oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(400, "project_id 格式錯")

    # R23#4 · 不覆寫人工欄位(asset_refs / constraints)
    # 改:addToSet asset_refs(append 不 dup)+ 獨立欄位存場勘 issues
    r = db.projects.update_one(
        {"_id": p_oid},
        {
            "$push": {"handoff.asset_refs": survey_note},
            "$set": {
                "handoff.site_survey_id": survey_id,
                "handoff.site_issues": issues,
                "handoff.site_venue": venue,
                "handoff.updated_by": email,
                "handoff.updated_at": datetime.now(timezone.utc),
            },
        },
    )
    if r.matched_count == 0:
        raise HTTPException(404, "project 不存在")
    return {"pushed": True, "issues_count": len(issues)}


# ============================================================
# B4(v1.3)· audio_note · 現場 PM 錄音 → Whisper STT → 存 db
# ============================================================
def _process_audio_note(survey_id_str: str, audio_path: str, mime: str,
                         duration_sec: Optional[float]):
    """背景 task · 跑 Whisper STT · 結果 push 到 site_surveys.audio_notes[]
    重用 routers/memory.py 同 Whisper chain · 失敗回 status:failed 不 raise"""
    from main import db
    from routers.memory import _retry, _openai_key_for_stt
    note_id = ObjectId()  # 預先產 · 給前端引用
    try:
        try:
            import openai
        except ImportError:
            logger.error("[site-audio] OpenAI SDK 未裝 · 跳 STT")
            return

        client = openai.OpenAI(api_key=_openai_key_for_stt())
        try:
            def _stt():
                with open(audio_path, "rb") as af:
                    return client.audio.transcriptions.create(
                        model="whisper-1", file=af,
                    )
            tr = _retry("Whisper", _stt, attempts=3)
            transcript = tr.text
        except Exception as e:
            logger.error("[site-audio] Whisper 失敗 sid=%s · %s", survey_id_str, e)
            db.site_surveys.update_one(
                {"_id": ObjectId(survey_id_str)},
                {"$push": {"audio_notes": {
                    "_id": note_id,
                    "status": "failed",
                    "error": f"STT 失敗: {str(e)[:200]}",
                    "mime": mime,
                    "duration_sec": duration_sec,
                    "created_at": datetime.now(timezone.utc),
                }}},
            )
            return

        db.site_surveys.update_one(
            {"_id": ObjectId(survey_id_str)},
            {"$push": {"audio_notes": {
                "_id": note_id,
                "status": "done",
                "transcript": transcript,
                "mime": mime,
                "duration_sec": duration_sec,
                "created_at": datetime.now(timezone.utc),
            }},
             "$set": {"updated_at": datetime.now(timezone.utc)}},
        )
        logger.info("[site-audio] sid=%s · transcript len=%d", survey_id_str, len(transcript or ""))
    finally:
        # PDPA · 一律刪 tmp · 防原始音檔留盤
        try:
            os.remove(audio_path)
        except OSError:
            pass


@router.post("/site-survey/{survey_id}/audio")
async def upload_audio_note(
    survey_id: str,
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    duration_sec: Optional[float] = Form(default=None),
    email: str = require_user_dep(),
):
    """B4 · 加 audio note 給該 survey · STT 背景跑

    Returns
    -------
    { note_id, status: "processing" }
    前端 polling /site-survey/{id} 看 audio_notes[] 內 status 變 done

    Limits:
    - 5 MB(預期 30s opus < 500KB · 留 buffer)
    - mime 必白名單(防上傳非 audio)
    - 一張 survey 最多 10 個 audio note(防 DoS)
    """
    from main import db
    oid = _oid(survey_id)
    survey = db.site_surveys.find_one({"_id": oid}, {"owner": 1, "audio_notes": 1})
    if not survey:
        raise HTTPException(404, "survey 不存在")
    # 只 owner 能加 audio
    if survey.get("owner") != email:
        raise HTTPException(403, "只能加自己場勘的 audio")

    # 限制 audio 數
    existing = len(survey.get("audio_notes") or [])
    if existing >= MAX_AUDIO_PER_SURVEY:
        raise HTTPException(429, f"超過 audio note 上限 {MAX_AUDIO_PER_SURVEY}")

    # mime 驗
    if audio.content_type not in ALLOWED_AUDIO_MIMES:
        raise HTTPException(400, f"audio mime 不接受:{audio.content_type}")

    # 寫 tmp(streaming · 64KB chunk · 防大檔吃光記憶體)
    fd, tmp_path = tempfile.mkstemp(prefix=f"chengfu-site-audio-{survey_id}-", suffix=".bin")
    raw_size = 0
    try:
        while True:
            chunk = await audio.read(64 * 1024)
            if not chunk:
                break
            raw_size += len(chunk)
            if raw_size > MAX_AUDIO_BYTES:
                os.close(fd)
                os.remove(tmp_path)
                raise HTTPException(
                    413,
                    f"audio > {MAX_AUDIO_BYTES // 1024 // 1024}MB · 縮短或 transcode",
                )
            os.write(fd, chunk)
        os.close(fd)
    except HTTPException:
        raise
    except Exception as e:
        os.close(fd)
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise HTTPException(500, f"audio 寫 tmp 失敗:{e}")

    if raw_size < 1024:  # < 1KB · 八成是空檔
        os.remove(tmp_path)
        raise HTTPException(400, "audio 太小 · 至少 1KB(可能錄到空)")

    # 背景跑 STT(同 memory.py pattern)
    background_tasks.add_task(
        _process_audio_note, survey_id, tmp_path, audio.content_type, duration_sec,
    )
    return {"status": "processing", "size_bytes": raw_size}

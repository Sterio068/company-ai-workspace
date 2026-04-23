"""
Media CRM router · v1.2 Feature #6(FEATURE-PROPOSALS · R14)

PR 公司記者 / 主編資料庫 + 發稿歷史 + 推薦引擎

不用 AI · 純 regex + set match · cost 0 · 100 筆資料秒回

涵蓋 7 endpoint:
- /media/contacts GET · POST · PUT · DELETE(CRUD 軟刪)
- /media/contacts/{id}/notes POST(加接觸 pitch 歷史)
- /media/contacts/import-csv POST(批次匯入 · upsert by email)
- /media/recommend POST · body {topic, limit} → top 10 記者 + match 分數

Collection · media_contacts:
{
  _id, name, outlet (媒體名), beats: [str], email, phone?,
  notes?, last_pitched_at?, pitched_count=0, accepted_count=0,
  accepted_topics: [str], is_active=True,
  created_at, updated_at, created_by: email,
}
"""
import csv
import io
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from bson.errors import InvalidId

from ._deps import require_admin_dep, require_user_dep


router = APIRouter(tags=["media"])
logger = logging.getLogger("chengfu")


def _oid(contact_id: str) -> ObjectId:
    try:
        return ObjectId(contact_id)
    except (InvalidId, TypeError):
        raise HTTPException(400, "contact_id 格式錯誤")


class MediaContact(BaseModel):
    name: str
    outlet: str                # 媒體名 · 如「聯合報」「商業周刊」
    beats: list[str] = []      # 負責主題 · 如 ["政府標案", "環保"]
    email: str                 # 不用 EmailStr · 容忍舊資料格式
    phone: Optional[str] = None
    notes: Optional[str] = None


class MediaContactPatch(BaseModel):
    name: Optional[str] = None
    outlet: Optional[str] = None
    beats: Optional[list[str]] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class RecommendRequest(BaseModel):
    topic: list[str]           # 推薦用主題 tags e.g. ["環保", "政府"]
    limit: int = 10


class PitchRecord(BaseModel):
    contact_id: str
    topic: str
    press_release_ref: Optional[str] = None
    accepted: Optional[bool] = None


# ============================================================
# CRUD
# ============================================================
@router.get("/media/contacts")
def list_contacts(
    search: Optional[str] = None,
    outlet: Optional[str] = None,
    beat: Optional[str] = None,
    include_inactive: bool = False,
    limit: int = Query(default=50, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
    _user: str = require_user_dep(),
):
    """列記者 · 支援 search(name/outlet/notes) + outlet/beat filter"""
    from main import db, serialize
    q = {}
    if not include_inactive:
        q["is_active"] = True
    if outlet:
        q["outlet"] = outlet
    if beat:
        q["beats"] = {"$in": [beat]}
    if search:
        # Mongo regex · 中文支援
        pat = {"$regex": search, "$options": "i"}
        q["$or"] = [{"name": pat}, {"outlet": pat}, {"notes": pat}]

    # 非 admin 遮 phone 欄(R14#2 PDPA · Level 02 電話)
    projection = None
    from main import _admin_allowlist
    if _user not in _admin_allowlist:
        projection = {"phone": 0}

    cursor = db.media_contacts.find(q, projection).sort("name", 1).skip(skip).limit(limit)
    items = serialize(list(cursor))
    total = db.media_contacts.count_documents(q)
    return {"items": items, "total": total, "skip": skip, "limit": limit,
            "has_more": (skip + len(items)) < total}


@router.post("/media/contacts")
def create_contact(c: MediaContact, admin_email: str = require_admin_dep()):
    """建單筆記者 · admin 才能加(防同事亂輸入)"""
    from main import db
    data = c.model_dump()
    # email 去重(unique index)
    if db.media_contacts.find_one({"email": data["email"].lower()}):
        raise HTTPException(409, f"email {data['email']} 已存在")
    data["email"] = data["email"].lower()
    data["is_active"] = True
    data["pitched_count"] = 0
    data["accepted_count"] = 0
    data["accepted_topics"] = []
    data["created_at"] = datetime.now(timezone.utc)
    data["updated_at"] = datetime.now(timezone.utc)
    data["created_by"] = admin_email
    r = db.media_contacts.insert_one(data)
    return {"id": str(r.inserted_id)}


@router.put("/media/contacts/{contact_id}")
def update_contact(contact_id: str, p: MediaContactPatch, _admin: str = require_admin_dep()):
    from main import db
    updates = {k: v for k, v in p.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        raise HTTPException(400, "沒有可更新欄位")
    if "email" in updates:
        updates["email"] = updates["email"].lower()
    updates["updated_at"] = datetime.now(timezone.utc)
    r = db.media_contacts.update_one({"_id": _oid(contact_id)}, {"$set": updates})
    if r.matched_count == 0:
        raise HTTPException(404, "記者不存在")
    return {"updated": r.modified_count}


@router.delete("/media/contacts/{contact_id}")
def deactivate_contact(contact_id: str, _admin: str = require_admin_dep()):
    """軟刪(is_active=false)· 保留 pitch 歷史 · 未來可以 undo"""
    from main import db
    r = db.media_contacts.update_one(
        {"_id": _oid(contact_id)},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "記者不存在")
    return {"deactivated": True}


# ============================================================
# Pitch 歷史
# ============================================================
@router.post("/media/pitches")
def record_pitch(pitch: PitchRecord, email: str = require_user_dep()):
    """記錄發稿 · pitched_count++ · 若 accepted=True 也更新 accepted_count"""
    from main import db
    oid = _oid(pitch.contact_id)
    contact = db.media_contacts.find_one({"_id": oid})
    if not contact:
        raise HTTPException(404, "記者不存在")

    pitch_doc = {
        "contact_id": pitch.contact_id,
        "topic": pitch.topic,
        "press_release_ref": pitch.press_release_ref,
        "accepted": pitch.accepted,
        "pitched_at": datetime.now(timezone.utc),
        "pitched_by": email,
    }
    db.media_pitch_history.insert_one(pitch_doc)

    # 更新 contact 統計
    updates = {
        "$inc": {"pitched_count": 1},
        "$set": {"last_pitched_at": datetime.now(timezone.utc),
                 "updated_at": datetime.now(timezone.utc)},
    }
    if pitch.accepted:
        updates["$inc"]["accepted_count"] = 1
        updates["$addToSet"] = {"accepted_topics": pitch.topic}
    db.media_contacts.update_one({"_id": oid}, updates)
    return {"recorded": True}


@router.get("/media/contacts/{contact_id}/pitches")
def list_pitches(contact_id: str, _user: str = require_user_dep()):
    from main import db, serialize
    _oid(contact_id)  # 驗格式
    cursor = db.media_pitch_history.find(
        {"contact_id": contact_id}
    ).sort("pitched_at", -1).limit(50)
    return serialize(list(cursor))


# ============================================================
# 推薦演算法
# ============================================================
@router.post("/media/recommend")
def recommend_contacts(req: RecommendRequest, _admin: str = require_admin_dep()):
    """主題 → top N 記者 + 分數 + 理由

    R21#3 · admin-only · 回傳含 email(PDPA Level 02)· 一般同事不直接拿
    · 若同事要發稿 · 走「admin 推薦 → 填 04 新聞稿 → admin 寄」流程

    score = 0.5 × jaccard(topic, beats)
          + 0.3 × (accepted_count / max_accepted)
          + 0.2 × recency_factor(last_pitched · 太常打擾扣分)
    """
    from main import db
    topics = set(t.strip() for t in req.topic if t.strip())
    if not topics:
        raise HTTPException(400, "topic 不可空")

    active = list(db.media_contacts.find({"is_active": True}))
    if not active:
        return {"items": [], "note": "無 active 記者"}

    max_accepted = max((c.get("accepted_count", 0) for c in active), default=1) or 1

    now = datetime.now(timezone.utc)
    scored = []
    for c in active:
        beats = set(c.get("beats", []))
        accepted_topics = set(c.get("accepted_topics", []))
        combined = beats | accepted_topics
        if not combined:
            continue

        # Jaccard(topic, beats+accepted_topics)
        intersect = topics & combined
        union = topics | combined
        jaccard = len(intersect) / len(union) if union else 0

        if jaccard == 0:
            continue  # 完全沒重疊 · 不推

        # Accepted count 加權(0-1 normalize)
        acc_score = (c.get("accepted_count", 0) / max_accepted)

        # Recency factor · last_pitched < 7 天扣分(太常打擾)
        last = c.get("last_pitched_at")
        if last:
            days = (now - last).days
            if days < 7:
                recency = 0.2  # 扣分
            elif days < 30:
                recency = 0.6
            else:
                recency = 1.0
        else:
            # R21#5 · 從沒接觸過給 0.6 · 不是 1.0(避免壓過老關係)
            # 老關係(accepted_count > 0)雖 recency 可能普通 · 但 acc_score 更高
            recency = 0.6

        score = 0.5 * jaccard + 0.3 * acc_score + 0.2 * recency
        scored.append({
            "id": str(c["_id"]),
            "name": c["name"],
            "outlet": c["outlet"],
            "beats": list(beats),
            "email": c["email"],
            "accepted_count": c.get("accepted_count", 0),
            "pitched_count": c.get("pitched_count", 0),
            "last_pitched_at": last.isoformat() if last else None,
            "score": round(score, 3),
            "reason": {
                "matched_topics": list(intersect),
                "jaccard": round(jaccard, 3),
                "accepted_weight": round(acc_score, 3),
                "recency_weight": round(recency, 3),
            },
        })

    scored.sort(key=lambda x: -x["score"])
    return {"items": scored[:req.limit], "total_candidates": len(active), "recommended": len(scored)}


# ============================================================
# CSV 匯入(初始建庫用)
# ============================================================
@router.post("/media/contacts/import-csv")
async def import_csv(
    file: UploadFile = File(...),
    admin_email: str = require_admin_dep(),
):
    """上傳 CSV · upsert by email · 預期欄位:name, outlet, beats, email, phone, notes

    beats 欄位用 "|" 分隔 · 例:「環保|政府|食品」
    pitched_count / accepted_count 不覆寫 · 只改 profile
    空 email 或 invalid → skip · 記錄 errors 回傳
    """
    from main import db
    content = await file.read()
    if not content:
        raise HTTPException(400, "空檔")
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "CSV > 5MB · 請拆批")

    # R21#2 · 多編碼 fallback · UTF-8 BOM → Big5 → GBK
    text = None
    for enc in ("utf-8-sig", "big5", "gbk"):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise HTTPException(400, "編碼無法辨識 · 請用 UTF-8 / Big5 / GBK")

    reader = csv.DictReader(io.StringIO(text))
    required = {"name", "outlet", "email"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise HTTPException(400, f"CSV 必含欄位:{required} · 目前:{reader.fieldnames}")

    imported, updated, errors = 0, 0, []
    for idx, row in enumerate(reader, 2):  # 第 2 行起(第 1 行是 header)
        email = (row.get("email") or "").strip().lower()
        if not email or "@" not in email:
            errors.append({"row": idx, "email": row.get("email"), "issue": "email 格式錯"})
            continue
        # R21#2 · 不在 import 階段改 row(會污染 DB · "'張三" 變奇怪資料)
        # CSV injection 防護改在 export 階段做(若未來加 /media/contacts/export)

        beats_raw = (row.get("beats") or "").strip()
        beats = [b.strip() for b in beats_raw.split("|") if b.strip()]

        doc_set = {
            "name": (row.get("name") or "").strip(),
            "outlet": (row.get("outlet") or "").strip(),
            "beats": beats,
            "email": email,
            "phone": (row.get("phone") or "").strip() or None,
            "notes": (row.get("notes") or "").strip() or None,
            "updated_at": datetime.now(timezone.utc),
        }
        doc_insert = {
            "is_active": True,
            "pitched_count": 0,
            "accepted_count": 0,
            "accepted_topics": [],
            "created_at": datetime.now(timezone.utc),
            "created_by": admin_email,
        }
        existing = db.media_contacts.find_one({"email": email})
        try:
            if existing:
                db.media_contacts.update_one({"email": email}, {"$set": doc_set})
                updated += 1
            else:
                db.media_contacts.insert_one({**doc_insert, **doc_set})
                imported += 1
        except DuplicateKeyError:
            # R21 · 真 Mongo unique 撞(race condition · 另個 request 同 email 同時 insert)
            errors.append({"row": idx, "email": email, "issue": "duplicate_email"})
        except Exception as e:
            errors.append({"row": idx, "email": email, "issue": str(e)[:100]})

    return {
        "imported": imported,
        "updated": updated,
        "errors": errors,
        "total_rows": imported + updated + len(errors),
    }


# ============================================================
# B3(v1.3)· CSV Export · 給老闆 / 合作夥伴拿名單
# ============================================================
def _csv_safe(v) -> str:
    """B3 · 防 CSV injection · = + - @ tab CR LF 開頭加 ' 前綴
    詳見 OWASP CSV Injection · Excel/Numbers/Sheets 開檔會 eval 公式
    """
    if v is None:
        return ""
    s = str(v)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r", "\n"):
        return "'" + s
    return s


@router.get("/media/contacts/export.csv")
def export_contacts_csv(
    include_inactive: bool = False,
    _admin: str = require_admin_dep(),
):
    """匯出全名單 CSV · admin only(含 email / phone PII)
    streaming 防 1k+ 筆爆記憶體 · CSV injection 防(_csv_safe)

    columns: name, outlet, beats, email, phone, accepted_count, pitched_count,
             last_pitched_at, accepted_topics, notes, is_active, created_at
    """
    from main import db
    from fastapi.responses import StreamingResponse

    q = {} if include_inactive else {"is_active": {"$ne": False}}
    cursor = db.media_contacts.find(q).sort("name", 1)

    def _stream():
        # BOM for Excel UTF-8 CSV(中文不亂碼)
        yield "\ufeff"
        # header
        yield ",".join([
            "name", "outlet", "beats", "email", "phone",
            "accepted_count", "pitched_count", "last_pitched_at",
            "accepted_topics", "notes", "is_active", "created_at",
        ]) + "\r\n"
        # rows
        for doc in cursor:
            beats = ";".join(doc.get("beats") or [])
            topics = ";".join(doc.get("accepted_topics") or [])
            last = doc.get("last_pitched_at")
            created = doc.get("created_at")
            row = [
                _csv_safe(doc.get("name")),
                _csv_safe(doc.get("outlet")),
                _csv_safe(beats),
                _csv_safe(doc.get("email")),
                _csv_safe(doc.get("phone")),
                str(doc.get("accepted_count", 0)),
                str(doc.get("pitched_count", 0)),
                last.isoformat() if isinstance(last, datetime) else "",
                _csv_safe(topics),
                _csv_safe(doc.get("notes")),
                str(doc.get("is_active", True)),
                created.isoformat() if isinstance(created, datetime) else "",
            ]
            # csv.writer 處理 quote · 不重做
            buf = io.StringIO()
            csv.writer(buf, quoting=csv.QUOTE_MINIMAL).writerow(row)
            yield buf.getvalue()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return StreamingResponse(
        _stream(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="chengfu-media-contacts-{today}.csv"',
            "Cache-Control": "no-store",
        },
    )

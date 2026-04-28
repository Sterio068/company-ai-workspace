"""
NotebookLM parallel knowledge bridge.

本地 MongoDB 是主資料庫；NotebookLM Source Pack 是可審核的衍生快照。
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from routers._deps import _is_admin_user, _serialize, require_admin_dep, require_permission_dep, require_user_dep, user_permissions
from services.notebooklm_client import (
    NotebookLMClientError,
    NotebookLMConfig,
    add_text_source,
    admin_config_status,
    create_notebook,
    load_config,
    public_status,
    upload_file_source,
    validate_config,
)
from services.source_pack_renderer import build_source_pack


router = APIRouter(prefix="/notebooklm", tags=["notebooklm"])


class SourcePackScope(str, Enum):
    project = "project"
    tenders = "tenders"
    company = "company"
    training = "training"


class SourcePackRequest(BaseModel):
    scope: SourcePackScope
    project_id: Optional[str] = None
    title: Optional[str] = None
    max_items: int = Field(default=20, ge=1, le=100)
    sensitivity: str = Field(default="all", max_length=24)


class SourcePackSyncRequest(BaseModel):
    notebook_id: Optional[str] = None
    create_notebook: bool = True
    notebook_title: Optional[str] = None
    confirm_send_to_notebooklm: bool = False


class NotebookLMSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    project_number: Optional[str] = Field(default=None, max_length=80)
    location: Optional[str] = Field(default=None, max_length=80)
    endpoint_location: Optional[str] = Field(default=None, max_length=80)
    access_token: Optional[str] = Field(default=None, max_length=10000)
    clear_access_token: bool = False


MAX_NOTEBOOK_FILES = 300
MAX_NOTEBOOK_FILE_BYTES = 200 * 1024 * 1024
MAX_NOTEBOOK_BATCH_BYTES = 1024 * 1024 * 1024


def _pack_oid(pack_id: str) -> ObjectId:
    try:
        return ObjectId(pack_id)
    except (InvalidId, TypeError):
        raise HTTPException(400, "source_pack_id 格式錯誤")


def _project_oid(project_id: str) -> ObjectId:
    try:
        return ObjectId(project_id)
    except (InvalidId, TypeError):
        raise HTTPException(400, "project_id 格式錯誤")


def _project_access_query(project_id: str, email: str, is_admin: bool) -> dict:
    q = {"_id": _project_oid(project_id)}
    if not is_admin:
        q["$or"] = [
            {"owner": email},
            {"collaborators": email},
            {"next_owner": email},
        ]
    return q


def _project_doc(db, project_id: str, email: str, is_admin: bool) -> dict:
    doc = db.projects.find_one(_project_access_query(project_id, email, is_admin))
    if not doc:
        if db.projects.find_one({"_id": _project_oid(project_id)}, {"_id": 1}):
            raise HTTPException(403, "只能操作自己負責或協作中的工作包")
        raise HTTPException(404, "工作包不存在")
    return doc


def _project_notebook_title(project: dict) -> str:
    name = str(project.get("name") or project.get("_id") or "未命名工作包").strip()
    client = str(project.get("client") or "").strip()
    return f"{client} · {name}" if client else name


def _project_id_from_pack(pack: dict) -> Optional[str]:
    for entity in pack.get("source_entities") or []:
        if entity.get("type") == "project" and entity.get("id"):
            return str(entity["id"])
    return None


def _audit_notebooklm(db, action: str, user: str, resource: str, details: dict):
    db.audit_log.insert_one({
        "action": action,
        "user": user,
        "resource": resource,
        "details": details,
        "created_at": datetime.now(timezone.utc),
    })


def _notebooklm_error_detail(e: NotebookLMClientError) -> dict:
    return {
        "message": e.message,
        "recovery_hint": e.recovery_hint,
        "provider_status": e.status_code,
    }


def _candidate_notebooklm_config(payload: NotebookLMSettingsUpdate) -> NotebookLMConfig:
    current = load_config()
    access_token = current.access_token
    if payload.clear_access_token:
        access_token = ""
    if payload.access_token is not None and payload.access_token.strip():
        access_token = payload.access_token.strip()
    return NotebookLMConfig(
        enabled=payload.enabled if payload.enabled is not None else current.enabled,
        project_number=(payload.project_number.strip() if payload.project_number is not None else current.project_number),
        location=(payload.location.strip() if payload.location is not None and payload.location.strip() else current.location),
        endpoint_location=(
            payload.endpoint_location.strip()
            if payload.endpoint_location is not None and payload.endpoint_location.strip()
            else current.endpoint_location
        ),
        access_token=access_token,
    )


def _should_validate_notebooklm_settings(payload: NotebookLMSettingsUpdate) -> bool:
    return any(
        value is not None
        for value in (
            payload.enabled,
            payload.project_number,
            payload.location,
            payload.endpoint_location,
            payload.access_token if payload.access_token and payload.access_token.strip() else None,
        )
    )


def _can_access_source_pack(db, pack: dict, email: str, is_admin: bool) -> bool:
    if is_admin:
        return True
    project_id = _project_id_from_pack(pack)
    if not project_id:
        return True
    return bool(db.projects.find_one(_project_access_query(project_id, email, False), {"_id": 1}))


def _agent_acting_user(db, request: Request, admin_identity: str) -> tuple[str, bool, str]:
    """Resolve the real user ACL for an internal Agent action.

    Internal token auth proves the caller is the system, not which human/project
    boundary should be used.  X-Acting-User makes that boundary explicit.
    """
    acting = (request.headers.get("X-Acting-User") or "").strip().lower()
    if admin_identity.startswith("internal:") and not acting:
        raise HTTPException(400, "Agent NotebookLM action 必須提供 X-Acting-User")
    if not acting:
        acting = admin_identity.strip().lower()
    if not acting or acting.startswith("internal:"):
        raise HTTPException(400, "X-Acting-User 必須是有效同仁 email")
    user_doc = db.users.find_one({"email": acting}, {"chengfu_active": 1})
    if not user_doc:
        raise HTTPException(404, "acting user 不存在")
    if user_doc and user_doc.get("chengfu_active") is False:
        raise HTTPException(403, "acting user 帳號已停用")
    acting_is_admin = _is_admin_user(acting)
    perms = user_permissions(acting)
    if not acting_is_admin and "*" not in perms and "knowledge.search" not in perms:
        raise HTTPException(403, "acting user 需要 knowledge.search 權限")
    return acting, acting_is_admin, f"agent:{acting}"


def _ensure_project_notebook(db, project_id: str, email: str, is_admin: bool,
                             title: Optional[str] = None) -> dict:
    project = _project_doc(db, project_id, email, is_admin)
    existing = db.notebooklm_project_notebooks.find_one({"project_id": project_id})
    if existing and existing.get("notebook_id"):
        return existing | {"created": False, "configured": True}

    status = public_status()
    notebook_title = title or _project_notebook_title(project)
    now = datetime.now(timezone.utc)
    if not status["configured"]:
        doc = {
            "project_id": project_id,
            "title": notebook_title,
            "notebook_id": None,
            "web_url": None,
            "configured": False,
            "state": "local_ready",
            "created_by": email,
            "created_at": now,
            "updated_at": now,
        }
        db.notebooklm_project_notebooks.update_one(
            {"project_id": project_id},
            {"$set": doc},
            upsert=True,
        )
        return doc | {"created": False, "missing": status.get("missing", [])}

    result = create_notebook(notebook_title)
    notebook = result.get("notebook") or {}
    notebook_id = notebook.get("notebookId")
    if not notebook_id:
        raise HTTPException(502, "NotebookLM 建立筆記本失敗")
    doc = {
        "project_id": project_id,
        "title": notebook_title,
        "notebook_id": notebook_id,
        "web_url": notebook.get("web_url"),
        "configured": True,
        "state": "ready",
        "created_by": email,
        "created_at": existing.get("created_at") if existing else now,
        "updated_at": now,
        "raw": notebook,
    }
    db.notebooklm_project_notebooks.update_one(
        {"project_id": project_id},
        {"$set": doc},
        upsert=True,
    )
    return doc | {"created": True}


def _normalize_match_text(value: str) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def _guess_project_id(db, email: str, is_admin: bool, names: list[str]) -> Optional[str]:
    haystack = _normalize_match_text(" ".join(names))
    if not haystack:
        return None
    query = {} if is_admin else {
        "$or": [
            {"owner": email},
            {"collaborators": email},
            {"next_owner": email},
        ]
    }
    best: tuple[int, Optional[str]] = (0, None)
    for project in db.projects.find(query, {"name": 1, "client": 1}).limit(500):
        tokens = [
            _normalize_match_text(project.get("name")),
            _normalize_match_text(project.get("client")),
        ]
        score = 0
        for token in tokens:
            if token and token in haystack:
                score += len(token)
            elif token and haystack in token:
                score += max(1, len(haystack) // 2)
        if score > best[0]:
            best = (score, str(project["_id"]))
    return best[1]


async def _read_upload_bytes(file: UploadFile) -> bytes:
    content = await file.read()
    if len(content) > MAX_NOTEBOOK_FILE_BYTES:
        raise HTTPException(
            413,
            f"{file.filename or '檔案'} 超過單檔 {MAX_NOTEBOOK_FILE_BYTES // 1024 // 1024} MB 上限",
        )
    return content


async def _upload_files_to_project_notebook(
    db,
    *,
    files: list[UploadFile],
    relative_paths: list[str],
    project_id: Optional[str],
    batch_id: Optional[str],
    resume_failed_only: bool,
    email: str,
    is_admin: bool,
) -> dict:
    if not files:
        raise HTTPException(400, "請選擇至少一個檔案")
    if len(files) > MAX_NOTEBOOK_FILES:
        raise HTTPException(413, f"一次最多上傳 {MAX_NOTEBOOK_FILES} 個檔案")

    display_names = [
        (relative_paths[idx] if idx < len(relative_paths) and relative_paths[idx] else (file.filename or f"file-{idx + 1}"))
        for idx, file in enumerate(files)
    ]
    upload_batch_id = (batch_id or "").strip() or str(uuid4())
    resolved_project_id = project_id or _guess_project_id(db, email, is_admin, display_names)
    if not resolved_project_id:
        raise HTTPException(400, "無法自動判斷要歸入哪個工作包,請先選擇工作包")

    try:
        notebook = _ensure_project_notebook(db, resolved_project_id, email, is_admin)
    except NotebookLMClientError as e:
        raise HTTPException(e.status_code, _notebooklm_error_detail(e))
    now = datetime.now(timezone.utc)
    if not notebook.get("configured") or not notebook.get("notebook_id"):
        records = []
        for idx, file in enumerate(files):
            record = {
                "project_id": resolved_project_id,
                "batch_id": upload_batch_id,
                "upload_index": idx,
                "notebook_id": None,
                "relative_path": display_names[idx],
                "file_name": file.filename,
                "content_type": file.content_type,
                "status": "skipped_unconfigured",
                "reason": "NotebookLM Enterprise 尚未設定；檔案未送出。",
                "created_by": email,
                "created_at": now,
            }
            db.notebooklm_file_uploads.insert_one(record)
            records.append(record)
        return {
            "configured": False,
            "batch_id": upload_batch_id,
            "total": len(records),
            "project_id": resolved_project_id,
            "notebook": notebook,
            "uploaded": 0,
            "failed": 0,
            "skipped": len(records),
            "items": records,
        }

    total = 0
    items = []
    uploaded = 0
    failed = 0
    skipped = 0
    for idx, file in enumerate(files):
        relative_path = display_names[idx]
        if resume_failed_only and batch_id:
            already_uploaded = db.notebooklm_file_uploads.find_one({
                "project_id": resolved_project_id,
                "batch_id": upload_batch_id,
                "notebook_id": notebook["notebook_id"],
                "relative_path": relative_path,
                "status": "uploaded",
            }, {"_id": 1, "size": 1, "notebook_id": 1})
            if already_uploaded:
                skipped += 1
                record = {
                    "project_id": resolved_project_id,
                    "batch_id": upload_batch_id,
                    "upload_index": idx,
                    "notebook_id": notebook["notebook_id"],
                    "relative_path": relative_path,
                    "file_name": file.filename,
                    "content_type": file.content_type,
                    "size": already_uploaded.get("size"),
                    "status": "skipped_already_uploaded",
                    "created_by": email,
                    "created_at": now,
                }
                items.append(record)
                continue
        try:
            content = await _read_upload_bytes(file)
            total += len(content)
            if total > MAX_NOTEBOOK_BATCH_BYTES:
                raise HTTPException(
                    413,
                    f"一次資料夾上傳超過 {MAX_NOTEBOOK_BATCH_BYTES // 1024 // 1024} MB 上限",
                )
            result = upload_file_source(
                notebook["notebook_id"],
                relative_path,
                content,
                file.content_type or "application/octet-stream",
            )
            status = "uploaded" if result.get("configured") else "skipped_unconfigured"
            record = {
                "project_id": resolved_project_id,
                "batch_id": upload_batch_id,
                "upload_index": idx,
                "notebook_id": notebook["notebook_id"],
                "relative_path": relative_path,
                "file_name": file.filename,
                "content_type": file.content_type,
                "size": len(content),
                "status": status,
                "result": result,
                "created_by": email,
                "created_at": now,
            }
            uploaded += 1 if status == "uploaded" else 0
        except HTTPException:
            raise
        except NotebookLMClientError as e:
            failed += 1
            record = {
                "project_id": resolved_project_id,
                "batch_id": upload_batch_id,
                "upload_index": idx,
                "notebook_id": notebook["notebook_id"],
                "relative_path": relative_path,
                "file_name": file.filename,
                "content_type": file.content_type,
                "status": "failed",
                "error": e.message[:500],
                "recovery_hint": e.recovery_hint,
                "provider_status": e.status_code,
                "created_by": email,
                "created_at": now,
            }
        except Exception as e:
            failed += 1
            record = {
                "project_id": resolved_project_id,
                "batch_id": upload_batch_id,
                "upload_index": idx,
                "notebook_id": notebook["notebook_id"],
                "relative_path": relative_path,
                "file_name": file.filename,
                "content_type": file.content_type,
                "status": "failed",
                "error": str(e)[:500],
                "created_by": email,
                "created_at": now,
            }
        db.notebooklm_file_uploads.insert_one(record)
        items.append(record)

    db.notebooklm_project_notebooks.update_one(
        {"project_id": resolved_project_id},
        {"$set": {"updated_at": datetime.now(timezone.utc), "last_upload_at": datetime.now(timezone.utc)}},
    )
    return {
        "configured": True,
        "batch_id": upload_batch_id,
        "total": len(display_names),
        "project_id": resolved_project_id,
        "notebook": notebook,
        "uploaded": uploaded,
        "failed": failed,
        "skipped": skipped,
        "items": items,
    }


def _source_pack_from_request(db, req: SourcePackRequest, email: str, is_admin: bool) -> dict:
    pack = build_source_pack(
        db,
        req.scope.value,
        email=email,
        is_admin=is_admin,
        project_id=req.project_id,
        max_items=req.max_items,
    )
    pack["title"] = req.title or pack["title"]
    pack["sensitivity"] = req.sensitivity
    return pack


def _preview_pack_response(db, req: SourcePackRequest, email: str, is_admin: bool) -> dict:
    pack = _source_pack_from_request(db, req, email, is_admin)
    return {k: v for k, v in pack.items() if k != "content_md"} | {
        "preview_md": pack["content_md"][:6000],
    }


def _store_source_pack(db, req: SourcePackRequest, email: str, is_admin: bool,
                       created_by_override: Optional[str] = None) -> dict:
    pack = _source_pack_from_request(db, req, email, is_admin)
    now = datetime.now(timezone.utc)
    created_by = created_by_override or email
    pack.update({
        "status": "local_ready",
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
        "sync": {
            "provider": "notebooklm",
            "state": "not_synced",
            "notebook_id": None,
            "source_id": None,
        },
    })
    existing = db.notebooklm_source_packs.find_one({"content_hash": pack["content_hash"]})
    if existing:
        db.notebooklm_source_packs.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "title": pack["title"],
                "updated_at": pack["updated_at"],
                "created_by": created_by,
                "sensitivity": pack["sensitivity"],
            }},
        )
        existing.update({
            "title": pack["title"],
            "updated_at": pack["updated_at"],
            "created_by": created_by,
            "sensitivity": pack["sensitivity"],
        })
        result = existing | {"deduped": True}
        _audit_notebooklm(db, "notebooklm_source_pack_create", created_by, str(existing["_id"]), {
            "scope": pack["scope"],
            "sensitivity": pack["sensitivity"],
            "content_hash": pack["content_hash"],
            "deduped": True,
            "source_entities": pack.get("source_entities", []),
        })
        return result
    r = db.notebooklm_source_packs.insert_one(pack)
    pack["_id"] = r.inserted_id
    _audit_notebooklm(db, "notebooklm_source_pack_create", created_by, str(r.inserted_id), {
        "scope": pack["scope"],
        "sensitivity": pack["sensitivity"],
        "content_hash": pack["content_hash"],
        "deduped": False,
        "source_entities": pack.get("source_entities", []),
    })
    return pack | {"deduped": False}


def _list_source_pack_docs(db, scope: Optional[SourcePackScope], limit: int,
                           email: str, is_admin: bool) -> dict:
    q = {}
    if scope:
        q["scope"] = scope.value
    projection = {"content_md": 0}
    # Pull a bounded window then enforce project ACL in Python. Source packs are
    # low-volume audit snapshots, and this keeps project access logic centralized.
    candidates = list(db.notebooklm_source_packs.find(q, projection).sort("updated_at", -1).limit(limit * 5))
    items = [p for p in candidates if _can_access_source_pack(db, p, email, is_admin)][:limit]
    return {"items": items, "count": len(items)}


def _source_pack_needs_confirm(pack: dict) -> bool:
    return pack.get("sensitivity") == "L3" or str(pack.get("created_by") or "").startswith("agent:")


def _sync_source_pack_doc(db, pack_id: str, req: SourcePackSyncRequest, admin: str,
                          acting_email: Optional[str] = None,
                          acting_is_admin: bool = True) -> dict:
    pack = db.notebooklm_source_packs.find_one({"_id": _pack_oid(pack_id)})
    if not pack:
        raise HTTPException(404, "source pack 不存在")
    acting_email = acting_email or admin
    if not _can_access_source_pack(db, pack, acting_email, acting_is_admin):
        raise HTTPException(403, "只能同步自己可存取工作包產生的資料包")

    run = {
        "pack_id": pack_id,
        "requested_by": admin,
        "acting_user": acting_email,
        "sensitivity": pack.get("sensitivity") or "all",
        "status": "running",
        "created_at": datetime.now(timezone.utc),
    }
    run_id = db.notebooklm_sync_runs.insert_one(run).inserted_id
    _audit_notebooklm(db, "notebooklm_source_pack_sync_request", admin, pack_id, {
        "acting_user": acting_email,
        "sensitivity": pack.get("sensitivity") or "all",
        "scope": pack.get("scope"),
        "content_hash": pack.get("content_hash"),
    })

    try:
        status = public_status()
        if not status["configured"]:
            result = {
                "configured": False,
                "state": "local_ready",
                "reason": "NotebookLM Enterprise 尚未設定；資料包已保存在本地，可人工貼入 NotebookLM。",
                "missing": status.get("missing", []),
            }
            db.notebooklm_sync_runs.update_one({"_id": run_id}, {"$set": {
                "status": "skipped_unconfigured",
                "finished_at": datetime.now(timezone.utc),
                "result": result,
            }})
            return result | {"run_id": run_id}

        needs_confirm = _source_pack_needs_confirm(pack)
        if needs_confirm and not req.confirm_send_to_notebooklm:
            reason = "L3 機敏資料" if pack.get("sensitivity") == "L3" else "Agent 建立的資料包"
            db.notebooklm_sync_runs.update_one({"_id": run_id}, {"$set": {
                "status": "confirm_required",
                "finished_at": datetime.now(timezone.utc),
                "reason": reason,
            }})
            raise HTTPException(409, {
                "code": "notebooklm_confirm_required",
                "message": f"同步前需二次確認:{reason}將送到 NotebookLM Enterprise",
                "reason": reason,
            })

        notebook_id = req.notebook_id
        notebook_result = None
        project_id = _project_id_from_pack(pack)
        if not notebook_id and project_id:
            notebook = _ensure_project_notebook(db, project_id, acting_email, acting_is_admin, req.notebook_title)
            notebook_id = notebook.get("notebook_id")
            notebook_result = {"notebook": notebook}
        if not notebook_id and req.create_notebook:
            notebook_result = create_notebook(req.notebook_title or pack["title"])
            notebook_id = (notebook_result.get("notebook") or {}).get("notebookId")
        if not notebook_id:
            raise HTTPException(400, "請提供 notebook_id 或啟用 create_notebook")

        source_result = add_text_source(notebook_id, pack["title"], pack["content_md"])
        source_id = None
        if source_result.get("sources"):
            source_id = ((source_result["sources"][0].get("sourceId") or {}).get("id"))
        sync_doc = {
            "provider": "notebooklm",
            "state": "synced",
            "notebook_id": notebook_id,
            "source_id": source_id,
            "synced_at": datetime.now(timezone.utc),
            "notebook": notebook_result,
            "source": source_result,
        }
        db.notebooklm_source_packs.update_one(
            {"_id": pack["_id"]},
            {"$set": {"status": "synced", "sync": sync_doc, "updated_at": datetime.now(timezone.utc)}},
        )
        db.notebooklm_sync_runs.update_one({"_id": run_id}, {"$set": {
            "status": "synced",
            "finished_at": datetime.now(timezone.utc),
            "result": sync_doc,
        }})
        return sync_doc | {"run_id": run_id}
    except NotebookLMClientError as e:
        detail = _notebooklm_error_detail(e)
        db.notebooklm_sync_runs.update_one({"_id": run_id}, {"$set": {
            "status": "failed",
            "finished_at": datetime.now(timezone.utc),
            "error": e.message[:500],
            "recovery_hint": e.recovery_hint,
            "provider_status": e.status_code,
        }})
        raise HTTPException(e.status_code, detail)
    except HTTPException as e:
        existing_run = db.notebooklm_sync_runs.find_one({"_id": run_id}, {"status": 1})
        if existing_run and existing_run.get("status") == "confirm_required":
            raise
        db.notebooklm_sync_runs.update_one({"_id": run_id}, {"$set": {
            "status": "failed",
            "finished_at": datetime.now(timezone.utc),
            "error": str(e.detail),
        }})
        raise
    except Exception as e:
        db.notebooklm_sync_runs.update_one({"_id": run_id}, {"$set": {
            "status": "failed",
            "finished_at": datetime.now(timezone.utc),
            "error": str(e)[:500],
        }})
        raise HTTPException(502, f"NotebookLM 同步失敗:{str(e)[:180]}")


@router.get("/status")
def notebooklm_status(_user: str = require_user_dep()):
    from main import db
    return {
        "notebooklm": public_status(),
        "local": {
            "source_packs": db.notebooklm_source_packs.count_documents({}),
            "sync_runs": db.notebooklm_sync_runs.count_documents({}),
            "source_of_truth": "MongoDB / 本地檔案",
            "external_role": "NotebookLM 僅作為衍生知識庫",
        },
    }


@router.get("/settings")
def notebooklm_settings(_admin: str = require_admin_dep()):
    """Admin-only runtime config · secrets are redacted."""
    return admin_config_status()


@router.put("/settings")
def update_notebooklm_settings(payload: NotebookLMSettingsUpdate, admin: str = require_admin_dep()):
    """Update NotebookLM Enterprise config from the launcher.

    Sensitive token is write-only: the status endpoint only returns configured
    bool + preview, never the original value.
    """
    from main import audit_col, db

    values: dict[str, str] = {}
    if payload.enabled is not None:
        values["NOTEBOOKLM_ENTERPRISE_ENABLED"] = "true" if payload.enabled else "false"
    for field, env_name in (
        ("project_number", "NOTEBOOKLM_PROJECT_NUMBER"),
        ("location", "NOTEBOOKLM_LOCATION"),
        ("endpoint_location", "NOTEBOOKLM_ENDPOINT_LOCATION"),
    ):
        raw = getattr(payload, field)
        if raw is not None:
            values[env_name] = raw.strip()
    if payload.access_token is not None and payload.access_token.strip():
        values["NOTEBOOKLM_ACCESS_TOKEN"] = payload.access_token.strip()

    validation = None
    candidate = _candidate_notebooklm_config(payload)
    if candidate.configured and _should_validate_notebooklm_settings(payload):
        try:
            validation = validate_config(candidate)
        except NotebookLMClientError as e:
            audit_col.insert_one({
                "action": "notebooklm_settings_validate_failed",
                "user": admin,
                "resource": "notebooklm",
                "details": {
                    "fields": [name for name in values if name != "NOTEBOOKLM_ACCESS_TOKEN"],
                    "access_token_updated": "NOTEBOOKLM_ACCESS_TOKEN" in values,
                    "recovery_hint": e.recovery_hint,
                    "provider_status": e.status_code,
                },
                "created_at": datetime.now(timezone.utc),
            })
            raise HTTPException(412, _notebooklm_error_detail(e))

    now = datetime.now(timezone.utc)
    for name, value in values.items():
        db.system_settings.update_one(
            {"name": name},
            {"$set": {
                "name": name,
                "value": value,
                "updated_at": now,
                "updated_by": admin,
            }},
            upsert=True,
        )
    if payload.clear_access_token:
        db.system_settings.delete_one({"name": "NOTEBOOKLM_ACCESS_TOKEN"})

    audit_col.insert_one({
        "action": "notebooklm_settings_update",
        "user": admin,
        "resource": "notebooklm",
        "details": {
            "fields": [name for name in values if name != "NOTEBOOKLM_ACCESS_TOKEN"],
            "access_token_updated": "NOTEBOOKLM_ACCESS_TOKEN" in values,
            "access_token_cleared": payload.clear_access_token,
            "validated": bool(validation),
        },
        "created_at": now,
    })
    return {"updated": True, "validation": validation, "notebooklm": admin_config_status()}


@router.post("/projects/{project_id}/notebook")
def ensure_project_notebook(project_id: str, email: str = require_permission_dep("knowledge.search")):
    """One project maps to one NotebookLM notebook."""
    from main import db
    return _serialize(_ensure_project_notebook(db, project_id, email, _is_admin_user(email)))


@router.get("/projects/{project_id}/notebook")
def get_project_notebook(project_id: str, email: str = require_permission_dep("knowledge.search")):
    from main import db
    _project_doc(db, project_id, email, _is_admin_user(email))
    doc = db.notebooklm_project_notebooks.find_one({"project_id": project_id})
    if not doc:
        return {"project_id": project_id, "notebook_id": None, "state": "not_created"}
    return _serialize(doc)


@router.post("/uploads/auto")
async def upload_to_project_notebook_auto(
    files: list[UploadFile] = File(...),
    relative_paths: Optional[list[str]] = Form(default=None),
    project_id: Optional[str] = Form(default=None),
    batch_id: Optional[str] = Form(default=None),
    resume_failed_only: bool = Form(default=False),
    email: str = require_permission_dep("knowledge.search"),
):
    """Upload one file or a whole folder to the matching project notebook.

    If project_id is omitted, the backend guesses from folder/file names.
    """
    from main import db
    return _serialize(await _upload_files_to_project_notebook(
        db,
        files=files,
        relative_paths=relative_paths or [],
        project_id=project_id,
        batch_id=batch_id,
        resume_failed_only=resume_failed_only,
        email=email,
        is_admin=_is_admin_user(email),
    ))


@router.post("/projects/{project_id}/upload")
async def upload_to_project_notebook(
    project_id: str,
    files: list[UploadFile] = File(...),
    relative_paths: Optional[list[str]] = Form(default=None),
    batch_id: Optional[str] = Form(default=None),
    resume_failed_only: bool = Form(default=False),
    email: str = require_permission_dep("knowledge.search"),
):
    from main import db
    return _serialize(await _upload_files_to_project_notebook(
        db,
        files=files,
        relative_paths=relative_paths or [],
        project_id=project_id,
        batch_id=batch_id,
        resume_failed_only=resume_failed_only,
        email=email,
        is_admin=_is_admin_user(email),
    ))


@router.post("/source-packs/preview")
def preview_source_pack(req: SourcePackRequest, email: str = require_permission_dep("knowledge.search")):
    from main import db
    return _preview_pack_response(db, req, email, _is_admin_user(email))


@router.post("/source-packs")
def create_source_pack(req: SourcePackRequest, email: str = require_permission_dep("knowledge.search")):
    from main import db
    return _serialize(_store_source_pack(db, req, email, _is_admin_user(email)))


@router.get("/source-packs")
def list_source_packs(
    scope: Optional[SourcePackScope] = None,
    limit: int = Query(default=30, ge=1, le=100),
    email: str = require_permission_dep("knowledge.search"),
):
    from main import db
    return _serialize(_list_source_pack_docs(db, scope, limit, email, _is_admin_user(email)))


@router.get("/source-packs/{pack_id}")
def get_source_pack(pack_id: str, email: str = require_permission_dep("knowledge.search")):
    from main import db
    doc = db.notebooklm_source_packs.find_one({"_id": _pack_oid(pack_id)})
    if not doc:
        raise HTTPException(404, "source pack 不存在")
    if not _can_access_source_pack(db, doc, email, _is_admin_user(email)):
        raise HTTPException(403, "只能讀取自己可存取工作包產生的資料包")
    return _serialize(doc)


@router.post("/source-packs/{pack_id}/sync")
def sync_source_pack(
    pack_id: str,
    req: SourcePackSyncRequest,
    admin: str = require_admin_dep(),
):
    from main import db
    return _serialize(_sync_source_pack_doc(db, pack_id, req, admin))


@router.post("/agent/source-packs/preview")
def agent_preview_source_pack(req: SourcePackRequest, request: Request, actor: str = require_admin_dep()):
    """Internal action endpoint for supervisor/specialist agents.

    Agents can prepare reviewable data packs through the internal token path,
    but they still cannot change NotebookLM credentials or mutate source data.
    """
    from main import db
    acting_user, acting_is_admin, _created_by = _agent_acting_user(db, request, actor)
    return _preview_pack_response(db, req, acting_user, acting_is_admin)


@router.post("/agent/source-packs")
def agent_create_source_pack(req: SourcePackRequest, request: Request, actor: str = require_admin_dep()):
    from main import db
    acting_user, acting_is_admin, created_by = _agent_acting_user(db, request, actor)
    return _serialize(_store_source_pack(
        db,
        req,
        acting_user,
        acting_is_admin,
        created_by_override=created_by,
    ))


@router.get("/agent/source-packs")
def agent_list_source_packs(
    request: Request,
    scope: Optional[SourcePackScope] = None,
    limit: int = Query(default=10, ge=1, le=50),
    actor: str = require_admin_dep(),
):
    from main import db
    acting_user, acting_is_admin, _created_by = _agent_acting_user(db, request, actor)
    return _serialize(_list_source_pack_docs(db, scope, limit, acting_user, acting_is_admin))


@router.post("/agent/source-packs/{pack_id}/sync")
def agent_sync_source_pack(
    pack_id: str,
    req: SourcePackSyncRequest,
    request: Request,
    actor: str = require_admin_dep(),
):
    from main import db
    acting_user, acting_is_admin, _created_by = _agent_acting_user(db, request, actor)
    return _serialize(_sync_source_pack_doc(
        db,
        pack_id,
        req,
        actor,
        acting_email=acting_user,
        acting_is_admin=acting_is_admin,
    ))

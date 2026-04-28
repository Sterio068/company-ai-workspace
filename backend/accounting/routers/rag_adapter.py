"""
LibreChat RAG API compatible adapter.

Why this exists:
- LibreChat v0.8.5 still calls RAG_API_URL for /embed, /query, /text and
  /documents when file_search or file parsing is enabled.
- Pulling the upstream rag_api + pgvector images adds a fragile delivery
  dependency for a 10-person local Mac mini deployment.

This adapter keeps the same HTTP contract LibreChat expects, but stores
extracted text in MongoDB and uses deterministic keyword retrieval. It is a
delivery-safe baseline; a future v2 can swap this adapter for pgvector without
changing LibreChat configuration.
"""

from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import jwt
from bson import ObjectId
from fastapi import APIRouter, Body, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from auth_deps import _legacy_auth_headers_enabled, _secrets_equal
from routers._deps import get_users_col
from services.knowledge_extract import extract

router = APIRouter(prefix="/rag", tags=["rag-adapter"])

_MAX_CHARS = 120_000
_CHUNK_SIZE = 1500
_CHUNK_OVERLAP = 150


class QueryRequest(BaseModel):
    file_id: str
    query: str = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=20)
    entity_id: Optional[str] = None


def _rag_col():
    from main import db

    return db.rag_documents


def _user_email_from_payload(payload: dict[str, Any]) -> str:
    email = (payload.get("email") or "").strip().lower()
    if email:
        return email
    user_id = payload.get("id") or payload.get("sub") or payload.get("userId")
    if not user_id:
        return ""
    try:
        oid = ObjectId(str(user_id))
    except Exception:
        return ""
    user = get_users_col().find_one({"_id": oid}, {"email": 1})
    return (user.get("email") or "").strip().lower() if user else ""


def _assert_active_user(email: str) -> str:
    if not email:
        raise HTTPException(401, "Missing or invalid Authorization header")
    try:
        user = get_users_col().find_one({"email": email}, {"chengfu_active": 1})
    except Exception as exc:
        raise HTTPException(503, "使用者權限查詢失敗 · 請稍後再試") from exc
    if user and user.get("chengfu_active") is False:
        raise HTTPException(403, "帳號已停用 · 請聯絡管理員")
    return email


def _rag_caller(
    authorization: Optional[str] = Header(default=None),
    x_internal_token: Optional[str] = Header(default=None),
    x_user_email: Optional[str] = Header(default=None),
) -> str:
    """Authenticate internal LibreChat RAG calls.

    LibreChat forwards the user's bearer token when it calls RAG_API_URL. Keep a
    legacy header path only for local tests/dev; production compose disables it.
    """
    expected_internal = os.getenv("ECC_INTERNAL_TOKEN", "").strip()
    if expected_internal and _secrets_equal((x_internal_token or "").strip(), expected_internal):
        return "internal:rag"

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        for secret_name in ("JWT_SECRET", "JWT_REFRESH_SECRET"):
            secret = os.getenv(secret_name, "")
            if not secret or secret.startswith("<GENERATE"):
                continue
            try:
                payload = jwt.decode(token, secret, algorithms=["HS256"])
            except jwt.InvalidTokenError:
                continue
            return _assert_active_user(_user_email_from_payload(payload))

    if _legacy_auth_headers_enabled() and x_user_email:
        return _assert_active_user(x_user_email.strip().lower())

    raise HTTPException(401, "Missing or invalid Authorization header")


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", name or "upload.txt")
    return cleaned[:160] or "upload.txt"


async def _save_upload(file: UploadFile) -> str:
    suffix = Path(file.filename or "upload.txt").suffix or ".txt"
    fd, path = tempfile.mkstemp(prefix="chengfu-rag-", suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
        return path
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def _extract_text(path: str, filename: str) -> str:
    result = extract(path)
    text = (
        result.get("content")
        or result.get("text")
        or result.get("content_preview")
        or ""
    )
    if not text and result.get("type") == "unknown":
        text = f"檔案 {filename} 暫無可抽取文字。"
    return str(text)[:_MAX_CHARS]


def _chunk_text(text: str) -> list[dict[str, Any]]:
    normalized = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not normalized:
        return []

    chunks: list[dict[str, Any]] = []
    step = max(1, _CHUNK_SIZE - _CHUNK_OVERLAP)
    for idx, start in enumerate(range(0, len(normalized), step), start=1):
        piece = normalized[start:start + _CHUNK_SIZE].strip()
        if piece:
            chunks.append({"index": idx, "page": 1, "content": piece})
    return chunks


def _query_terms(query: str) -> list[str]:
    raw = query.strip().lower()
    terms = re.findall(r"[a-z0-9#._-]+|[\u4e00-\u9fff]{2,}", raw)
    # Add Chinese bigrams so short queries like "主色" still hit longer phrases.
    for phrase in re.findall(r"[\u4e00-\u9fff]{2,}", raw):
        terms.extend(phrase[i:i + 2] for i in range(max(0, len(phrase) - 1)))
    return sorted({t for t in terms if t})


def _score(content: str, terms: list[str], query: str) -> float:
    haystack = content.lower()
    score = 0.0
    if query.strip().lower() in haystack:
        score += 3.0
    for term in terms:
        if term in haystack:
            score += 1.0
    return score


@router.get("/health")
def health():
    return {"status": "ok", "adapter": "chengfu-mongo-keyword-rag"}


@router.post("/text")
async def parse_text(
    file_id: str = Form(default=""),
    file: UploadFile = File(...),
    _caller: str = Depends(_rag_caller),
):
    path = await _save_upload(file)
    try:
        text = _extract_text(path, file.filename or file_id or "upload.txt")
        return {"text": text}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


@router.post("/embed")
async def embed_file(
    file_id: str = Form(...),
    entity_id: Optional[str] = Form(default=None),
    storage_metadata: Optional[str] = Form(default=None),
    file: UploadFile = File(...),
    _caller: str = Depends(_rag_caller),
):
    filename = _safe_filename(file.filename or file_id)
    path = await _save_upload(file)
    try:
        text = _extract_text(path, filename)
        chunks = _chunk_text(text)
        doc = {
            "file_id": file_id,
            "entity_id": entity_id,
            "filename": filename,
            "text": text,
            "chunks": chunks,
            "storage_metadata": storage_metadata,
            "updated_at": datetime.now(timezone.utc),
        }
        _rag_col().update_one({"file_id": file_id, "entity_id": entity_id}, {"$set": doc}, upsert=True)
        return {
            "status": True,
            "known_type": bool(text),
            "file_id": file_id,
            "chunk_count": len(chunks),
        }
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


@router.post("/query")
def query_file(req: QueryRequest, _caller: str = Depends(_rag_caller)):
    filter_doc: dict[str, Any] = {"file_id": req.file_id}
    if req.entity_id is not None:
        filter_doc["entity_id"] = req.entity_id
    doc = _rag_col().find_one(filter_doc)
    if not doc:
        return []

    terms = _query_terms(req.query)
    scored = []
    for chunk in doc.get("chunks") or []:
        content = str(chunk.get("content") or "")
        score = _score(content, terms, req.query)
        if score <= 0:
            continue
        distance = max(0.0, 1.0 / (1.0 + score))
        scored.append((distance, chunk))

    scored.sort(key=lambda item: item[0])
    results = []
    for distance, chunk in scored[:req.k]:
        results.append([
            {
                "page_content": chunk.get("content") or "",
                "metadata": {
                    "source": doc.get("filename") or req.file_id,
                    "page": chunk.get("page") or 1,
                },
            },
            distance,
        ])
    return results


@router.delete("/documents")
def delete_documents(
    file_ids: Optional[list[str]] = Body(default=None),
    _caller: str = Depends(_rag_caller),
):
    if not file_ids:
        return {"status": True, "deleted": 0}
    result = _rag_col().delete_many({"file_id": {"$in": file_ids}})
    return {"status": True, "deleted": result.deleted_count}

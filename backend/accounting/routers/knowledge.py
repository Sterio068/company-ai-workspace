"""
Knowledge router · V1.1-SPEC §E · 多來源知識庫

ROADMAP §11.1 B-6 · 從 main.py 抽出(700+ 行 · 最大一塊)
- E-1 · /admin/sources CRUD + health
- E-2 · 多格式抽字 + Meili 索引(/knowledge/list,read,search)
- §10.3 · X-Agent-Num server-side derive(_derive_agent_num + _resolve_agent_num)

依賴:
- services.knowledge_indexer · Meili 索引 + 增量
- services.knowledge_extract · PyMuPDF / docx / pptx / xlsx / image OCR
- routers/_deps.py · _serialize / get_db / require_admin_dep
- main.py(lazy)· knowledge_sources_col / knowledge_audit_col / convos_col / _legacy_auth_headers_enabled
"""
import os
import re
import logging
import mimetypes
import fnmatch
from datetime import datetime
from typing import Optional, Literal
from collections import OrderedDict

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from bson import ObjectId

from services import knowledge_indexer
from services.knowledge_extract import extract as extract_file

from ._deps import require_admin_dep


router = APIRouter(tags=["knowledge"])
logger = logging.getLogger("chengfu")


# ============================================================
# Meili client(lazy init)
# ============================================================
_meili_client = None


def _get_meili_client():
    global _meili_client
    if _meili_client is not None:
        return _meili_client
    try:
        import meilisearch
        host = os.getenv("MEILI_HOST", "http://meilisearch:7700")
        key = os.getenv("MEILI_MASTER_KEY", "")
        _meili_client = meilisearch.Client(host, key)
        return _meili_client
    except Exception as e:
        logger.warning("[knowledge] Meili client init failed: %s", e)
        return None


# ============================================================
# Source root 白名單 · Codex Round 10.5 收緊到公司域
# ============================================================
_ALLOWED_SOURCE_ROOTS = [
    p.strip() for p in os.getenv(
        "KNOWLEDGE_ALLOWED_ROOTS",
        "/Volumes,/data,/tmp/chengfu-test-sources",  # 預設不含 /Users · /mnt
    ).split(",") if p.strip()
]


def _validate_source_path(abs_path: str) -> str:
    """路徑必須在允許 root 之下 · realpath 解 symlink"""
    try:
        resolved = os.path.realpath(abs_path)
    except Exception as e:
        raise HTTPException(400, f"路徑解析失敗:{e}")
    resolved = os.path.abspath(resolved)
    allowed = any(
        resolved == os.path.realpath(root) or
        resolved.startswith(os.path.realpath(root).rstrip("/") + "/")
        for root in _ALLOWED_SOURCE_ROOTS
    )
    if not allowed:
        raise HTTPException(
            400,
            f"路徑 {resolved}(原 {abs_path}) 不在允許清單 {_ALLOWED_SOURCE_ROOTS} · "
            "請改環境變數 KNOWLEDGE_ALLOWED_ROOTS(但先確認為公司擁有的資料夾)",
        )
    return resolved


# ============================================================
# Models
# ============================================================
class KnowledgeSource(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: Literal["smb", "local", "symlink", "usb"] = "local"
    path: str = Field(min_length=1)
    exclude_patterns: list[str] = [
        "*.lock", "~$*", ".DS_Store", "Thumbs.db", ".git/*",
    ]
    agent_access: list[str] = []  # 空=所有 Agent 可讀
    mime_whitelist: Optional[list[str]] = None  # null=全收
    max_size_mb: int = Field(default=50, ge=1, le=500)


class KnowledgeSourcePatch(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    exclude_patterns: Optional[list[str]] = None
    agent_access: Optional[list[str]] = None
    mime_whitelist: Optional[list[str]] = None
    max_size_mb: Optional[int] = Field(default=None, ge=1, le=500)


def _serialize_source(doc: dict) -> dict:
    """MongoDB doc → JSON · ObjectId & datetime → str(欄位專用版)"""
    if not doc:
        return {}
    out = dict(doc)
    out["id"] = str(out.pop("_id"))
    for k in ("created_at", "updated_at", "last_indexed_at"):
        v = out.get(k)
        if isinstance(v, datetime):
            out[k] = v.isoformat()
    return out


def _path_is_excluded(rel_path: str, excludes: list[str]) -> bool:
    """fnmatch pattern 檢查 · 包含檔名與路徑層級"""
    name = os.path.basename(rel_path)
    for pat in excludes or []:
        if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel_path, pat):
            return True
        if pat.endswith("/*") and rel_path.startswith(pat[:-2].lstrip("/") + "/"):
            return True
    return False


# ============================================================
# Cache · agent_access 過濾(ROADMAP §11.5 + Codex R5#3)
# ============================================================
_AGENT_FORBIDDEN_CACHE: dict = {"data": {}, "ts": 0.0, "version": None}
_AGENT_FORBIDDEN_TTL = 300.0  # 5 分鐘


def _sources_cache_version() -> str:
    """R10#2 修 R5#3 · 用 sentinel doc 取代 max(updated_at)
    · max(updated_at) 在 delete source 時不變 · 其他 worker 不會 invalidate(等 TTL)
    · sentinel doc 在 _invalidate 時 bump version · 其他 worker 立即看到變
    """
    from main import db
    try:
        doc = db.knowledge_meta.find_one({"name": "sources_cache_version"}, {"v": 1})
        return doc.get("v", "init") if doc else "init"
    except Exception:
        return "fallback"


def _agent_forbidden_sources(agent_num: Optional[str]) -> set:
    """ROADMAP §11.5 + R10#2 · cache version 用 sentinel doc · CRUD 立即跨 worker 失效"""
    from main import knowledge_sources_col
    import time
    now = time.time()
    cache = _AGENT_FORBIDDEN_CACHE
    current_version = _sources_cache_version()
    if cache["version"] != current_version or (now - cache["ts"]) > _AGENT_FORBIDDEN_TTL:
        cache["data"] = {}
        cache["ts"] = now
        cache["version"] = current_version

    key = agent_num or "__none__"
    if key not in cache["data"]:
        forbidden = set()
        for src in knowledge_sources_col.find(
            {"enabled": True, "agent_access": {"$exists": True, "$ne": []}},
            {"_id": 1, "agent_access": 1},
        ):
            if not agent_num or agent_num not in src["agent_access"]:
                forbidden.add(str(src["_id"]))
        cache["data"][key] = forbidden
    return cache["data"][key]


def _invalidate_sources_cache():
    """source CRUD 後呼叫 · R10#2 · upsert sentinel doc → 其他 worker 下次 request 看到 version 變"""
    from main import db
    import uuid as _uuid
    try:
        db.knowledge_meta.update_one(
            {"name": "sources_cache_version"},
            {"$set": {"v": _uuid.uuid4().hex, "ts": datetime.utcnow()}},
            upsert=True,
        )
    except Exception as e:
        logger.warning("[knowledge] cache version bump fail · 退回 local clear: %s", e)
    _AGENT_FORBIDDEN_CACHE["ts"] = 0.0
    _AGENT_FORBIDDEN_CACHE["data"] = {}
    _AGENT_FORBIDDEN_CACHE["version"] = None


# ============================================================
# Codex R7#11 + R8#9 · X-Agent-Num server-side derivation · ROADMAP §10.3
# ============================================================
_AGENT_NUM_FROM_CONVO_CACHE: "OrderedDict[str, tuple[Optional[str], float]]" = OrderedDict()
_AGENT_NUM_CACHE_TTL = 300.0
_AGENT_NUM_CACHE_MAX = 500
_AGENT_NUM_PATTERN = re.compile(r"#(\d{1,2})\b")


def _derive_agent_num(request: Request, conversation_id: Optional[str] = None) -> Optional[str]:
    """ROADMAP §10.3 · server-side derive agent_num 從 conversation_id"""
    from main import convos_col, db
    if not conversation_id:
        conversation_id = (request.query_params.get("conversation_id") if request else None)
    if not conversation_id:
        conversation_id = (request.headers.get("X-Conversation-Id") if request else None)
    if not conversation_id:
        return None

    import time
    now = time.time()
    cached = _AGENT_NUM_FROM_CONVO_CACHE.get(conversation_id)
    if cached and now - cached[1] < _AGENT_NUM_CACHE_TTL:
        _AGENT_NUM_FROM_CONVO_CACHE.move_to_end(conversation_id)
        return cached[0]

    agent_num: Optional[str] = None
    try:
        convo = convos_col.find_one(
            {"$or": [{"conversationId": conversation_id}, {"_id": conversation_id}]},
            {"agent_id": 1, "agentOptions": 1},
        )
        if not convo:
            try:
                convo = convos_col.find_one({"_id": ObjectId(conversation_id)},
                                            {"agent_id": 1, "agentOptions": 1})
            except Exception:
                pass
        if convo:
            agent_id = convo.get("agent_id") or (convo.get("agentOptions") or {}).get("agent")
            if agent_id:
                agent = db.agents.find_one(
                    {"$or": [{"id": agent_id}, {"_id": agent_id}]},
                    {"description": 1, "name": 1},
                )
                if agent:
                    for field in ("description", "name"):
                        text = agent.get(field) or ""
                        m = _AGENT_NUM_PATTERN.search(text)
                        if m:
                            agent_num = m.group(1).zfill(2)
                            break
    except Exception as e:
        logger.debug("[auth] _derive_agent_num conv=%s · %s", conversation_id, e)

    while len(_AGENT_NUM_FROM_CONVO_CACHE) >= _AGENT_NUM_CACHE_MAX:
        _AGENT_NUM_FROM_CONVO_CACHE.popitem(last=False)
    _AGENT_NUM_FROM_CONVO_CACHE[conversation_id] = (agent_num, now)
    return agent_num


def _resolve_agent_num(request: Request, conversation_id: Optional[str] = None) -> Optional[str]:
    """合併入口 · prod 走 derive · dev mode + ALLOW_LEGACY_AUTH_HEADERS 才信 header"""
    from main import _legacy_auth_headers_enabled
    derived = _derive_agent_num(request, conversation_id)
    if derived is not None:
        return derived
    if _legacy_auth_headers_enabled():
        return (request.headers.get("X-Agent-Num") if request else None) or None
    return None


# ============================================================
# Admin · Sources CRUD
# ============================================================
@router.get("/admin/sources")
def list_sources(_admin: str = require_admin_dep()):
    """列所有資料源 · 包含 disabled"""
    from main import knowledge_sources_col
    docs = list(knowledge_sources_col.find({}).sort("created_at", -1))
    return [_serialize_source(d) for d in docs]


@router.post("/admin/sources")
def create_source(src: KnowledgeSource, admin_email: str = require_admin_dep()):
    """建一個資料源 · 驗路徑存在且在 allowed roots 之下"""
    from main import knowledge_sources_col
    abs_path = _validate_source_path(src.path)
    if not os.path.exists(abs_path):
        raise HTTPException(
            400,
            f"路徑不存在或容器無法 mount:{abs_path} · 若是 NAS 請先 mount 再建 source",
        )
    if not os.access(abs_path, os.R_OK):
        raise HTTPException(403, f"路徑無讀取權限:{abs_path}")
    if knowledge_sources_col.find_one({"path": abs_path}):
        raise HTTPException(409, f"路徑已登記為資料源:{abs_path}")

    doc = src.model_dump()
    doc.update({
        "enabled": True,
        "path": abs_path,
        "last_indexed_at": None,
        "last_index_stats": None,
        "created_by": admin_email,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    r = knowledge_sources_col.insert_one(doc)
    sid = str(r.inserted_id)
    _invalidate_sources_cache()
    logger.info("[knowledge] source created: %s (%s) by %s", sid, abs_path, admin_email)
    return {
        "id": sid,
        "validation": {"path_exists": True, "readable": True, "abs_path": abs_path},
    }


@router.patch("/admin/sources/{source_id}")
def update_source(
    source_id: str,
    patch: KnowledgeSourcePatch,
    _admin: str = require_admin_dep(),
):
    """更新 source · 路徑不可改"""
    from main import knowledge_sources_col
    try:
        _id = ObjectId(source_id)
    except Exception:
        raise HTTPException(400, "source_id 格式錯誤")
    updates = {k: v for k, v in patch.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        raise HTTPException(400, "沒有可更新欄位")
    updates["updated_at"] = datetime.utcnow()
    r = knowledge_sources_col.update_one({"_id": _id}, {"$set": updates})
    if r.matched_count == 0:
        raise HTTPException(404, "資料源不存在")
    _invalidate_sources_cache()
    return {"ok": True, "updated": r.modified_count}


@router.delete("/admin/sources/{source_id}")
def delete_source(source_id: str, _admin: str = require_admin_dep()):
    """刪 source · 連帶從 Meili 清此 source 的文件"""
    from main import knowledge_sources_col
    try:
        _id = ObjectId(source_id)
    except Exception:
        raise HTTPException(400, "source_id 格式錯誤")
    doc = knowledge_sources_col.find_one_and_delete({"_id": _id})
    if not doc:
        raise HTTPException(404, "資料源不存在")
    _invalidate_sources_cache()
    meili = _get_meili_client()
    cleanup = knowledge_indexer.delete_source_from_index(source_id, meili) \
        if meili else {"ok": False, "reason": "meili not configured"}
    logger.info("[knowledge] source deleted: %s · meili_cleanup=%s", source_id, cleanup)
    return {"ok": True, "name": doc.get("name"), "meili_cleanup": cleanup}


@router.get("/admin/sources/{source_id}/health")
def source_health(source_id: str, _admin: str = require_admin_dep()):
    """Round 9 · NAS SMB 睡眠斷線偵測"""
    from main import knowledge_sources_col
    try:
        _id = ObjectId(source_id)
    except Exception:
        raise HTTPException(400, "source_id 格式錯誤")
    src = knowledge_sources_col.find_one({"_id": _id})
    if not src:
        raise HTTPException(404, "資料源不存在")

    path = src["path"]
    health = {
        "source_id": source_id,
        "name": src.get("name"),
        "path": path,
        "enabled": src.get("enabled", True),
        "checked_at": datetime.utcnow().isoformat(),
    }

    health["path_exists"] = os.path.exists(path)
    if not health["path_exists"]:
        health["status"] = "unreachable"
        health["issue"] = (
            f"路徑無法到達 · {path} · "
            "若是 SMB/NAS · 可能 Mac sleep 後 mount 失效 · "
            "請手動跑 mount -t smbfs ... 重掛"
        )
        return health

    health["readable"] = os.access(path, os.R_OK)
    if not health["readable"]:
        health["status"] = "permission_denied"
        health["issue"] = "路徑存在但 accounting 容器沒讀權限 · 檢查 NAS 帳號權限"
        return health

    try:
        entries = os.listdir(path)
        health["entry_count"] = len(entries)
    except Exception as e:
        health["status"] = "list_error"
        health["issue"] = f"列目錄失敗:{type(e).__name__}: {e}"
        return health

    last_stats = src.get("last_index_stats") or {}
    last_count = last_stats.get("file_count", 0)
    if last_count >= 50 and health["entry_count"] == 0:
        health["status"] = "suspicious_empty"
        health["issue"] = (
            f"上次索引 {last_count} 檔 · 目前 top-level 為空 · "
            "強烈懷疑 NAS mount 失效"
        )
        return health

    health["status"] = "ok"
    return health


@router.get("/admin/sources/health")
def all_sources_health(_admin: str = require_admin_dep()):
    """所有 enabled sources 一鍵巡檢"""
    from main import knowledge_sources_col
    results = []
    summary = {"ok": 0, "unreachable": 0, "suspicious": 0, "other": 0}
    for src in knowledge_sources_col.find({"enabled": True}):
        sid = str(src["_id"])
        try:
            h = source_health(sid, _admin=_admin)
        except HTTPException as e:
            h = {"source_id": sid, "name": src.get("name"),
                 "status": "error", "issue": str(e.detail)}
        results.append(h)
        s = h.get("status", "other")
        if s == "ok":
            summary["ok"] += 1
        elif s == "unreachable":
            summary["unreachable"] += 1
        elif s == "suspicious_empty":
            summary["suspicious"] += 1
        else:
            summary["other"] += 1
    return {
        "checked_at": datetime.utcnow().isoformat(),
        "summary": summary,
        "sources": results,
    }


@router.post("/admin/sources/{source_id}/reindex")
def reindex_source_endpoint(source_id: str, _admin: str = require_admin_dep()):
    """手動觸發 reindex · 同步執行(source 不大時可接受)"""
    from main import knowledge_sources_col
    try:
        _id = ObjectId(source_id)
    except Exception:
        raise HTTPException(400, "source_id 格式錯誤")
    src = knowledge_sources_col.find_one({"_id": _id})
    if not src:
        raise HTTPException(404, "資料源不存在")
    if not src.get("enabled"):
        raise HTTPException(400, "資料源已停用")
    meili = _get_meili_client()
    stats = knowledge_indexer.reindex_source(source_id, knowledge_sources_col, meili)
    return stats


# ============================================================
# Public Read API · 同仁 + Agent 都可叫
# ============================================================
@router.get("/knowledge/list")
def knowledge_list(source_id: Optional[str] = None, project: Optional[str] = None,
                   conversation_id: Optional[str] = None,
                   request: Request = None):
    """列資料源 / 列某 source 下的 top-level 資料夾 / 列某資料夾下的檔

    Round 9 Q3 · 無 source_id 時依 agent_num 過濾
    ROADMAP §10.3 · agent_num 改 server-side derive 自 conversation_id
    """
    from main import knowledge_sources_col
    if not source_id:
        agent_num = _resolve_agent_num(request, conversation_id)
        docs = list(knowledge_sources_col.find(
            {"enabled": True},
            {"_id": 1, "name": 1, "type": 1, "path": 1, "last_index_stats": 1,
             "agent_access": 1},
        ))
        docs = [d for d in docs
                if not d.get("agent_access") or
                (agent_num and agent_num in d["agent_access"])]
        return {
            "sources": [
                {
                    "id": str(d["_id"]),
                    "name": d["name"],
                    "type": d["type"],
                    "file_count": (d.get("last_index_stats") or {}).get("file_count", 0),
                }
                for d in docs
            ]
        }

    try:
        _id = ObjectId(source_id)
    except Exception:
        raise HTTPException(400, "source_id 格式錯誤")
    src = knowledge_sources_col.find_one({"_id": _id, "enabled": True})
    if not src:
        raise HTTPException(404, "資料源不存在或已停用")

    agent_num = _resolve_agent_num(request, conversation_id)
    if src.get("agent_access") and (not agent_num or agent_num not in src["agent_access"]):
        raise HTTPException(403, f"此資料源未開放給 #{agent_num} 助手")

    base = os.path.realpath(src["path"])
    target = os.path.realpath(os.path.join(base, project)) if project else base
    try:
        common = os.path.commonpath([base, target])
    except ValueError:
        raise HTTPException(403, "路徑越界")
    if common != base:
        raise HTTPException(403, "路徑越界(symlink 或 ../ 逃逸)")
    if not os.path.isdir(target):
        raise HTTPException(404, "資料夾不存在")

    excludes = src.get("exclude_patterns", [])
    entries = []
    try:
        for name in sorted(os.listdir(target)):
            if name.startswith("."):
                continue
            rel = os.path.relpath(os.path.join(target, name), base)
            if _path_is_excluded(rel, excludes):
                continue
            full = os.path.join(target, name)
            is_dir = os.path.isdir(full)
            entries.append({
                "name": name,
                "rel_path": rel,
                "is_dir": is_dir,
                "size": os.path.getsize(full) if not is_dir else None,
            })
    except PermissionError as e:
        # R10#1 · 不洩漏 OS error 訊息 / 實體路徑(原行為)
        logger.warning("[knowledge] list permission denied · src=%s · %s", source_id, e)
        raise HTTPException(403, "資料夾讀取權限不足")

    return {
        "source_id": source_id,
        "source_name": src["name"],
        "rel_path": project or "",
        "entries": entries,
    }


@router.get("/knowledge/read")
def knowledge_read(
    source_id: str,
    rel_path: str,
    request: Request,
    conversation_id: Optional[str] = None,
):
    """讀某 source 內某檔的 metadata + 抽字內容

    安全:path traversal 強制 · agent_access 白名單 · audit log
    ROADMAP §10.3 · agent_num 改 server-side derive
    """
    from main import knowledge_sources_col, knowledge_audit_col
    try:
        _id = ObjectId(source_id)
    except Exception:
        raise HTTPException(400, "source_id 格式錯誤")
    src = knowledge_sources_col.find_one({"_id": _id, "enabled": True})
    if not src:
        raise HTTPException(404, "資料源不存在或已停用")

    agent_num = _resolve_agent_num(request, conversation_id)
    if src.get("agent_access") and (not agent_num or agent_num not in src["agent_access"]):
        raise HTTPException(403, f"此資料源未開放給 #{agent_num} 助手")

    base = os.path.realpath(src["path"])
    abs_path = os.path.realpath(os.path.join(base, rel_path))
    try:
        common = os.path.commonpath([base, abs_path])
    except ValueError:
        raise HTTPException(403, "路徑越界")
    if common != base:
        raise HTTPException(403, "路徑越界(symlink 或 ../ 逃逸)")
    if not os.path.isfile(abs_path):
        raise HTTPException(404, "檔案不存在或不是檔案")

    if _path_is_excluded(rel_path, src.get("exclude_patterns", [])):
        raise HTTPException(403, "此檔案在排除清單內")

    size = os.path.getsize(abs_path)
    max_size = src.get("max_size_mb", 50) * 1024 * 1024
    if size > max_size:
        raise HTTPException(413, f"檔案超過 {src.get('max_size_mb', 50)}MB 上限")

    # Audit log · fail-closed(Codex Round 10.5 紅 · PDPA)
    user_email = (request.headers.get("X-User-Email") or "").strip().lower() or None
    try:
        knowledge_audit_col.insert_one({
            "user": user_email,
            "agent": agent_num,
            "source_id": source_id,
            "rel_path": rel_path,
            "size": size,
            "created_at": datetime.utcnow(),
        })
    except Exception as e:
        logger.error("[knowledge] audit log fail · 擋讀取(fail-closed): %s", e)
        raise HTTPException(
            503,
            "Audit log 服務暫時不可用 · 為 PDPA 合規暫停讀取 · 請找 Champion 或 Sterio",
        )

    extracted = extract_file(abs_path)
    mime, _ = mimetypes.guess_type(abs_path)
    return {
        "source_id": source_id,
        "source_name": src["name"],
        "rel_path": rel_path,
        "filename": os.path.basename(abs_path),
        "size": size,
        "mime": mime or "application/octet-stream",
        "modified_at": datetime.fromtimestamp(
            os.path.getmtime(abs_path)
        ).isoformat(),
        **{k: v for k, v in extracted.items()
           if k not in ("path", "filename", "size", "modified_at")},
    }


@router.get("/knowledge/search")
def knowledge_search(
    q: str = Query(min_length=2),
    source_id: Optional[str] = None,
    project: Optional[str] = None,
    conversation_id: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    request: Request = None,
):
    """全文搜尋 · 經 Meili · source_id / project 可過濾"""
    meili = _get_meili_client()
    if not meili:
        return {
            "query": q,
            "hits": [],
            "estimatedTotalHits": 0,
            "message": "搜尋服務未啟用 · 請管理員檢查 Meili",
        }
    result = knowledge_indexer.search(meili, q, source_id=source_id, project=project, limit=limit)

    agent_num = _resolve_agent_num(request, conversation_id)
    if isinstance(result, dict) and result.get("hits"):
        forbidden_ids = _agent_forbidden_sources(agent_num)
        if forbidden_ids:
            original = len(result["hits"])
            result["hits"] = [h for h in result["hits"]
                              if h.get("source_id") not in forbidden_ids]
            removed = original - len(result["hits"])
            if removed:
                result["filtered_for_agent"] = removed
    return result

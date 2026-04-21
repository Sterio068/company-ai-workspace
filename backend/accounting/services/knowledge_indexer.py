"""
知識庫增量索引器 · V1.1-SPEC §E-2
=====================================
每日凌晨 02:00 cron 跑 · 遍歷所有 enabled knowledge_sources · 各別增量 index 到 Meili
所有 source 共用一個 Meili index `chengfu_knowledge` · 透過 filterableAttributes 區隔

- 增量:比對 last_indexed_at · 只處理 mtime 之後的檔
- 排除:source.exclude_patterns + dir 結尾 / 斜線
- 限制:max_size_mb + mime_whitelist
- 失敗:單檔出錯 continue · 記 errors 計數

本模組只接 db + meili_client 參數 · 不 import main.py(services/__init__.py 設計原則)
"""
import os
import fnmatch
import hashlib
import pathlib
import logging
from datetime import datetime
from bson import ObjectId

from .knowledge_extract import extract

logger = logging.getLogger("chengfu.indexer")

MEILI_INDEX_NAME = "chengfu_knowledge"

# Meili index 設定(idempotent)· 索引不存在時會自動建
MEILI_SETTINGS = {
    "searchableAttributes": [
        "filename", "content_preview", "project", "source_name",
    ],
    "filterableAttributes": [
        "source_id", "source_name", "project", "type",
    ],
    "sortableAttributes": ["modified_at"],
}


def _match_excluded(rel_path: str, patterns: list[str]) -> bool:
    """支援:*.log(basename fnmatch) / /sensitive/*(目錄前綴)"""
    name = os.path.basename(rel_path)
    for p in patterns or []:
        if p.startswith("/"):
            if rel_path.startswith(p.lstrip("/").rstrip("*").rstrip("/")):
                return True
        elif fnmatch.fnmatch(name, p) or fnmatch.fnmatch(rel_path, p):
            return True
    return False


def _doc_id_for(source_id: str, rel_path: str) -> str:
    """Meili 文件 id · source_id + rel_path 決定唯一性 · 同檔修改 id 不變(覆蓋索引)"""
    return hashlib.md5(f"{source_id}::{rel_path}".encode()).hexdigest()


def _submit_and_wait(index, docs: list, meili_client, timeout_s: int = 60) -> bool:
    """Codex Round 10.5 fix · 真的等 Meili indexing 成功才算成功

    add_documents 只是 enqueue · 回 task uid · 之後可能 failed(例如 schema 衝突)
    我們要 poll 該 task 直到 succeeded/failed · 才能決定 search 進度是否前進

    Returns
    -------
    True  · task succeeded · 可前進 last_search_indexed_at
    False · 任一錯 · 下次 cron 會重試(因為 last_search_indexed_at 不動)
    """
    if not index or not docs:
        return True  # 空批 · 視為成功
    try:
        task_info = index.add_documents(docs)
    except Exception as e:
        logger.error("[indexer] Meili add_documents fail: %s", e)
        return False
    # task_info 可能是 TaskInfo object or dict · 取 uid
    task_uid = getattr(task_info, "task_uid", None) or getattr(task_info, "taskUid", None)
    if task_uid is None and isinstance(task_info, dict):
        task_uid = task_info.get("taskUid") or task_info.get("task_uid")
    if task_uid is None:
        # 舊 Meili client 不回 task · 只能賭 · log 警告
        logger.warning("[indexer] add_documents 未回 task_uid · 無法確認 · 假成功")
        return True
    # Poll task status
    try:
        result = meili_client.wait_for_task(task_uid, timeout_in_ms=timeout_s * 1000)
        status = getattr(result, "status", None) or (
            result.get("status") if isinstance(result, dict) else None
        )
        if status == "succeeded":
            return True
        logger.error(
            "[indexer] Meili task %s status=%s · error=%s",
            task_uid, status,
            getattr(result, "error", None) or (result.get("error") if isinstance(result, dict) else None),
        )
        return False
    except Exception as e:
        logger.error("[indexer] wait_for_task %s fail: %s", task_uid, e)
        return False


def _ensure_index(meili_client):
    """確保 index 存在、primaryKey 正確、settings 套用 · idempotent

    Meili 有個陷阱:第一次 update_settings 會 auto-create 無 primaryKey 的 index
    之後 add_documents 會因「多個 *_id 欄位」失敗(id / source_id 候選衝突)
    所以要先 explicit create_index(primaryKey='id') · 再 update_settings
    """
    try:
        # 先檢查 index 是否已存在且有 primary key
        info = meili_client.index(MEILI_INDEX_NAME).fetch_info()
        pk = getattr(info, "primary_key", None)
    except Exception:
        info, pk = None, None

    if info is None:
        # 不存在 · 建立(帶 primary key)
        meili_client.create_index(MEILI_INDEX_NAME, {"primaryKey": "id"})
    elif pk is None:
        # 存在但沒 primary key(先前 auto-create 的產物)· 砍掉重建
        logger.warning("[indexer] index %s 沒 primaryKey · 重建", MEILI_INDEX_NAME)
        meili_client.delete_index(MEILI_INDEX_NAME)
        meili_client.create_index(MEILI_INDEX_NAME, {"primaryKey": "id"})

    index = meili_client.index(MEILI_INDEX_NAME)
    index.update_settings(MEILI_SETTINGS)
    return index


def reindex_source(source_id: str, knowledge_sources_col, meili_client=None) -> dict:
    """對單一 source 增量索引。

    Parameters
    ----------
    source_id : str · MongoDB ObjectId string
    knowledge_sources_col : pymongo Collection
    meili_client : meilisearch.Client · None 則只抽字不上 Meili(測試用)

    Returns
    -------
    dict · {ok/skipped, file_count, index_seconds, errors, skipped_reasons}
    """
    try:
        _id = ObjectId(source_id)
    except Exception:
        return {"ok": False, "reason": f"source_id 格式錯誤: {source_id}"}

    src = knowledge_sources_col.find_one({"_id": _id})
    if not src:
        return {"ok": False, "reason": "資料源不存在"}
    if not src.get("enabled"):
        return {"ok": False, "skipped": True, "reason": "已停用"}

    started = datetime.utcnow()
    # Round 9 Q4 · 兩階段時間戳(拆 scanned 與 search_indexed)
    # - last_scanned_at · 最近一次抽字到本地(即使 Meili 掛也前進)
    # - last_search_indexed_at · 最近一次成功寫入 Meili(搜尋可用)
    #
    # 增量 threshold 選擇:
    # (a) 帶 Meili → 用 last_search_indexed_at · Meili 掛過的檔會被補跑
    # (b) 不帶 Meili(cron 沒配 / test 模式) → 用 last_scanned_at 避免重跑抽字
    # (c) 舊 source(只有 last_indexed_at legacy) → 當 scanned 的 fallback
    last_scanned = src.get("last_scanned_at")
    last_search = src.get("last_search_indexed_at")
    legacy = src.get("last_indexed_at")

    import calendar
    def _to_epoch(dt):
        if not isinstance(dt, datetime):
            return 0
        # TZ · datetime.utcnow() 是 naive · .timestamp() 被當 local 轉 → 8h 偏差
        # 精度 · Mongo 存 datetime 只保 ms · st_mtime 有 μs · int 化對齊
        return calendar.timegm(dt.utctimetuple())

    if meili_client is not None:
        # (a) 用 search 進度 · 這樣 Meili 掛過的檔會自動補跑
        # 注意:若 last_search 從未成功 · 就從 0 開始(不 fallback 到 scanned/legacy)
        #       這正是 Q4 的核心 · 強迫 Meili 補齊所有檔
        if isinstance(last_search, datetime):
            since_mtime = _to_epoch(last_search)
        else:
            since_mtime = 0  # Meili 從沒成功過 · 重跑所有檔
    else:
        # (b) 純抽字模式 · 用 scanned 避免重跑(沒 Meili 需求就不浪費抽字)
        if isinstance(last_scanned, datetime):
            since_mtime = _to_epoch(last_scanned)
        elif isinstance(legacy, datetime):
            since_mtime = _to_epoch(legacy)
        else:
            since_mtime = 0

    excludes = src.get("exclude_patterns", [])
    mime_white = src.get("mime_whitelist")  # None = 全收
    max_bytes = int(src.get("max_size_mb", 50)) * 1024 * 1024

    # Meili 若失敗(例如 key 錯)不擋索引流程 · 還是抽字 + 更新 last_indexed_at
    index = None
    meili_error = None
    if meili_client:
        try:
            index = _ensure_index(meili_client)
        except Exception as e:
            meili_error = f"{type(e).__name__}: {str(e)[:120]}"
            logger.warning("[indexer] Meili unavailable · continuing without search: %s", meili_error)

    docs_batch: list[dict] = []
    file_count = 0
    errors = 0
    skipped_excluded = 0
    skipped_unchanged = 0
    skipped_too_big = 0
    skipped_mime = 0

    base = src["path"]
    if not os.path.isdir(base):
        return {
            "ok": False,
            "reason": f"路徑不存在或不可讀: {base}",
        }

    for root, dirs, files in os.walk(base):
        # 修剪目錄 · 別走進排除的
        dirs[:] = [
            d for d in dirs
            if not _match_excluded(
                os.path.relpath(os.path.join(root, d), base),
                excludes,
            )
        ]
        for f in files:
            path = os.path.join(root, f)
            rel = os.path.relpath(path, base)
            if _match_excluded(rel, excludes):
                skipped_excluded += 1
                continue
            try:
                stat = os.stat(path)
            except OSError:
                errors += 1
                continue
            # 增量:只處理 mtime 之後 · file mtime 也 int 化(mongomock/Mongo 截 ms 精度)
            if int(stat.st_mtime) <= since_mtime:
                skipped_unchanged += 1
                continue
            if stat.st_size > max_bytes:
                skipped_too_big += 1
                continue
            ext = pathlib.Path(f).suffix.lower().lstrip(".")
            if mime_white and ext not in [w.lower().lstrip(".") for w in mime_white]:
                skipped_mime += 1
                continue

            try:
                doc = extract(path)
            except Exception as e:
                logger.warning("[indexer] extract fail %s: %s", path, e)
                errors += 1
                continue
            if doc.get("type") == "error":
                errors += 1
                # 還是 index 進去 · 讓使用者看得到「這檔讀失敗」
            # 衍生欄位給 Meili
            doc["id"] = _doc_id_for(str(src["_id"]), rel)
            doc["source_id"] = str(src["_id"])
            doc["source_name"] = src["name"]
            doc["rel_path"] = rel
            # 自動推 project · 若結構是 projects/<案>/...
            parts = rel.split(os.sep)
            if len(parts) > 1 and parts[0] == "projects":
                doc["project"] = parts[1]
            else:
                doc["project"] = None

            docs_batch.append(doc)
            file_count += 1

            # 批次送 Meili · 避免單次 payload 太大
            # Codex Round 10.5 fix · add_documents 只是 enqueue · 要 wait_for_task 才算真入
            if index and len(docs_batch) >= 200:
                task_ok = _submit_and_wait(index, docs_batch, meili_client)
                if not task_ok:
                    errors += len(docs_batch)
                docs_batch = []

    # flush 最後一批
    if index and docs_batch:
        task_ok = _submit_and_wait(index, docs_batch, meili_client)
        if not task_ok:
            errors += len(docs_batch)

    # Q4 · 三種情境:
    # (a) 沒給 meili_client(cron / 測試沒配)· 不計搜尋進度 · 但 scanned 仍前進
    # (b) 給了但 _ensure_index fail(key 錯 / Meili down)· scanned 前進但 search 不進
    # (c) 正常 · 兩個都前進
    meili_configured = meili_client is not None
    meili_succeeded = bool(index) and (file_count == 0 or errors < file_count)

    stats = {
        "ok": True,
        "file_count": file_count,
        "index_seconds": round((datetime.utcnow() - started).total_seconds(), 2),
        "errors": errors,
        "skipped": {
            "excluded": skipped_excluded,
            "unchanged": skipped_unchanged,
            "too_big": skipped_too_big,
            "wrong_mime": skipped_mime,
        },
        "meili": "indexed" if meili_succeeded else ("unavailable" if meili_error else "not_configured"),
    }
    if meili_error:
        stats["meili_error"] = meili_error

    # Q4 · 寫回兩階段時間戳
    now = datetime.utcnow()
    update_doc = {
        "last_scanned_at": now,  # scanning 永遠前進(抽字已跑)
        "last_index_stats": stats,
    }
    if meili_configured and meili_succeeded:
        # 有 Meili 且寫成功 → search 進度前進
        update_doc["last_search_indexed_at"] = now
        update_doc["last_indexed_at"] = now  # legacy 同步
        stats["search_progress_advanced"] = True
    elif meili_configured and not meili_succeeded:
        # 有 Meili 但掛了 → search 不進 · legacy 退守到舊 search 時間
        stats["search_progress_advanced"] = False
        update_doc["last_indexed_at"] = last_search or legacy
        logger.warning(
            "[indexer] source=%s · Meili 寫入失敗 · 下次 cron 會重試此批",
            src["name"],
        )
    else:
        # 沒給 Meili(cron/test 模式 · 不期望搜尋) → legacy 前進
        update_doc["last_indexed_at"] = now
        stats["search_progress_advanced"] = None  # 不適用

    knowledge_sources_col.update_one({"_id": src["_id"]}, {"$set": update_doc})
    logger.info(
        "[indexer] source=%s · files=%d · errors=%d · took=%.1fs · meili=%s",
        src["name"], file_count, errors, stats["index_seconds"],
        "ok" if meili_succeeded else ("n/a" if not meili_configured else "lag"),
    )
    return stats


def reindex_all(knowledge_sources_col, meili_client=None) -> dict:
    """cron 入口 · 所有 enabled sources 各跑一輪"""
    results = {}
    for src in knowledge_sources_col.find({"enabled": True}):
        sid = str(src["_id"])
        try:
            results[src["name"]] = reindex_source(sid, knowledge_sources_col, meili_client)
        except Exception as e:
            logger.exception("[indexer] reindex_all %s fail", src.get("name"))
            results[src["name"]] = {"ok": False, "reason": str(e)}
    return results


def delete_source_from_index(source_id: str, meili_client) -> dict:
    """source 被刪時 · 從 Meili 清掉所有該 source 的文件"""
    if not meili_client:
        return {"ok": False, "reason": "meili not configured"}
    try:
        index = meili_client.index(MEILI_INDEX_NAME)
        # Meili 支援 delete_documents(filter="...")
        task = index.delete_documents(filter=f'source_id = "{source_id}"')
        return {"ok": True, "task_uid": getattr(task, "task_uid", None)}
    except Exception as e:
        logger.warning("[indexer] Meili cleanup fail %s: %s", source_id, e)
        return {"ok": False, "reason": str(e)}


def search(meili_client, q: str, source_id: str = None, project: str = None,
           limit: int = 20) -> dict:
    """給 main.py /knowledge/search 用的包裝"""
    if not meili_client:
        return {"hits": [], "estimatedTotalHits": 0,
                "message": "Meili 未配置"}
    filters = []
    if source_id:
        filters.append(f'source_id = "{source_id}"')
    if project:
        filters.append(f'project = "{project}"')
    try:
        index = meili_client.index(MEILI_INDEX_NAME)
        return index.search(q, {
            "limit": max(1, min(100, limit)),
            "filter": " AND ".join(filters) if filters else None,
            "attributesToRetrieve": [
                "id", "filename", "rel_path", "source_id", "source_name",
                "project", "type", "content_preview", "modified_at",
            ],
        })
    except Exception as e:
        logger.warning("[indexer] search fail: %s", e)
        return {"hits": [], "estimatedTotalHits": 0,
                "message": f"搜尋失敗:{type(e).__name__}"}

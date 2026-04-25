"""
Admin · 系統自動更新 endpoints(v1.3 vNext · 對應 scripts/update.sh)

4 個 endpoint:
- GET  /admin/update/status   讀 reports/update-status.json(check-update.sh 寫的)
- POST /admin/update/check    立即觸發 check-update.sh(不更新 · 只看)
- POST /admin/update/run      觸發 update.sh --yes --json(背景跑 · 回 task_id)
- GET  /admin/update/run/{task_id}  · 看背景 task 進度(stream output)
- POST /admin/update/rollback 回滾(payload: target sha 或 previous)
- GET  /admin/update/history  讀 reports/update-history.jsonl

設計決策:
- 用 BackgroundTasks 跑 update.sh · 避免 HTTP timeout
- task 進度寫到 /tmp/chengfu-update-task-{id}.log · GET 讀
- single-instance lock 由 update.sh 自己管(/tmp/chengfu-update.lock)
- rollback 必須帶 confirm_target sha · 防 mis-click
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import subprocess
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .._deps import require_admin_dep


router = APIRouter(tags=["admin"])
logger = logging.getLogger("chengfu")


# ============================================================
# Path 設定 · 容器內 vs 本機 dev
# ============================================================
def _project_root() -> pathlib.Path:
    """容器內 = /app/.. · 本機 = repo root"""
    candidates = [
        pathlib.Path("/host/chengfu"),  # docker volume mount(若有)
        pathlib.Path(__file__).parent.parent.parent.parent.parent,  # backend/accounting/routers/admin/update.py → repo
    ]
    for p in candidates:
        if (p / "scripts" / "update.sh").exists():
            return p
    return candidates[-1]  # fallback


def _scripts_dir() -> pathlib.Path:
    return _project_root() / "scripts"


def _reports_dir() -> pathlib.Path:
    p = _project_root() / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _tasks_dir() -> pathlib.Path:
    p = pathlib.Path("/tmp/chengfu-update-tasks")
    p.mkdir(parents=True, exist_ok=True)
    return p


# ============================================================
# Models
# ============================================================
class UpdateRunRequest(BaseModel):
    confirm: bool = False  # 必須 true · 防 mis-click


class UpdateRollbackRequest(BaseModel):
    target: str  # commit sha · 或 "previous"
    confirm_target: str  # 必須等於 target · 防誤刪
    reason: str = "manual"


# ============================================================
# Helpers
# ============================================================
def _read_status() -> dict:
    """讀 check-update.sh 寫的 status JSON"""
    status_file = _reports_dir() / "update-status.json"
    if not status_file.exists():
        return {
            "status": "unknown",
            "message": "從未檢查過 · 請先 POST /admin/update/check",
            "checked_at": None,
        }
    try:
        return json.loads(status_file.read_text(encoding="utf-8"))
    except Exception as e:
        return {"status": "error", "message": f"status JSON 損壞:{e}"}


def _read_history(limit: int = 20) -> list[dict]:
    """讀 update.sh / rollback.sh 寫的 history JSONL"""
    history_file = _reports_dir() / "update-history.jsonl"
    if not history_file.exists():
        return []
    items = []
    try:
        with open(history_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.warning(f"讀 history 失敗:{e}")
        return []
    # 最新在前
    return list(reversed(items))[:limit]


def _run_check_sync() -> dict:
    """同步跑 check-update.sh · 回最新 status"""
    script = _scripts_dir() / "check-update.sh"
    if not script.exists():
        raise HTTPException(500, f"找不到 {script}")
    try:
        subprocess.run(
            ["bash", str(script), "--quiet"],
            cwd=_project_root(),
            timeout=30,
            capture_output=True,
            text=True,
            check=False,  # 不檢 returncode · 失敗也要回 status
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "check-update.sh 超過 30 秒 · 網路慢?")
    return _read_status()


def _run_update_background(task_id: str):
    """BackgroundTask · 跑 update.sh --yes --json · output 寫 task log"""
    script = _scripts_dir() / "update.sh"
    log_file = _tasks_dir() / f"{task_id}.log"
    meta_file = _tasks_dir() / f"{task_id}.json"

    # 開始 · 寫 meta
    meta_file.write_text(json.dumps({
        "task_id": task_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
    }, ensure_ascii=False), encoding="utf-8")

    try:
        with open(log_file, "w", encoding="utf-8") as fh:
            proc = subprocess.run(
                ["bash", str(script), "--yes", "--json"],
                cwd=_project_root(),
                stdout=fh,
                stderr=subprocess.STDOUT,
                timeout=600,  # 10 min · docker rebuild + health check
                check=False,
            )
        # 完成 · 解析最後 1 行 JSON(update.sh stdout 最後 emit_json 結果)
        last_json = {}
        try:
            log_text = log_file.read_text(encoding="utf-8")
            for line in reversed(log_text.strip().split("\n")):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    last_json = json.loads(line)
                    break
        except Exception:
            pass
        meta_file.write_text(json.dumps({
            "task_id": task_id,
            "started_at": json.loads(meta_file.read_text(encoding="utf-8"))["started_at"],
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "done" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "result": last_json,
        }, ensure_ascii=False), encoding="utf-8")
    except subprocess.TimeoutExpired:
        meta_file.write_text(json.dumps({
            "task_id": task_id,
            "status": "timeout",
            "message": "update.sh 超過 10 分鐘 · 自動殺",
        }, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        meta_file.write_text(json.dumps({
            "task_id": task_id,
            "status": "exception",
            "message": str(e)[:500],
        }, ensure_ascii=False), encoding="utf-8")


# ============================================================
# Endpoints
# ============================================================
@router.get("/admin/update/status")
def update_status(_admin: str = require_admin_dep()):
    """讀目前是否有新版可更新 · check-update.sh 每日 03:00 寫的"""
    status = _read_status()
    history = _read_history(limit=5)
    return {
        "status": status,
        "recent_history": history,
        "current_commit": _get_current_commit(),
    }


@router.post("/admin/update/check")
def trigger_check(_admin: str = require_admin_dep()):
    """立即跑一次 check-update.sh · 取代等隔天 cron · 同步回 status"""
    status = _run_check_sync()
    return {"status": status, "checked_now": True}


@router.post("/admin/update/run")
def trigger_update(
    payload: UpdateRunRequest,
    background_tasks: BackgroundTasks,
    _admin: str = require_admin_dep(),
):
    """背景觸發 update.sh · 回 task_id · 前端 poll /run/{task_id}

    payload.confirm 必須 true · 防誤觸
    """
    if not payload.confirm:
        raise HTTPException(400, "必須帶 confirm=true")

    # 先 sanity check · 確認真的有新版可更
    status = _read_status()
    if status.get("status") not in ("available",):
        # 可能是 up_to_date / unknown / error · 強制再 check 一次
        status = _run_check_sync()
        if status.get("status") != "available":
            raise HTTPException(
                409,
                f"目前狀態 {status.get('status')} · {status.get('message', '')} · 沒新版可更"
            )

    task_id = uuid.uuid4().hex[:12]
    background_tasks.add_task(_run_update_background, task_id)
    return {
        "task_id": task_id,
        "started": True,
        "poll_url": f"/admin/update/run/{task_id}",
        "estimated_seconds": 90,
        "note": "更新中 · 期間 Web UI 會短暫斷線(約 30 秒)",
    }


@router.get("/admin/update/run/{task_id}")
def get_task_progress(task_id: str, _admin: str = require_admin_dep()):
    """看背景 update task 進度"""
    # 防 path traversal · 只接受 hex
    if not all(c in "0123456789abcdef" for c in task_id) or len(task_id) > 64:
        raise HTTPException(400, "invalid task_id")

    meta_file = _tasks_dir() / f"{task_id}.json"
    log_file = _tasks_dir() / f"{task_id}.log"

    if not meta_file.exists():
        raise HTTPException(404, f"task {task_id} 不存在 · 可能還沒 spawn 或已過期")

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    log_tail = ""
    if log_file.exists():
        # 只回最後 4KB · 防 1MB 一次回
        try:
            with open(log_file, "rb") as fh:
                fh.seek(0, 2)
                size = fh.tell()
                fh.seek(max(0, size - 4096))
                log_tail = fh.read().decode("utf-8", errors="replace")
        except Exception:
            pass

    return {
        "meta": meta,
        "log_tail": log_tail,
    }


@router.get("/admin/update/run/{task_id}/log", response_class=PlainTextResponse)
def get_task_log(task_id: str, _admin: str = require_admin_dep()):
    """看完整 task log(plain text · 給 admin debug)"""
    if not all(c in "0123456789abcdef" for c in task_id) or len(task_id) > 64:
        raise HTTPException(400, "invalid task_id")
    log_file = _tasks_dir() / f"{task_id}.log"
    if not log_file.exists():
        raise HTTPException(404, "log 不存在")
    return log_file.read_text(encoding="utf-8")


@router.post("/admin/update/rollback")
def trigger_rollback(
    payload: UpdateRollbackRequest,
    background_tasks: BackgroundTasks,
    _admin: str = require_admin_dep(),
):
    """回滾到指定 sha 或上一個成功 update 之前

    payload.target = sha 或 "previous"
    payload.confirm_target 必須等於 payload.target(防 mis-click)
    """
    target = payload.target.strip()
    confirm = payload.confirm_target.strip()
    if target != confirm:
        raise HTTPException(400, "confirm_target 不匹配 · 防 mis-click")

    if target == "previous":
        cmd = ["bash", str(_scripts_dir() / "rollback.sh"), "--previous", "--yes",
               "--reason", payload.reason]
    else:
        # 驗證 sha 格式 · 7-64 hex
        if not all(c in "0123456789abcdef" for c in target.lower()) \
           or not (7 <= len(target) <= 64):
            raise HTTPException(400, "target 不像 git sha")
        cmd = ["bash", str(_scripts_dir() / "rollback.sh"),
               "--to", target, "--yes",
               "--reason", payload.reason]

    task_id = uuid.uuid4().hex[:12]

    def _run():
        log_file = _tasks_dir() / f"{task_id}.log"
        meta_file = _tasks_dir() / f"{task_id}.json"
        meta_file.write_text(json.dumps({
            "task_id": task_id,
            "action": "rollback",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }, ensure_ascii=False), encoding="utf-8")
        try:
            with open(log_file, "w", encoding="utf-8") as fh:
                proc = subprocess.run(cmd, cwd=_project_root(),
                                      stdout=fh, stderr=subprocess.STDOUT,
                                      timeout=300, check=False)
            meta_file.write_text(json.dumps({
                "task_id": task_id,
                "action": "rollback",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "status": "done" if proc.returncode == 0 else "failed",
                "returncode": proc.returncode,
            }, ensure_ascii=False), encoding="utf-8")
        except subprocess.TimeoutExpired:
            meta_file.write_text(json.dumps({
                "task_id": task_id,
                "action": "rollback",
                "status": "timeout",
            }, ensure_ascii=False), encoding="utf-8")

    background_tasks.add_task(_run)
    return {
        "task_id": task_id,
        "started": True,
        "poll_url": f"/admin/update/run/{task_id}",
        "target": target,
    }


@router.get("/admin/update/history")
def update_history(
    limit: int = Query(default=20, ge=1, le=200),
    _admin: str = require_admin_dep(),
):
    """讀 update / rollback 歷史"""
    return {"items": _read_history(limit=limit)}


def _get_current_commit() -> dict:
    """讀本機 git HEAD"""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_project_root(),
            capture_output=True, text=True, timeout=5, check=False,
        )
        full = proc.stdout.strip()
        if not full:
            return {"sha": None, "short": None, "date": None}
        proc2 = subprocess.run(
            ["git", "log", "-1", "--format=%ci"],
            cwd=_project_root(),
            capture_output=True, text=True, timeout=5, check=False,
        )
        return {
            "sha": full,
            "short": full[:7],
            "date": proc2.stdout.strip() or None,
        }
    except Exception as e:
        return {"sha": None, "short": None, "date": None, "error": str(e)[:200]}

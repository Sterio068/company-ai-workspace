"""
NotebookLM Source Pack renderer.

Local MongoDB remains the source of truth.  A source pack is a deterministic,
reviewable Markdown snapshot that can be stored locally, copied manually, or
sent to NotebookLM Enterprise as raw text.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException


def _workspace_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "knowledge-base").exists() or (parent / "frontend").exists():
            return parent
    return Path("/app")


def _doc_dir(env_name: str, fallback: Path) -> Path:
    configured = os.getenv(env_name, "").strip()
    if configured:
        return Path(configured)
    return fallback


WORKSPACE_ROOT = _workspace_root()
COMPANY_DOC_DIR = _doc_dir("SOURCE_PACK_COMPANY_DIR", WORKSPACE_ROOT / "knowledge-base" / "company")
TRAINING_DOC_DIR = _doc_dir("SOURCE_PACK_TRAINING_DIR", WORKSPACE_ROOT / "frontend" / "launcher" / "user-guide")


def _escape_md(value: Any) -> str:
    text = str(value or "").strip()
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _fmt_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date().isoformat()
    return str(value or "")


def _money(value: Any) -> int:
    try:
        return int(round(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _percent(value: Any) -> str:
    try:
        return f"{round(float(value or 0), 2):g}"
    except (TypeError, ValueError):
        return "0"


def _project_oid(project_id: str) -> ObjectId:
    try:
        return ObjectId(project_id)
    except (InvalidId, TypeError):
        raise HTTPException(400, "project_id 格式錯誤")


def _append_list(lines: list[str], title: str, items: list[str]):
    lines.append(f"## {title}")
    if not items:
        lines.append("- 尚無資料")
        lines.append("")
        return
    for item in items:
        lines.append(f"- {_escape_md(item)}")
    lines.append("")


def _project_access_query(project_id: str, email: str, is_admin: bool) -> dict:
    q = {"_id": _project_oid(project_id)}
    if not is_admin:
        q["$or"] = [
            {"owner": email},
            {"collaborators": email},
            {"next_owner": email},
        ]
    return q


def _render_handoff(lines: list[str], handoff: dict):
    lines.append("## 交棒卡")
    lines.append(f"- 目標:{_escape_md(handoff.get('goal') or '尚未填寫')}")
    _append_list(lines, "限制與注意事項", handoff.get("constraints") or [])
    next_actions = list(handoff.get("next_actions") or [])
    for action in handoff.get("meeting_next_actions") or []:
        if action not in next_actions:
            next_actions.append(action)
    _append_list(lines, "下一步", next_actions)
    refs = []
    for ref in (handoff.get("asset_refs") or []) + (handoff.get("site_asset_refs") or []):
        refs.append(f"{ref.get('label') or '素材'} · {ref.get('ref') or ''}".strip())
    _append_list(lines, "素材與參考", refs)


def _render_meetings(lines: list[str], meetings: list[dict]):
    lines.append("## 會議速記摘要")
    if not meetings:
        lines.append("- 尚無已完成會議摘要")
        lines.append("")
        return
    for m in meetings:
        s = m.get("structured") or {}
        lines.append(f"### {s.get('title') or '未命名會議'}")
        lines.append(f"- 建立時間:{_fmt_dt(m.get('created_at'))}")
        if s.get("decisions"):
            lines.append("- 決議:")
            for item in s.get("decisions") or []:
                lines.append(f"  - {_escape_md(item)}")
        if s.get("action_items"):
            lines.append("- 待辦:")
            for a in s.get("action_items") or []:
                due = f" · 期限 {a.get('due')}" if a.get("due") else ""
                lines.append(f"  - {_escape_md(a.get('what'))} · {_escape_md(a.get('who') or '未指派')}{due}")
        if s.get("key_numbers"):
            lines.append("- 關鍵數字:")
            for n in s.get("key_numbers") or []:
                lines.append(f"  - {_escape_md(n.get('label'))}:{_escape_md(n.get('value'))}")
        lines.append("")


def _render_site_surveys(lines: list[str], surveys: list[dict]):
    lines.append("## 場勘摘要")
    if not surveys:
        lines.append("- 尚無已完成場勘")
        lines.append("")
        return
    for survey in surveys:
        s = survey.get("structured") or {}
        venue = s.get("venue") or {}
        lines.append(f"### 場勘 {_fmt_dt(survey.get('created_at'))}")
        lines.append(f"- 場地:{_escape_md(venue.get('type') or '未辨識')} · {_escape_md(venue.get('size_estimate') or '')}")
        lines.append(f"- 照片:{survey.get('image_count', 0)} 張")
        if s.get("entrances"):
            lines.append(f"- 入口:{'、'.join(map(_escape_md, s.get('entrances') or []))}")
        if s.get("issues"):
            lines.append("- 問題:")
            for issue in s.get("issues") or []:
                lines.append(f"  - {_escape_md(issue)}")
        lines.append("")


def _render_accounting(lines: list[str], finance: Optional[dict]):
    lines.append("## 專案財務摘要")
    if not finance:
        lines.append("- 尚無專案財務資料")
        lines.append("")
        return
    lines.extend([
        f"- 收入:NT$ {_money(finance.get('income')):,.0f}",
        f"- 支出:NT$ {_money(finance.get('expense')):,.0f}",
        f"- 毛利:NT$ {_money(finance.get('margin')):,.0f}",
        f"- 毛利率:{_percent(finance.get('margin_rate'))}%",
        "",
    ])


def build_project_pack(db, project_id: str, email: str, is_admin: bool, max_items: int = 20) -> dict:
    project = db.projects.find_one(_project_access_query(project_id, email, is_admin))
    if not project:
        if db.projects.find_one({"_id": _project_oid(project_id)}, {"_id": 1}):
            raise HTTPException(403, "只能同步自己負責或協作中的工作包")
        raise HTTPException(404, "工作包不存在")

    title = f"工作包 · {project.get('name') or project_id}"
    lines = [
        f"# {title}",
        "",
        "> 這是由本地資料庫產生的 NotebookLM 資料包。NotebookLM 是衍生知識庫,本地 MongoDB 仍是唯一主資料庫。",
        "",
        "## 基本資料",
        f"- 客戶:{_escape_md(project.get('client'))}",
        f"- 預算:NT$ {project.get('budget') or 0:,.0f}",
        f"- 截止日:{_escape_md(project.get('deadline'))}",
        f"- 狀態:{_escape_md(project.get('status'))}",
        "",
    ]
    _render_handoff(lines, project.get("handoff") or {})

    meetings = list(db.meetings.find({
        "project_id": project_id,
        "status": "done",
    }, {"transcript": 0, "_tmp_audio_path": 0}).sort("created_at", -1).limit(max_items))
    _render_meetings(lines, meetings)

    surveys = list(db.site_surveys.find({
        "project_id": project_id,
        "status": "done",
    }, {"_tmp_image_paths": 0, "_tmp_mime_list": 0}).sort("created_at", -1).limit(max_items))
    _render_site_surveys(lines, surveys)

    finance = db.accounting_projects_finance.find_one({"project_id": project_id}, {"_id": 0})
    _render_accounting(lines, finance)

    return _pack(title, "project", lines, [{"type": "project", "id": project_id}])


def build_tenders_pack(db, email: str, is_admin: bool, max_items: int = 30) -> dict:
    del email, is_admin
    title = "商機雷達 · 標案與 CRM 摘要"
    alerts = list(db.tender_alerts.find({}).sort("discovered_at", -1).limit(max_items))
    leads = list(db.crm_leads.find({"source": "tender_alert"}).sort("updated_at", -1).limit(max_items))
    lines = [
        f"# {title}",
        "",
        "## 最新標案",
    ]
    if not alerts:
        lines.append("- 尚無標案監測資料")
    for t in alerts:
        lines.append(f"- [{_escape_md(t.get('status') or 'new')}] {_escape_md(t.get('title'))} · {_escape_md(t.get('unit_name'))} · 關鍵字:{_escape_md(t.get('keyword'))}")
    lines.extend(["", "## CRM 商機"])
    if not leads:
        lines.append("- 尚無由標案匯入的商機")
    for lead in leads:
        budget = f"NT$ {lead.get('budget', 0):,.0f}" if lead.get("budget") else "未填預算"
        lines.append(f"- {_escape_md(lead.get('title'))} · {_escape_md(lead.get('client'))} · {_escape_md(lead.get('stage'))} · {budget}")
    return _pack(title, "tenders", lines, [{"type": "tender_alerts"}, {"type": "crm_leads"}])


def build_docs_pack(kind: str, max_files: int = 20) -> dict:
    if kind == "company":
        title = "公司知識 · 品牌與 SOP"
        roots = [COMPANY_DOC_DIR]
    else:
        title = "教育訓練 · 使用教學"
        roots = [TRAINING_DOC_DIR]
    lines = [f"# {title}", ""]
    count = 0
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("*.md")):
            if count >= max_files:
                break
            try:
                content = path.read_text(encoding="utf-8")[:12000]
            except UnicodeDecodeError:
                continue
            lines.extend([f"## {path.name}", "", content.strip(), ""])
            count += 1
    if count == 0:
        lines.append("- 尚無可匯出的 Markdown 文件")
    return _pack(title, kind, lines, [{"type": "docs", "kind": kind, "count": count}])


def build_source_pack(db, scope: str, *, email: str, is_admin: bool, project_id: Optional[str] = None,
                      max_items: int = 20) -> dict:
    if scope == "project":
        if not project_id:
            raise HTTPException(400, "scope=project 必須提供 project_id")
        return build_project_pack(db, project_id, email, is_admin, max_items=max_items)
    if scope == "tenders":
        return build_tenders_pack(db, email, is_admin, max_items=max_items)
    if scope in {"company", "training"}:
        return build_docs_pack(scope, max_files=max_items)
    raise HTTPException(400, f"不支援的 source pack scope:{scope}")


def _pack(title: str, scope: str, lines: list[str], entities: list[dict]) -> dict:
    content = "\n".join(lines).strip() + "\n"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return {
        "title": title,
        "scope": scope,
        "content_md": content,
        "content_hash": content_hash,
        "source_entities": entities,
        "word_count": len(content.split()),
        "char_count": len(content),
    }

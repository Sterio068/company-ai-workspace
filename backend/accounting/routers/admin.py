"""
Admin router · ROADMAP §11.1 B-7 · 從 main.py 抽出(13 endpoint · ~500 行)

涵蓋:
- /admin/dashboard · 一頁式總覽
- /admin/demo-data DELETE · 清 seed 示範資料
- /admin/export GET · streaming JSON
- /admin/import POST · append 匯入
- /admin/audit-log GET/POST · 維運查
- /admin/email/send POST · SMTP @_limiter 20/hour
- /admin/send-monthly-report POST · cron 每月觸發
- /admin/monthly-report GET · 月度營運報告
- /admin/cost · /admin/adoption · /admin/librechat-contract · /admin/budget-status
- /admin/top-users · /admin/tender-funnel · /admin/ocr/reprobe
- /admin/agent-prompts GET/POST/DELETE · 線上調 prompt

設計決策:
- /admin/sources/* 已在 routers/knowledge.py(B-6 跟 knowledge 一起搬)
- /quota/check + /quota/preflight 留在 main.py(nginx auth_request 直連 · slowapi 緊耦合)
- 全部 helpers / settings lazy import from main · 跟 knowledge router 同 pattern
"""
import os
import json
import logging
import pathlib
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


def _parse_date_boundary(raw: str, *, end: bool = False) -> datetime:
    """R18 · audit-log 日期 parser · 容忍 YYYY-MM-DD 或完整 ISO datetime
    原本 f"{start_date}T00:00:00" 若 raw 已含 T 會變 T..T 導致 ValueError 500
    """
    s = raw.strip().replace("Z", "+00:00")
    try:
        if "T" in s:
            return datetime.fromisoformat(s)
        d = date.fromisoformat(s)
        return datetime.combine(d, datetime.max.time() if end else datetime.min.time())
    except ValueError:
        raise HTTPException(422, "date must be YYYY-MM-DD or ISO datetime")

from ._deps import require_admin_dep


router = APIRouter(tags=["admin"])
logger = logging.getLogger("chengfu")


# ============================================================
# Models
# ============================================================
class ImportData(BaseModel):
    """資料匯入 · 從另一台機還原 · 或接受夥伴公司資料"""
    accounts: list = []
    projects: list = []
    transactions: list = []
    invoices: list = []
    quotes: list = []


class EmailNotification(BaseModel):
    to: str
    subject: str
    body: str
    body_type: Literal["text", "html"] = "text"


class AgentPromptUpdate(BaseModel):
    agent_num: str  # "00" - "09"
    new_instructions: str
    reason: str
    editor: str


# ============================================================
# Helper · 從 monthly_report 推 action_items
# ============================================================
def _generate_action_items(feedbacks: list) -> list[dict]:
    """從回饋推導改進建議 · 簡單版 · v1.5 接 Claude 深度分析"""
    items = []
    downs = [f for f in feedbacks if f.get("verdict") == "down"]
    by_agent = {}
    for f in downs:
        by_agent.setdefault(f.get("agent_name", "unknown"), []).append(f)

    for agent, fs in by_agent.items():
        if len(fs) >= 3:
            items.append({
                "agent": agent,
                "issue": f"本月 👎 回饋 {len(fs)} 次",
                "suggestion": "檢視 Agent instructions 並調整 · 或新增 Skill",
                "priority": "high" if len(fs) >= 5 else "medium",
            })
    return items


# ============================================================
# D · Dashboard
# ============================================================
@router.get("/admin/dashboard")
def admin_dashboard(_admin: str = require_admin_dep()):
    """一頁式承富 AI 系統總覽"""
    from main import (
        pnl_report, projects_col, feedback_col, convos_col,
    )
    from routers.feedback import _compute_feedback_stats

    today = date.today()
    month_start = today.replace(day=1).isoformat()
    today_str = today.isoformat()

    pnl = pnl_report(month_start, today_str)
    active_projects = projects_col.count_documents({"status": "active"})
    total_projects = projects_col.count_documents({})
    fb_stats = _compute_feedback_stats()
    total_feedback = feedback_col.count_documents({})
    up_count = feedback_col.count_documents({"verdict": "up"})

    try:
        total_convos = convos_col.count_documents({})
        month_convos = convos_col.count_documents({
            "createdAt": {"$gte": datetime.fromisoformat(month_start + "T00:00:00")}
        })
    except Exception:
        total_convos = 0
        month_convos = 0

    return {
        "as_of": datetime.now().isoformat(),
        "accounting": {
            "month_income": pnl["total_income"],
            "month_expense": pnl["total_expense"],
            "month_net": pnl["net_profit"],
        },
        "projects": {
            "active": active_projects,
            "total": total_projects,
        },
        "feedback": {
            "total": total_feedback,
            "up": up_count,
            "satisfaction_rate": round(up_count / total_feedback * 100, 1) if total_feedback else 0,
            "by_agent": fb_stats,
        },
        "conversations": {
            "total": total_convos,
            "this_month": month_convos,
        },
    }


@router.delete("/admin/demo-data")
def clear_demo_data(_admin: str = require_admin_dep()):
    """清除 seed-demo-data.py 建立的示範資料(正式上線前必跑)"""
    from main import db
    result = {
        "projects": db.projects.delete_many({"_demo": True}).deleted_count,
        "transactions": db.accounting_transactions.delete_many({"_demo": True}).deleted_count,
        "invoices": db.accounting_invoices.delete_many({"_demo": True}).deleted_count,
        "quotes": db.accounting_quotes.delete_many({"_demo": True}).deleted_count,
        "feedback": db.feedback.delete_many({"_demo": True}).deleted_count,
        "tender_alerts": db.tender_alerts.delete_many({"_demo": True}).deleted_count,
    }
    return {"cleared": result, "total": sum(result.values())}


# ============================================================
# 資料匯出 / 匯入(合規 + 遷移)
# ============================================================
@router.get("/admin/export")
def export_all_data(_admin: str = require_admin_dep()):
    """一鍵匯出 · ROADMAP §11.14 · streaming JSON 不全 list memory"""
    from main import (
        accounts_col, transactions_col, invoices_col, quotes_col,
        projects_col, feedback_col, db, serialize,
    )

    def _stream():
        yield '{"exported_at":"' + datetime.now(timezone.utc).isoformat() + '",'
        yield '"version":"v1.0","collections":{'
        first_col = True
        cols = [
            ("accounts", accounts_col),
            ("transactions", transactions_col),
            ("invoices", invoices_col),
            ("quotes", quotes_col),
            ("projects", projects_col),
            ("feedback", feedback_col),
            ("tender_alerts", db.tender_alerts),
        ]
        for name, col in cols:
            if not first_col:
                yield ","
            first_col = False
            yield f'"{name}":['
            first_doc = True
            for doc in col.find():
                if not first_doc:
                    yield ","
                first_doc = False
                yield json.dumps(serialize(doc), ensure_ascii=False, default=str)
            yield "]"
        yield "},"
        yield '"counts":' + json.dumps({
            name: col.count_documents({}) for name, col in cols
        }) + "}"

    return StreamingResponse(
        _stream(),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=chengfu-export-{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"},
    )


@router.post("/admin/import")
def import_data(payload: ImportData, _admin: str = require_admin_dep()):
    """從 JSON 匯入資料 · 不會覆蓋既有,只 append"""
    from main import (
        accounts_col, transactions_col, invoices_col, quotes_col, projects_col,
    )
    result = {}
    for name, col, docs in [
        ("accounts", accounts_col, payload.accounts),
        ("projects", projects_col, payload.projects),
        ("transactions", transactions_col, payload.transactions),
        ("invoices", invoices_col, payload.invoices),
        ("quotes", quotes_col, payload.quotes),
    ]:
        if not docs:
            result[name] = 0
            continue
        for d in docs:
            d.pop("_id", None)
        col.insert_many(docs)
        result[name] = len(docs)
    return {"imported": result}


# ============================================================
# Audit log · ROADMAP §11.9
# ============================================================
@router.get("/admin/cron-runs")
def list_cron_runs(
    script: Optional[str] = None,
    limit: int = Query(default=30, ge=1, le=200),
    _admin: str = require_admin_dep(),
):
    """R14#14 · admin 看 cron 成功紀錄 · 「昨天 digest 有跑?」一眼看

    產自 scripts/daily-digest.py 的 _record_cron_success()
    TTL 30 天自動清
    """
    from main import db, serialize
    q = {}
    if script: q["script"] = script
    cursor = db.cron_runs.find(q).sort("at", -1).limit(limit)
    items = serialize(list(cursor))
    return {"items": items, "count": len(items)}


@router.get("/admin/audit-log")
def audit_log(
    action: Optional[str] = None,
    user: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),  # R14#5 · 封頂 500
    skip: int = Query(default=0, ge=0),
    start_date: Optional[str] = None,  # YYYY-MM-DD
    end_date: Optional[str] = None,
    _admin: str = require_admin_dep(),
):
    """查 audit_log · admin 維運期
    R14#5 · 加 pagination + date range filter · 防一年百萬條全撈
    """
    from main import audit_col, serialize
    q = {}
    if action: q["action"] = action
    if user:   q["user"] = user
    # date range · R18 · 容忍 YYYY-MM-DD 或完整 ISO datetime
    if start_date or end_date:
        q["created_at"] = {}
        if start_date:
            q["created_at"]["$gte"] = _parse_date_boundary(start_date)
        if end_date:
            q["created_at"]["$lte"] = _parse_date_boundary(end_date, end=True)
    cursor = audit_col.find(q).sort("created_at", -1).skip(skip).limit(limit)
    items = serialize(list(cursor))
    total = audit_col.count_documents(q)
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": (skip + len(items)) < total,
    }


@router.post("/admin/audit-log")
def log_action(action: str, user: str, resource: Optional[str] = None,
               details: Optional[dict] = None, _admin: str = require_admin_dep()):
    """寫 audit · 給未來 Agent / orchestrator 寫敏感操作"""
    from main import audit_col
    audit_col.insert_one({
        "action": action,
        "user": user,
        "resource": resource,
        "details": details or {},
        "created_at": datetime.now(timezone.utc),
    })
    return {"logged": True}


# ============================================================
# Email 通知(月報 / 異常告警)
# ============================================================
def _send_email_internal(msg: EmailNotification) -> dict:
    """純 SMTP 邏輯 · 給 send_email endpoint 與 send_monthly_report 共用"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_host = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    smtp_user = os.getenv("EMAIL_USERNAME")
    smtp_pass = os.getenv("EMAIL_PASSWORD")
    from_addr = os.getenv("EMAIL_FROM", "ai@chengfu.com")
    from_name = os.getenv("EMAIL_FROM_NAME", "承富 AI 系統")

    if not smtp_user or not smtp_pass:
        raise HTTPException(503, "SMTP 未設定(EMAIL_USERNAME / EMAIL_PASSWORD)")

    m = MIMEMultipart()
    m["Subject"] = msg.subject
    m["From"] = f"{from_name} <{from_addr}>"
    m["To"] = msg.to
    m.attach(MIMEText(msg.body, msg.body_type, "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.send_message(m)
        return {"sent": True, "to": msg.to}
    except Exception as e:
        raise HTTPException(502, f"SMTP 失敗: {str(e)[:200]}")


def send_email(msg: EmailNotification, request: Request,
               _admin: str = require_admin_dep()):
    """透過 SMTP 寄 Email · Audit sec F-1 · 防 SMTP 帳號濫用 · 月報 + 警告夠用

    R11#1 · rate limit(20/hour)由 main.py register_rate_limited_routes 動態註冊
    原 `@router.post + _admin_router.send_email = wrap(...)` 假修 · @router.post 已 capture 原 fn
    """
    return _send_email_internal(msg)


# R11#1 · 真動態註冊 rate-limited route · 由 main.py wire 時呼叫
_EMAIL_ROUTES_REGISTERED = False


def register_rate_limited_routes(limit_decorator):
    """main.py 在 include_router 之前呼叫 · 把 send_email 包 rate limit 後註冊到 router

    R11#1 codex 抓 · @router.post 已 capture 原 fn · 後續 reassign module attr 無效
    解法:不用 @router.post 註冊 send_email · 改 add_api_route 動態加 wrapped 版
    """
    global _EMAIL_ROUTES_REGISTERED
    if _EMAIL_ROUTES_REGISTERED:
        return
    router.add_api_route(
        "/admin/email/send",
        limit_decorator(send_email),
        methods=["POST"],
    )
    _EMAIL_ROUTES_REGISTERED = True


@router.post("/admin/send-monthly-report")
def send_monthly_report_to_admin(_admin: str = require_admin_dep()):
    """產生月報 + 寄給 ADMIN_EMAIL · 可由 cron 每月 1 日觸發"""
    report = monthly_report()
    admin_email = os.getenv("ADMIN_EMAIL", "sterio@chengfu.local")

    body = f"""<html><body style="font-family: -apple-system, sans-serif;">
<h1>承富 AI 月報 · {report['month']}</h1>

<h2>💰 本月財務</h2>
<ul>
  <li>收入:NT$ {report['financial']['income']:,.0f}</li>
  <li>支出:NT$ {report['financial']['expense']:,.0f}</li>
  <li>淨利:NT$ {report['financial']['net']:,.0f}</li>
  <li>vs 上月淨利變化:NT$ {report['financial']['vs_prev_month']['net_change']:+,.0f}</li>
</ul>

<h2>👍 使用者回饋</h2>
<ul>
  <li>總回饋:{report['feedback']['total']} 筆</li>
  <li>👍 / 👎:{report['feedback']['up']} / {report['feedback']['down']}</li>
  <li>滿意度:{report['feedback']['satisfaction']}%</li>
  <li>主要讚美:{', '.join(str(x) for x in report['feedback']['top_praises'][:3])}</li>
  <li>主要投訴:{', '.join(str(x) for x in report['feedback']['top_complaints'][:3])}</li>
</ul>

<h2>🎯 行動建議</h2>
<ul>
{''.join([f"<li><b>{a.get('agent', '')}</b>:{a.get('issue', '')} - {a.get('suggestion', '')}</li>" for a in report['action_items']])}
</ul>

<hr>
<p style="color:#888;font-size:12px">承富 AI 系統自動產出 · 如需調整請聯繫 Sterio</p>
</body></html>"""

    _send_email_internal(EmailNotification(
        to=admin_email,
        subject=f"承富 AI 月報 · {report['month']}",
        body=body,
        body_type="html",
    ))
    return {"sent": True, "to": admin_email, "month": report["month"]}


@router.get("/admin/monthly-report")
def monthly_report(month: Optional[str] = None, _admin: str = require_admin_dep()):
    """月度營運報告 · 給老闆/Sterio 月底看

    R11#2 · 必須走 require_admin_dep · 不能用 Optional[str]=None
    原寫法:FastAPI 把 _admin 當 Optional query param · 攻擊者能 GET /admin/monthly-report 取得月報
    新寫法:Depends 強制 admin · 內部 send_monthly_report() 直接 call 仍 OK(Python 不檢查 Depends)
    """
    from main import pnl_report, feedback_col
    from routers.feedback import _compute_feedback_stats

    now = datetime.now()
    if month:
        y, m = map(int, month.split("-"))
    else:
        y, m = now.year, now.month

    month_start = date(y, m, 1).isoformat()
    next_m = date(y + (m // 12), (m % 12) + 1, 1)
    month_end = (next_m - timedelta(days=1)).isoformat()
    prev_start = date(y - (1 if m == 1 else 0), (m - 1 or 12), 1).isoformat()
    prev_end = (date(y, m, 1) - timedelta(days=1)).isoformat()

    current_pnl = pnl_report(month_start, month_end)
    prev_pnl = pnl_report(prev_start, prev_end)

    month_fb = list(feedback_col.find({
        "created_at": {"$gte": datetime.fromisoformat(f"{month_start}T00:00:00")}
    }))
    up_fb = [f for f in month_fb if f.get("verdict") == "up"]
    down_fb = [f for f in month_fb if f.get("verdict") == "down"]

    complaint_keywords = {}
    for f in down_fb:
        note = f.get("note", "") or ""
        for word in ["品質", "格式", "字數", "語氣", "錯字", "漏", "慢", "不對"]:
            if word in note:
                complaint_keywords[word] = complaint_keywords.get(word, 0) + 1

    praise_keywords = {}
    for f in up_fb:
        note = f.get("note", "") or ""
        for word in ["準", "清楚", "快", "省時", "精確", "完整"]:
            if word in note:
                praise_keywords[word] = praise_keywords.get(word, 0) + 1

    return {
        "month": f"{y}-{m:02d}",
        "period": {"from": month_start, "to": month_end},
        "financial": {
            "income": current_pnl["total_income"],
            "expense": current_pnl["total_expense"],
            "net": current_pnl["net_profit"],
            "vs_prev_month": {
                "income_change": round(current_pnl["total_income"] - prev_pnl["total_income"], 2),
                "net_change": round(current_pnl["net_profit"] - prev_pnl["net_profit"], 2),
            },
        },
        "feedback": {
            "total": len(month_fb),
            "up": len(up_fb),
            "down": len(down_fb),
            "satisfaction": round(len(up_fb) / len(month_fb) * 100, 1) if month_fb else None,
            "top_complaints": sorted(complaint_keywords.items(), key=lambda x: -x[1])[:5],
            "top_praises": sorted(praise_keywords.items(), key=lambda x: -x[1])[:5],
        },
        "agents": _compute_feedback_stats(),
        "action_items": _generate_action_items(month_fb),
    }


# ============================================================
# Admin / ROI / Quota endpoints · v5 重構(thin wrapper for admin_metrics service)
# Settings(_USD_TO_NTD / _MONTHLY_BUDGET_NTD / etc.)仍在 main · lazy import
# ============================================================
@router.get("/admin/cost")
def cost_summary(days: int = 30, _admin: str = require_admin_dep()):
    """粗估 API cost by model"""
    from main import db
    from services import admin_metrics
    return admin_metrics.cost_by_model(db, days)


@router.get("/admin/adoption")
def adoption_summary(days: int = 7, _admin: str = require_admin_dep()):
    """Codex Round 10.5 黃 6 · 支撐 BOSS-VIEW ROI 公式的 adoption 數字"""
    from main import db, _users_col, projects_col, feedback_col, _USD_TO_NTD
    from services import admin_metrics
    return admin_metrics.adoption_metrics(
        db, _users_col, projects_col, feedback_col,
        days=days, usd_to_ntd=_USD_TO_NTD,
    )


@router.get("/admin/librechat-contract")
def librechat_contract(_admin: str = require_admin_dep()):
    """升版後第一件事 · 驗 LibreChat 私有 schema 是否還相容"""
    from main import db
    from services import admin_metrics
    return admin_metrics.librechat_contract(db)


@router.post("/admin/ocr/reprobe")
def reprobe_ocr(_admin: str = require_admin_dep()):
    """Codex R2.5 · 不用重啟容器就能重試 OCR probe"""
    from services.knowledge_extract import reset_ocr_cache, probe_ocr_startup
    reset_ocr_cache()
    return probe_ocr_startup()


@router.get("/admin/budget-status")
def budget_status(_admin: str = require_admin_dep()):
    """本月預算進度 · 給 Launcher 首頁進度條 + email 預警用"""
    from main import db, _MONTHLY_BUDGET_NTD, _USD_TO_NTD
    from services import admin_metrics
    return admin_metrics.budget_status(db, _MONTHLY_BUDGET_NTD, _USD_TO_NTD)


@router.get("/admin/top-users")
def top_users(days: int = 30, limit: int = 10, _admin: str = require_admin_dep()):
    """Top N 用量同仁"""
    from main import db, _users_col, _USER_SOFT_CAP_DEFAULT, _USD_TO_NTD
    from services import admin_metrics
    return admin_metrics.top_users(db, _users_col, days, limit,
                                   _USER_SOFT_CAP_DEFAULT, _USD_TO_NTD)


@router.get("/admin/tender-funnel")
def tender_funnel(_admin: str = require_admin_dep()):
    """本月標案漏斗"""
    from main import db
    from services import admin_metrics
    return admin_metrics.tender_funnel(db)


# ============================================================
# Agent Playground(admin 線上調 Agent prompt · 不用改 JSON)
# ============================================================
@router.get("/admin/agent-prompts")
def list_agent_prompts(_admin: str = require_admin_dep()):
    """列出所有 10 Agent 的當前 prompt"""
    from main import db
    presets_dir = pathlib.Path("/app/presets") if pathlib.Path("/app/presets").exists() \
                  else pathlib.Path(__file__).parent.parent.parent.parent / "config-templates" / "presets"
    agents = []
    if presets_dir.exists():
        for f in sorted(presets_dir.glob("0*.json")):
            try:
                data = json.load(open(f))
                override = db.agent_overrides.find_one({"agent_num": f.stem.split("-")[0]})
                agents.append({
                    "agent_num": f.stem.split("-")[0],
                    "title": data.get("title"),
                    "model": data.get("model"),
                    "instructions_original": data.get("promptPrefix", "")[:500] + "...",
                    "instructions_original_full": data.get("promptPrefix", ""),
                    "override": override.get("new_instructions") if override else None,
                    "override_at": override.get("created_at") if override else None,
                })
            except Exception:
                pass
    return agents


@router.post("/admin/agent-prompts")
def update_agent_prompt(payload: AgentPromptUpdate, _admin: str = require_admin_dep()):
    """線上更新 Agent prompt(寫 override collection · 不動原 JSON)"""
    from main import db, audit_col
    # R31 修 · email 一律 lower · PDPA exact-match 才不漏
    editor_lc = (payload.editor or "").strip().lower()
    db.agent_overrides.update_one(
        {"agent_num": payload.agent_num},
        {"$set": {
            "new_instructions": payload.new_instructions,
            "reason": payload.reason,
            "editor": editor_lc,
            "created_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    audit_col.insert_one({
        "action": "agent_prompt_update",
        "user": editor_lc,
        "resource": f"agent_{payload.agent_num}",
        "details": {"reason": payload.reason, "length": len(payload.new_instructions)},
        "created_at": datetime.now(timezone.utc),
    })
    return {"updated": True, "note": "變更已記錄,執行 create-agents.py --only <num> 即可生效"}


@router.delete("/admin/agent-prompts/{agent_num}")
def revert_agent_prompt(agent_num: str, _admin: str = require_admin_dep()):
    """還原 Agent prompt 為原始 JSON 版"""
    from main import db
    r = db.agent_overrides.delete_one({"agent_num": agent_num})
    return {"reverted": r.deleted_count > 0}


# ============================================================
# Secrets 管理 · 前端 Admin UI 設 API key(寫 Mongo system_settings)
# ============================================================
# 每個 secret 的 metadata(顯示 / 申請連結 / 能否前端寫)
SECRETS_META = {
    "ANTHROPIC_API_KEY": {
        "label": "Anthropic API Key",
        "desc": "Claude 模型 · 必須 · Tier 2 預存 USD $50",
        "console_url": "https://console.anthropic.com/settings/keys",
        "frontend_writable": False,  # LibreChat 讀 .env · 改 Keychain 才生效
        "source": ".env + macOS Keychain",
        "required": True,
    },
    "OPENAI_API_KEY": {
        "label": "OpenAI API Key",
        "desc": "設計助手生圖(gpt-image-2)+ STT 語音轉文字(選配)",
        "console_url": "https://platform.openai.com/api-keys",
        "frontend_writable": True,  # v1.2 加 · accounting design router 用 · 不影響 LibreChat .env STT
        "source": "Mongo system_settings(可前端改)· STT 另走 .env",
        "required": False,
    },
    "FAL_API_KEY": {
        "label": "Fal.ai API Key",
        "desc": "設計助手生圖(Recraft v3)· 承富 Q7 一次 3 張",
        "console_url": "https://fal.ai/dashboard/keys",
        "frontend_writable": True,  # 存 Mongo · design router 讀取
        "source": "Mongo system_settings(可前端改)",
        "required": False,
    },
    "IMAGE_PROVIDER": {
        "label": "生圖 Provider",
        "desc": "選 'fal'(Recraft v3 · NT$ 4 / 3 張)或 'openai'(gpt-image-2 · NT$ 20 / 3 張)",
        "console_url": "",
        "frontend_writable": True,  # admin 可切換
        "source": "Mongo system_settings(可前端改)· 預設 fal",
        "required": False,
    },
    "EMAIL_USERNAME": {
        "label": "SMTP Username",
        "desc": "月報自動寄信用(選配)",
        "console_url": "",
        "frontend_writable": False,
        "source": ".env",
        "required": False,
    },
    "EMAIL_PASSWORD": {
        "label": "SMTP Password",
        "desc": "SMTP 密碼 · Gmail 用 App Password · 不是本密碼",
        "console_url": "https://myaccount.google.com/apppasswords",
        "frontend_writable": False,
        "source": ".env + macOS Keychain",
        "required": False,
    },
    "JWT_REFRESH_SECRET": {
        "label": "JWT Refresh Secret",
        "desc": "認證 cookie 用 · prod 必設 · 跟 LibreChat .env 同步",
        "console_url": "",
        "frontend_writable": False,
        "source": "macOS Keychain(install 時自動產)",
        "required": True,
    },
    "ECC_INTERNAL_TOKEN": {
        "label": "ECC Internal Token",
        "desc": "cron → accounting admin endpoint 用 · prod 必設",
        "console_url": "",
        "frontend_writable": False,
        "source": "macOS Keychain(install 時自動產)",
        "required": True,
    },
    "MEILI_MASTER_KEY": {
        "label": "Meilisearch Master Key",
        "desc": "全文搜尋 index 管理 · 承富 Day 0 後不該改",
        "console_url": "",
        "frontend_writable": False,
        "source": "macOS Keychain(install 時自動產)",
        "required": True,
    },
}


def _get_secret_value(name: str) -> Optional[str]:
    """先試 Mongo system_settings · 再 fallback env(LibreChat / launch 來的)"""
    from main import db
    try:
        doc = db.system_settings.find_one({"name": name})
        if doc and doc.get("value"):
            return doc["value"]
    except Exception:
        pass
    return os.getenv(name, "") or None


@router.get("/admin/secrets/status")
def secrets_status(_admin: str = require_admin_dep()):
    """回所有 secret 的狀態 · 不回值(只看有沒設)"""
    result = []
    for name, meta in SECRETS_META.items():
        value = _get_secret_value(name)
        is_set = bool(value and not value.startswith("<"))
        result.append({
            "name": name,
            "label": meta["label"],
            "desc": meta["desc"],
            "console_url": meta["console_url"],
            "frontend_writable": meta["frontend_writable"],
            "source": meta["source"],
            "required": meta["required"],
            "is_set": is_set,
            "preview": (value[:8] + "..." + value[-4:]) if (is_set and len(value) > 12) else ("(已設)" if is_set else "(未設)"),
        })
    return {"secrets": result, "total": len(result), "set_count": sum(1 for s in result if s["is_set"])}


class SecretUpdate(BaseModel):
    value: str


@router.post("/admin/secrets/{name}")
def update_secret(name: str, payload: SecretUpdate, _admin: str = require_admin_dep()):
    """只允許前端改 FAL_API_KEY 等 frontend_writable · 其他走 Keychain

    寫入 Mongo system_settings · design router 下次 request lazy 讀
    """
    from main import db, audit_col
    meta = SECRETS_META.get(name)
    if not meta:
        raise HTTPException(404, f"未知的 secret:{name}")
    if not meta["frontend_writable"]:
        raise HTTPException(
            403,
            f"{name} 不能前端改 · 需走 macOS Keychain + 重啟容器 · "
            f"見 {meta.get('source', '...')}"
        )
    value = (payload.value or "").strip()
    if not value:
        # 空值 → 刪除
        db.system_settings.delete_one({"name": name})
        audit_col.insert_one({
            "action": "secret_clear",
            "user": _admin,
            "resource": name,
            "created_at": datetime.now(timezone.utc),
        })
        return {"cleared": True, "name": name}
    db.system_settings.update_one(
        {"name": name},
        {"$set": {
            "name": name,
            "value": value,
            "updated_at": datetime.now(timezone.utc),
            "updated_by": _admin,
        }},
        upsert=True,
    )
    audit_col.insert_one({
        "action": "secret_update",
        "user": _admin,
        "resource": name,
        "details": {"length": len(value)},
        "created_at": datetime.now(timezone.utc),
    })
    return {"updated": True, "name": name, "note": "下次 request 生效(不用重啟容器)"}


# ============================================================
# 技術債#5(2026-04-23)· PDPA / GDPR 17 條 · 同仁離職全資料刪除
# ============================================================
class PdpaDeleteRequest(BaseModel):
    confirm_email: str  # admin 必須 type 一次完整 email · 防 mis-click
    dry_run: bool = True  # 預設 dry_run · 真刪要 explicit false


@router.post("/admin/users/{user_email}/delete-all")
def pdpa_delete_user(user_email: str, payload: PdpaDeleteRequest,
                     _admin: str = require_admin_dep()):
    """PDPA 17 條 · 同仁離職 / 自願刪除請求 · 把該 user 跨 collection 全刪

    跨 collection 範圍(承富 v1.2 + R29 補):
    刪除類(該 user 私有資料):
    - user_preferences(line_token / webhook_url / agent prefs)
    - feedback(該 user 的 thumbs up/down)
    - meetings(該 user 上傳的會議速記)
    - site_surveys(該 user 拍的場勘照片 metadata)
    - scheduled_posts(author = user_email)
    - knowledge_audit(user 搜的 audit log)
    - chengfu_quota_overrides(若有)
    - design_jobs(R29 補 · user 欄 · prompt + 圖檔 reference)
    - agent_overrides(R29 補 · admin 為該 user 客製 prompt)

    切人關聯類(資料屬公司 · 只切 user 識別):
    - crm_leads(owner=None · lead 屬公司業務)
    - media_pitch_history(R29 補 · pitched_by=None · pitch 紀錄屬公司)
    - media_contacts(R29 補 · created_by=None · 媒體名單屬公司)

    保留類(法規要求保留):
    - audit_log / main audit_col(操作 audit · PDPA 第 11 條保留)

    安全護欄:
    1. require admin · 不開放自助
    2. confirm_email 必須等於 user_email(防 mis-click 刪錯人)
    3. dry_run=true 只算 count · 不真刪
    4. dry_run=false 真刪 + 寫 audit 不可改
    5. admin 不能刪自己(防誤操作 lock 自己出去)
    """
    from main import db, _admin_allowlist

    if payload.confirm_email.strip().lower() != user_email.strip().lower():
        raise HTTPException(400, "confirm_email 不匹配 · 防 mis-click · 請 type 一次完整 email")

    if user_email.strip().lower() == _admin.strip().lower():
        raise HTTPException(400, "admin 不能刪自己 · 請另一位 admin 操作")

    target = user_email.strip().lower()
    # 自查補:audit 寫 main.audit_col(=db.audit_log)· 跟其他 admin 操作一致
    # 原本誤用 db.knowledge_audit · /admin/audit-log 看不到 PDPA 紀錄
    from main import audit_col
    import re

    # R31 修 · case-insensitive · legacy 資料可能存大小寫混合(Leaving@ChengFu.Local)
    # 用 regex 完整匹配 + 不含 . 的 escape · 防 admin 名含特殊字元誤判
    def ci(field_value: str):
        """Case-insensitive 完整 match · 防 legacy mixed-case 漏"""
        return {"$regex": f"^{re.escape(field_value)}$", "$options": "i"}

    target_ci = ci(target)

    # 刪除類 · collection → query
    delete_targets = [
        ("user_preferences", {"user_email": target_ci}),
        ("feedback", {"user_email": target_ci}),
        ("meetings", {"owner": target_ci}),
        ("site_surveys", {"owner": target_ci}),
        ("scheduled_posts", {"author": target_ci}),
        ("knowledge_audit", {"user": target_ci}),
        ("chengfu_quota_overrides", {"email": target_ci}),
        ("design_jobs", {"user": target_ci}),       # R29 補
        ("agent_overrides", {"user_email": target_ci}),  # R29 補(若 admin 有為該 user 客製)
    ]

    # 切人關聯類 · collection → (query, $set patch)
    # R30 補 · 把所有殘留 target email 的欄位全清(法規洞)
    unset_targets = [
        ("crm_leads", {"owner": target_ci}, {"owner": None}),
        ("media_pitch_history", {"pitched_by": target_ci}, {"pitched_by": None}),  # R29 補
        ("media_contacts", {"created_by": target_ci}, {"created_by": None}),       # R29 補
        # R30 補 · 7 個漏網欄位
        ("knowledge_sources", {"created_by": target_ci}, {"created_by": None}),
        ("projects", {"owner": target_ci}, {"owner": None}),
        ("projects", {"handoff.updated_by": target_ci}, {"handoff.updated_by": None}),
        ("crm_stage_history", {"changed_by": target_ci}, {"changed_by": None}),
        ("agent_overrides", {"editor": target_ci}, {"editor": None}),
        ("system_settings", {"updated_by": target_ci}, {"updated_by": None}),
        # R31 補 · tender_alerts.reviewed_by(同事 review 標案 Go/No-Go 的紀錄)
        ("tender_alerts", {"reviewed_by": target_ci}, {"reviewed_by": None}),
    ]

    counts = {}
    for col_name, q in delete_targets:
        col = db[col_name]
        if payload.dry_run:
            counts[col_name] = col.count_documents(q)
        else:
            r = col.delete_many(q)
            counts[col_name] = r.deleted_count

    for col_name, q, patch in unset_targets:
        col = db[col_name]
        # 多筆 unset 同 collection 不同欄位 · key 用 col + 欄位
        field = next(iter(q.keys()))
        key = f"{col_name}_unset_{field.replace('.', '_')}"
        if payload.dry_run:
            counts[key] = col.count_documents(q)
        else:
            r = col.update_many(q, {"$set": patch})
            counts[key] = r.modified_count

    # R30 補 · crm_leads.notes[].by 是 array element
    # R31 修 · 優先用 Mongo $[n] arrayFilters atomic · 防同時新增 note race
    # mongomock 不支援 NotImplementedError 才 fallback Python
    notes_q = {"notes.by": target_ci}
    if payload.dry_run:
        counts["crm_leads_notes_by_unset"] = db.crm_leads.count_documents(notes_q)
    else:
        try:
            r = db.crm_leads.update_many(
                notes_q,
                {"$set": {"notes.$[n].by": None}},
                array_filters=[{"n.by": target_ci}],
            )
            counts["crm_leads_notes_by_unset"] = r.modified_count
        except NotImplementedError:
            # mongomock fallback · 整 notes 覆寫(test 環境用 · 沒 race)
            affected = list(db.crm_leads.find(notes_q, {"_id": 1, "notes": 1}))
            modified = 0
            for lead in affected:
                new_notes = [
                    {**n, "by": None}
                    if n.get("by", "").lower() == target else n
                    for n in (lead.get("notes") or [])
                ]
                db.crm_leads.update_one(
                    {"_id": lead["_id"]}, {"$set": {"notes": new_notes}}
                )
                modified += 1
            counts["crm_leads_notes_by_unset"] = modified

    # 寫 audit · 不論 dry_run 都記
    audit_col.insert_one({
        "action": "pdpa_delete" if not payload.dry_run else "pdpa_delete_dryrun",
        "user": _admin,
        "resource": target,
        "details": counts,
        "created_at": datetime.now(timezone.utc),
    })

    return {
        "user_email": target,
        "dry_run": payload.dry_run,
        "counts": counts,
        "total": sum(counts.values()),
        "note": ("dry_run · 沒真刪 · 確認後 dry_run=false 重打"
                 if payload.dry_run else "已刪 · 不可恢復 · audit 已紀錄"),
        # R30 補 · 提醒 LibreChat 對話資料是另一個 DB · 此 endpoint 不碰
        "librechat_warning": (
            "此操作不刪 LibreChat 對話紀錄(MongoDB librechat DB)· "
            "如需清對話 · 走 docs/05-SECURITY.md §人員異動 流程 · "
            "或 mongo shell:db.conversations.deleteMany({user:'<user_id>'})"
        ),
    }

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
from datetime import datetime, date, timedelta
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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
        yield '{"exported_at":"' + datetime.utcnow().isoformat() + '",'
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
        headers={"Content-Disposition": f"attachment; filename=chengfu-export-{datetime.utcnow().strftime('%Y%m%d')}.json"},
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
@router.get("/admin/audit-log")
def audit_log(action: Optional[str] = None,
    user: Optional[str] = None,
    limit: int = 100, _admin: str = require_admin_dep()):
    """查 audit_log · 給 admin 維運期手動 curl 用"""
    from main import audit_col, serialize
    q = {}
    if action: q["action"] = action
    if user:   q["user"] = user
    return serialize(list(audit_col.find(q).sort("created_at", -1).limit(limit)))


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
        "created_at": datetime.utcnow(),
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
    db.agent_overrides.update_one(
        {"agent_num": payload.agent_num},
        {"$set": {
            "new_instructions": payload.new_instructions,
            "reason": payload.reason,
            "editor": payload.editor,
            "created_at": datetime.utcnow(),
        }},
        upsert=True,
    )
    audit_col.insert_one({
        "action": "agent_prompt_update",
        "user": payload.editor,
        "resource": f"agent_{payload.agent_num}",
        "details": {"reason": payload.reason, "length": len(payload.new_instructions)},
        "created_at": datetime.utcnow(),
    })
    return {"updated": True, "note": "變更已記錄,執行 create-agents.py --only <num> 即可生效"}


@router.delete("/admin/agent-prompts/{agent_num}")
def revert_agent_prompt(agent_num: str, _admin: str = require_admin_dep()):
    """還原 Agent prompt 為原始 JSON 版"""
    from main import db
    r = db.agent_overrides.delete_one({"agent_num": agent_num})
    return {"reverted": r.deleted_count > 0}

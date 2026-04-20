"""
承富 AI · 統一後端服務 FastAPI
========================================
整合承富所有非對話資料 · MongoDB 儲存 · 對接 LibreChat / Launcher / Agents

模組:
  A. 會計:科目、交易、發票、報價、專案財務、應收應付、報表
  B. 專案:團隊共享專案管理(取代 localStorage)
  C. 回饋:👍👎 集中收集 + 分析
  D. 管理:成本/品質/使用儀表板、異常告警
  E. 安全:Level 03 內容分級檢查、簡易 RBAC
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, date
from enum import Enum
import os
from pymongo import MongoClient
from bson import ObjectId

# ============================================================
# MongoDB
# ============================================================
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/chengfu")
client = MongoClient(MONGO_URI)
db = client.get_default_database()

# Collections
accounts_col = db.accounting_accounts
transactions_col = db.accounting_transactions
invoices_col = db.accounting_invoices
quotes_col = db.accounting_quotes
projects_finance_col = db.accounting_projects_finance
projects_col = db.projects
feedback_col = db.feedback
audit_col = db.audit_log
convos_col = db.conversations  # LibreChat 的 collection · 只讀

# ============================================================
# App
# ============================================================
app = FastAPI(
    title="承富會計 API",
    description="承富 AI 系統 · 內建會計模組",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # nginx 代理後端所以 OK
    allow_methods=["*"],
    allow_headers=["*"],
)

# Orchestrator(v2.0 · 主管家跨 Agent 呼叫)
try:
    from orchestrator import router as orchestrator_router
    app.include_router(orchestrator_router)
except ImportError:
    pass  # httpx 未裝時不啟用

# ============================================================
# Helpers
# ============================================================
def serialize(doc):
    """ObjectId → str."""
    if not doc:
        return doc
    if isinstance(doc, list):
        return [serialize(d) for d in doc]
    if isinstance(doc, dict):
        return {k: (str(v) if isinstance(v, ObjectId) else
                    serialize(v) if isinstance(v, (dict, list)) else v)
                for k, v in doc.items()}
    return doc

# ============================================================
# 台灣預設會計科目(一次性 seed)
# ============================================================
DEFAULT_ACCOUNTS = [
    # 資產
    {"code": "1101", "name": "現金",            "type": "asset"},
    {"code": "1102", "name": "銀行存款",         "type": "asset"},
    {"code": "1108", "name": "零用金",          "type": "asset"},
    {"code": "1181", "name": "應收帳款",         "type": "asset"},
    {"code": "1281", "name": "存出保證金",       "type": "asset"},
    {"code": "1611", "name": "生財設備",         "type": "asset"},
    # 負債
    {"code": "2101", "name": "應付帳款",         "type": "liability"},
    {"code": "2161", "name": "代收款項",         "type": "liability"},
    {"code": "2199", "name": "應付稅捐",         "type": "liability"},
    # 權益
    {"code": "3101", "name": "資本",            "type": "equity"},
    {"code": "3301", "name": "本期損益",         "type": "equity"},
    # 收入
    {"code": "4111", "name": "服務收入",         "type": "income"},
    {"code": "4118", "name": "其他營業收入",      "type": "income"},
    # 費用
    {"code": "5101", "name": "外包支出",         "type": "expense"},
    {"code": "5201", "name": "場地費",           "type": "expense"},
    {"code": "5202", "name": "設備租賃",         "type": "expense"},
    {"code": "5203", "name": "餐飲費",           "type": "expense"},
    {"code": "5204", "name": "交通費",           "type": "expense"},
    {"code": "5205", "name": "印刷費",           "type": "expense"},
    {"code": "5301", "name": "薪資支出",         "type": "expense"},
    {"code": "5302", "name": "勞健保費",         "type": "expense"},
    {"code": "5401", "name": "辦公室租金",       "type": "expense"},
    {"code": "5402", "name": "水電費",           "type": "expense"},
    {"code": "5403", "name": "軟體訂閱",         "type": "expense"},
    {"code": "5901", "name": "雜項費用",         "type": "expense"},
]


# ============================================================
# Models
# ============================================================
class AccountType(str, Enum):
    asset = "asset"
    liability = "liability"
    equity = "equity"
    income = "income"
    expense = "expense"


class Account(BaseModel):
    code: str
    name: str
    type: AccountType
    active: bool = True


class Transaction(BaseModel):
    date: str  # YYYY-MM-DD
    memo: str
    debit_account: str   # account code
    credit_account: str
    amount: float
    project_id: Optional[str] = None
    vendor: Optional[str] = None
    customer: Optional[str] = None
    tags: list[str] = []


class InvoiceItem(BaseModel):
    description: str
    quantity: float
    unit_price: float

    @property
    def subtotal(self):
        return self.quantity * self.unit_price


class Invoice(BaseModel):
    invoice_no: Optional[str] = None  # 自動產
    date: str
    customer: str
    customer_tax_id: Optional[str] = None  # 統編
    items: list[InvoiceItem]
    tax_included: bool = False  # 是否含稅報價
    tax_rate: float = 0.05  # 5%
    project_id: Optional[str] = None
    status: Literal["draft", "issued", "paid", "cancelled"] = "draft"
    notes: Optional[str] = None


class Quote(BaseModel):
    quote_no: Optional[str] = None
    date: str
    customer: str
    items: list[InvoiceItem]
    tax_included: bool = False
    tax_rate: float = 0.05
    valid_until: str
    project_id: Optional[str] = None
    status: Literal["draft", "sent", "accepted", "rejected", "expired"] = "draft"
    terms: Optional[str] = None


# ============================================================
# Endpoints · 科目
# ============================================================
@app.post("/accounts/seed")
def seed_accounts():
    """初始化預設科目(冪等)。"""
    created = 0
    for acc in DEFAULT_ACCOUNTS:
        if not accounts_col.find_one({"code": acc["code"]}):
            accounts_col.insert_one({**acc, "active": True, "created_at": datetime.utcnow()})
            created += 1
    return {"seeded": created, "total": accounts_col.count_documents({})}


@app.get("/accounts")
def list_accounts(type: Optional[AccountType] = None):
    q = {"active": True}
    if type:
        q["type"] = type.value
    return serialize(list(accounts_col.find(q).sort("code", 1)))


@app.post("/accounts")
def create_account(acc: Account):
    if accounts_col.find_one({"code": acc.code}):
        raise HTTPException(400, f"科目編號 {acc.code} 已存在")
    r = accounts_col.insert_one({**acc.dict(), "created_at": datetime.utcnow()})
    return {"id": str(r.inserted_id)}


# ============================================================
# Endpoints · 交易
# ============================================================
@app.post("/transactions")
def create_transaction(tx: Transaction):
    for code in [tx.debit_account, tx.credit_account]:
        if not accounts_col.find_one({"code": code}):
            raise HTTPException(400, f"科目 {code} 不存在")
    data = tx.dict()
    data["created_at"] = datetime.utcnow()
    r = transactions_col.insert_one(data)
    # 更新專案財務
    if tx.project_id:
        _update_project_finance(tx.project_id)
    return {"id": str(r.inserted_id)}


@app.get("/transactions")
def list_transactions(
    project_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
):
    q = {}
    if project_id:
        q["project_id"] = project_id
    if date_from or date_to:
        q["date"] = {}
        if date_from: q["date"]["$gte"] = date_from
        if date_to:   q["date"]["$lte"] = date_to
    return serialize(list(transactions_col.find(q).sort("date", -1).limit(limit)))


@app.delete("/transactions/{tx_id}")
def delete_transaction(tx_id: str):
    r = transactions_col.delete_one({"_id": ObjectId(tx_id)})
    return {"deleted": r.deleted_count}


# ============================================================
# Endpoints · 發票
# ============================================================
def _next_invoice_no():
    yy = datetime.now().strftime("%y")
    prefix = f"INV-{yy}"
    last = invoices_col.find_one({"invoice_no": {"$regex": f"^{prefix}"}}, sort=[("invoice_no", -1)])
    next_seq = int(last["invoice_no"].split("-")[-1]) + 1 if last else 1
    return f"{prefix}-{next_seq:04d}"


@app.post("/invoices")
def create_invoice(inv: Invoice):
    data = inv.dict()
    if not data.get("invoice_no"):
        data["invoice_no"] = _next_invoice_no()
    # 計算
    subtotal = sum(item["quantity"] * item["unit_price"] for item in data["items"])
    if data["tax_included"]:
        total = subtotal
        tax = subtotal - subtotal / (1 + data["tax_rate"])
        subtotal = total - tax
    else:
        tax = subtotal * data["tax_rate"]
        total = subtotal + tax
    data.update({"subtotal": round(subtotal, 2), "tax": round(tax, 2),
                 "total": round(total, 2), "created_at": datetime.utcnow()})
    r = invoices_col.insert_one(data)
    return {"id": str(r.inserted_id), "invoice_no": data["invoice_no"], "total": data["total"]}


@app.get("/invoices")
def list_invoices(status: Optional[str] = None, project_id: Optional[str] = None):
    q = {}
    if status:    q["status"] = status
    if project_id: q["project_id"] = project_id
    return serialize(list(invoices_col.find(q).sort("date", -1).limit(100)))


# ============================================================
# Endpoints · 報價單
# ============================================================
def _next_quote_no():
    yy = datetime.now().strftime("%y")
    prefix = f"Q-{yy}"
    last = quotes_col.find_one({"quote_no": {"$regex": f"^{prefix}"}}, sort=[("quote_no", -1)])
    next_seq = int(last["quote_no"].split("-")[-1]) + 1 if last else 1
    return f"{prefix}-{next_seq:04d}"


@app.post("/quotes")
def create_quote(quote: Quote):
    data = quote.dict()
    if not data.get("quote_no"):
        data["quote_no"] = _next_quote_no()
    subtotal = sum(item["quantity"] * item["unit_price"] for item in data["items"])
    if data["tax_included"]:
        total = subtotal
        tax = subtotal - subtotal / (1 + data["tax_rate"])
        subtotal = total - tax
    else:
        tax = subtotal * data["tax_rate"]
        total = subtotal + tax
    data.update({"subtotal": round(subtotal, 2), "tax": round(tax, 2),
                 "total": round(total, 2), "created_at": datetime.utcnow()})
    r = quotes_col.insert_one(data)
    return {"id": str(r.inserted_id), "quote_no": data["quote_no"], "total": data["total"]}


@app.get("/quotes")
def list_quotes(status: Optional[str] = None):
    q = {}
    if status: q["status"] = status
    return serialize(list(quotes_col.find(q).sort("date", -1).limit(100)))


# ============================================================
# Endpoints · 專案財務
# ============================================================
def _update_project_finance(project_id: str):
    txs = list(transactions_col.find({"project_id": project_id}))
    income = sum(tx["amount"] for tx in txs
                 if accounts_col.find_one({"code": tx["credit_account"]}, {"type": 1, "_id": 0}).get("type") == "income")
    expense = sum(tx["amount"] for tx in txs
                  if accounts_col.find_one({"code": tx["debit_account"]}, {"type": 1, "_id": 0}).get("type") == "expense")
    margin = income - expense
    margin_rate = (margin / income * 100) if income > 0 else 0
    projects_finance_col.update_one(
        {"project_id": project_id},
        {"$set": {
            "project_id": project_id,
            "income": round(income, 2),
            "expense": round(expense, 2),
            "margin": round(margin, 2),
            "margin_rate": round(margin_rate, 2),
            "updated_at": datetime.utcnow(),
        }},
        upsert=True,
    )


@app.get("/projects/{project_id}/finance")
def get_project_finance(project_id: str):
    _update_project_finance(project_id)
    p = projects_finance_col.find_one({"project_id": project_id})
    return serialize(p) or {"project_id": project_id, "income": 0, "expense": 0, "margin": 0, "margin_rate": 0}


# ============================================================
# Endpoints · 報表
# ============================================================
@app.get("/reports/pnl")
def pnl_report(date_from: str, date_to: str):
    """損益表(收入 - 費用)。"""
    txs = list(transactions_col.find({"date": {"$gte": date_from, "$lte": date_to}}))
    by_account = {}
    for tx in txs:
        for code, amount in [(tx["debit_account"], tx["amount"]), (tx["credit_account"], -tx["amount"])]:
            acc = accounts_col.find_one({"code": code})
            if not acc:
                continue
            key = (acc["code"], acc["name"], acc["type"])
            by_account[key] = by_account.get(key, 0) + (amount if acc["type"] == "expense" else -amount)

    income = {f"{k[0]} {k[1]}": v for k, v in by_account.items() if k[2] == "income"}
    expense = {f"{k[0]} {k[1]}": v for k, v in by_account.items() if k[2] == "expense"}
    total_income = sum(income.values())
    total_expense = sum(expense.values())
    return {
        "period": {"from": date_from, "to": date_to},
        "income": income,
        "total_income": round(total_income, 2),
        "expense": expense,
        "total_expense": round(total_expense, 2),
        "net_profit": round(total_income - total_expense, 2),
    }


@app.get("/reports/aging")
def aging_report():
    """應收帳款帳齡。"""
    today = date.today()
    buckets = {"0-30": 0, "31-60": 0, "61-90": 0, "90+": 0}
    invoices = list(invoices_col.find({"status": {"$in": ["issued"]}}))
    for inv in invoices:
        inv_date = date.fromisoformat(inv["date"])
        days = (today - inv_date).days
        if days <= 30:   buckets["0-30"]  += inv["total"]
        elif days <= 60: buckets["31-60"] += inv["total"]
        elif days <= 90: buckets["61-90"] += inv["total"]
        else:            buckets["90+"]   += inv["total"]
    return {"today": today.isoformat(), "buckets": {k: round(v, 2) for k, v in buckets.items()},
            "total": round(sum(buckets.values()), 2)}


# ============================================================
# B · 專案(取代 Launcher localStorage · 團隊共享)
# ============================================================
class Project(BaseModel):
    name: str
    client: Optional[str] = None
    budget: Optional[float] = None
    deadline: Optional[str] = None
    description: Optional[str] = None
    status: Literal["active", "closed"] = "active"
    owner: Optional[str] = None


@app.get("/projects")
def list_projects(status: Optional[str] = None):
    q = {}
    if status: q["status"] = status
    return serialize(list(projects_col.find(q).sort("updated_at", -1)))


@app.post("/projects")
def create_project(p: Project):
    data = p.dict()
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()
    r = projects_col.insert_one(data)
    return {"id": str(r.inserted_id)}


@app.put("/projects/{project_id}")
def update_project(project_id: str, p: Project):
    data = p.dict(exclude_unset=True)
    data["updated_at"] = datetime.utcnow()
    r = projects_col.update_one({"_id": ObjectId(project_id)}, {"$set": data})
    return {"updated": r.modified_count}


@app.delete("/projects/{project_id}")
def delete_project(project_id: str):
    r = projects_col.delete_one({"_id": ObjectId(project_id)})
    return {"deleted": r.deleted_count}


# ============================================================
# C · 回饋(👍👎 集中收集)
# ============================================================
class Feedback(BaseModel):
    message_id: str
    conversation_id: Optional[str] = None
    agent_name: Optional[str] = None
    verdict: Literal["up", "down"]
    note: Optional[str] = None
    user_email: Optional[str] = None


@app.post("/feedback")
def create_feedback(fb: Feedback):
    data = fb.dict()
    data["created_at"] = datetime.utcnow()
    feedback_col.update_one(
        {"message_id": fb.message_id, "user_email": fb.user_email},
        {"$set": data},
        upsert=True,
    )
    return {"ok": True}


@app.get("/feedback")
def list_feedback(verdict: Optional[str] = None, agent: Optional[str] = None, limit: int = 100):
    q = {}
    if verdict: q["verdict"] = verdict
    if agent:   q["agent_name"] = {"$regex": agent, "$options": "i"}
    return serialize(list(feedback_col.find(q).sort("created_at", -1).limit(limit)))


@app.get("/feedback/stats")
def feedback_stats():
    """👍 / 👎 比率 by agent。"""
    pipeline = [
        {"$group": {
            "_id": "$agent_name",
            "up":    {"$sum": {"$cond": [{"$eq": ["$verdict", "up"]}, 1, 0]}},
            "down":  {"$sum": {"$cond": [{"$eq": ["$verdict", "down"]}, 1, 0]}},
            "total": {"$sum": 1},
        }},
    ]
    stats = list(feedback_col.aggregate(pipeline))
    return [
        {"agent": s["_id"] or "unknown",
         "up": s["up"], "down": s["down"], "total": s["total"],
         "score": round(s["up"] / s["total"] * 100, 1) if s["total"] > 0 else 0}
        for s in stats
    ]


# ============================================================
# D · 管理 / 儀表板
# ============================================================
@app.get("/admin/dashboard")
def admin_dashboard():
    """一頁式承富 AI 系統總覽。"""
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    today_str = today.isoformat()

    # 會計摘要
    pnl = pnl_report(month_start, today_str)

    # 專案
    active_projects = projects_col.count_documents({"status": "active"})
    total_projects = projects_col.count_documents({})

    # 回饋
    fb_stats = feedback_stats()
    total_feedback = feedback_col.count_documents({})
    up_count = feedback_col.count_documents({"verdict": "up"})

    # 對話(LibreChat 的 collection)
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


@app.delete("/admin/demo-data")
def clear_demo_data():
    """清除 seed-demo-data.py 建立的示範資料(正式上線前必跑)。"""
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
@app.get("/admin/export")
def export_all_data():
    """一鍵匯出承富所有資料(JSON · for 合規稽核 / 遷移 / 備份)。"""
    return {
        "exported_at": datetime.utcnow().isoformat(),
        "version": "v1.0",
        "accounts": serialize(list(accounts_col.find())),
        "transactions": serialize(list(transactions_col.find())),
        "invoices": serialize(list(invoices_col.find())),
        "quotes": serialize(list(quotes_col.find())),
        "projects": serialize(list(projects_col.find())),
        "feedback": serialize(list(feedback_col.find())),
        "tender_alerts": serialize(list(db.tender_alerts.find())),
        "counts": {
            "accounts": accounts_col.count_documents({}),
            "transactions": transactions_col.count_documents({}),
            "invoices": invoices_col.count_documents({}),
            "quotes": quotes_col.count_documents({}),
            "projects": projects_col.count_documents({}),
            "feedback": feedback_col.count_documents({}),
            "tender_alerts": db.tender_alerts.count_documents({}),
        },
    }


class ImportData(BaseModel):
    """資料匯入(例:從另一台機還原 · 或接受夥伴公司資料)。"""
    accounts: list = []
    projects: list = []
    transactions: list = []
    invoices: list = []
    quotes: list = []


@app.post("/admin/import")
def import_data(payload: ImportData):
    """從 JSON 匯入資料 · 不會覆蓋既有,只 append。"""
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
        # 移除 _id 避免衝突
        for d in docs:
            d.pop("_id", None)
        col.insert_many(docs)
        result[name] = len(docs)
    return {"imported": result}


# ============================================================
# Audit log(重要操作紀錄 · admin 可查)
# ============================================================
@app.get("/admin/audit-log")
def audit_log(
    action: Optional[str] = None,
    user: Optional[str] = None,
    limit: int = 100,
):
    q = {}
    if action: q["action"] = action
    if user:   q["user"] = user
    return serialize(list(audit_col.find(q).sort("created_at", -1).limit(limit)))


@app.post("/admin/audit-log")
def log_action(action: str, user: str, resource: Optional[str] = None, details: Optional[dict] = None):
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
class EmailNotification(BaseModel):
    to: str
    subject: str
    body: str
    body_type: Literal["text", "html"] = "text"


@app.post("/admin/email/send")
def send_email(msg: EmailNotification):
    """透過 SMTP 寄 Email(使用 .env 的 EMAIL_* 設定)。

    主要用途:月報自動寄給 admin · 異常告警 · 使用者密碼重設。
    """
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


@app.post("/admin/send-monthly-report")
def send_monthly_report_to_admin():
    """產生月報 + 寄給 ADMIN_EMAIL · 可由 cron 每月 1 日觸發。"""
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

    send_email(EmailNotification(
        to=admin_email,
        subject=f"承富 AI 月報 · {report['month']}",
        body=body,
        body_type="html",
    ))
    return {"sent": True, "to": admin_email, "month": report["month"]}


@app.get("/tender-alerts")
def list_tender_alerts(status: Optional[str] = None, keyword: Optional[str] = None, limit: int = 50):
    """列出採購網監測抓到的標案(Launcher 專用)。"""
    q = {}
    if status:  q["status"] = status
    if keyword: q["keyword"] = keyword
    alerts = db.tender_alerts
    return serialize(list(alerts.find(q).sort("discovered_at", -1).limit(limit)))


@app.put("/tender-alerts/{tender_key}")
def update_tender_alert(tender_key: str, status: str):
    """標記標案狀態(new / reviewing / interested / skipped)。"""
    r = db.tender_alerts.update_one(
        {"tender_key": tender_key},
        {"$set": {"status": status, "reviewed_at": datetime.utcnow()}}
    )
    return {"updated": r.modified_count}


@app.get("/admin/monthly-report")
def monthly_report(month: Optional[str] = None):
    """月度營運報告 · 給老闆/Sterio 月底看。

    - 財務表現 vs 上月
    - 各 Agent 使用與品質趨勢
    - 使用者活躍度 top 5
    - 👍👎 主要投訴 / 讚美主題
    - 建議新 Skill(從 pattern 提取)
    """
    from datetime import timedelta
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

    # 財務
    current_pnl = pnl_report(month_start, month_end)
    prev_pnl = pnl_report(prev_start, prev_end)

    # 回饋趨勢
    month_fb = list(feedback_col.find({
        "created_at": {"$gte": datetime.fromisoformat(f"{month_start}T00:00:00")}
    }))
    up_fb = [f for f in month_fb if f.get("verdict") == "up"]
    down_fb = [f for f in month_fb if f.get("verdict") == "down"]

    # 主要投訴 keyword(從 down_fb 的 note)
    complaint_keywords = {}
    for f in down_fb:
        note = f.get("note", "") or ""
        for word in ["品質", "格式", "字數", "語氣", "錯字", "漏", "慢", "不對"]:
            if word in note:
                complaint_keywords[word] = complaint_keywords.get(word, 0) + 1

    # 主要讚美
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
        "agents": feedback_stats(),
        "action_items": _generate_action_items(month_fb),
    }


def _generate_action_items(feedbacks: list) -> list[dict]:
    """從回饋推導改進建議。簡單版 · v1.5 會接 Claude 深度分析。"""
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


@app.get("/admin/cost")
def cost_summary(days: int = 30):
    """粗估 API cost(從 LibreChat transactions collection 讀 · 若存在)。
    若 LibreChat 有 `transactions` collection 記 tokenCredits,可直接累計。
    """
    try:
        lc_tx = db.transactions  # LibreChat 的 tokens transactions collection
        from_dt = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        from_dt -= timedelta(days=days)
        pipeline = [
            {"$match": {"createdAt": {"$gte": from_dt}}},
            {"$group": {
                "_id": "$model",
                "input_tokens":  {"$sum": "$rawAmount.prompt"},
                "output_tokens": {"$sum": "$rawAmount.completion"},
                "count":         {"$sum": 1},
            }},
        ]
        stats = list(lc_tx.aggregate(pipeline))
        return {"period_days": days, "by_model": stats}
    except Exception as e:
        return {"error": str(e), "note": "需 LibreChat transactions collection 存在"}


# ============================================================
# E · 安全 · Level 03 內容分級檢查
# ============================================================
LEVEL_3_PATTERNS = [
    # 選情 / 政治
    r"選情", r"民調", r"政黨內部", r"候選人(策略|規劃)",
    # 未公告標案
    r"未公告.{0,10}標", r"內定.{0,5}廠商", r"評審.{0,5}名單",
    # 個資(強 pattern)
    r"\b[A-Z]\d{9}\b",  # 身份證
    r"\b\d{10}\b",      # 手機號
    r"\b\d{3}-\d{3}-\d{3}\b",
    # 客戶機敏
    r"客戶.{0,5}(帳戶|密碼|財務狀況)",
    # 競爭對手情報
    r"(對手|競品).{0,5}(內部|機密|計畫)",
]


class ContentCheck(BaseModel):
    text: str


@app.post("/safety/classify")
def classify_level(payload: ContentCheck):
    """Level 03 keyword classifier · 在 Agent 處理前預掃。"""
    import re
    hits = []
    for pattern in LEVEL_3_PATTERNS:
        matches = re.findall(pattern, payload.text)
        if matches:
            hits.extend(matches if isinstance(matches[0], str) else [str(m) for m in matches])
    level = "03" if hits else ("02" if len(payload.text) > 500 else "01")
    return {
        "level": level,
        "triggers": hits[:10],  # 最多回 10 個命中
        "recommendation": {
            "01": "可直接處理",
            "02": "建議去識別化(客戶名/金額)後處理",
            "03": "❌ 禁止送 AI,請改人工處理或待階段二本地模型",
        }[level],
    }


# ============================================================
# Context Summary Middleware(對話超長自動摘要 · 省 token)
# ============================================================
class SummarizeRequest(BaseModel):
    conversation_id: str
    keep_recent: int = 10  # 保留最近 N 輪不摘要
    force: bool = False    # 強制摘要(即使未達門檻)


@app.post("/memory/summarize-conversation")
def summarize_conversation(req: SummarizeRequest):
    """對話超過 N 輪時用 Haiku 摘要前面的 · 存回 conversation metadata。

    節省邏輯:
      - 20 輪對話 × 平均 1500 tokens = 30k tokens context
      - 摘要成 2k tokens + 保留最近 10 輪(10k) = 12k tokens
      - 每次呼叫省約 60% context
    """
    msgs_col = db.messages
    try:
        messages = list(msgs_col.find(
            {"conversationId": req.conversation_id}
        ).sort("createdAt", 1))
    except Exception as e:
        raise HTTPException(500, f"MongoDB 查詢失敗: {e}")

    if len(messages) <= req.keep_recent and not req.force:
        return {"summarized": False, "reason": f"對話僅 {len(messages)} 輪,未達門檻"}

    to_summarize = messages[:-req.keep_recent] if not req.force else messages
    if not to_summarize:
        return {"summarized": False, "reason": "無可摘要訊息"}

    # 用 Anthropic Haiku 摘要
    try:
        import anthropic
        client = anthropic.Anthropic()

        # 組成可讀的對話文字
        dialogue = "\n\n".join([
            f"{m.get('sender', m.get('role', 'user'))}: {(m.get('text') or '')[:500]}"
            for m in to_summarize
        ])

        summary_resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""把以下承富 AI 對話摘要成 200-400 字 · 保留關鍵事實 / 決議 / 待辦 · 繁中 · 台灣用語:\n\n{dialogue}"""
            }]
        )
        summary_text = summary_resp.content[0].text

        # 存回 conversation metadata
        db.conversations.update_one(
            {"conversationId": req.conversation_id},
            {"$set": {
                "chengfu_summary": summary_text,
                "chengfu_summary_up_to": str(to_summarize[-1].get("_id", "")),
                "chengfu_summarized_at": datetime.utcnow(),
                "chengfu_summarized_messages": len(to_summarize),
            }}
        )

        return {
            "summarized": True,
            "messages_summarized": len(to_summarize),
            "summary_length": len(summary_text),
            "kept_recent": req.keep_recent,
            "estimated_tokens_saved": sum(len(m.get("text", "")) for m in to_summarize) // 4,
        }
    except Exception as e:
        raise HTTPException(500, f"摘要失敗: {e}")


# ============================================================
# User Preferences(跨 Agent 使用者記憶)· Level 4 Learning 核心
# ============================================================
class UserPreference(BaseModel):
    key: str          # e.g. "writing_style" / "formality" / "favorite_clients"
    value: str        # 任意字串
    learned_from: Optional[str] = None  # 從哪個對話 / Agent 學到
    confidence: float = 1.0  # 0-1


@app.get("/users/{user_email}/preferences")
def get_user_prefs(user_email: str):
    """取使用者所有偏好 · Agent 對話開始會呼叫。"""
    prefs = list(db.user_preferences.find({"user_email": user_email}))
    return {
        "user_email": user_email,
        "preferences": {p["key"]: p["value"] for p in prefs},
        "count": len(prefs),
    }


@app.post("/users/{user_email}/preferences")
def save_user_pref(user_email: str, pref: UserPreference):
    """記使用者偏好 · 可由 Agent 主動呼叫(「記住 user 偏好正式語氣」)。"""
    db.user_preferences.update_one(
        {"user_email": user_email, "key": pref.key},
        {"$set": {
            "user_email": user_email,
            "key": pref.key,
            "value": pref.value,
            "learned_from": pref.learned_from,
            "confidence": pref.confidence,
            "updated_at": datetime.utcnow(),
        }},
        upsert=True,
    )
    return {"saved": True}


@app.delete("/users/{user_email}/preferences/{key}")
def delete_user_pref(user_email: str, key: str):
    r = db.user_preferences.delete_one({"user_email": user_email, "key": key})
    return {"deleted": r.deleted_count}


# ============================================================
# CRM Pipeline(Kanban · 標案 → 提案 → 得標 → 執行 → 結案)
# ============================================================
class LeadStage(str, Enum):
    lead       = "lead"          # 新機會(採購網自動進這)
    qualifying = "qualifying"    # 評估中(Go/No-Go 進行)
    proposing  = "proposing"     # 撰寫提案中
    submitted  = "submitted"     # 已送件等結果
    won        = "won"           # 得標
    lost       = "lost"          # 未得標
    executing  = "executing"     # 執行中(得標後)
    closed     = "closed"        # 結案完成


class Lead(BaseModel):
    title: str
    client: Optional[str] = None
    stage: LeadStage = LeadStage.lead
    source: Optional[str] = None  # tender_alert / manual / referral
    budget: Optional[float] = None
    deadline: Optional[str] = None
    owner: Optional[str] = None
    description: Optional[str] = None
    tender_key: Optional[str] = None  # 若從 tender_alert 來
    probability: float = 0.0  # 0-1
    notes: list[dict] = []  # 觸點 / 會議紀錄


@app.get("/crm/leads")
def list_leads(stage: Optional[str] = None, owner: Optional[str] = None):
    """Kanban 讀全部 leads · 依階段分組。"""
    q = {}
    if stage: q["stage"] = stage
    if owner: q["owner"] = owner
    leads = list(db.crm_leads.find(q).sort("updated_at", -1))
    return serialize(leads)


@app.post("/crm/leads")
def create_lead(lead: Lead):
    data = lead.dict()
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()
    r = db.crm_leads.insert_one(data)
    return {"id": str(r.inserted_id)}


@app.put("/crm/leads/{lead_id}")
def update_lead(lead_id: str, updates: dict):
    """部分更新 · 支援拖動 Kanban(只改 stage)或完整編輯。"""
    allowed = {"title", "client", "stage", "source", "budget", "deadline",
               "owner", "description", "probability", "notes"}
    update = {k: v for k, v in updates.items() if k in allowed}
    update["updated_at"] = datetime.utcnow()

    # 若改到 stage · 記錄變動歷史
    if "stage" in update:
        db.crm_stage_history.insert_one({
            "lead_id": lead_id,
            "new_stage": update["stage"],
            "changed_at": datetime.utcnow(),
            "changed_by": updates.get("_by"),
        })

    r = db.crm_leads.update_one({"_id": ObjectId(lead_id)}, {"$set": update})
    return {"updated": r.modified_count}


@app.delete("/crm/leads/{lead_id}")
def delete_lead(lead_id: str):
    r = db.crm_leads.delete_one({"_id": ObjectId(lead_id)})
    return {"deleted": r.deleted_count}


@app.post("/crm/leads/{lead_id}/notes")
def add_lead_note(lead_id: str, note: str, by: Optional[str] = None):
    """加觸點 · 電話 / 會議 / Email 紀錄。"""
    db.crm_leads.update_one(
        {"_id": ObjectId(lead_id)},
        {"$push": {"notes": {
            "text": note, "at": datetime.utcnow().isoformat(), "by": by,
        }},
         "$set": {"updated_at": datetime.utcnow()}}
    )
    return {"added": True}


@app.get("/crm/stats")
def crm_stats():
    """Kanban 儀表統計。"""
    pipeline = [
        {"$group": {"_id": "$stage", "count": {"$sum": 1},
                    "budget_total": {"$sum": "$budget"}}},
    ]
    by_stage = list(db.crm_leads.aggregate(pipeline))
    # 計算勝率(won / (won + lost))
    won = db.crm_leads.count_documents({"stage": "won"})
    lost = db.crm_leads.count_documents({"stage": "lost"})
    win_rate = round(won / (won + lost) * 100, 1) if (won + lost) > 0 else None

    # 漏斗價值(進行中的 leads 總預算 × 機率)
    active_leads = list(db.crm_leads.find({
        "stage": {"$in": ["lead", "qualifying", "proposing", "submitted"]}
    }))
    expected_value = sum(
        (l.get("budget") or 0) * (l.get("probability") or 0.5)
        for l in active_leads
    )

    return {
        "by_stage": [{"stage": s["_id"], "count": s["count"],
                      "budget_total": s["budget_total"] or 0} for s in by_stage],
        "win_rate": win_rate,
        "active_pipeline_value": round(expected_value, 0),
        "total_leads": sum(s["count"] for s in by_stage),
    }


@app.post("/crm/import-from-tenders")
def import_leads_from_tenders():
    """把標記為 'interested' 的 tender_alerts 轉成 CRM leads。"""
    interested = list(db.tender_alerts.find({"status": "interested"}))
    imported = 0
    for t in interested:
        # 避免重複
        if db.crm_leads.find_one({"tender_key": t.get("tender_key")}):
            continue
        db.crm_leads.insert_one({
            "title": t.get("title"),
            "client": t.get("unit_name"),
            "stage": "lead",
            "source": "tender_alert",
            "tender_key": t.get("tender_key"),
            "description": f"來源:政府電子採購網 · 關鍵字「{t.get('keyword')}」",
            "probability": 0.5,
            "notes": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })
        imported += 1
    return {"imported": imported, "total_interested": len(interested)}


# ============================================================
# Agent Playground(admin 線上調 Agent prompt · 不用改 JSON)
# ============================================================
class AgentPromptUpdate(BaseModel):
    agent_num: str  # "00" - "09"
    new_instructions: str
    reason: str
    editor: str


@app.get("/admin/agent-prompts")
def list_agent_prompts():
    """列出所有 10 Agent 的當前 prompt(從 JSON 讀 · 之後改從 MongoDB override)。"""
    import pathlib
    presets_dir = pathlib.Path("/app/presets") if pathlib.Path("/app/presets").exists() \
                  else pathlib.Path(__file__).parent.parent.parent / "config-templates" / "presets"
    agents = []
    if presets_dir.exists():
        for f in sorted(presets_dir.glob("0*.json")):
            try:
                data = json.load(open(f))
                # 若有 override 以 override 為準
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


@app.post("/admin/agent-prompts")
def update_agent_prompt(payload: AgentPromptUpdate):
    """線上更新 Agent prompt(寫 override collection · 不動原 JSON)。

    實際生效需再跑 create-agents.py 重建,或透過 LibreChat API patch。
    本 API 先記錄變更,未來可自動同步。
    """
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
    # 記 audit log
    audit_col.insert_one({
        "action": "agent_prompt_update",
        "user": payload.editor,
        "resource": f"agent_{payload.agent_num}",
        "details": {"reason": payload.reason, "length": len(payload.new_instructions)},
        "created_at": datetime.utcnow(),
    })
    return {"updated": True, "note": "變更已記錄,執行 create-agents.py --only <num> 即可生效"}


@app.delete("/admin/agent-prompts/{agent_num}")
def revert_agent_prompt(agent_num: str):
    """還原 Agent prompt 為原始 JSON 版。"""
    r = db.agent_overrides.delete_one({"agent_num": agent_num})
    return {"reverted": r.deleted_count > 0}


# ============================================================
# Health
# ============================================================
@app.get("/healthz")
def health():
    return {
        "status": "ok",
        "mongo": db.name,
        "accounts": accounts_col.count_documents({}),
        "projects": projects_col.count_documents({}),
        "feedback": feedback_col.count_documents({}),
    }


@app.on_event("startup")
def startup():
    # 自動 seed 預設科目
    if accounts_col.count_documents({}) == 0:
        seed_accounts()
    # 建立 indexes
    feedback_col.create_index([("agent_name", 1), ("verdict", 1)])
    feedback_col.create_index([("created_at", -1)])
    projects_col.create_index([("status", 1), ("updated_at", -1)])
    audit_col.create_index([("created_at", -1)])

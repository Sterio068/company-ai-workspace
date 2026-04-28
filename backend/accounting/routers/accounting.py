"""
Accounting router · v1.3 §11.1 B-8 · 從 main.py 抽出(會計核心)

涵蓋 12 endpoint:
- /accounts/seed · /accounts GET · /accounts POST
- /transactions GET/POST/DELETE
- /invoices GET/POST(_next_invoice_no 內生流水號)
- /quotes GET/POST(_next_quote_no)
- /projects/{id}/finance(_update_project_finance · txn 連動)
- /reports/pnl · /reports/aging

設計決策:
- DEFAULT_ACCOUNTS 25 個台灣科目隨此 router 走(seed_accounts 唯一 caller)
- _account_type_map · _update_project_finance · _next_*_no 都隨來
- pnl_report 留在 router · admin.py 透過 `from routers.accounting import pnl_report` 用
- /projects/* 仍在 main.py(B 區塊 · v1.3 後續可抽 routers/projects.py)
"""
import logging
from datetime import datetime, date, timezone
from enum import Enum
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from bson import ObjectId
from bson.errors import InvalidId

from ._deps import require_permission_dep, require_user_dep


# R27#2 · router-wide require login · nginx 直接公開 /api-accounting/* · 沒登入禁讀寫
# 個別 admin 操作(seed / DELETE)在 endpoint 級再升 require_admin_dep
router = APIRouter(tags=["accounting"], dependencies=[require_user_dep()])
logger = logging.getLogger("chengfu")


def _tx_oid(tx_id: str) -> ObjectId:
    """R15 · transaction ObjectId 統一解析 · bad id 回 400 而非 500"""
    try:
        return ObjectId(tx_id)
    except (InvalidId, TypeError):
        raise HTTPException(400, "tx_id 格式錯誤")


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
@router.post("/accounts/seed")
def seed_accounts(_user: str = require_permission_dep("accounting.edit")):
    """初始化預設科目(冪等)"""
    from main import accounts_col
    created = 0
    for acc in DEFAULT_ACCOUNTS:
        if not accounts_col.find_one({"code": acc["code"]}):
            accounts_col.insert_one({**acc, "active": True, "created_at": datetime.now(timezone.utc)})
            created += 1
    return {"seeded": created, "total": accounts_col.count_documents({})}


@router.get("/accounts")
def list_accounts(
    type: Optional[AccountType] = None,
    _user: str = require_permission_dep("accounting.view"),
):
    from main import accounts_col, serialize
    q = {"active": True}
    if type:
        q["type"] = type.value
    return serialize(list(accounts_col.find(q).sort("code", 1)))


@router.post("/accounts")
def create_account(acc: Account, _user: str = require_permission_dep("accounting.edit")):
    from main import accounts_col
    if accounts_col.find_one({"code": acc.code}):
        raise HTTPException(400, f"科目編號 {acc.code} 已存在")
    r = accounts_col.insert_one({**acc.model_dump(), "created_at": datetime.now(timezone.utc)})
    return {"id": str(r.inserted_id)}


# ============================================================
# Endpoints · 交易
# ============================================================
@router.post("/transactions")
def create_transaction(tx: Transaction, _user: str = require_permission_dep("accounting.edit")):
    from main import accounts_col, transactions_col
    for code in [tx.debit_account, tx.credit_account]:
        if not accounts_col.find_one({"code": code}):
            raise HTTPException(400, f"科目 {code} 不存在")
    data = tx.model_dump()
    data["created_at"] = datetime.now(timezone.utc)
    r = transactions_col.insert_one(data)
    if tx.project_id:
        _update_project_finance(tx.project_id)
    return {"id": str(r.inserted_id)}


@router.get("/transactions")
def list_transactions(
    project_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    _user: str = require_permission_dep("accounting.view"),
):
    from main import transactions_col, serialize
    q = {}
    if project_id:
        q["project_id"] = project_id
    if date_from or date_to:
        q["date"] = {}
        if date_from: q["date"]["$gte"] = date_from
        if date_to:   q["date"]["$lte"] = date_to
    return serialize(list(transactions_col.find(q).sort("date", -1).limit(limit)))


@router.delete("/transactions/{tx_id}")
def delete_transaction(tx_id: str, _user: str = require_permission_dep("accounting.edit")):
    """R15 · 用 _tx_oid · 補 404"""
    from main import transactions_col
    r = transactions_col.delete_one({"_id": _tx_oid(tx_id)})
    if r.deleted_count == 0:
        raise HTTPException(404, "交易不存在")
    return {"deleted": r.deleted_count}


# ============================================================
# Endpoints · 發票
# ============================================================
def _next_invoice_no():
    from main import invoices_col
    yy = datetime.now(timezone.utc).strftime("%y")
    prefix = f"INV-{yy}"
    last = invoices_col.find_one({"invoice_no": {"$regex": f"^{prefix}"}}, sort=[("invoice_no", -1)])
    next_seq = int(last["invoice_no"].split("-")[-1]) + 1 if last else 1
    return f"{prefix}-{next_seq:04d}"


@router.post("/invoices")
def create_invoice(inv: Invoice, _user: str = require_permission_dep("accounting.edit")):
    from main import invoices_col
    data = inv.model_dump()
    if not data.get("invoice_no"):
        data["invoice_no"] = _next_invoice_no()
    subtotal = sum(item["quantity"] * item["unit_price"] for item in data["items"])
    if data["tax_included"]:
        total = subtotal
        tax = subtotal - subtotal / (1 + data["tax_rate"])
        subtotal = total - tax
    else:
        tax = subtotal * data["tax_rate"]
        total = subtotal + tax
    data.update({"subtotal": round(subtotal, 2), "tax": round(tax, 2),
                 "total": round(total, 2), "created_at": datetime.now(timezone.utc)})
    r = invoices_col.insert_one(data)
    return {"id": str(r.inserted_id), "invoice_no": data["invoice_no"], "total": data["total"]}


@router.get("/invoices")
def list_invoices(
    status: Optional[str] = None,
    project_id: Optional[str] = None,
    _user: str = require_permission_dep("accounting.view"),
):
    from main import invoices_col, serialize
    q = {}
    if status:    q["status"] = status
    if project_id: q["project_id"] = project_id
    return serialize(list(invoices_col.find(q).sort("date", -1).limit(100)))


# ============================================================
# Endpoints · 報價單
# ============================================================
def _next_quote_no():
    from main import quotes_col
    yy = datetime.now(timezone.utc).strftime("%y")
    prefix = f"Q-{yy}"
    last = quotes_col.find_one({"quote_no": {"$regex": f"^{prefix}"}}, sort=[("quote_no", -1)])
    next_seq = int(last["quote_no"].split("-")[-1]) + 1 if last else 1
    return f"{prefix}-{next_seq:04d}"


@router.post("/quotes")
def create_quote(quote: Quote, _user: str = require_permission_dep("accounting.edit")):
    from main import quotes_col
    data = quote.model_dump()
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
                 "total": round(total, 2), "created_at": datetime.now(timezone.utc)})
    r = quotes_col.insert_one(data)
    return {"id": str(r.inserted_id), "quote_no": data["quote_no"], "total": data["total"]}


@router.get("/quotes")
def list_quotes(
    status: Optional[str] = None,
    _user: str = require_permission_dep("accounting.view"),
):
    from main import quotes_col, serialize
    q = {}
    if status: q["status"] = status
    return serialize(list(quotes_col.find(q).sort("date", -1).limit(100)))


# ============================================================
# Endpoints · 專案財務
# ============================================================
def _account_type_map() -> dict:
    """Audit perf #1+#2 · 一次撈所有 account.type 進 dict
    Mongo accounts ~30 列 + 不常變 · 替代 N+1 find_one"""
    from main import accounts_col
    return {a["code"]: a.get("type") for a in accounts_col.find({}, {"code": 1, "type": 1, "_id": 0})}


def _update_project_finance(project_id: str):
    from main import transactions_col, projects_finance_col
    txs = list(transactions_col.find({"project_id": project_id}))
    type_map = _account_type_map()
    income = sum(tx["amount"] for tx in txs
                 if type_map.get(tx["credit_account"]) == "income")
    expense = sum(tx["amount"] for tx in txs
                  if type_map.get(tx["debit_account"]) == "expense")
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
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )


@router.get("/projects/{project_id}/finance")
def get_project_finance(
    project_id: str,
    _user: str = require_permission_dep("accounting.view"),
):
    from main import projects_finance_col, serialize
    _update_project_finance(project_id)
    p = projects_finance_col.find_one({"project_id": project_id})
    return serialize(p) or {"project_id": project_id, "income": 0, "expense": 0, "margin": 0, "margin_rate": 0}


# ============================================================
# Endpoints · 報表
# ============================================================
@router.get("/reports/pnl")
def pnl_report(
    date_from: str,
    date_to: str,
    _user: str = require_permission_dep("accounting.view"),
):
    """損益表(收入 - 費用)· Audit perf #2 · 一次撈 accounts dict 取代 find_one 迴圈

    NB: admin router monthly_report / dashboard 也會 from routers.accounting import pnl_report
    直接呼叫(不過 HTTP)· 函式 signature 必須能 plain Python call
    """
    from main import transactions_col, accounts_col
    txs = list(transactions_col.find({"date": {"$gte": date_from, "$lte": date_to}}))
    accounts_map = {a["code"]: a for a in accounts_col.find({})}
    by_account = {}
    for tx in txs:
        for code, amount in [(tx["debit_account"], tx["amount"]), (tx["credit_account"], -tx["amount"])]:
            acc = accounts_map.get(code)
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


@router.get("/reports/aging")
def aging_report(_user: str = require_permission_dep("accounting.view")):
    """應收帳款帳齡"""
    from main import invoices_col
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


@router.get("/reports/overview")
def accounting_overview(_user: str = require_permission_dep("accounting.view")):
    """會計工作台摘要 · 前端一支 API 拿到本月、應收、報價與待處理提醒"""
    from main import invoices_col, quotes_col, transactions_col
    today = date.today()
    date_from = today.replace(day=1).isoformat()
    date_to = today.isoformat()
    pnl = pnl_report(date_from=date_from, date_to=date_to, _user=_user)
    aging = aging_report(_user=_user)
    unpaid = list(invoices_col.find({"status": {"$in": ["draft", "issued"]}}).sort("date", 1).limit(20))
    active_quotes = list(quotes_col.find({"status": {"$in": ["draft", "sent"]}}).sort("valid_until", 1).limit(20))
    recent_transactions = list(transactions_col.find({}).sort("date", -1).limit(5))
    unpaid_total = sum(inv.get("total", 0) or 0 for inv in unpaid)
    quote_total = sum(q.get("total", 0) or 0 for q in active_quotes)
    return {
        "period": {"from": date_from, "to": date_to},
        "pnl": pnl,
        "aging": aging,
        "unpaid": {
            "count": len(unpaid),
            "total": round(unpaid_total, 2),
            "oldest_date": unpaid[0].get("date") if unpaid else None,
        },
        "quotes": {
            "active_count": len(active_quotes),
            "active_total": round(quote_total, 2),
            "next_expiring": active_quotes[0].get("valid_until") if active_quotes else None,
        },
        "recent_transactions_count": len(recent_transactions),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

"""會計科目 + 交易 + 發票 + 報價 + 報表 router。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime, date
from enum import Enum
from bson import ObjectId


router = APIRouter(prefix="", tags=["accounting"])


class AccountType(str, Enum):
    asset = "asset"; liability = "liability"; equity = "equity"
    income = "income"; expense = "expense"


class Account(BaseModel):
    code: str; name: str; type: AccountType; active: bool = True


class Transaction(BaseModel):
    date: str; memo: str
    debit_account: str; credit_account: str
    amount: float
    project_id: Optional[str] = None
    vendor: Optional[str] = None
    customer: Optional[str] = None
    tags: list[str] = []


class InvoiceItem(BaseModel):
    description: str; quantity: float; unit_price: float


class Invoice(BaseModel):
    invoice_no: Optional[str] = None
    date: str; customer: str
    customer_tax_id: Optional[str] = None
    items: list[InvoiceItem]
    tax_included: bool = False; tax_rate: float = 0.05
    project_id: Optional[str] = None
    status: Literal["draft", "issued", "paid", "cancelled"] = "draft"
    notes: Optional[str] = None


class Quote(BaseModel):
    quote_no: Optional[str] = None
    date: str; customer: str
    items: list[InvoiceItem]
    tax_included: bool = False; tax_rate: float = 0.05
    valid_until: str
    project_id: Optional[str] = None
    status: Literal["draft", "sent", "accepted", "rejected", "expired"] = "draft"
    terms: Optional[str] = None


def get_db():
    from main import db
    return db


def serialize(doc):
    if not doc:
        return doc
    if isinstance(doc, list):
        return [serialize(d) for d in doc]
    if isinstance(doc, dict):
        return {k: (str(v) if isinstance(v, ObjectId) else
                    serialize(v) if isinstance(v, (dict, list)) else v)
                for k, v in doc.items()}
    return doc


# ==================== 科目 ====================
@router.get("/accounts")
def list_accounts(type: Optional[AccountType] = None):
    db = get_db()
    q = {"active": True}
    if type: q["type"] = type.value
    return serialize(list(db.accounting_accounts.find(q).sort("code", 1)))


@router.post("/accounts")
def create_account(acc: Account):
    db = get_db()
    if db.accounting_accounts.find_one({"code": acc.code}):
        raise HTTPException(400, f"科目編號 {acc.code} 已存在")
    r = db.accounting_accounts.insert_one({**acc.dict(), "created_at": datetime.utcnow()})
    return {"id": str(r.inserted_id)}


# ==================== 交易 ====================
@router.post("/transactions")
def create_transaction(tx: Transaction):
    db = get_db()
    for code in [tx.debit_account, tx.credit_account]:
        if not db.accounting_accounts.find_one({"code": code}):
            raise HTTPException(400, f"科目 {code} 不存在")
    data = tx.dict()
    data["created_at"] = datetime.utcnow()
    r = db.accounting_transactions.insert_one(data)
    if tx.project_id:
        from main import _update_project_finance
        _update_project_finance(tx.project_id)
    return {"id": str(r.inserted_id)}


@router.get("/transactions")
def list_transactions(project_id: Optional[str] = None, date_from: Optional[str] = None,
                     date_to: Optional[str] = None, limit: int = 50):
    db = get_db()
    q = {}
    if project_id: q["project_id"] = project_id
    if date_from or date_to:
        q["date"] = {}
        if date_from: q["date"]["$gte"] = date_from
        if date_to:   q["date"]["$lte"] = date_to
    return serialize(list(db.accounting_transactions.find(q).sort("date", -1).limit(limit)))


@router.delete("/transactions/{tx_id}")
def delete_transaction(tx_id: str):
    db = get_db()
    r = db.accounting_transactions.delete_one({"_id": ObjectId(tx_id)})
    return {"deleted": r.deleted_count}


# ==================== 發票 ====================
def _next_invoice_no(db):
    yy = datetime.now().strftime("%y")
    prefix = f"INV-{yy}"
    last = db.accounting_invoices.find_one({"invoice_no": {"$regex": f"^{prefix}"}}, sort=[("invoice_no", -1)])
    next_seq = int(last["invoice_no"].split("-")[-1]) + 1 if last else 1
    return f"{prefix}-{next_seq:04d}"


@router.post("/invoices")
def create_invoice(inv: Invoice):
    db = get_db()
    data = inv.dict()
    if not data.get("invoice_no"):
        data["invoice_no"] = _next_invoice_no(db)
    subtotal = sum(it["quantity"] * it["unit_price"] for it in data["items"])
    if data["tax_included"]:
        total = subtotal; tax = subtotal - subtotal / (1 + data["tax_rate"]); subtotal = total - tax
    else:
        tax = subtotal * data["tax_rate"]; total = subtotal + tax
    data.update({"subtotal": round(subtotal, 2), "tax": round(tax, 2),
                 "total": round(total, 2), "created_at": datetime.utcnow()})
    r = db.accounting_invoices.insert_one(data)
    return {"id": str(r.inserted_id), "invoice_no": data["invoice_no"], "total": data["total"]}


@router.get("/invoices")
def list_invoices(status: Optional[str] = None, project_id: Optional[str] = None):
    db = get_db()
    q = {}
    if status:     q["status"] = status
    if project_id: q["project_id"] = project_id
    return serialize(list(db.accounting_invoices.find(q).sort("date", -1).limit(100)))


# ==================== 報價 ====================
def _next_quote_no(db):
    yy = datetime.now().strftime("%y")
    prefix = f"Q-{yy}"
    last = db.accounting_quotes.find_one({"quote_no": {"$regex": f"^{prefix}"}}, sort=[("quote_no", -1)])
    next_seq = int(last["quote_no"].split("-")[-1]) + 1 if last else 1
    return f"{prefix}-{next_seq:04d}"


@router.post("/quotes")
def create_quote(q: Quote):
    db = get_db()
    data = q.dict()
    if not data.get("quote_no"):
        data["quote_no"] = _next_quote_no(db)
    subtotal = sum(it["quantity"] * it["unit_price"] for it in data["items"])
    if data["tax_included"]:
        total = subtotal; tax = subtotal - subtotal / (1 + data["tax_rate"]); subtotal = total - tax
    else:
        tax = subtotal * data["tax_rate"]; total = subtotal + tax
    data.update({"subtotal": round(subtotal, 2), "tax": round(tax, 2),
                 "total": round(total, 2), "created_at": datetime.utcnow()})
    r = db.accounting_quotes.insert_one(data)
    return {"id": str(r.inserted_id), "quote_no": data["quote_no"], "total": data["total"]}


@router.get("/quotes")
def list_quotes(status: Optional[str] = None):
    db = get_db()
    q = {}
    if status: q["status"] = status
    return serialize(list(db.accounting_quotes.find(q).sort("date", -1).limit(100)))


# ==================== 報表 ====================
@router.get("/reports/pnl")
def pnl_report(date_from: str, date_to: str):
    db = get_db()
    txs = list(db.accounting_transactions.find({"date": {"$gte": date_from, "$lte": date_to}}))
    by_account = {}
    for tx in txs:
        for code, amount in [(tx["debit_account"], tx["amount"]), (tx["credit_account"], -tx["amount"])]:
            acc = db.accounting_accounts.find_one({"code": code})
            if not acc:
                continue
            key = (acc["code"], acc["name"], acc["type"])
            by_account[key] = by_account.get(key, 0) + (amount if acc["type"] == "expense" else -amount)

    income  = {f"{k[0]} {k[1]}": v for k, v in by_account.items() if k[2] == "income"}
    expense = {f"{k[0]} {k[1]}": v for k, v in by_account.items() if k[2] == "expense"}
    return {
        "period": {"from": date_from, "to": date_to},
        "income": income, "total_income": round(sum(income.values()), 2),
        "expense": expense, "total_expense": round(sum(expense.values()), 2),
        "net_profit": round(sum(income.values()) - sum(expense.values()), 2),
    }


@router.get("/reports/aging")
def aging_report():
    db = get_db()
    today = date.today()
    buckets = {"0-30": 0, "31-60": 0, "61-90": 0, "90+": 0}
    for inv in db.accounting_invoices.find({"status": "issued"}):
        days = (today - date.fromisoformat(inv["date"])).days
        if days <= 30:   buckets["0-30"]  += inv["total"]
        elif days <= 60: buckets["31-60"] += inv["total"]
        elif days <= 90: buckets["61-90"] += inv["total"]
        else:            buckets["90+"]   += inv["total"]
    return {"today": today.isoformat(),
            "buckets": {k: round(v, 2) for k, v in buckets.items()},
            "total": round(sum(buckets.values()), 2)}

"""
Scripts shared fixtures · R14#17 · v1.2 Sprint 3

原本 create-users.py / seed-demo-data.py / upload-knowledge-base.py
各自造 User / Project mock · v1.2 加 user.department 時 3 處都要改。

抽共用 factory · 減少 drift。

用法(scripts 內部):
  from fixtures import create_demo_user, create_demo_project, default_tender

  user = create_demo_user("alice@chengfu.local", role="admin")
  project = create_demo_project(name="海洋廢棄物案")
"""
from datetime import datetime, timedelta
from typing import Optional


def create_demo_user(
    email: str,
    name: Optional[str] = None,
    role: str = "USER",
    department: Optional[str] = None,
) -> dict:
    """LibreChat users collection 的 demo user · 不含密碼(那走 LibreChat API)"""
    return {
        "email": email.lower(),
        "username": email.split("@")[0],
        "name": name or email.split("@")[0].title(),
        "role": role,  # USER | ADMIN
        "department": department or "general",
        "provider": "local",
        "emailVerified": True,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
        "_demo": True,  # 方便 /admin/demo-data DELETE 清掉
    }


def create_demo_project(
    name: str,
    client: Optional[str] = None,
    budget: Optional[float] = None,
    deadline_days: int = 30,
    status: str = "active",
    owner: Optional[str] = None,
) -> dict:
    return {
        "name": name,
        "client": client or "示範客戶",
        "budget": budget or 500000.0,
        "deadline": (datetime.utcnow() + timedelta(days=deadline_days)).date().isoformat(),
        "description": f"[demo] {name}",
        "status": status,
        "owner": owner or "demo@chengfu.local",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "_demo": True,
    }


def create_demo_lead(
    title: str,
    client: Optional[str] = None,
    stage: str = "lead",
    budget: Optional[float] = None,
    owner: Optional[str] = None,
) -> dict:
    """CRM lead demo · 給 seed-demo-data.py / test 用"""
    return {
        "title": title,
        "client": client or "示範客戶",
        "stage": stage,
        "source": "manual",
        "budget": budget or 300000.0,
        "probability": 0.5,
        "owner": owner or "demo@chengfu.local",
        "notes": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "_demo": True,
    }


def create_demo_tender(
    tender_key: str,
    title: Optional[str] = None,
    unit_name: Optional[str] = None,
    keyword: str = "測試關鍵字",
    status: str = "new",
) -> dict:
    """tender_alerts collection · g0v 採購網監測 demo · 給 test / seed 用"""
    return {
        "tender_key": tender_key,
        "title": title or f"測試標案 {tender_key}",
        "unit_name": unit_name or "示範機關",
        "keyword": keyword,
        "status": status,  # new | reviewing | interested | skipped
        "discovered_at": datetime.utcnow(),
        "_demo": True,
    }


def create_demo_transaction(
    debit_account: str = "5901",  # 雜項費用
    credit_account: str = "1102",  # 銀行存款
    amount: float = 10000.0,
    memo: Optional[str] = None,
    project_id: Optional[str] = None,
) -> dict:
    """accounting_transactions demo · 不走 create-agents 流水號"""
    return {
        "date": datetime.utcnow().date().isoformat(),
        "memo": memo or "[demo] 測試交易",
        "debit_account": debit_account,
        "credit_account": credit_account,
        "amount": amount,
        "project_id": project_id,
        "tags": ["demo"],
        "created_at": datetime.utcnow(),
        "_demo": True,
    }


def create_demo_feedback(
    message_id: str,
    verdict: str = "up",
    agent_name: str = "🎯 投標顧問",
    user_email: str = "demo@chengfu.local",
    note: Optional[str] = None,
) -> dict:
    return {
        "message_id": message_id,
        "verdict": verdict,
        "agent_name": agent_name,
        "user_email": user_email,
        "note": note or "",
        "created_at": datetime.utcnow(),
        "_demo": True,
    }

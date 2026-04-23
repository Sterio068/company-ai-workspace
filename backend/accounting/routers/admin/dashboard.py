"""
v1.3 A1 · admin 拆檔(第一批)· 純讀儀表 + ROI 指標 endpoints

從 admin/__init__.py 抽出 · 7 個無 side-effect 的 read-only endpoint:
- /admin/dashboard      · 一頁式總覽
- /admin/cost           · API cost by model + Whisper(B2 v1.3)
- /admin/adoption       · 採納率 (BOSS-VIEW ROI)
- /admin/budget-status  · 本月預算進度
- /admin/top-users      · Top N 用量
- /admin/tender-funnel  · 標案漏斗
- /admin/librechat-contract · LibreChat schema 驗

設計:
- 不改 endpoint 路徑 · 完全相容
- 全 require_admin_dep
- 沒 cross-state(無 _EMAIL_ROUTES_REGISTERED 之類 module global)
- 透過 admin/__init__.py include_router 合併到主 router
"""
import logging
from datetime import datetime, date

from fastapi import APIRouter, Query

from .._deps import require_admin_dep


router = APIRouter(tags=["admin"])
logger = logging.getLogger("chengfu")


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


@router.get("/admin/cost")
def cost_summary(days: int = Query(default=30, ge=1, le=365),
                 _admin: str = require_admin_dep()):
    """粗估 API cost by model · R37 · 加 days 上下限防裸 int 探勘
    B2(v1.3)· 含 Whisper(OpenAI STT)分項 · 從 meetings + site_audio 計"""
    from main import db, _USD_TO_NTD
    from services import admin_metrics
    return admin_metrics.cost_by_model(db, days, usd_to_ntd=_USD_TO_NTD)


@router.get("/admin/adoption")
def adoption_summary(days: int = Query(default=7, ge=1, le=365),
                     _admin: str = require_admin_dep()):
    """Codex Round 10.5 黃 6 · 支撐 BOSS-VIEW ROI 公式的 adoption 數字
    R37 · 加 days 上下限"""
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


@router.get("/admin/budget-status")
def budget_status(_admin: str = require_admin_dep()):
    """本月預算進度 · 給 Launcher 首頁進度條 + email 預警用"""
    from main import db, _MONTHLY_BUDGET_NTD, _USD_TO_NTD
    from services import admin_metrics
    return admin_metrics.budget_status(db, _MONTHLY_BUDGET_NTD, _USD_TO_NTD)


@router.get("/admin/top-users")
def top_users(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=100),
    _admin: str = require_admin_dep(),
):
    """Top N 用量同仁 · R37 · days/limit 加上下限"""
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

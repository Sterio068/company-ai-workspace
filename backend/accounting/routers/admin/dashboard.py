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
from datetime import datetime, date, timezone
from typing import Any

from fastapi import APIRouter, Query

from .._deps import require_admin_dep


router = APIRouter(tags=["admin"])
logger = logging.getLogger("chengfu")


MONITORED_COLLECTIONS = (
    "users",
    "conversations",
    "messages",
    "projects",
    "feedback",
    "knowledge_sources",
    "knowledge_audit",
    "notebooklm_source_packs",
    "notebooklm_file_uploads",
    "notebooklm_sync_runs",
    "crm_leads",
    "tender_alerts",
    "accounting_transactions",
    "accounting_invoices",
    "accounting_quotes",
    "accounting_projects_finance",
    "meetings",
    "site_surveys",
    "design_jobs",
    "workflow_runs",
    "frontend_errors",
)

_ONE_GB = 1024 * 1024 * 1024


@router.get("/admin/dashboard")
def admin_dashboard(_admin: str = require_admin_dep()):
    """一頁式AI 系統總覽"""
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
        "as_of": datetime.now(timezone.utc).isoformat(),
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


@router.get("/admin/cost/today")
def cost_today(_admin: str = require_admin_dep()):
    """今日 + 本月 USD 用量 · 給 macOS Notification Center / menubar widget

    回 schema:
      { today_usd, month_usd, budget_usd | null }
    """
    from datetime import timedelta
    from main import db, _USD_TO_NTD, _MONTHLY_BUDGET_NTD
    from services.admin_metrics import transaction_token_stats, price_ntd

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def _spent_usd(from_dt):
        try:
            stats = transaction_token_stats(db, from_dt)
            spent_ntd = sum(
                price_ntd(s.get("model") or "", s.get("tin", 0) or 0,
                          s.get("tout", 0) or 0, _USD_TO_NTD) for s in stats
            )
            return round(spent_ntd / _USD_TO_NTD, 2) if _USD_TO_NTD else 0.0
        except Exception as e:
            logger.warning("[cost/today] aggregate fail: %s", e)
            return 0.0

    return {
        "today_usd": _spent_usd(today_start),
        "month_usd": _spent_usd(month_start),
        "budget_usd": (
            round(_MONTHLY_BUDGET_NTD / _USD_TO_NTD, 2)
            if _MONTHLY_BUDGET_NTD and _USD_TO_NTD else None
        ),
        "month": now.strftime("%Y-%m"),
    }


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


@router.get("/admin/storage-stats")
def storage_stats(_admin: str = require_admin_dep()):
    """MongoDB collection/storage dashboard · P2 技術債可觀測性

    給管理面板一眼看出:
    - 哪些 collection 文件數快速膨脹
    - 哪些 collection 缺索引或索引過多
    - 哪些 collection storage 已接近需要清理/歸檔

    在 mongomock / 權限不足環境下,collStats 可能不可用;此時仍回 count + index_count,
    不讓整個 admin dashboard 因維運指標失敗而壞掉。
    """
    from main import db

    items = [_collection_health(db, name) for name in MONITORED_COLLECTIONS]
    totals = {
        "documents": sum(i["count"] for i in items),
        "size_bytes": sum(i["size_bytes"] for i in items),
        "storage_bytes": sum(i["storage_bytes"] for i in items),
        "index_bytes": sum(i["index_bytes"] for i in items),
        "alerts": sum(1 for i in items if i["alert_level"] != "ok"),
    }
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "items": sorted(items, key=lambda i: (i["alert_rank"], i["storage_bytes"], i["count"]), reverse=True),
        "totals": totals,
    }


def _collection_health(db: Any, name: str) -> dict:
    col = db[name]
    try:
        count = int(col.estimated_document_count())
    except Exception:
        try:
            count = int(col.count_documents({}))
        except Exception:
            count = 0

    try:
        indexes = col.index_information()
        index_count = max(len(indexes), 0)
    except Exception:
        index_count = 0

    size_bytes = 0
    storage_bytes = 0
    index_bytes = 0
    stats_available = False
    try:
        stats = db.command("collStats", name)
        size_bytes = int(stats.get("size") or 0)
        storage_bytes = int(stats.get("storageSize") or 0)
        index_bytes = int(stats.get("totalIndexSize") or 0)
        stats_available = True
    except Exception:
        # collStats 在測試替身或低權限帳號可能不可用;前端仍可用 count/index 判斷趨勢。
        pass

    alert_level = "ok"
    alert_reason = ""
    alert_rank = 0
    if storage_bytes >= _ONE_GB:
        alert_level = "critical"
        alert_reason = "儲存量已超過 1GB,建議安排歸檔或 TTL 檢查"
        alert_rank = 3
    elif count >= 100_000:
        alert_level = "warn"
        alert_reason = "文件數超過 100,000,建議檢查查詢索引與保留期限"
        alert_rank = 2
    elif count > 0 and index_count <= 1 and name not in {"frontend_errors"}:
        alert_level = "watch"
        alert_reason = "已有資料但索引偏少,若查詢變慢需補索引"
        alert_rank = 1

    return {
        "collection": name,
        "count": count,
        "index_count": index_count,
        "size_bytes": size_bytes,
        "storage_bytes": storage_bytes,
        "index_bytes": index_bytes,
        "stats_available": stats_available,
        "alert_level": alert_level,
        "alert_reason": alert_reason,
        "alert_rank": alert_rank,
    }

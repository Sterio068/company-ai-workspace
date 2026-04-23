"""
System router · 技術債#2(2026-04-23)· 從 main.py 抽出 3 endpoints

涵蓋:
- /quota/check · launcher 送對話前先打
- /quota/preflight · nginx auth_request gate(需 rate limit)
- /healthz · 容器 healthcheck

設計:
- /quota/preflight 需 slowapi `_limiter` decorator · main.py 用
  `register_rate_limited_routes(limit_decorator)` 動態加(同 admin.py 模式)
- /quota/check 不需 rate limit · 直接 @router.get
- 不加 router-wide require_user_dep · /healthz 必須匿名
  個別 endpoint 各自處理 auth(quota_check 已用 current_user_email_dep)
"""
import os
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from ._deps import current_user_email_dep, get_db


router = APIRouter(tags=["system"])
logger = logging.getLogger("chengfu")


# ============================================================
# /quota/check · 對話前 quota 檢查
# ============================================================
@router.get("/quota/check")
def quota_check(email: Optional[str] = current_user_email_dep()):
    """Launcher 送對話前先打 · 超 100% 直接擋送(hard_stop 模式)"""
    from main import (
        _users_col, _admin_allowlist, QUOTA_MODE, QUOTA_OVERRIDE_EMAILS,
        _USER_SOFT_CAP_DEFAULT, _USD_TO_NTD,
    )
    from services import admin_metrics
    db = get_db()
    return admin_metrics.quota_check(
        db, _users_col, email,
        mode=QUOTA_MODE,
        override_emails=QUOTA_OVERRIDE_EMAILS,
        admin_allowlist=_admin_allowlist,
        user_soft_cap_ntd=_USER_SOFT_CAP_DEFAULT,
        usd_to_ntd=_USD_TO_NTD,
    )


# ============================================================
# /quota/preflight · nginx auth_request gate
# ============================================================
def _quota_preflight_impl(request: Request,
                          email: Optional[str] = current_user_email_dep()):
    """Codex R7#9 + R8#3 · nginx auth_request 用 · 看 user 是否仍在預算內

    回應 contract:
    - 204 No Content · 通過(允許 LibreChat /api/ask)
    - 429 Too Many Requests · 擋 · 帶 X-Quota-* response headers 給 nginx error_page 用
    - 401 · 沒驗到身份(prod 嚴格擋 · dev 視為通過 · 給 launcher 開發空間)
    """
    from main import (
        _users_col, _admin_allowlist, QUOTA_MODE, QUOTA_OVERRIDE_EMAILS,
        _USER_SOFT_CAP_DEFAULT, _USD_TO_NTD, _is_prod,
    )
    from services import admin_metrics
    from starlette.responses import Response
    from fastapi.responses import JSONResponse

    db = get_db()
    if not email:
        if _is_prod():
            raise HTTPException(401, "未識別使用者 · LibreChat 對話需登入")
        return Response(status_code=204)
    result = admin_metrics.quota_check(
        db, _users_col, email,
        mode=QUOTA_MODE,
        override_emails=QUOTA_OVERRIDE_EMAILS,
        admin_allowlist=_admin_allowlist,
        user_soft_cap_ntd=_USER_SOFT_CAP_DEFAULT,
        usd_to_ntd=_USD_TO_NTD,
    )
    if result.get("allowed") is False:
        spent = result.get("spent_ntd", 0)
        cap = result.get("cap_ntd", 0)
        rid = getattr(request.state, "request_id", "")
        return JSONResponse(
            status_code=429,
            content={
                "detail": {
                    "reason": result.get("reason", "quota exceeded"),
                    "spent_ntd": spent,
                    "cap_ntd": cap,
                    "request_id": rid,
                }
            },
            headers={
                "X-Quota-Spent-Ntd": str(spent),
                "X-Quota-Cap-Ntd": str(cap),
                "X-Quota-Request-Id": str(rid),
            },
        )
    return Response(status_code=204)


_PREFLIGHT_REGISTERED = False


def register_rate_limited_routes(limit_decorator):
    """main.py 在 include_router 之前呼叫 · 把 quota_preflight 包 rate limit 後動態註冊
    同 admin.py register_rate_limited_routes 模式 · 防 @router.get capture 原 fn 後 reassign 失效
    """
    global _PREFLIGHT_REGISTERED
    if _PREFLIGHT_REGISTERED:
        return
    router.add_api_route(
        "/quota/preflight",
        limit_decorator(_quota_preflight_impl),
        methods=["GET"],
    )
    _PREFLIGHT_REGISTERED = True


# ============================================================
# /healthz · 容器 healthcheck · 必須匿名(docker / nginx 每分鐘打)
# ============================================================
@router.get("/healthz")
def health():
    from main import accounts_col, projects_col, feedback_col, knowledge_sources_col
    from services.knowledge_extract import ocr_status
    db = get_db()
    return {
        "status": "ok",
        "mongo": db.name,
        "accounts": accounts_col.count_documents({}),
        "projects": projects_col.count_documents({}),
        "feedback": feedback_col.count_documents({}),
        "knowledge_sources": knowledge_sources_col.count_documents({"enabled": True}),
        "ocr": ocr_status(),
    }

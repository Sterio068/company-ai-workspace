"""
v1.3 A5 · Social OAuth router(infra · 不真接 Meta API)

Endpoints:
- GET  /social/oauth/start?platform=facebook → 302 redirect to Meta auth
- GET  /social/oauth/callback?code=... → exchange code 存 token
- POST /social/oauth/disconnect?platform=...
- GET  /social/oauth/status                 → admin 看誰連了誰

設計:
- B1 真打 Meta API 留 v1.4(等承富送 Meta App 審核)
- A5 此 PR 走 mock provider · 真 Meta 來 callback URL 即生效
- platform handler 走 services/social_providers.py(目前 mock)

Future cutover(B1):
1. 承富老闆送 Meta App 審核 · 取 app_id + app_secret
2. 寫 services/oauth_providers/meta.py · 真打 https://graph.facebook.com
3. social_oauth.py callback 改走真 provider
4. mock 退役
"""
import logging
import os
import secrets
from typing import Literal, Optional
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from ._deps import get_db, require_admin_dep, require_user_dep


router = APIRouter(tags=["social-oauth"])
logger = logging.getLogger("chengfu")

ALLOWED_PLATFORMS = {"facebook", "instagram", "linkedin"}

# v1.3 A3 · CRITICAL C-8 · OAUTH_REDIRECT_BASE_URL 白名單
# 不再信任 request 的 X-Forwarded-Host(可被偽造做 open-redirect)
_OAUTH_BASE_URL = os.getenv("OAUTH_REDIRECT_BASE_URL", "").strip().rstrip("/")


def _app_creds(platform: str) -> tuple[str, str]:
    """從 env 拿 platform 的 app_id + app_secret · 沒設 raise"""
    env_id = f"{platform.upper()}_APP_ID"
    env_secret = f"{platform.upper()}_APP_SECRET"
    app_id = os.getenv(env_id, "").strip()
    app_secret = os.getenv(env_secret, "").strip()
    if not app_id or not app_secret:
        raise HTTPException(
            503,
            f"{platform} App 未配置 · 需設 env {env_id} + {env_secret}(B1 留 v1.4)"
        )
    return app_id, app_secret


def _redirect_uri(request: Request) -> str:
    """callback URL · scheme + host + /api-accounting/social/oauth/callback

    v1.3 A3 · CRITICAL C-8 · 不再信任 X-Forwarded-Host(可偽造)
    優先順序:
    1. OAUTH_REDIRECT_BASE_URL env 白名單(prod 強制)
    2. (dev fallback) request.headers x-forwarded-host

    Open-redirect 防護:OAuth provider(Meta/LinkedIn)會比對註冊的 redirect_uri,
    若被偽造為攻擊者 host,provider 端會拒絕。但加 env 白名單做雙重保險,
    避免依賴 provider 行為。
    """
    # Prod 強制走 env
    if _OAUTH_BASE_URL:
        # 驗證白名單格式 · 防 env 設成 javascript:alert 等
        parsed = urlparse(_OAUTH_BASE_URL)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise HTTPException(
                500,
                "OAUTH_REDIRECT_BASE_URL 設定錯 · 必須 https://domain.com 格式",
            )
        return f"{_OAUTH_BASE_URL}/api-accounting/social/oauth/callback"

    # Dev fallback · 容 X-Forwarded-Host(本機 / 測試)
    scheme = request.headers.get("x-forwarded-proto", "http")
    host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost"))
    logger.warning(
        "[oauth] OAUTH_REDIRECT_BASE_URL 未設 · 退化從 request header 取 host=%s · prod 必設 env",
        host,
    )
    return f"{scheme}://{host}/api-accounting/social/oauth/callback"


@router.get("/social/oauth/start")
def oauth_start(
    request: Request,
    platform: Literal["facebook", "instagram", "linkedin"] = Query(...),
    email: str = require_user_dep(),
):
    """OAuth 起點 · 302 redirect 到 platform auth page
    state = random 32 bytes hex · cookie 存 + callback 驗 防 CSRF
    """
    if platform not in ALLOWED_PLATFORMS:
        raise HTTPException(400, f"不支援的 platform: {platform}")

    app_id, _ = _app_creds(platform)  # 沒設會 raise 503
    state = secrets.token_hex(16)
    db = get_db()

    # 暫存 state · TTL 10 min(callback 必 10 min 內回)
    from datetime import datetime, timezone, timedelta
    db.social_oauth_states.update_one(
        {"state": state},
        {"$set": {
            "state": state,
            "user_email": email.strip().lower(),
            "platform": platform,
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        }},
        upsert=True,
    )

    # B1 留 v1.4 · 真實 redirect URL 各 platform 不同
    # facebook · https://www.facebook.com/v18.0/dialog/oauth?...
    # IG · 同 facebook(走 IG Business)
    # linkedin · https://www.linkedin.com/oauth/v2/authorization?...
    auth_urls = {
        "facebook": "https://www.facebook.com/v18.0/dialog/oauth",
        "instagram": "https://www.facebook.com/v18.0/dialog/oauth",
        "linkedin": "https://www.linkedin.com/oauth/v2/authorization",
    }
    scopes = {
        "facebook": "pages_manage_posts,pages_read_engagement",
        "instagram": "instagram_basic,instagram_content_publish",
        "linkedin": "r_liteprofile,w_member_social",
    }
    redirect_uri = _redirect_uri(request)
    # v1.3 A3 · CRITICAL C-8 · urlencode 防 app_id / redirect_uri / state 含特殊字元
    # 注入 query 參數(原本 f-string 拼接 · `&` `=` 在 redirect_uri 會破壞 query)
    params = urlencode({
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": scopes[platform],
        "response_type": "code",
    })
    auth_url = f"{auth_urls[platform]}?{params}"
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/social/oauth/callback")
def oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """OAuth callback · platform 拿 code 換 access_token · 存 db
    安全:state cookie 比對 · 防 CSRF"""
    if error:
        raise HTTPException(400, f"OAuth 錯誤:{error}")
    if not code or not state:
        raise HTTPException(400, "缺 code 或 state")

    db = get_db()
    state_doc = db.social_oauth_states.find_one({"state": state})
    if not state_doc:
        raise HTTPException(400, "state 不認識 · 重新從 /social/oauth/start")

    from datetime import datetime, timezone
    expires_at = state_doc.get("expires_at")
    # mongomock 把 aware datetime 存成 naive · 比較前統一補 tz
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at < datetime.now(timezone.utc):
        db.social_oauth_states.delete_one({"state": state})
        raise HTTPException(400, "state 過期(10 min)· 重新從 /social/oauth/start")

    user_email = state_doc["user_email"]
    platform = state_doc["platform"]

    # B1 留 v1.4 · 真打 platform code → token 換
    # 此處 mock · 給 token sample · 模擬成功
    from services import oauth_tokens
    mock_token_response = {
        "access_token": f"MOCK-{platform}-{secrets.token_hex(8)}",
        "refresh_token": None,  # FB 不給 refresh token(用 long-lived)
        "expires_in": 60 * 60 * 24 * 60,  # 60 天 long-lived
        "scopes": ["mock-scope"],
        "account_id": f"mock-{platform}-account-id",
        "account_name": f"{user_email} ({platform})",
    }
    oauth_tokens.store_token(
        db, user_email, platform,
        access_token=mock_token_response["access_token"],
        refresh_token=mock_token_response["refresh_token"],
        expires_in_seconds=mock_token_response["expires_in"],
        scopes=mock_token_response["scopes"],
        account_id=mock_token_response["account_id"],
        account_name=mock_token_response["account_name"],
    )
    # 用後即刪 state · 防重用
    db.social_oauth_states.delete_one({"state": state})

    # 302 回 launcher social view
    return RedirectResponse(url=f"/#social?connected={platform}", status_code=302)


@router.post("/social/oauth/disconnect")
def oauth_disconnect(
    platform: Literal["facebook", "instagram", "linkedin"] = Query(...),
    email: str = require_user_dep(),
):
    """user 主動取消綁定"""
    from services import oauth_tokens
    deleted = oauth_tokens.revoke_token(get_db(), email, platform)
    return {"deleted": deleted, "platform": platform}


@router.get("/social/oauth/status")
def oauth_status(
    user: Optional[str] = None,
    _admin: str = require_admin_dep(),
):
    """admin 看誰連了哪些 platform · 不回 token 本身"""
    from services import oauth_tokens
    return {"connections": oauth_tokens.list_connections(get_db(), user_email=user)}

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
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Header, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, date
from enum import Enum
import os
import json
import uuid
import logging
import asyncio
import hmac
import httpx
from collections import OrderedDict
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
knowledge_sources_col = db.knowledge_sources  # V1.1 §E · 多來源知識庫
knowledge_audit_col = db.knowledge_audit      # /knowledge/read audit trail

# ============================================================
# Codex R7#1 / R7#2 / R7#10 · prod-mode auth 調節 helper
# 必須在 lifespan 之前定義 · 因為 startup 會 call
# ============================================================
def _is_prod() -> bool:
    """環境判斷 · ECC_ENV / NODE_ENV 任一為 production"""
    return (
        os.getenv("ECC_ENV", "").lower() == "production"
        or os.getenv("NODE_ENV", "").lower() == "production"
    )


def _jwt_refresh_configured() -> bool:
    """JWT_REFRESH_SECRET 真有設 · 不是 placeholder"""
    sec = os.getenv("JWT_REFRESH_SECRET", "")
    return bool(sec) and not sec.startswith("<GENERATE")


def _legacy_auth_headers_enabled() -> bool:
    """R7#10 · 是否允許 X-User-Email header fallback
    · prod 預設 OFF(必走 cookie 或 internal token)
    · dev 預設 ON(沒 LibreChat 也能 launcher 開發)
    · prod 若 nginx 沒 strip header · 攻擊者可偽造身份 → 設 ALLOW_LEGACY_AUTH_HEADERS=1 才開"""
    explicit = os.getenv("ALLOW_LEGACY_AUTH_HEADERS", "").strip()
    if explicit == "1":
        return True
    if explicit == "0":
        return False
    # 預設行為 · prod=False · dev=True
    return not _is_prod()


def _env_mode_configured() -> bool:
    """Codex R8#6 · ECC_ENV / NODE_ENV 必須有一個明確設(防誤配 dev mode)"""
    return bool(os.getenv("ECC_ENV", "").strip() or os.getenv("NODE_ENV", "").strip())


def _secrets_equal(a: str, b: str) -> bool:
    """Codex R8#2 · 比 secret 用 hmac.compare_digest 防 timing attack"""
    if not a or not b:
        return False
    try:
        return hmac.compare_digest(a, b)
    except Exception:
        return False


# ============================================================
# Lifespan (FastAPI ≥ 0.93 推薦取代 on_event)
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup · seed + indexes(原 startup 函式內容)
    if accounts_col.count_documents({}) == 0:
        seed_accounts()
    feedback_col.create_index([("agent_name", 1), ("verdict", 1)])
    feedback_col.create_index([("created_at", -1)])
    projects_col.create_index([("status", 1), ("updated_at", -1)])
    projects_col.create_index([("name", 1)])
    audit_col.create_index([("created_at", -1)])
    audit_col.create_index([("user", 1), ("action", 1)])
    db.tender_alerts.create_index([("status", 1), ("discovered_at", -1)])
    db.tender_alerts.create_index([("tender_key", 1)], unique=True, sparse=True)
    db.crm_leads.create_index([("stage", 1), ("updated_at", -1)])
    db.crm_leads.create_index([("source", 1)])
    transactions_col.create_index([("date", -1)])
    transactions_col.create_index([("project_id", 1)])
    invoices_col.create_index([("date", -1)])
    invoices_col.create_index([("status", 1), ("date", -1)])
    knowledge_sources_col.create_index([("enabled", 1), ("created_at", -1)])
    knowledge_sources_col.create_index([("path", 1)], unique=True)
    knowledge_audit_col.create_index([("created_at", -1)])
    knowledge_audit_col.create_index([("user", 1), ("source_id", 1)])
    # Round 9 implicit · log TTL 防無限長(估 10 人 × 50 read/day × 365 ≈ 182k doc/年)
    # PDPA 留 90 天 audit 已綽綽有餘 · admin 想看歷史另存 export
    # R14#4 · 原本 try/except 靜默過 · 若 index 選項不同(TTL) 會留舊的 · TTL 沒生效 · 月 +4GB
    # 修:檢查現有 index · 不符就 drop 再 recreate · fail-loud 確保 TTL 真生效
    _ttl_name = "ttl_90d"
    _ttl_expected = 90 * 24 * 3600
    try:
        _existing = knowledge_audit_col.index_information()
        _wrong = False
        for _n, _info in _existing.items():
            if _n == _ttl_name and _info.get("expireAfterSeconds") != _ttl_expected:
                _wrong = True
                break
        if _wrong:
            knowledge_audit_col.drop_index(_ttl_name)
            logger.info("[ttl] knowledge_audit · drop stale TTL · will recreate")
        knowledge_audit_col.create_index(
            [("created_at", 1)],
            expireAfterSeconds=_ttl_expected,
            name=_ttl_name,
        )
        logger.info("[ttl] knowledge_audit · TTL 90d ensured")
    except Exception as e:
        # 真正意外(非 IndexSame)· 要 loud 警告 · 不能靜默
        logger.error("[ttl] knowledge_audit TTL failed · data bloat risk: %s", e)
    # R20#8 · meetings transcript TTL · Feature #1 · 10 人 × 週 10 × 年 = 5000 doc
    # 留 365 天(年度回顧需要)· 之後自動清 · PDPA
    try:
        db.meetings.create_index([("owner", 1), ("created_at", -1)])
        db.meetings.create_index(
            [("created_at", 1)],
            expireAfterSeconds=365 * 24 * 3600,
            name="ttl_365d",
        )
    except Exception as e:
        logger.warning("[ttl] meetings TTL: %s", e)
    # Feature #5 · scheduled_posts index(cron 掃 queue 主 key)
    try:
        db.scheduled_posts.create_index([("status", 1), ("schedule_at", 1)])
        db.scheduled_posts.create_index([("author", 1), ("created_at", -1)])
    except Exception as e:
        logger.warning("[index] scheduled_posts: %s", e)
    # Feature #7 · site_surveys index
    try:
        db.site_surveys.create_index([("owner", 1), ("created_at", -1)])
        db.site_surveys.create_index([("project_id", 1), ("created_at", -1)])
        # TTL 2 年(活動週期 + 後續復盤)· 過期自動清
        db.site_surveys.create_index(
            [("created_at", 1)],
            expireAfterSeconds=2 * 365 * 24 * 3600,
            name="ttl_2y",
        )
    except Exception as e:
        logger.warning("[index] site_surveys: %s", e)
    # Feature #6 · media_contacts email unique(R21#4 · partial 排除空字串)
    try:
        db.media_contacts.create_index(
            [("email", 1)],
            unique=True,
            partialFilterExpression={"email": {"$type": "string", "$gt": ""}},
        )
        db.media_contacts.create_index([("outlet", 1), ("beats", 1)])
        db.media_pitch_history.create_index([("contact_id", 1), ("pitched_at", -1)])
    except Exception as e:
        logger.warning("[index] media_contacts: %s", e)
    # design_jobs 同樣加 TTL · 圖檔留 Fal CDN · log 純查詢 ROI 用 · 留 180 天
    try:
        db.design_jobs.create_index(
            [("created_at", 1)],
            expireAfterSeconds=180 * 24 * 3600,
            name="ttl_180d",
        )
    except Exception as e:
        logger.warning("[ttl] design_jobs TTL index: %s", e)
    try:
        db.conversations.create_index([("chengfu_summarized_at", -1)])
    except Exception as e:
        logger.debug("[index] conversations.chengfu_summarized_at skip: %s", e)
    logger.info("indexes ensured · app ready")
    # ROADMAP §11.12 + Codex R6#1 / R7#1 · JWT secret 啟動檢查
    # 注意:LibreChat v0.8.4 access token 在 JSON · 不發 token cookie
    # 我們改驗 refreshToken cookie · 用 JWT_REFRESH_SECRET 簽
    # R7#1 · refresh payload 是 {id, sessionId} 不是 {email} · 必須 lookup users
    _jwt_refresh = os.getenv("JWT_REFRESH_SECRET", "")
    if not _jwt_refresh or _jwt_refresh.startswith("<GENERATE"):
        if _is_prod():
            # R7#1 · prod 強制 fail closed · dev/test 仍只 warn
            raise RuntimeError(
                "JWT_REFRESH_SECRET required in production · "
                "從 LibreChat .env 同步 JWT_REFRESH_SECRET 進 accounting "
                "(否則 cookie auth OFF · X-User-Email 可被偽造)"
            )
        logger.warning(
            "[auth] JWT_REFRESH_SECRET 未設或為 placeholder(dev mode)· "
            "Cookie 驗 OFF · admin endpoint 走 X-User-Email 相容路徑(可被偽造)· "
            "production 必設 · 見 docs/05-SECURITY.md"
        )
    else:
        logger.info("[auth] JWT_REFRESH_SECRET 已設 · cookie 驗 ON · admin 強制 trusted")
    # R7#10 · prod legacy header fallback 預設關 · 開發或明確 opt-in 才開
    if not _legacy_auth_headers_enabled():
        logger.info("[auth] X-User-Email legacy fallback OFF · 必走 cookie 或 internal token")
    else:
        logger.warning(
            "[auth] X-User-Email legacy fallback ON · "
            "dev mode 或 ALLOW_LEGACY_AUTH_HEADERS=1 · prod 應確保 nginx 已 strip 此 header"
        )
    # R8#6 · ECC_ENV / NODE_ENV 必須明確設 · 防部署人員忘加 docker-compose env 落回 dev mode
    if not _env_mode_configured():
        raise RuntimeError(
            "ECC_ENV or NODE_ENV must be set explicitly · "
            "預設 dev mode 太危險 · prod 部署必設 ECC_ENV=production"
        )
    # R7#2 + R8#2 · ECC_INTERNAL_TOKEN 啟動時檢查 · prod 強制
    if not os.getenv("ECC_INTERNAL_TOKEN", "").strip():
        if _is_prod():
            raise RuntimeError(
                "ECC_INTERNAL_TOKEN required in production · "
                "cron daily-digest / tender-monitor 須有此 token 呼叫 admin endpoint"
            )
        logger.warning(
            "[auth] ECC_INTERNAL_TOKEN 未設(dev mode 容許)· cron 跨 service 呼叫會 401"
        )
    # Codex Round 10.5 · 啟動時主動探 OCR · /healthz 立刻看得到真狀態
    try:
        from services.knowledge_extract import probe_ocr_startup
        ocr = probe_ocr_startup()
        logger.info("OCR probe · available=%s · langs=%s", ocr.get("available"), ocr.get("langs"))
    except Exception as e:
        logger.warning("OCR startup probe fail: %s", e)
    # R20#1 · Feature #1 recover stuck meeting(container restart 期間 transcribing)
    try:
        from routers.memory import recover_stale_meetings
        recover_stale_meetings(max_stale_minutes=10)
    except Exception as e:
        logger.warning("[meeting] recover_stale 啟動失敗(非致命): %s", e)
    # R23#2 · Feature #7 recover stuck site survey
    try:
        from routers.site_survey import recover_stale_surveys
        recover_stale_surveys(max_stale_minutes=10)
    except Exception as e:
        logger.warning("[site-survey] recover_stale 啟動失敗(非致命): %s", e)
    yield
    # Shutdown
    logger.info("app shutting down")


# ============================================================
# App
# ============================================================
app = FastAPI(
    title="承富會計 API",
    description="承富 AI 系統 · 內建會計模組",
    version="1.0.0",
    lifespan=lifespan,
    # Audit · sec F-1 + tech-debt #2 · 關閉 prod /docs · 防 schema 洩漏
    # 內網開發要看 docs · 設 ECC_DOCS_ENABLED=1
    docs_url="/docs" if os.getenv("ECC_DOCS_ENABLED") == "1" else None,
    openapi_url="/openapi.json" if os.getenv("ECC_DOCS_ENABLED") == "1" else None,
    redoc_url=None,
)

# ============================================================
# Rate limiting · slowapi(Audit · sec F-1)
# 預設按 remote IP 限速 · 高敏 endpoint 加 @limiter.limit("N/minute")
# 注意:單 worker 才用 in-memory · 多 worker 要 Redis backend
# ============================================================
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware


def _user_or_ip(request: Request) -> str:
    """Codex R5#7 + R6#2 + R7#2 · 限速 key 優先 trusted user · IP fallback

    R6#2 抓:SlowAPIMiddleware 在 endpoint dependency 前跑 · request.state 還沒設
    修正:在 key_func 內直接驗 cookie · 不依賴 state

    R7#2 抓:`if request.headers.get("X-Internal-Token")` 只看存在 · 不比對 secret
    任何人 curl 加亂塞 X-Internal-Token: foo 就能打同一 internal bucket
    修正:必須等於 ECC_INTERNAL_TOKEN env value
    """
    # R7#2 + R8#2 · Internal token 必須 secret-equal · 用 hmac.compare_digest 防 timing attack
    expected_internal = os.getenv("ECC_INTERNAL_TOKEN", "").strip()
    provided_internal = (request.headers.get("X-Internal-Token") or "").strip()
    if _secrets_equal(provided_internal, expected_internal):
        return "u:internal"
    # 直接呼叫 _verify_librechat_cookie · 不靠 request.state(middleware 順序問題)
    try:
        verified_email = _verify_librechat_cookie(request)
        if verified_email:
            return f"u:{verified_email}"
    except Exception:
        pass
    # Fallback · IP(nginx X-Forwarded-For 已被 chengfu-proxy.conf 設)
    return f"ip:{get_remote_address(request)}"


_limiter = Limiter(
    key_func=_user_or_ip,
    default_limits=[os.getenv("RATE_LIMIT_DEFAULT", "120/minute")],
    storage_uri="memory://",  # v1.2 改 Redis 才能多 worker 一致
)
app.state.limiter = _limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ============================================================
# CORS · 白名單(env CORS_ORIGINS 逗號分隔覆寫)
# ============================================================
_default_origins = "http://localhost,http://localhost:3080,http://承富-ai.local"
_cors_env = os.getenv("CORS_ORIGINS", _default_origins)
# 另允許 Cloudflare Tunnel 網域(CLOUDFLARE_TUNNEL_DOMAIN 單一值)
_tunnel = os.getenv("CLOUDFLARE_TUNNEL_DOMAIN", "").strip()
_allow_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
if _tunnel:
    _allow_origins.append(f"https://{_tunnel}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-User-Email", "X-User-Role", "X-Request-ID"],
)

# ============================================================
# Request ID + 結構化 log middleware
# ============================================================
logger = logging.getLogger("chengfu")
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","msg":"%(message)s"}',
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        from starlette.responses import JSONResponse
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = rid
        try:
            resp = await call_next(request)
        except HTTPException as e:
            # HTTPException 讓 FastAPI 正常處理 · 但回寫 header
            logger.error(f"rid={rid} http_exc={e.status_code}:{e.detail}")
            resp = JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail, "request_id": rid},
            )
        except Exception as e:
            logger.error(f"rid={rid} unhandled_exc={type(e).__name__}:{e}")
            resp = JSONResponse(
                status_code=500,
                content={"detail": "internal server error", "request_id": rid},
            )
        resp.headers["X-Request-ID"] = rid
        logger.info(f"rid={rid} {request.method} {request.url.path} -> {resp.status_code}")
        return resp


app.add_middleware(RequestIDMiddleware)

# Orchestrator(v2.0 · 主管家跨 Agent 呼叫)
# Audit fix · tech-debt #1 · 不再 silent · ImportError 必 log + 顯示哪邊壞
try:
    from orchestrator import router as orchestrator_router
    app.include_router(orchestrator_router)
    logger.info("orchestrator router loaded · D-010 主管家上線")
except ImportError as e:
    logger.warning(
        "orchestrator 未載入 · D-010/D-011 主管家功能 OFF · 原因: %s",
        e,
    )

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
# Auth · 簡易 RBAC(靠 LibreChat Mongo user role 查 · 非 JWT 硬解)
# ============================================================
_users_col = db.users  # LibreChat 的 users collection

# ADMIN_EMAILS env 白名單(逗號分隔)· 相容舊部署用 ADMIN_EMAIL 單值
_admin_allowlist = {e.strip().lower() for e in (
    os.getenv("ADMIN_EMAILS", os.getenv("ADMIN_EMAIL", "sterio068@gmail.com")).split(",")
) if e.strip()}


def _verify_librechat_cookie(request: Request) -> Optional[str]:
    """Codex R6#1 + R7#1 · 修正 R5#1 + R6#1 錯誤前提

    R5#1 假設 LibreChat 發 `token` cookie · 但 v0.8.4 原始碼:
    - login/refresh 回 JSON {token, user} · access 只在 response body
    - cookie 只設 refreshToken + token_provider
    所以 R5#1 cookie 路徑「永遠 None」= 等於沒做認證強化

    R6#1 改驗 refreshToken · 但只 read `payload.email`
    R7#1 抓:LibreChat refresh payload 實際是 {id, sessionId} · 不是 {email}
    驗證來源:packages/data-schemas/src/methods/session.ts
    所以 R6#1 仍 silent fail · prod cookie 路徑等於沒接

    R7#1 修正:
    1. JWT 解出 payload.id(Mongo ObjectId hex string)
    2. 用 _users_col.find_one({"_id": ObjectId(id)}) 反查 email
    3. 失敗 → None · 走 X-User-Email legacy(若 ALLOW_LEGACY_AUTH_HEADERS)
    4. 為效能 · LRU cache 60 秒(refresh token 7d 期效 · email 變動極少)
    """
    try:
        import jwt as _jwt
        # R6#1 · LibreChat 實際發 refreshToken · 不發 token cookie
        refresh_token = request.cookies.get("refreshToken")
        if not refresh_token:
            return None
        sec = os.getenv("JWT_REFRESH_SECRET", "")
        if not sec or sec.startswith("<GENERATE"):
            return None
        try:
            payload = _jwt.decode(refresh_token, sec, algorithms=["HS256"])
        except _jwt.ExpiredSignatureError:
            logger.debug("[auth] refreshToken expired · user should re-login")
            return None
        except _jwt.InvalidTokenError as e:
            logger.debug("[auth] refreshToken invalid · %s", e)
            return None
        # R7#1 · payload 標準是 {id, sessionId} · email 是 LibreChat 後來加的非標欄位
        # 先試 payload.email(若 LibreChat 升級加上)· 失敗才走 ID lookup(主路徑)
        email_in_payload = (payload.get("email") or "").strip().lower()
        if email_in_payload:
            return email_in_payload
        user_id = payload.get("id") or payload.get("sub") or payload.get("userId")
        if not user_id:
            logger.debug("[auth] refreshToken payload 無 id 欄位 · keys=%s", list(payload.keys()))
            return None
        return _lookup_user_email_cached(str(user_id))
    except Exception as e:
        logger.debug("[auth] cookie verify outer fail: %s", e)
        return None


# R7#1 + R8#1 · 真 LRU cache for user email lookup · 60s TTL(refresh token 7d · email 不常變)
# R8#1 · OrderedDict + popitem(last=False) 真 LRU 語意 · 不再「滿 200 直接清空」
_USER_EMAIL_CACHE: "OrderedDict[str, tuple[str, float]]" = OrderedDict()
_USER_EMAIL_CACHE_TTL = 60.0
_USER_EMAIL_CACHE_MAX = 200


def _lookup_user_email_cached(user_id: str) -> Optional[str]:
    """從 _users_col 反查 email · 60s LRU cache · OrderedDict 真 LRU 不集體 miss"""
    import time
    now = time.time()
    cached = _USER_EMAIL_CACHE.get(user_id)
    if cached and now - cached[1] < _USER_EMAIL_CACHE_TTL:
        # R8#1 · 真 LRU · 命中時 move_to_end 標記為最近使用
        _USER_EMAIL_CACHE.move_to_end(user_id)
        return cached[0] or None
    try:
        # ObjectId 可能 invalid(舊 token)· try-except 包好
        try:
            oid = ObjectId(user_id)
        except Exception:
            return None
        u = _users_col.find_one({"_id": oid}, {"email": 1})
        email = (u.get("email") or "").strip().lower() if u else ""
        # R8#1 · 真 LRU evict · pop 最舊 · 不再 clear 整片
        while len(_USER_EMAIL_CACHE) >= _USER_EMAIL_CACHE_MAX:
            _USER_EMAIL_CACHE.popitem(last=False)
        _USER_EMAIL_CACHE[user_id] = (email, now)
        return email or None
    except Exception as e:
        logger.debug("[auth] users lookup id=%s · %s", user_id, e)
        return None


def current_user_email(
    request: Request,
    x_user_email: Optional[str] = Header(default=None),
) -> Optional[str]:
    """取得當前使用者 email · 優先順序(Codex R3.2 / R7#1 / R7#10):
    1. LibreChat refreshToken cookie + JWT_REFRESH_SECRET + 反查 _users_col(R7#1)
    2. X-User-Email header(legacy · ALLOW_LEGACY_AUTH_HEADERS 才開 · prod 預設 OFF)

    R7#10:prod 若 nginx 沒 strip X-User-Email · 任何人 curl 可偽造 admin。
    所以 prod 預設關 fallback · 只有 dev / 明確 opt-in 才開。
    """
    trusted_email = _verify_librechat_cookie(request)
    if trusted_email:
        request.state.email_trusted = True
        return trusted_email
    request.state.email_trusted = False
    # R7#10 · prod 模式預設關 X-User-Email fallback · 防 nginx 沒 strip 時被偽造
    if not _legacy_auth_headers_enabled():
        return None
    return (x_user_email or "").strip().lower() or None


def require_admin(request: Request,
                  email: Optional[str] = Depends(current_user_email)) -> str:
    """硬權限 · 用在所有 /admin/* 與敏感端點。

    Codex R3.2 / R5#2 · 三道路徑:
    1. Cookie-trusted email + 白名單 / users.role == ADMIN(嚴格 · production)
    2. X-Internal-Token header(cron / 內部 service · ECC_INTERNAL_TOKEN env)
    3. X-User-Email + 白名單 + JWT_SECRET 未設(legacy 測試模式 · production 不接受)
    """
    # ============ Codex R5#2 + R8#2 · 內部 service token(daily-digest cron 用) ============
    # R8#2 · hmac.compare_digest 防 timing attack
    internal_token_expected = os.getenv("ECC_INTERNAL_TOKEN", "").strip()
    if internal_token_expected:
        provided = (request.headers.get("X-Internal-Token") or "").strip()
        if _secrets_equal(provided, internal_token_expected):
            return "internal:cron"

    if not email:
        raise HTTPException(403, "未識別使用者 · 請從 launcher 進入登入")

    trusted = getattr(request.state, "email_trusted", False)
    # R6#1 · 改檢查 JWT_REFRESH_SECRET(cookie 用這個簽)
    _refresh_sec = os.getenv("JWT_REFRESH_SECRET", "")
    jwt_configured = bool(_refresh_sec) and not _refresh_sec.startswith("<GENERATE")

    if not trusted and jwt_configured:
        logger.warning(
            "[auth] admin endpoint %s 被非 cookie 路徑呼叫(email=%s)· 擋",
            request.url.path, email,
        )
        raise HTTPException(
            403,
            "Admin 操作需從 launcher 登入(含 LibreChat cookie)· "
            "X-User-Email header 單獨不足以授權 · 或設 X-Internal-Token"
        )

    if email in _admin_allowlist:
        return email
    try:
        u = _users_col.find_one({"email": email})
        if u and (u.get("role") or "").upper() == "ADMIN":
            return email
    except Exception as e:
        logger.warning("[auth] users.find_one fail email=%s · %s", email, e)
    raise HTTPException(403, f"需要管理員權限 · {email} 不在白名單內")


# ============================================================
# L3 機敏 · 2026-04-21 老闆決議「先不硬擋」
# 保留下方 /safety/classify endpoint 供前端提示用 · 不在 backend 做阻擋
# 未來擴展時:把 LEVEL_3_PATTERNS 複用成 assert_not_l3,這裡就不重複宣告
# ============================================================


# ============================================================
# A · 會計核心 · v1.3 §11.1 B-8 已抽到 routers/accounting.py
# 含 accounts CRUD / transactions / invoices / quotes / pnl / aging / project finance
# DEFAULT_ACCOUNTS + 6 models + 4 helpers(_next_*_no / _account_type_map / _update_project_finance)
# ============================================================
from routers import accounting as _accounting_router
app.include_router(_accounting_router.router)

# 向後相容:lifespan + admin_router 用 main.serialize / main.pnl_report 等
# 重新 export 給其他 router lazy import
seed_accounts = _accounting_router.seed_accounts
pnl_report = _accounting_router.pnl_report


# ============================================================
# B · 專案 + Handoff · v1.3 §11.1 B-10 已抽到 routers/projects.py
# 含 /projects CRUD + /projects/{id}/handoff GET/PUT(B2 4 格卡)
# ============================================================
from routers import projects as _projects_router
app.include_router(_projects_router.router)


# ============================================================
# C · 回饋(👍👎)· ROADMAP §11.1 已抽到 routers/feedback.py
# ============================================================
from routers import feedback as _feedback_router
app.include_router(_feedback_router.router)


# ============================================================
# D · Admin · ROADMAP §11.1 B-7 已抽到 routers/admin.py
# 含 dashboard / export / import / audit-log / email / monthly-report /
# cost / adoption / budget-status / top-users / tender-funnel / agent-prompts
# settings(_USD_TO_NTD / _MONTHLY_BUDGET_NTD / 等)留 main · admin.py lazy import
# /quota/check + /quota/preflight 仍在 main(slowapi 緊耦合 · nginx auth_request 直連)
# ============================================================
from routers import admin as _admin_router
# R11#1 真動態註冊 rate-limited route(原 reassign send_email 對 @router.post 已 capture 的 fn 無效)
# 必須在 include_router 之前呼叫 · 才會 add_api_route 進 router
_admin_router.register_rate_limited_routes(_limiter.limit("20/hour"))
app.include_router(_admin_router.router)



# Tenders · ROADMAP §11.1 已抽到 routers/tenders.py
from routers import tenders as _tenders_router
app.include_router(_tenders_router.router)




# ============================================================
# Admin / ROI / Quota endpoints · v5 重構(拆到 services/admin_metrics.py)
# 下方只保留 thin wrapper:呼叫 service + require_admin decorator
# Service 內部邏輯見 backend/accounting/services/admin_metrics.py
# ============================================================
from services import admin_metrics

# Settings · R14#6 · 改從 config.py 集中 · 保留 alias 向後相容
# 舊 code / test_main.py 仍用 main._USD_TO_NTD 等 · 改指向 config.settings
from config import settings as _settings
_USD_TO_NTD = _settings.usd_to_ntd
_MONTHLY_BUDGET_NTD = _settings.monthly_budget_ntd
_USER_SOFT_CAP_DEFAULT = _settings.user_soft_cap_ntd
QUOTA_MODE = _settings.quota_mode
QUOTA_OVERRIDE_EMAILS = set(_settings.quota_override_emails)



@app.get("/quota/check")
def quota_check(email: Optional[str] = Depends(current_user_email)):
    """Launcher 送對話前先打 · 超 100% 直接擋送(hard_stop 模式)"""
    return admin_metrics.quota_check(
        db, _users_col, email,
        mode=QUOTA_MODE,
        override_emails=QUOTA_OVERRIDE_EMAILS,
        admin_allowlist=_admin_allowlist,
        user_soft_cap_ntd=_USER_SOFT_CAP_DEFAULT,
        usd_to_ntd=_USD_TO_NTD,
    )


@app.get("/quota/preflight")
@_limiter.limit(os.getenv("RATE_LIMIT_QUOTA_PREFLIGHT", "60/minute"))
def quota_preflight(request: Request, email: Optional[str] = Depends(current_user_email)):
    """Codex R7#9 + R8#3 · nginx auth_request 用 · 看 user 是否仍在預算內

    回應 contract:
    - 204 No Content · 通過(允許 LibreChat /api/ask)
    - 429 Too Many Requests · 擋 · 帶 X-Quota-* response headers 給 nginx error_page 用
    - 401 · 沒驗到身份(prod 嚴格擋 · dev 視為通過 · 給 launcher 開發空間)

    使用方式(nginx):
        location = /_quota_gate {
            internal;
            proxy_pass http://accounting:8000/quota/preflight;
        }
        location /api/ask {
            auth_request /_quota_gate;
            auth_request_set $quota_spent_ntd $upstream_http_x_quota_spent_ntd;
            ...
        }

    R8#3 · 加 60/min 專屬 rate limit(防 user 連發 100 次 /api/ask 打死 quota_check)
    """
    from starlette.responses import Response
    from fastapi.responses import JSONResponse
    if not email:
        # prod 嚴格 · dev 放行給 launcher 開發
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
        # R8#3 · 透過 X-Quota-* response headers 把細節傳給 nginx error_page
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



# ============================================================
# F · Fal.ai Recraft v3 · ROADMAP §11.1 已抽到 routers/design.py
# ============================================================
from routers import design as _design_router
app.include_router(_design_router.router)




# ============================================================
# E · 安全 · Level 03 內容分級檢查 · ROADMAP §11.1 已抽到 routers/safety.py
# ============================================================
from routers import safety as _safety_router
app.include_router(_safety_router.router)


# ============================================================
# Context Summary · v1.3 §11.1 B-11 已抽到 routers/memory.py
# /memory/summarize-conversation · Haiku 摘要 · 省 60% context token
# ============================================================
from routers import memory as _memory_router
app.include_router(_memory_router.router)


# ============================================================
# User Preferences · ROADMAP §11.1 已抽到 routers/users.py
# ============================================================
from routers import users as _users_router
app.include_router(_users_router.router)


# ============================================================
# CRM Pipeline · v1.3 §11.1 B-9 已抽到 routers/crm.py
# Kanban · 標案 → 提案 → 得標 → 執行 → 結案 · 7 endpoint
# ============================================================
from routers import crm as _crm_router
app.include_router(_crm_router.router)

# ============================================================
# Media CRM · v1.2 Feature #6 · 記者資料庫 + 推薦(routers/media.py)
# ============================================================
from routers import media as _media_router
app.include_router(_media_router.router)

# ============================================================
# Social scheduler · v1.2 Feature #5 · FB/IG/LinkedIn 貼文排程
# ============================================================
from routers import social as _social_router
app.include_router(_social_router.router)

# ============================================================
# Site Survey · v1.2 Feature #7 · 場勘 PWA + Claude Vision
# ============================================================
from routers import site_survey as _site_survey_router
app.include_router(_site_survey_router.router)

# ============================================================
# G · 多來源知識庫 · ROADMAP §11.1 B-6 已抽到 routers/knowledge.py
# E-1 · /admin/sources CRUD + health
# E-2 · /knowledge/list,read,search · multi-format extract · Meili index
# §10.3 · X-Agent-Num server-side derive 也在 routers/knowledge.py
# ============================================================
from routers import knowledge as _knowledge_router
app.include_router(_knowledge_router.router)

# ============================================================
# Health
# ============================================================
@app.get("/healthz")
def health():
    from services.knowledge_extract import ocr_status
    return {
        "status": "ok",
        "mongo": db.name,
        "accounts": accounts_col.count_documents({}),
        "projects": projects_col.count_documents({}),
        "feedback": feedback_col.count_documents({}),
        "knowledge_sources": knowledge_sources_col.count_documents({"enabled": True}),
        "ocr": ocr_status(),  # Round 9 implicit · OCR tesseract 缺失曝光
    }


# startup() 已 migrate 到上方 lifespan() · 此處留空避免重複註冊

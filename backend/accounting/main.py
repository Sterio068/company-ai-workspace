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
    try:
        knowledge_audit_col.create_index(
            [("created_at", 1)],
            expireAfterSeconds=90 * 24 * 3600,
            name="ttl_90d",
        )
    except Exception as e:
        # 如果 index 已存在 + TTL 不同 · 不擋啟動
        logger.warning("[ttl] knowledge_audit TTL index: %s", e)
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
    r = accounts_col.insert_one({**acc.model_dump(), "created_at": datetime.utcnow()})
    return {"id": str(r.inserted_id)}


# ============================================================
# Endpoints · 交易
# ============================================================
@app.post("/transactions")
def create_transaction(tx: Transaction):
    for code in [tx.debit_account, tx.credit_account]:
        if not accounts_col.find_one({"code": code}):
            raise HTTPException(400, f"科目 {code} 不存在")
    data = tx.model_dump()
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
    data = inv.model_dump()
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
def _account_type_map() -> dict:
    """Audit perf #1+#2 · 一次撈所有 account.type 進 dict
    Mongo accounts ~30 列 + 不常變 · 替代 N+1 find_one
    每次 _update_project_finance / pnl_report 共用"""
    return {a["code"]: a.get("type") for a in accounts_col.find({}, {"code": 1, "type": 1, "_id": 0})}


def _update_project_finance(project_id: str):
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
    """損益表(收入 - 費用)。Audit perf #2 · 一次撈 accounts dict 取代 find_one 迴圈"""
    txs = list(transactions_col.find({"date": {"$gte": date_from, "$lte": date_to}}))
    accounts_map = {a["code"]: a for a in accounts_col.find({})}  # code -> doc
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
    data = p.model_dump()
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()
    r = projects_col.insert_one(data)
    return {"id": str(r.inserted_id)}


@app.put("/projects/{project_id}")
def update_project(project_id: str, p: Project):
    data = p.model_dump(exclude_unset=True)  # py-review #1 · pydantic v2 一致
    data["updated_at"] = datetime.utcnow()
    r = projects_col.update_one({"_id": ObjectId(project_id)}, {"$set": data})
    return {"updated": r.modified_count}


@app.delete("/projects/{project_id}")
def delete_project(project_id: str):
    r = projects_col.delete_one({"_id": ObjectId(project_id)})
    return {"deleted": r.deleted_count}


# ------------------------------------------------------------
# B2 · Handoff 4 格卡(跨助手 · 跨人 · 跨日的交棒 artifact)
# V1.1-SPEC §C · 獨立 endpoint 不用 PUT /projects/{id} 全量更新
# ------------------------------------------------------------
class HandoffAssetRef(BaseModel):
    type: Literal["nas", "url", "file", "note"] = "note"
    label: str = ""
    ref: str = ""


class HandoffCard(BaseModel):
    goal: str = ""
    constraints: list[str] = []
    asset_refs: list[HandoffAssetRef] = []
    next_actions: list[str] = []
    source_conversation_id: Optional[str] = None


@app.put("/projects/{project_id}/handoff")
def update_handoff(project_id: str, card: HandoffCard, request: Request):
    """PM 存完 · 多分頁 BroadcastChannel 會通知其他同仁 re-render。"""
    email = (request.headers.get("X-User-Email") or "").strip().lower() or None
    payload = {
        **card.model_dump(),
        "updated_by": email,
        "updated_at": datetime.utcnow(),
    }
    try:
        r = projects_col.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {"handoff": payload, "updated_at": datetime.utcnow()}},
        )
    except Exception:
        raise HTTPException(400, "project_id 格式錯誤")
    if r.matched_count == 0:
        raise HTTPException(404, "專案不存在")
    return {"ok": True, "updated_at": payload["updated_at"].isoformat()}


@app.get("/projects/{project_id}/handoff")
def get_handoff(project_id: str):
    try:
        doc = projects_col.find_one(
            {"_id": ObjectId(project_id)}, {"handoff": 1, "name": 1}
        )
    except Exception:
        raise HTTPException(400, "project_id 格式錯誤")
    if not doc:
        raise HTTPException(404, "專案不存在")
    h = doc.get("handoff") or {}
    # datetime → isoformat · 前端可直接 JSON.parse
    if isinstance(h.get("updated_at"), datetime):
        h["updated_at"] = h["updated_at"].isoformat()
    return {"project_name": doc.get("name", ""), "handoff": h}


# ============================================================
# C · 回饋(👍👎)· ROADMAP §11.1 已抽到 routers/feedback.py
# ============================================================
from routers import feedback as _feedback_router
app.include_router(_feedback_router.router)


# ============================================================
# D · 管理 / 儀表板
# ============================================================
@app.get("/admin/dashboard")
def admin_dashboard(_admin: str = Depends(require_admin)):
    """一頁式承富 AI 系統總覽。"""
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    today_str = today.isoformat()

    # 會計摘要
    pnl = pnl_report(month_start, today_str)

    # 專案
    active_projects = projects_col.count_documents({"status": "active"})
    total_projects = projects_col.count_documents({})

    # 回饋(ROADMAP §11.1 + R6#4 · 用內部 helper · 跳過 admin Depends)
    from routers.feedback import _compute_feedback_stats
    fb_stats = _compute_feedback_stats()
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
def clear_demo_data(_admin: str = Depends(require_admin)):
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
def export_all_data(_admin: str = Depends(require_admin)):
    """一鍵匯出 · ROADMAP §11.14 · streaming JSON 不全 list memory
    對一年 transactions(數十 MB)· 原 list() 序列化期間 worker 凍結
    改 StreamingResponse · 逐 collection yield · memory 平穩"""
    from fastapi.responses import StreamingResponse

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
                # 逐 doc serialize · 一次只一個進 memory
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


class ImportData(BaseModel):
    """資料匯入(例:從另一台機還原 · 或接受夥伴公司資料)。"""
    accounts: list = []
    projects: list = []
    transactions: list = []
    invoices: list = []
    quotes: list = []


@app.post("/admin/import")
def import_data(payload: ImportData, _admin: str = Depends(require_admin)):
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
# Audit log · ROADMAP §11.9 · 目前無前端 caller
# 用途:Day 0 / 維運期 Sterio curl 直接查 · v1.2 接 admin UI 後會生量
# 不刪因為 D-009 Level 4 Learning 雛形會用
# ============================================================
@app.get("/admin/audit-log")
def audit_log(action: Optional[str] = None,
    user: Optional[str] = None,
    limit: int = 100, _admin: str = Depends(require_admin)):
    """查 audit_log · 給 admin 維運期手動 curl 用(無前端 UI · v1.2 補)"""
    q = {}
    if action: q["action"] = action
    if user:   q["user"] = user
    return serialize(list(audit_col.find(q).sort("created_at", -1).limit(limit)))


@app.post("/admin/audit-log")
def log_action(action: str, user: str, resource: Optional[str] = None, details: Optional[dict] = None, _admin: str = Depends(require_admin)):
    """寫 audit · 給未來 Agent / orchestrator 寫敏感操作(目前 0 caller)"""
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
@_limiter.limit("20/hour")  # Audit sec F-1 · 防 SMTP 帳號濫用 · 月報 + 警告夠用
def send_email(msg: EmailNotification, request: Request,
               _admin: str = Depends(require_admin)):
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
def send_monthly_report_to_admin(_admin: str = Depends(require_admin)):
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


# Tenders · ROADMAP §11.1 已抽到 routers/tenders.py
from routers import tenders as _tenders_router
app.include_router(_tenders_router.router)


@app.get("/admin/monthly-report")
def monthly_report(month: Optional[str] = None, _admin: str = Depends(require_admin)):
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
        "agents": (lambda: __import__("routers.feedback", fromlist=["_compute_feedback_stats"])._compute_feedback_stats())(),
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


# ============================================================
# Admin / ROI / Quota endpoints · v5 重構(拆到 services/admin_metrics.py)
# 下方只保留 thin wrapper:呼叫 service + require_admin decorator
# Service 內部邏輯見 backend/accounting/services/admin_metrics.py
# ============================================================
from services import admin_metrics

# Settings · 從 env 讀 · 傳進 service
_USD_TO_NTD = float(os.getenv("USD_TO_NTD", "32.5"))
_MONTHLY_BUDGET_NTD = float(os.getenv("MONTHLY_BUDGET_NTD", "12000"))
_USER_SOFT_CAP_DEFAULT = float(os.getenv("USER_SOFT_CAP_NTD", "1200"))
QUOTA_MODE = os.getenv("QUOTA_MODE", "soft_warn")  # hard_stop | soft_warn | off
QUOTA_OVERRIDE_EMAILS = {e.strip().lower() for e in os.getenv("QUOTA_OVERRIDE_EMAILS", "").split(",") if e.strip()}


@app.get("/admin/cost")
def cost_summary(days: int = 30, _admin: str = Depends(require_admin)):
    """粗估 API cost by model"""
    return admin_metrics.cost_by_model(db, days)


@app.get("/admin/adoption")
def adoption_summary(days: int = 7, _admin: str = Depends(require_admin)):
    """Codex Round 10.5 黃 6 · 支撐 BOSS-VIEW ROI 公式的 adoption 數字

    回:active_users / calls_distribution / handoff 填寫率 / Fal 本期成本 / 滿意度
    Champion 週報 + Day +3 / Day +14 里程碑量測
    """
    return admin_metrics.adoption_metrics(
        db, _users_col, projects_col, feedback_col,
        days=days, usd_to_ntd=_USD_TO_NTD,
    )


@app.get("/admin/librechat-contract")
def librechat_contract(_admin: str = Depends(require_admin)):
    """升版後第一件事 · 驗 LibreChat 私有 schema 是否還相容"""
    return admin_metrics.librechat_contract(db)


@app.post("/admin/ocr/reprobe")
def reprobe_ocr(_admin: str = Depends(require_admin)):
    """Codex R2.5 · 不用重啟容器就能重試 OCR probe
    維運場景:tesseract 裝完 / TESSDATA_PREFIX 修完 / 臨時語言包問題解完"""
    from services.knowledge_extract import reset_ocr_cache, probe_ocr_startup
    reset_ocr_cache()
    return probe_ocr_startup()


@app.get("/admin/budget-status")
def budget_status(_admin: str = Depends(require_admin)):
    """本月預算進度 · 給 Launcher 首頁進度條 + email 預警用"""
    return admin_metrics.budget_status(db, _MONTHLY_BUDGET_NTD, _USD_TO_NTD)


@app.get("/admin/top-users")
def top_users(days: int = 30, limit: int = 10, _admin: str = Depends(require_admin)):
    """Top N 用量同仁"""
    return admin_metrics.top_users(db, _users_col, days, limit,
                                     _USER_SOFT_CAP_DEFAULT, _USD_TO_NTD)


@app.get("/admin/tender-funnel")
def tender_funnel(_admin: str = Depends(require_admin)):
    """本月標案漏斗"""
    return admin_metrics.tender_funnel(db)


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
# User Preferences · ROADMAP §11.1 已抽到 routers/users.py
# ============================================================
from routers import users as _users_router
app.include_router(_users_router.router)


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
    data = lead.model_dump()
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
def list_agent_prompts(_admin: str = Depends(require_admin)):
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
def update_agent_prompt(payload: AgentPromptUpdate, _admin: str = Depends(require_admin)):
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
def revert_agent_prompt(agent_num: str, _admin: str = Depends(require_admin)):
    """還原 Agent prompt 為原始 JSON 版。"""
    r = db.agent_overrides.delete_one({"agent_num": agent_num})
    return {"reverted": r.deleted_count > 0}


# ============================================================
# G · 多來源知識庫(V1.1-SPEC §E · 老闆 Q3 · 不只 NAS)
# E-1:knowledge_sources collection + Admin CRUD + 公開讀取 API
# E-2:多格式抽字 + Meili 索引 cron(另一批)
# E-3:前端 Admin UI + 知識庫 view(另一批)
# ============================================================
import fnmatch
from services import knowledge_indexer
from services.knowledge_extract import extract as extract_file

# Meili client · 延遲初始化(container 啟動順序不保證 Meili 已 ready)
_meili_client = None


def _get_meili_client():
    global _meili_client
    if _meili_client is not None:
        return _meili_client
    try:
        import meilisearch
        host = os.getenv("MEILI_HOST", "http://meilisearch:7700")
        key = os.getenv("MEILI_MASTER_KEY", "")
        _meili_client = meilisearch.Client(host, key)
        return _meili_client
    except Exception as e:
        logger.warning("[knowledge] Meili client init failed: %s", e)
        return None


# 允許掛載的 source root 白名單(Codex Round 10.5 · 收緊到公司域)
# /Users 過寬 · 離職員工桌面會被索引 · 預設只開 /Volumes(NAS)+ /data(容器 bind mount)
# /Users + /mnt 要用請透過 env 明確打開 · 強迫老闆或 Sterio 知情同意
_ALLOWED_SOURCE_ROOTS = [
    p.strip() for p in os.getenv(
        "KNOWLEDGE_ALLOWED_ROOTS",
        "/Volumes,/data,/tmp/chengfu-test-sources"  # 預設不含 /Users · /mnt
    ).split(",") if p.strip()
]


def _validate_source_path(abs_path: str):
    """路徑必須在允許 root 之下 · 防止意外把 /etc 或 /root 索引進去

    Codex Round 10.5 fix · 用 realpath 解 symlink
    否則使用者可建 /data/my-link → /Users/other-user/secrets · 繞過白名單
    """
    # 先 realpath(解 symlink)· 再 abspath(去掉 ../)
    try:
        resolved = os.path.realpath(abs_path)
    except Exception as e:
        raise HTTPException(400, f"路徑解析失敗:{e}")
    resolved = os.path.abspath(resolved)
    allowed = any(
        resolved == os.path.realpath(root) or
        resolved.startswith(os.path.realpath(root).rstrip("/") + "/")
        for root in _ALLOWED_SOURCE_ROOTS
    )
    if not allowed:
        raise HTTPException(
            400,
            f"路徑 {resolved}(原 {abs_path}) 不在允許清單 {_ALLOWED_SOURCE_ROOTS} · "
            "請改環境變數 KNOWLEDGE_ALLOWED_ROOTS(但先確認為公司擁有的資料夾)",
        )
    return resolved


class KnowledgeSource(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: Literal["smb", "local", "symlink", "usb"] = "local"
    path: str = Field(min_length=1)
    exclude_patterns: list[str] = [
        "*.lock", "~$*", ".DS_Store", "Thumbs.db", ".git/*",
    ]
    agent_access: list[str] = []  # 空=所有 Agent 可讀
    mime_whitelist: Optional[list[str]] = None  # null=全收
    max_size_mb: int = Field(default=50, ge=1, le=500)


class KnowledgeSourcePatch(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    exclude_patterns: Optional[list[str]] = None
    agent_access: Optional[list[str]] = None
    mime_whitelist: Optional[list[str]] = None
    max_size_mb: Optional[int] = Field(default=None, ge=1, le=500)


def _serialize_source(doc: dict) -> dict:
    """MongoDB doc → JSON · ObjectId & datetime → str"""
    if not doc:
        return {}
    out = dict(doc)
    out["id"] = str(out.pop("_id"))
    for k in ("created_at", "updated_at", "last_indexed_at"):
        v = out.get(k)
        if isinstance(v, datetime):
            out[k] = v.isoformat()
    return out


@app.get("/admin/sources")
def list_sources(_admin: str = Depends(require_admin)):
    """列所有資料源 · 包含 disabled(Admin UI 才看到 disabled)"""
    docs = list(knowledge_sources_col.find({}).sort("created_at", -1))
    return [_serialize_source(d) for d in docs]


@app.post("/admin/sources")
def create_source(src: KnowledgeSource, admin_email: str = Depends(require_admin)):
    """建一個資料源 · 驗路徑存在且在 allowed roots 之下。

    回 {id, validation} · 建立後 cron 下次會自動 reindex
    (E-2 會加 reindex_source_async 觸發即時索引)
    """
    abs_path = _validate_source_path(src.path)
    if not os.path.exists(abs_path):
        raise HTTPException(
            400,
            f"路徑不存在或容器無法 mount:{abs_path} · "
            "若是 NAS 請先 mount 再建 source",
        )
    if not os.access(abs_path, os.R_OK):
        raise HTTPException(403, f"路徑無讀取權限:{abs_path}")
    # 避免重複路徑
    if knowledge_sources_col.find_one({"path": abs_path}):
        raise HTTPException(409, f"路徑已登記為資料源:{abs_path}")

    doc = src.model_dump()
    doc.update({
        "enabled": True,
        "path": abs_path,
        "last_indexed_at": None,
        "last_index_stats": None,
        "created_by": admin_email,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    r = knowledge_sources_col.insert_one(doc)
    sid = str(r.inserted_id)
    _invalidate_sources_cache()  # ROADMAP §11.5
    logger.info("[knowledge] source created: %s (%s) by %s", sid, abs_path, admin_email)
    return {
        "id": sid,
        "validation": {"path_exists": True, "readable": True, "abs_path": abs_path},
    }


@app.patch("/admin/sources/{source_id}")
def update_source(
    source_id: str,
    patch: KnowledgeSourcePatch,
    _admin: str = Depends(require_admin),
):
    """更新 source · 路徑不可改(太容易亂 index)· 要換 path 請刪再建"""
    try:
        _id = ObjectId(source_id)
    except Exception:
        raise HTTPException(400, "source_id 格式錯誤")
    updates = {k: v for k, v in patch.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        raise HTTPException(400, "沒有可更新欄位")
    updates["updated_at"] = datetime.utcnow()
    r = knowledge_sources_col.update_one({"_id": _id}, {"$set": updates})
    if r.matched_count == 0:
        raise HTTPException(404, "資料源不存在")
    _invalidate_sources_cache()  # ROADMAP §11.5
    return {"ok": True, "updated": r.modified_count}


@app.delete("/admin/sources/{source_id}")
def delete_source(source_id: str, _admin: str = Depends(require_admin)):
    """刪 source · 連帶從 Meili 清此 source 的文件(best-effort · Meili 掛也不擋刪)"""
    try:
        _id = ObjectId(source_id)
    except Exception:
        raise HTTPException(400, "source_id 格式錯誤")
    doc = knowledge_sources_col.find_one_and_delete({"_id": _id})
    if not doc:
        raise HTTPException(404, "資料源不存在")
    _invalidate_sources_cache()  # ROADMAP §11.5
    # 從 Meili 清這個 source 的所有文件
    meili = _get_meili_client()
    cleanup = knowledge_indexer.delete_source_from_index(source_id, meili) \
        if meili else {"ok": False, "reason": "meili not configured"}
    logger.info("[knowledge] source deleted: %s · meili_cleanup=%s", source_id, cleanup)
    return {"ok": True, "name": doc.get("name"), "meili_cleanup": cleanup}


@app.get("/admin/sources/{source_id}/health")
def source_health(source_id: str, _admin: str = Depends(require_admin)):
    """Round 9 暗示風險 · NAS SMB 睡眠斷線偵測

    macOS SMB autofs 在 sleep 後常掛失效 · 索引 cron 跑時看似空 source
    這個 endpoint 主動檢查 mount 狀態 + 路徑可讀 + 大致檔案數
    Admin UI / Uptime Kuma 可定期 ping
    """
    try:
        _id = ObjectId(source_id)
    except Exception:
        raise HTTPException(400, "source_id 格式錯誤")
    src = knowledge_sources_col.find_one({"_id": _id})
    if not src:
        raise HTTPException(404, "資料源不存在")

    path = src["path"]
    health = {
        "source_id": source_id,
        "name": src.get("name"),
        "path": path,
        "enabled": src.get("enabled", True),
        "checked_at": datetime.utcnow().isoformat(),
    }

    # 1. 路徑存在?
    health["path_exists"] = os.path.exists(path)
    if not health["path_exists"]:
        health["status"] = "unreachable"
        health["issue"] = (
            f"路徑無法到達 · {path} · "
            "若是 SMB/NAS · 可能 Mac sleep 後 mount 失效 · "
            "請手動跑 mount -t smbfs ... 重掛"
        )
        return health

    # 2. 可讀?
    health["readable"] = os.access(path, os.R_OK)
    if not health["readable"]:
        health["status"] = "permission_denied"
        health["issue"] = "路徑存在但 accounting 容器沒讀權限 · 檢查 NAS 帳號權限"
        return health

    # 3. 是不是空目錄(掛壞了會看似空)
    try:
        entries = os.listdir(path)
        health["entry_count"] = len(entries)
    except Exception as e:
        health["status"] = "list_error"
        health["issue"] = f"列目錄失敗:{type(e).__name__}: {e}"
        return health

    # 4. 與上次索引的檔案數對比 · 落差太大 = 警告(可能 mount 壞但 path 仍 exist)
    last_stats = src.get("last_index_stats") or {}
    last_count = last_stats.get("file_count", 0)
    if last_count >= 50 and health["entry_count"] == 0:
        health["status"] = "suspicious_empty"
        health["issue"] = (
            f"上次索引 {last_count} 檔 · 目前 top-level 為空 · "
            "強烈懷疑 NAS mount 失效"
        )
        return health

    health["status"] = "ok"
    return health


@app.get("/admin/sources/health")
def all_sources_health(_admin: str = Depends(require_admin)):
    """所有 enabled sources 一鍵巡檢 · 給 Uptime Kuma / Admin dashboard 用"""
    results = []
    summary = {"ok": 0, "unreachable": 0, "suspicious": 0, "other": 0}
    for src in knowledge_sources_col.find({"enabled": True}):
        sid = str(src["_id"])
        try:
            h = source_health(sid, _admin=_admin)
        except HTTPException as e:
            h = {"source_id": sid, "name": src.get("name"),
                 "status": "error", "issue": str(e.detail)}
        results.append(h)
        s = h.get("status", "other")
        if s == "ok":
            summary["ok"] += 1
        elif s == "unreachable":
            summary["unreachable"] += 1
        elif s == "suspicious_empty":
            summary["suspicious"] += 1
        else:
            summary["other"] += 1
    return {
        "checked_at": datetime.utcnow().isoformat(),
        "summary": summary,
        "sources": results,
    }


@app.post("/admin/sources/{source_id}/reindex")
def reindex_source_endpoint(source_id: str, _admin: str = Depends(require_admin)):
    """手動觸發 reindex · 同步執行(source 不大時可以接受)。

    大 source(> 5000 檔)建議走 cron 或背景 task(v1.2 做 Celery / ARQ)
    """
    try:
        _id = ObjectId(source_id)
    except Exception:
        raise HTTPException(400, "source_id 格式錯誤")
    src = knowledge_sources_col.find_one({"_id": _id})
    if not src:
        raise HTTPException(404, "資料源不存在")
    if not src.get("enabled"):
        raise HTTPException(400, "資料源已停用")
    meili = _get_meili_client()
    stats = knowledge_indexer.reindex_source(source_id, knowledge_sources_col, meili)
    return stats


# ------------------------------------------------------------
# 公開讀取 API · 同仁 + Agent 都可叫
# ------------------------------------------------------------
def _path_is_excluded(rel_path: str, excludes: list[str]) -> bool:
    """fnmatch pattern 檢查 · 包含檔名與路徑層級"""
    name = os.path.basename(rel_path)
    for pat in excludes or []:
        if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel_path, pat):
            return True
        # 資料夾 pattern(結尾 /*)也比對 parent
        if pat.endswith("/*") and rel_path.startswith(pat[:-2].lstrip("/") + "/"):
            return True
    return False


@app.get("/knowledge/list")
def knowledge_list(source_id: Optional[str] = None, project: Optional[str] = None,
                   request: Request = None):
    """列資料源 / 列某 source 下的 top-level 資料夾 / 列某資料夾下的檔

    Round 9 Q3 · 無 source_id 時依 X-Agent-Num 過濾
    未授權 Agent 連 source 名稱都看不到(PR 公司客戶名單本身就是機敏)
    """
    # 無 source_id · 回所有 enabled sources(依 agent_access 過濾)
    if not source_id:
        agent_num = (request.headers.get("X-Agent-Num") if request else None)
        docs = list(knowledge_sources_col.find(
            {"enabled": True},
            {"_id": 1, "name": 1, "type": 1, "path": 1, "last_index_stats": 1,
             "agent_access": 1},
        ))
        # Q3 + Codex R3.3 · agent_num 在白名單外的 source 完全藏起
        # 原邏輯:agent_num 有值才過濾 · 不帶 header 就看到全部(含機敏)
        # 新邏輯:source 有 agent_access 白名單 → 必需對應 agent_num 才看得到
        #         source 無 agent_access(空 []) → 公開 · 所有人可見
        docs = [d for d in docs
                if not d.get("agent_access") or
                (agent_num and agent_num in d["agent_access"])]
        return {
            "sources": [
                {
                    "id": str(d["_id"]),
                    "name": d["name"],
                    "type": d["type"],
                    "file_count": (d.get("last_index_stats") or {}).get("file_count", 0),
                }
                for d in docs
            ]
        }

    try:
        _id = ObjectId(source_id)
    except Exception:
        raise HTTPException(400, "source_id 格式錯誤")
    src = knowledge_sources_col.find_one({"_id": _id, "enabled": True})
    if not src:
        raise HTTPException(404, "資料源不存在或已停用")

    # Agent 存取權限檢查
    agent_num = (request.headers.get("X-Agent-Num") if request else None)
    # Codex R3.3 · source 有 agent_access 白名單時 · 缺 X-Agent-Num 預設拒絕
    # 否則直接呼叫 API 不帶 header 可繞過限制 · 看到「只給投標助手」的機敏資料
    if src.get("agent_access") and (not agent_num or agent_num not in src["agent_access"]):
        raise HTTPException(403, f"此資料源未開放給 #{agent_num} 助手")

    # Codex R3.4 · 用 realpath + commonpath 取代 abspath.startswith
    base = os.path.realpath(src["path"])
    target = os.path.realpath(os.path.join(base, project)) if project else base
    # path traversal 防護(含 symlink)
    try:
        common = os.path.commonpath([base, target])
    except ValueError:
        raise HTTPException(403, "路徑越界")
    if common != base:
        raise HTTPException(403, "路徑越界(symlink 或 ../ 逃逸)")
    if not os.path.isdir(target):
        raise HTTPException(404, "資料夾不存在")

    excludes = src.get("exclude_patterns", [])
    entries = []
    try:
        for name in sorted(os.listdir(target)):
            if name.startswith("."):
                continue
            rel = os.path.relpath(os.path.join(target, name), base)
            if _path_is_excluded(rel, excludes):
                continue
            full = os.path.join(target, name)
            is_dir = os.path.isdir(full)
            entries.append({
                "name": name,
                "rel_path": rel,
                "is_dir": is_dir,
                "size": os.path.getsize(full) if not is_dir else None,
            })
    except PermissionError:
        raise HTTPException(403, "資料夾讀取權限不足")

    return {
        "source_id": source_id,
        "source_name": src["name"],
        "rel_path": project or "",
        "entries": entries,
    }


@app.get("/knowledge/read")
def knowledge_read(
    source_id: str,
    rel_path: str,
    request: Request,
):
    """讀某 source 內某檔的 metadata + 前 2000 字預覽。

    E-1 只做 metadata(size/modified/mime 猜測)· 真正抽字在 E-2 做。
    安全:path traversal 強制 · agent_access 白名單 · audit log 寫進 knowledge_audit
    """
    try:
        _id = ObjectId(source_id)
    except Exception:
        raise HTTPException(400, "source_id 格式錯誤")
    src = knowledge_sources_col.find_one({"_id": _id, "enabled": True})
    if not src:
        raise HTTPException(404, "資料源不存在或已停用")

    # Agent 存取權限
    agent_num = request.headers.get("X-Agent-Num")
    # Codex R3.3 · source 有 agent_access 白名單時 · 缺 X-Agent-Num 預設拒絕
    # 否則直接呼叫 API 不帶 header 可繞過限制 · 看到「只給投標助手」的機敏資料
    if src.get("agent_access") and (not agent_num or agent_num not in src["agent_access"]):
        raise HTTPException(403, f"此資料源未開放給 #{agent_num} 助手")

    # path traversal 防護(Codex R3.4 · realpath 解 symlink 再 commonpath)
    # 僅 abspath 不夠 · 使用者可在 source 內放 symlink 指向 source 外
    # 例:/Volumes/NAS/projects/link -> /Users/other/secrets
    # abspath 只做字面 ../ 解析 · 不跟 symlink · 仍會通過
    base = os.path.realpath(src["path"])  # 解 symlink
    abs_path = os.path.realpath(os.path.join(base, rel_path))
    try:
        common = os.path.commonpath([base, abs_path])
    except ValueError:
        # 不同 drive / 完全不同 root · Windows-style
        raise HTTPException(403, "路徑越界")
    if common != base:
        raise HTTPException(403, "路徑越界(symlink 或 ../ 逃逸)")
    if not os.path.isfile(abs_path):
        raise HTTPException(404, "檔案不存在或不是檔案")

    # exclude pattern 檢查(避免偷讀 .DS_Store 等)
    if _path_is_excluded(rel_path, src.get("exclude_patterns", [])):
        raise HTTPException(403, "此檔案在排除清單內")

    # 檔案大小檢查
    size = os.path.getsize(abs_path)
    max_size = src.get("max_size_mb", 50) * 1024 * 1024
    if size > max_size:
        raise HTTPException(413, f"檔案超過 {src.get('max_size_mb', 50)}MB 上限")

    # Audit log · fail-closed(Codex Round 10.5 紅)
    # PDPA 要求:讀 = 可追蹤 · 若 audit 寫不進去 · 不能讓讀取發生
    # 否則「寫失敗警告 + 回檔案」等於讀取無痕 · 違反資料最小原則
    user_email = (request.headers.get("X-User-Email") or "").strip().lower() or None
    try:
        knowledge_audit_col.insert_one({
            "user": user_email,
            "agent": agent_num,
            "source_id": source_id,
            "rel_path": rel_path,
            "size": size,
            "created_at": datetime.utcnow(),
        })
    except Exception as e:
        logger.error("[knowledge] audit log fail · 擋讀取(fail-closed): %s", e)
        raise HTTPException(
            503,
            "Audit log 服務暫時不可用 · 為 PDPA 合規暫停讀取 · 請找 Champion 或 Sterio",
        )

    # E-2 · extract() 按副檔名路由到 PDF/DOCX/PPTX/XLSX/image/text 抽字器
    extracted = extract_file(abs_path)
    import mimetypes
    mime, _ = mimetypes.guess_type(abs_path)
    return {
        "source_id": source_id,
        "source_name": src["name"],
        "rel_path": rel_path,
        "filename": os.path.basename(abs_path),
        "size": size,
        "mime": mime or "application/octet-stream",
        "modified_at": datetime.fromtimestamp(
            os.path.getmtime(abs_path)
        ).isoformat(),
        **{k: v for k, v in extracted.items()
           if k not in ("path", "filename", "size", "modified_at")},
    }


_AGENT_FORBIDDEN_CACHE: dict = {"data": {}, "ts": 0.0, "version": None}
_AGENT_FORBIDDEN_TTL = 300.0  # 5 分鐘


def _sources_max_updated_at() -> Optional[datetime]:
    """Codex R5#3 · 取所有 sources 最大 updated_at · 給 cache version 用
    workers=2 後 module-level cache 各 worker 獨立 · 改 Mongo-driven 版號
    任一 worker 改 source · 其他 worker 下次 search 看到 max(updated_at) 變 → invalidate"""
    try:
        doc = knowledge_sources_col.find_one(
            {}, sort=[("updated_at", -1)], projection={"updated_at": 1}
        )
        return doc.get("updated_at") if doc else None
    except Exception:
        return None


def _agent_forbidden_sources(agent_num: Optional[str]) -> set:
    """ROADMAP §11.5 + Codex R5#3 · cache 用 updated_at 跨 worker 一致

    每次呼叫先輕量查 max(updated_at)(< 1ms · 已建 index)· 變了就 rebuild
    比 5min TTL 安全 · admin 改 agent_access 後立即生效
    """
    import time
    now = time.time()
    cache = _AGENT_FORBIDDEN_CACHE

    # R5#3 · 比 Mongo updated_at 版本 · 而非純 TTL
    current_version = _sources_max_updated_at()
    if cache["version"] != current_version or (now - cache["ts"]) > _AGENT_FORBIDDEN_TTL:
        cache["data"] = {}
        cache["ts"] = now
        cache["version"] = current_version

    key = agent_num or "__none__"
    if key not in cache["data"]:
        forbidden = set()
        for src in knowledge_sources_col.find(
            {"enabled": True, "agent_access": {"$exists": True, "$ne": []}},
            {"_id": 1, "agent_access": 1},
        ):
            if not agent_num or agent_num not in src["agent_access"]:
                forbidden.add(str(src["_id"]))
        cache["data"][key] = forbidden
    return cache["data"][key]


def _invalidate_sources_cache():
    """source CRUD 後呼叫 · 本 worker 立即清(其他 worker 下次自動偵測 version 變)"""
    _AGENT_FORBIDDEN_CACHE["ts"] = 0.0
    _AGENT_FORBIDDEN_CACHE["data"] = {}
    _AGENT_FORBIDDEN_CACHE["version"] = None


@app.get("/knowledge/search")
def knowledge_search(
    q: str = Query(min_length=2),
    source_id: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    request: Request = None,
):
    """全文搜尋 · 經 Meili · source_id / project 可過濾

    Round 9 Q3 · 依 X-Agent-Num 過濾結果(連 hit 都不能透露)
    """
    meili = _get_meili_client()
    if not meili:
        return {
            "query": q,
            "hits": [],
            "estimatedTotalHits": 0,
            "message": "搜尋服務未啟用 · 請管理員檢查 Meili",
        }
    result = knowledge_indexer.search(meili, q, source_id=source_id, project=project, limit=limit)

    # Q3 + Codex R3.3 · 過濾 hit · 無 agent_num 時也要擋 agent_access 限定的 source
    # ROADMAP §11.5 · 5min TTL cache · 避免每次 search 都掃 sources collection
    agent_num = request.headers.get("X-Agent-Num") if request else None
    if isinstance(result, dict) and result.get("hits"):
        forbidden_ids = _agent_forbidden_sources(agent_num)
        if forbidden_ids:
            original = len(result["hits"])
            result["hits"] = [h for h in result["hits"]
                              if h.get("source_id") not in forbidden_ids]
            removed = original - len(result["hits"])
            if removed:
                result["filtered_for_agent"] = removed
    return result


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

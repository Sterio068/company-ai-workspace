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
# v1.18 · architect R2 第一階段 · 抽到 auth_deps.py
# 此處 re-export 維持 backward compat(main._is_prod 等仍可被 router lazy import)
# ============================================================
from auth_deps import (
    _is_prod,
    _jwt_refresh_configured,
    _legacy_auth_headers_enabled,
    _env_mode_configured,
    _secrets_equal,
)


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
    # C3(v1.3)· knowledge_file_hashes · 內容 hash 比對 · 防 mtime 變但內容沒變
    # unique (source_id, rel_path) · 同 source 同 path 只一筆
    db.knowledge_file_hashes.create_index(
        [("source_id", 1), ("rel_path", 1)], unique=True, name="src_path_uniq"
    )
    # v1.8 · 補 v1.7 4 collection 缺的 indexes(perf-optimizer 黃 2 警告)
    # 否則每次 cache lookup / dismiss / suppress 都是 collection scan
    try:
        db.ai_suggestions_cache.create_index([("user_email", 1)], unique=True, name="user_uniq")
        db.ai_dismissed.create_index(
            [("user_email", 1), ("until", -1)], name="user_until"
        )
        # auto-expire dismiss 過期的 doc(節省空間)
        db.ai_dismissed.create_index(
            [("until", 1)], expireAfterSeconds=0, name="dismiss_ttl"
        )
        db.ai_suppressions.create_index([("user_email", 1)], unique=True, name="user_uniq")
        db.user_preferences.create_index([("user_email", 1)], unique=True, name="user_uniq")
        db.smart_folders.create_index(
            [("user_email", 1), ("key", 1)], unique=True, name="user_key_uniq"
        )
        # branding 單一 doc · 不需 index(用 _id)
        # LibreChat messages · 加 conversationId index 大幅加速 ai-suggestions scan
        # 注意:LibreChat 是同一 db · 此 index 加在共用 collection
        db.messages.create_index([("conversationId", 1), ("createdAt", -1)], name="conv_time")
    except Exception as e:
        logger.warning("[index] v1.8 ai-suggestions/smart-folders: %s", e)
    # A5(v1.3)· social OAuth · token + state TTL
    try:
        db.social_oauth_tokens.create_index(
            [("user_email", 1), ("platform", 1)], unique=True, name="user_platform_uniq"
        )
        db.social_oauth_tokens.create_index([("expires_at", 1)])  # cron refresh 掃用
        # state · expires_at TTL · 過期自動清(防 stale state 累積)
        db.social_oauth_states.create_index([("state", 1)], unique=True)
        db.social_oauth_states.create_index(
            [("expires_at", 1)], expireAfterSeconds=0, name="state_ttl"
        )
    except Exception as e:
        logger.warning("[index] social_oauth: %s", e)
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
    # 技術債#9(2026-04-23)· 偵測舊 sparse 索引並 drop · 防 IndexKeySpecsConflict spam log
    try:
        existing = db.media_contacts.index_information().get("email_1")
        if existing and "partialFilterExpression" not in existing:
            # 舊 sparse 配置 · drop 後重建 partialFilter
            db.media_contacts.drop_index("email_1")
            logger.info("[index] media_contacts.email_1 · 舊 sparse 已 drop · 重建 partialFilter")
        db.media_contacts.create_index(
            [("email", 1)],
            unique=True,
            partialFilterExpression={"email": {"$type": "string", "$gt": ""}},
            name="email_1",
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
    # v1.57 perf P0-4 · workflow_runs / vision_extractions 索引(_daily_quota_check 與 audit 查詢用)
    try:
        db.workflow_runs.create_index(
            [("user_email", 1), ("started_at", -1)], name="user_started",
        )
        db.workflow_runs.create_index([("status", 1), ("started_at", -1)])
        # 365 天 TTL · audit 用 · 防無限堆積
        db.workflow_runs.create_index(
            [("started_at", 1)], expireAfterSeconds=365 * 24 * 3600, name="ttl_365d",
        )
    except Exception as e:
        logger.warning("[index] workflow_runs: %s", e)
    try:
        db.vision_extractions.create_index(
            [("user_email", 1), ("extracted_at", -1)], name="user_time",
        )
        db.vision_extractions.create_index(
            [("extracted_at", 1)], expireAfterSeconds=180 * 24 * 3600, name="ttl_180d",
        )
    except Exception as e:
        logger.warning("[index] vision_extractions: %s", e)
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

    # v1.3 batch6 · CRITICAL C-2 · OAuth token 加密 key 強制檢查
    _creds_key = os.getenv("CREDS_KEY", "")
    if not _creds_key or len(_creds_key) < 32:
        if _is_prod():
            raise RuntimeError(
                "CREDS_KEY required in production (>= 32 bytes) · "
                "OAuth token 會以 PLAIN: prefix 明文存庫 · 違反 PDPA"
            )
        logger.warning(
            "[security] CREDS_KEY 未設或太短(dev mode)· "
            "social OAuth token 將以明文 PLAIN: prefix 存庫 · production 必設"
        )
    else:
        logger.info("[security] CREDS_KEY 已設 · OAuth token AES-GCM 加密 ON")
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
    description="AI 系統 · 內建會計模組",
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


# v1.29 · architect R2 round 3 · _user_or_ip 抽到 auth_deps.py(factory + DI)
# 結構:
#   1. 此處 lazy wrapper · _limiter 抓得到 callable
#   2. _verify_librechat_cookie 定義(line ~426)
#   3. _bound_user_or_ip 真 binding(verify_cookie 已 ready)
# Limiter 在 call key_func 時才實際呼叫 wrapper · wrapper 跑 _bound_user_or_ip
_bound_user_or_ip = None  # 後綁 · 見 _verify_librechat_cookie 定義後

def _user_or_ip(request: Request) -> str:
    """Lazy wrapper · 真行為由 _bound_user_or_ip(在 auth_deps.make_user_or_ip 產生)"""
    if _bound_user_or_ip is None:
        # 啟動 race · _verify_librechat_cookie 還沒定義就被 call · fallback IP
        return f"ip:{get_remote_address(request)}"
    return _bound_user_or_ip(request)


_limiter = Limiter(
    key_func=_user_or_ip,
    default_limits=[os.getenv("RATE_LIMIT_DEFAULT", "2000/minute")],
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

# ============================================================
# Helpers
# v1.25 · architect R2 round 2 · serialize 抽到 auth_deps.py(見上方 import)
# 此處 re-export 維持 backward compat · `from main import serialize` 仍可用
# ============================================================
from auth_deps import serialize  # noqa: E402,F401


# ============================================================
# Auth · 簡易 RBAC(靠 LibreChat Mongo user role 查 · 非 JWT 硬解)
# ============================================================
_users_col = db.users  # LibreChat 的 users collection

# v1.31 · architect R2 round 5 · _admin_allowlist 抽到 auth_deps.load_admin_allowlist
# 行為 100% 一致(從 ADMIN_EMAILS / ADMIN_EMAIL env 讀)
from auth_deps import load_admin_allowlist
_admin_allowlist = load_admin_allowlist()
if not _admin_allowlist:
    logger.warning(
        "[admin] ADMIN_EMAILS 未設 · admin endpoint 將完全鎖死 · "
        "設 ADMIN_EMAILS=email1,email2 開放管理員"
    )


# v1.30 · architect R2 round 4 · _verify_librechat_cookie + _lookup_user_email_cached
# 抽到 auth_deps.make_cookie_verifier(factory + DI · 注入 users_col / logger)
# 行為 100% 一致(JWT decode → payload.email or id → users_col 反查 + 60s LRU)
from auth_deps import make_cookie_verifier
_verify_librechat_cookie, _lookup_user_email_cached = make_cookie_verifier(
    _users_col, logger=logger,
)


# v1.29 · R2 round 3 · 真 binding · 此時 _verify_librechat_cookie 已定義
# Limiter wrapper(line ~330)會 lazy delegate 到這裡
from auth_deps import make_user_or_ip
_bound_user_or_ip = make_user_or_ip(_verify_librechat_cookie, get_remote_address)


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


# v1.31 · architect R2 round 5 · require_admin 抽到 auth_deps.make_require_admin
# 行為 100% 一致(三道路徑:internal token / cookie + 白名單 / users.role==ADMIN)
# 此處薄包裝 · 加 Depends(current_user_email) FastAPI 依賴(auth_deps 不知 fastapi)
from auth_deps import make_require_admin
_require_admin_impl = make_require_admin(_users_col, _admin_allowlist, logger=logger)


def require_admin(request: Request,
                  email: Optional[str] = Depends(current_user_email)) -> str:
    """硬權限 · 用在所有 /admin/* 與敏感端點(thin wrapper · 真邏輯在 auth_deps)"""
    return _require_admin_impl(request, email)


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

# v1.12 · i18n endpoint(architect R3 收尾)· 公開 · launcher + librechat-relabel 共用 TERMS
from routers import i18n as _i18n_router
app.include_router(_i18n_router.router)

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


# Orchestrator(v2.0 · 主管家跨 Agent 呼叫)
# 放在 auth helper 定義之後載入,避免 require_user_dep import main.current_user_email 時循環。
try:
    from orchestrator import router as orchestrator_router
    app.include_router(orchestrator_router)
    logger.info("orchestrator router loaded · D-010 主管家上線")
except ImportError as e:
    logger.warning(
        "orchestrator 未載入 · D-010/D-011 主管家功能 OFF · 原因: %s",
        e,
    )

# v1.55 · Vision OCR 結構化抽取(招標 9 欄 / 表格 / 評分標準)
try:
    from routers import vision as _vision_router
    app.include_router(_vision_router.router)
    logger.info("vision router loaded · v1.55 OCR 結構化")
except ImportError as e:
    logger.warning("vision router 未載入 · 原因: %s", e)


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



# 技術債#2(2026-04-23)· /quota/check + /quota/preflight + /healthz 已抽 routers/system.py
# main.py 不再直接定義 · 後段 include_router 處理(配 register_rate_limited_routes)



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
# Social OAuth infra · v1.3 A5 · /social/oauth/{start,callback,disconnect,status}
# B1 真接 Meta API 留 v1.4(等承富送 App)· A5 此 PR 走 mock provider
# ============================================================
from routers import social_oauth as _social_oauth_router
app.include_router(_social_oauth_router.router)

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
# System router · 技術債#2(2026-04-23)· /quota/check + /quota/preflight + /healthz
# preflight 需動態 register · 因 _limiter 在 main 才有
# ============================================================
from routers import system as _system_router
_system_router.register_rate_limited_routes(
    _limiter.limit(os.getenv("RATE_LIMIT_QUOTA_PREFLIGHT", "60/minute"))
)
app.include_router(_system_router.router)


# startup() 已 migrate 到上方 lifespan() · 此處留空避免重複註冊

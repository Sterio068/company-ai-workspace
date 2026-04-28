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
from datetime import datetime, date, timezone
from enum import Enum
import os
import json
import re
import time
import uuid
import logging
import asyncio
import hmac
import httpx
from collections import OrderedDict
from pymongo import MongoClient
from bson import ObjectId
from infra.retention_policy import apply_retention_indexes

# ============================================================
# v1.66 Q3 · Sentry · 異常自動上報 · 設 SENTRY_DSN env 才啟用 · 沒設 no-op
# ============================================================
_sentry_dsn = os.getenv("SENTRY_DSN", "").strip()
if _sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        sentry_sdk.init(
            dsn=_sentry_dsn,
            environment=os.getenv("ECC_ENV", "development"),
            release=os.getenv("APP_VERSION", "unversioned"),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE", "0.1")),
            profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE", "0.0")),
            integrations=[FastApiIntegration(), StarletteIntegration()],
            send_default_pii=False,  # 不送 PII (email/cookie 等)
        )
    except Exception as _e:
        # sentry-sdk 沒裝或 init 失敗 · 不影響啟動
        print(f"[sentry] init skipped: {_e}")

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
    # NotebookLM parallel bridge · local source packs remain authoritative snapshots
    try:
        db.notebooklm_source_packs.create_index([("updated_at", -1)])
        db.notebooklm_source_packs.create_index([("scope", 1), ("updated_at", -1)])
        db.notebooklm_source_packs.create_index([("content_hash", 1)], unique=True)
        db.notebooklm_sync_runs.create_index([("created_at", -1)])
        db.notebooklm_sync_runs.create_index([("pack_id", 1), ("created_at", -1)])
    except Exception as e:
        logger.warning("[index] notebooklm: %s", e)
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
    # v1.66 Q3 · frontend errors · 30d TTL · admin dashboard 查
    try:
        db.frontend_errors.create_index([("created_at", -1)])
        db.frontend_errors.create_index(
            [("created_at", 1)], expireAfterSeconds=30 * 24 * 3600, name="ttl_30d",
        )
    except Exception as e:
        logger.warning("[index] frontend_errors: %s", e)
    try:
        applied_retention = apply_retention_indexes(db, logger)
        logger.info("[retention] managed TTL indexes ensured · count=%s", len(applied_retention))
    except Exception as e:
        logger.error("[retention] managed TTL index ensure failed · data bloat risk: %s", e)
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
    if not _creds_key or len(_creds_key) < 64:
        if _is_prod():
            raise RuntimeError(
                "CREDS_KEY required in production (32 bytes hex / 64 chars) · "
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
    if not os.getenv("ACTION_BRIDGE_TOKEN", "").strip():
        if _is_prod():
            raise RuntimeError(
                "ACTION_BRIDGE_TOKEN required in production · "
                "LibreChat Actions 必須用低權限 action token,不可重用 ECC_INTERNAL_TOKEN"
            )
        logger.warning(
            "[auth] ACTION_BRIDGE_TOKEN 未設(dev mode 容許)· LibreChat Actions 接線會被跳過"
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


_ACTION_BRIDGE_PATH_PREFIXES = (
    "/accounts",
    "/transactions",
    "/invoices",
    "/quotes",
    "/reports/",
    "/vision/",
    "/notebooklm/agent/",
    "/orchestrator/delegate",
)


def _action_bridge_path_allowed(path: str) -> bool:
    if path.startswith("/projects/") and path.endswith("/finance"):
        return True
    return any(path == p.rstrip("/") or path.startswith(p) for p in _ACTION_BRIDGE_PATH_PREFIXES)


def current_user_email(
    request: Request,
    x_user_email: Optional[str] = Header(default=None),
    x_acting_user: Optional[str] = Header(default=None),
) -> Optional[str]:
    """取得當前使用者 email · 優先順序(Codex R3.2 / R7#1 / R7#10):
    1. LibreChat refreshToken cookie + JWT_REFRESH_SECRET + 反查 _users_col(R7#1)
    2. X-User-Email header(legacy · ALLOW_LEGACY_AUTH_HEADERS 才開 · prod 預設 OFF)

    R7#10:prod 若 nginx 沒 strip X-User-Email · 任何人 curl 可偽造 admin。
    所以 prod 預設關 fallback · 只有 dev / 明確 opt-in 才開。
    """
    expected_internal = os.getenv("ECC_INTERNAL_TOKEN", "").strip()
    provided_internal = (request.headers.get("X-Internal-Token") or "").strip()
    raw_acting_user = (
        x_acting_user
        if isinstance(x_acting_user, str)
        else request.headers.get("X-Acting-User")
    )
    acting_email = (raw_acting_user or "").strip().lower()
    if expected_internal and acting_email and _secrets_equal(provided_internal, expected_internal):
        request.state.email_trusted = True
        request.state.auth_via = "internal_acting_user"
        return acting_email
    expected_action = os.getenv("ACTION_BRIDGE_TOKEN", "").strip()
    if (
        expected_action
        and acting_email
        and _secrets_equal(provided_internal, expected_action)
        and _action_bridge_path_allowed(request.url.path)
    ):
        request.state.email_trusted = True
        request.state.auth_via = "action_bridge"
        return acting_email

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

# v2.0-β · Vector RAG · OpenAI embedding 語意搜尋
try:
    from routers import vector_rag as _vector_rag_router
    app.include_router(_vector_rag_router.router)
    logger.info("vector_rag router loaded · v2.0-β 語意搜尋")
except ImportError as e:
    logger.warning("vector_rag router 未載入 · 原因: %s", e)


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
# LibreChat RAG adapter · /rag/{health,embed,query,text,documents}
# v1.70 · 對齊 LibreChat v0.8.5 RAG_API_URL contract,不新增外部容器
# ============================================================
from routers import rag_adapter as _rag_adapter_router
app.include_router(_rag_adapter_router.router)

# ============================================================
# NotebookLM parallel bridge · /notebooklm/*
# Local DB stays source-of-truth; NotebookLM receives derived source packs only.
# ============================================================
from routers import notebooklm as _notebooklm_router
app.include_router(_notebooklm_router.router)

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


# ============================================================
# v1.66 Q3 · 前端 error report endpoint · 集中看 mongo error_log
# ============================================================
class FrontendErrorReport(BaseModel):
    rid: str
    kind: str  # uncaught / unhandled-promise
    ts: Optional[str] = None
    ua: Optional[str] = None
    url: Optional[str] = None
    message: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None
    col: Optional[int] = None
    stack: Optional[str] = None


@app.post("/admin/error-log")
def report_frontend_error(report: FrontendErrorReport, request: Request):
    """前端 errors.js 集中收 · admin dashboard 可查 · TTL 30d"""
    try:
        email = current_user_email(request)  # 沒登入也接受 · email 為空
    except Exception:
        email = None
    doc = report.model_dump()
    doc["user_email"] = email
    doc["ip"] = (request.client.host if request.client else None)
    doc["created_at"] = datetime.now(timezone.utc)
    try:
        db.frontend_errors.insert_one(doc)
    except Exception:
        pass  # 不讓 error report 自己出錯影響使用者
    # Sentry 接 · backend 的 sentry_sdk 已 init · 可額外送 frontend events
    if _sentry_dsn:
        try:
            import sentry_sdk
            sentry_sdk.capture_message(
                f"[frontend] {report.kind}: {report.message or '?'}",
                level="error",
                extras={"rid": report.rid, "url": report.url, "stack": (report.stack or "")[:500]},
            )
        except Exception:
            pass
    return {"received": True, "rid": report.rid}


# X-Forwarded-Host 格式驗證 · 模組頂層 compile 一次 (避免每次請求 re.compile)
# 註:此處只擋語法錯誤的注入,不擋語法正確但任意的 host 字串
# 信任邊界靠部署層:nginx 設 `proxy_set_header X-Forwarded-Host $host` 強制覆寫
# (見 frontend/nginx/nginx.conf · 不接受 client 端傳的 X-Forwarded-Host)
# 若部署沒過 nginx 直接 expose accounting 8000,此 header 會被 client 完全控制
_FORWARDED_HOST_RE = re.compile(r"^[a-zA-Z0-9.\-]+(:\d{1,5})?$")


# ============================================================
# AI 引擎主備源 health check · launcher sidebar 主備源面板用
# - 不揭露 API key · 只判 key 存在 + 長度
# - 失敗永遠回 200 (避免 sidebar 顯紅嚇到使用者)
# - 30s cache (避免每分鐘真打 OpenAI/Anthropic · 與 launcher 60s refresh 配 30s buffer)
# - 多 worker 各自一份 cache(本機 Mac mini 4 worker · 冷啟動最多 4 次 mongo round trip · 可接受)
#   若改 cluster 部署,改用 Redis / Mongo TTL collection 跨 worker share
# ============================================================
_AI_HEALTH_CACHE: dict = {"at": 0.0, "data": None}
_AI_HEALTH_TTL_SEC = 30.0


def _ai_provider_state(api_key: str) -> dict:
    """純粹從 key 是否存在 + 長度判斷 · 不打網路(避免 latency / quota 浪費)"""
    if not api_key:
        return {"state": "down", "reason": "API key 未設定", "configured": False}
    if len(api_key) < 20:
        return {"state": "warn", "reason": "API key 長度異常", "configured": True}
    return {"state": "ok", "reason": "已就緒", "configured": True}


@app.get("/admin/access-urls")
def access_urls(request: Request, _admin: str = Depends(require_admin)) -> dict:
    """同仁連線網址清單 · admin view 顯示用

    來源:
      - LAN IP / hostname:start.sh 啟動時偵測 ifconfig 寫入 .host-network.json
      - tunnel hostname:從 ~/.cloudflared/config.yml 解析(若有)
      - current_origin:依使用者目前訪問的 URL 動態回(避免顯示無關 IP)

    Response:
      {
        "current_origin": "http://192.168.88.133",
        "lan_urls":  ["http://192.168.88.133", "http://192.168.50.147"],
        "mdns_url":  "http://steriodemac-mini.local",
        "tunnel_urls": ["https://ai.example.com"],
        "guidance": {
          "account_source": "由老闆統一設置 · 同仁向老闆領取 email + 預設密碼",
          "first_login": "首次登入後到右上角頭像 → 個人設定 改密碼"
        }
      }
    """
    path = os.getenv("HOST_NETWORK_FILE", "/data/host-network.json")
    info: dict = {"lan_ips": [], "hostname": "", "tunnel_hostnames": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            info = json.load(f) or info
    except FileNotFoundError:
        logger.warning("[access-urls] host network file 不存在 · start.sh 未跑或未掛 volume")
    except Exception as e:
        logger.warning(f"[access-urls] 讀檔失敗 {e}")

    lan_urls = [f"http://{ip}" for ip in (info.get("lan_ips") or []) if ip]
    mdns_url = f"http://{info['hostname']}" if info.get("hostname") else None
    tunnel_urls = [f"https://{h}" for h in (info.get("tunnel_hostnames") or []) if h]

    # 使用者目前正在用的 URL · 從 X-Forwarded-Host / Host header 推
    # 嚴格驗格式(防偽造 header 灌任意字串到 admin UI)· 失敗則回 None
    raw_host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").strip()
    raw_proto = (request.headers.get("x-forwarded-proto") or "http").strip().lower()
    current_origin = None
    if raw_host and _FORWARDED_HOST_RE.match(raw_host) and raw_proto in ("http", "https"):
        current_origin = f"{raw_proto}://{raw_host}"

    return {
        "current_origin": current_origin,
        "lan_urls": lan_urls,
        "mdns_url": mdns_url,
        "tunnel_urls": tunnel_urls,
        "detected_at": info.get("detected_at"),
        "guidance": {
            "account_source": "帳號 / 密碼由老闆統一設置 · 同仁向老闆領取",
            "first_login": "首次登入後請到右上角頭像 → 個人設定 改密碼",
            "remote_status": (
                "已啟用 · 在家 / 出差可用上方 tunnel 網址" if tunnel_urls
                else "尚未啟用遠端 · 請先設定 Cloudflare Tunnel(見 DEPLOY.md Phase 4)"
            ),
        },
    }


@app.get("/health/ai-providers")
def ai_providers_health(
    request: Request,
    email: Optional[str] = Depends(current_user_email),
) -> dict:
    """主備源連線狀態 · launcher sidebar 每 60s 拉

    C2 · auth gate:
    - 未登入(無 email) → 401(防匿名探測 key 是否存在)
    - 一般同仁登入 → 只回 available bool · 不揭露 reason / configured
    - admin 登入 → 完整狀態(reason / configured / latency)
    """
    if not email:
        raise HTTPException(401, "需登入才能查詢 AI 引擎狀態")
    is_admin = email in _admin_allowlist

    # cache 存的是 admin full payload · 非 admin 從中 derive redacted view
    now = time.time()
    cached = _AI_HEALTH_CACHE.get("data")
    if not cached or (now - _AI_HEALTH_CACHE["at"]) >= _AI_HEALTH_TTL_SEC:
        openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not openai_key:
            try:
                doc = db.system_settings.find_one({"name": "OPENAI_API_KEY"})
                if doc and doc.get("value"):
                    openai_key = str(doc["value"]).strip()
            except Exception:
                pass
        if not anthropic_key:
            try:
                doc = db.system_settings.find_one({"name": "ANTHROPIC_API_KEY"})
                if doc and doc.get("value"):
                    anthropic_key = str(doc["value"]).strip()
            except Exception:
                pass
        cached = {
            "providers": {
                "openai": _ai_provider_state(openai_key),
                "anthropic": _ai_provider_state(anthropic_key),
            },
            "primary": "openai",
            "backup": "anthropic",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        _AI_HEALTH_CACHE["at"] = now
        _AI_HEALTH_CACHE["data"] = cached

    if is_admin:
        return cached
    # 非 admin · 只回 state(綠/橙/紅/灰)· 不揭露 reason / configured / key 細節
    return {
        "providers": {
            k: {"state": v.get("state", "unknown")}
            for k, v in cached.get("providers", {}).items()
        },
        "primary": cached.get("primary"),
        "backup": cached.get("backup"),
        "ts": cached.get("ts"),
    }

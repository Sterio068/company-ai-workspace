"""
Centralized config · R14#6 · v1.2 Sprint 2

原本 settings 散在:
  - main.py · QUOTA_MODE / QUOTA_OVERRIDE_EMAILS / _USD_TO_NTD / _MONTHLY_BUDGET_NTD / _USER_SOFT_CAP_DEFAULT
  - routers/admin.py · lazy import 各處
  - routers/design.py · FAL_POLL_MAX_SECONDS / FAL_POLL_INTERVAL

抽 dataclass · 一次性產自 env · validation 在此 · 改設定不用 grep 全檔。

用法:
  from config import settings
  print(settings.monthly_budget_ntd)

不支援 runtime 改(改完 restart container)· dev 可 `reload_settings()` 測試用。
"""
from dataclasses import dataclass, field
from typing import Literal
import os


def _parse_float(env: str, default: float) -> float:
    """安全解析 env float · 失敗 fallback default"""
    try:
        return float(os.getenv(env, str(default)))
    except (TypeError, ValueError):
        return default


def _parse_int(env: str, default: int) -> int:
    try:
        return int(os.getenv(env, str(default)))
    except (TypeError, ValueError):
        return default


def _parse_email_set(env: str, default: str = "") -> set[str]:
    raw = os.getenv(env, default)
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


@dataclass(frozen=True)
class CompanyAISettings:
    """本公司 accounting 全域設定 · immutable · init-once"""

    # ---- 環境 ----
    env: Literal["development", "production"] = "development"
    node_env: str = "development"

    # ---- Auth ----
    jwt_refresh_secret: str = ""
    ecc_internal_token: str = ""
    allow_legacy_auth_headers: bool = True
    admin_allowlist: frozenset = field(default_factory=frozenset)

    # ---- Quota ----
    quota_mode: Literal["hard_stop", "soft_warn", "off"] = "soft_warn"
    quota_override_emails: frozenset = field(default_factory=frozenset)
    user_soft_cap_ntd: float = 1200.0
    monthly_budget_ntd: float = 12000.0
    usd_to_ntd: float = 32.5

    # ---- Fal.ai(Recraft) ----
    fal_poll_max_seconds: int = 12
    fal_poll_interval: float = 1.0

    # ---- Knowledge ----
    max_ocr_pages_per_pdf: int = 20

    @property
    def is_prod(self) -> bool:
        return self.env == "production" or self.node_env == "production"

    @property
    def jwt_refresh_configured(self) -> bool:
        sec = self.jwt_refresh_secret
        return bool(sec) and not sec.startswith("<GENERATE")

    @property
    def legacy_auth_headers_enabled(self) -> bool:
        """prod 預設關 · dev 預設開 · 明確 env=1 才開"""
        raw = os.getenv("ALLOW_LEGACY_AUTH_HEADERS", "").strip()
        if raw == "1":
            return True
        if raw == "0":
            return False
        return not self.is_prod


def _load_from_env() -> CompanyAISettings:
    """從 env 一次讀取 · 不支援 reload(改完 restart container)"""
    env = os.getenv("ECC_ENV", "").lower() or "development"
    node = os.getenv("NODE_ENV", "").lower() or "development"
    return CompanyAISettings(
        env="production" if env == "production" else "development",
        node_env=node,
        jwt_refresh_secret=os.getenv("JWT_REFRESH_SECRET", ""),
        ecc_internal_token=os.getenv("ECC_INTERNAL_TOKEN", ""),
        allow_legacy_auth_headers=os.getenv("ALLOW_LEGACY_AUTH_HEADERS", "") == "1",
        admin_allowlist=frozenset(_parse_email_set(
            "ADMIN_EMAILS",
            os.getenv("ADMIN_EMAIL", ""),
        )),
        quota_mode=os.getenv("QUOTA_MODE", "soft_warn"),  # type: ignore
        quota_override_emails=frozenset(_parse_email_set("QUOTA_OVERRIDE_EMAILS")),
        user_soft_cap_ntd=_parse_float("USER_SOFT_CAP_NTD", 1200.0),
        monthly_budget_ntd=_parse_float("MONTHLY_BUDGET_NTD", 12000.0),
        usd_to_ntd=_parse_float("USD_TO_NTD", 32.5),
        fal_poll_max_seconds=_parse_int("FAL_POLL_MAX_SECONDS", 12),
        fal_poll_interval=_parse_float("FAL_POLL_INTERVAL", 1.0),
        max_ocr_pages_per_pdf=_parse_int("MAX_OCR_PAGES_PER_PDF", 20),
    )


# Module-level singleton · import time 初始化
settings = _load_from_env()


def reload_settings() -> CompanyAISettings:
    """Dev / test 用 · 覆寫 module-level singleton"""
    global settings
    settings = _load_from_env()
    return settings

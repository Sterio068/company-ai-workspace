"""
v1.18 · Auth helper · architect R2 第一階段
=================================================
從 main.py(830 行)抽出 5 個純 env-based auth helper · 無 db / fastapi 依賴

抽出原則:
- 完全純函式 · 只 read os.environ + hmac
- 無 main.py 任何 module-level 依賴
- 不引入 cycle(main.py 改 import auth_deps · auth_deps 不 import main)

之後階段(v1.19+):
- Round 2:抽 serialize() · _user_or_ip() · 也純函式
- Round 3:抽 _verify_librechat_cookie / current_user_email · 需 db handle 注入
- Round 4:require_admin · _admin_allowlist 進來

本 round 的目標:小步快跑 · 0 風險 · 確保各 router 不破
策略:main.py 改 `from auth_deps import _is_prod, ...` · 行為 100% 相同
"""
import hmac
import os


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
    · prod 若 nginx 沒 strip header · 攻擊者可偽造身份
      → 設 ALLOW_LEGACY_AUTH_HEADERS=1 才開
    """
    explicit = os.getenv("ALLOW_LEGACY_AUTH_HEADERS", "").strip()
    if explicit == "1":
        return True
    if explicit == "0":
        return False
    # 預設行為 · prod=False · dev=True
    return not _is_prod()


def _env_mode_configured() -> bool:
    """Codex R8#6 · ECC_ENV / NODE_ENV 必須有一個明確設(防誤配 dev mode)"""
    return bool(
        os.getenv("ECC_ENV", "").strip()
        or os.getenv("NODE_ENV", "").strip()
    )


def _secrets_equal(a: str, b: str) -> bool:
    """Codex R8#2 · 比 secret 用 hmac.compare_digest 防 timing attack"""
    if not a or not b:
        return False
    try:
        return hmac.compare_digest(a, b)
    except Exception:
        return False

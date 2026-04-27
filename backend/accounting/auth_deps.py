"""
v1.18+v1.25 · Auth/serialization helper · architect R2 第一+二階段
=================================================
從 main.py 抽出純 helper · 無 db / fastapi 依賴

v1.18 抽出 5 個 env-based helper:
  _is_prod / _jwt_refresh_configured / _legacy_auth_headers_enabled
  _env_mode_configured / _secrets_equal

v1.25 加抽 1 個 BSON serialize helper:
  serialize(doc) · ObjectId → str(JSON-safe)

抽出原則:
- 完全純函式 · 只用 stdlib + bson
- 無 main.py / fastapi / db 依賴
- 不引入 cycle(main.py 改 import auth_deps · auth_deps 不 import main)

下階段(v1.26+):
- Round 3:抽 _user_or_ip(slowapi key_func · 需 fastapi.Request)
- Round 4:抽 _verify_librechat_cookie / current_user_email(需 db 注入)
- Round 5:抽 require_admin / _admin_allowlist
"""
import hmac
import os

from bson import ObjectId


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


# ============================================================
# v1.25 · BSON serialize · 從 main.py 抽出(architect R2 round 2)
# ============================================================
def serialize(doc):
    """ObjectId → str · dict/list 遞迴 · JSON-safe

    從 main.py 平移過來 · 100% 相同行為:
    - None / 空 → 原樣回
    - list → 各元素遞迴
    - dict → 值若是 ObjectId 轉 str / 若是 dict|list 遞迴 / 其他原樣
    - 其他 type → 原樣

    注意:這版不處理 datetime(routers/_deps._serialize 才有)·
    保持 main.py 原行為(不影響任何 router 已仰賴的格式)
    """
    if not doc:
        return doc
    if isinstance(doc, list):
        return [serialize(d) for d in doc]
    if isinstance(doc, dict):
        return {k: (str(v) if isinstance(v, ObjectId) else
                    serialize(v) if isinstance(v, (dict, list)) else v)
                for k, v in doc.items()}
    return doc

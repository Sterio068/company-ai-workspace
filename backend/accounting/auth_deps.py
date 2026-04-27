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
# v1.29 · _user_or_ip · architect R2 round 3
# 用 factory(DI) 模式 · 解 _verify_librechat_cookie 在 main.py 而非這裡的循環
# main.py 呼叫:_user_or_ip = make_user_or_ip(_verify_librechat_cookie)
# ============================================================
def make_user_or_ip(verify_cookie_fn, get_remote_address_fn):
    """factory · 給 SlowAPI Limiter key_func 用

    Args:
        verify_cookie_fn: callable(request) → email|None · 由 main.py 注入
        get_remote_address_fn: slowapi.util.get_remote_address(避 import 進 auth_deps)

    Returns:
        callable(request) → "u:internal" | "u:<email>" | "ip:<addr>"

    Codex R5#7 + R6#2 + R7#2 修:
    - SlowAPIMiddleware 在 endpoint dependency 前跑 · request.state 還沒設
    - X-Internal-Token 必須 secret-equal · 不只看存在
    - 用 hmac.compare_digest 防 timing attack
    """
    def _user_or_ip(request):
        # Internal token · secret-equal compare
        expected_internal = os.getenv("ECC_INTERNAL_TOKEN", "").strip()
        provided_internal = (request.headers.get("X-Internal-Token") or "").strip()
        if _secrets_equal(provided_internal, expected_internal):
            return "u:internal"
        # Cookie · 由 caller 注入的 verify_fn
        try:
            verified_email = verify_cookie_fn(request)
            if verified_email:
                return f"u:{verified_email}"
        except Exception:
            pass
        # IP fallback · 用 caller 注入的 get_remote_address
        return f"ip:{get_remote_address_fn(request)}"

    return _user_or_ip


# ============================================================
# v1.30 · cookie verification + email cache · architect R2 round 4
# ============================================================
def make_cookie_verifier(users_col, logger=None):
    """factory · 給 main.py 注入 users_col + logger 後產生:
    - verify_cookie(request) → email | None
    - lookup_user_email(user_id) → email | None(LRU cache · 60s TTL)

    純函式設計 · 跟 main.py 100% 行為一致:
    1. JWT decode refreshToken
    2. payload.email 直接拿
    3. 否則 payload.id → users_col.find_one 反查
    4. 反查走 OrderedDict 60s LRU(命中 move_to_end · 滿 200 evict 最舊)

    Returns:
        (verify_cookie, lookup_user_email)
    """
    import time
    from collections import OrderedDict
    try:
        import jwt as _jwt
    except ImportError:
        _jwt = None

    _CACHE: "OrderedDict[str, tuple]" = OrderedDict()
    _TTL = 60.0
    _MAX = 200

    def _log_debug(msg, *args):
        if logger:
            logger.debug(msg, *args)

    def lookup_user_email(user_id: str):
        """從 users_col 反查 email · 60s LRU"""
        now = time.time()
        cached = _CACHE.get(user_id)
        if cached and now - cached[1] < _TTL:
            _CACHE.move_to_end(user_id)
            return cached[0] or None
        try:
            try:
                oid = ObjectId(user_id)
            except Exception:
                return None
            u = users_col.find_one({"_id": oid}, {"email": 1})
            email = (u.get("email") or "").strip().lower() if u else ""
            while len(_CACHE) >= _MAX:
                _CACHE.popitem(last=False)
            _CACHE[user_id] = (email, now)
            return email or None
        except Exception as e:
            _log_debug("[auth] users lookup id=%s · %s", user_id, e)
            return None

    def verify_cookie(request):
        """LibreChat refreshToken cookie → email"""
        if _jwt is None:
            return None
        try:
            refresh_token = request.cookies.get("refreshToken")
            if not refresh_token:
                return None
            sec = os.getenv("JWT_REFRESH_SECRET", "")
            if not sec or sec.startswith("<GENERATE"):
                return None
            try:
                payload = _jwt.decode(refresh_token, sec, algorithms=["HS256"])
            except _jwt.ExpiredSignatureError:
                _log_debug("[auth] refreshToken expired · user should re-login")
                return None
            except _jwt.InvalidTokenError as e:
                _log_debug("[auth] refreshToken invalid · %s", e)
                return None
            email_in_payload = (payload.get("email") or "").strip().lower()
            if email_in_payload:
                return email_in_payload
            user_id = (
                payload.get("id") or payload.get("sub") or payload.get("userId")
            )
            if not user_id:
                _log_debug(
                    "[auth] refreshToken payload 無 id 欄位 · keys=%s",
                    list(payload.keys()),
                )
                return None
            return lookup_user_email(str(user_id))
        except Exception as e:
            _log_debug("[auth] cookie verify outer fail: %s", e)
            return None

    # 暴露 cache 給測試
    verify_cookie._cache = _CACHE
    lookup_user_email._cache = _CACHE
    return verify_cookie, lookup_user_email


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

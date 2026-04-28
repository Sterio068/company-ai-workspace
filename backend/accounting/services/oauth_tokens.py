"""
v1.3 A5 · Social OAuth token storage + 加密 + refresh helper

不含真 Meta/IG/LinkedIn API call(B1 留 v1.4 等承富送 App)
此 service 只做:
- token 加密存 db.social_oauth_tokens
- token 解密取
- expiring token detection(給 cron 用)
- platform-agnostic interface(各 platform 共用此 store)

加密用 CREDS_KEY env(LibreChat 同一把 · 重 startup 後可解)
若 CREDS_KEY 不在 · 退化明文存 + log warning(dev mode acceptable · prod 拒絕)

Schema · db.social_oauth_tokens:
{
  _id,
  user_email,                    # owner · case-insensitive lower
  platform,                      # facebook | instagram | linkedin
  access_token_encrypted,        # AES-GCM via CREDS_KEY · base64
  refresh_token_encrypted,       # 同上 · 可空(IG basic 沒給)
  scopes: [str],                 # 授權範圍
  account_id: str,               # 各 platform user/page id
  account_name: str,             # display name
  expires_at: datetime,          # access_token expiry · UTC
  connected_at: datetime,
  last_refreshed_at: datetime,
}
"""
import base64
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from auth_deps import _is_prod

logger = logging.getLogger("chengfu")


# ============================================================
# 加密(AES-GCM · 同 LibreChat CREDS_KEY)
# ============================================================
def _get_creds_key() -> Optional[bytes]:
    """從 env 拿 CREDS_KEY · hex string 轉 32 bytes
    沒設或太短 → None(caller 自己決定怎麼降級)"""
    raw = os.getenv("CREDS_KEY", "").strip()
    if not raw or len(raw) < 64:  # 32 bytes hex = 64 chars
        return None
    try:
        return bytes.fromhex(raw[:64])
    except ValueError:
        return None


def encrypt_token(plaintext: str) -> str:
    """AES-GCM 加密 · 回 base64 · 沒 CREDS_KEY → 退化「PLAIN:」前綴明文(警告)"""
    if not plaintext:
        return ""
    key = _get_creds_key()
    if key is None:
        if _is_prod():
            raise RuntimeError("CREDS_KEY required in production · 不允許 OAuth token 明文存庫")
        logger.warning("[oauth] CREDS_KEY 未設 · token 明文存(dev mode · prod 拒絕)")
        return "PLAIN:" + plaintext
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = os.urandom(12)
        cipher = AESGCM(key)
        ct = cipher.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ct).decode("ascii")
    except ImportError:
        if _is_prod():
            raise RuntimeError("cryptography required in production · 不允許 OAuth token 明文存庫")
        logger.warning("[oauth] cryptography 未裝 · 退化明文 · pip install cryptography")
        return "PLAIN:" + plaintext


def decrypt_token(encrypted: str) -> str:
    """加密反向 · 「PLAIN:」前綴認直接 strip"""
    if not encrypted:
        return ""
    if encrypted.startswith("PLAIN:"):
        return encrypted[6:]
    key = _get_creds_key()
    if key is None:
        raise RuntimeError("decrypt 需 CREDS_KEY · 但未設")
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        raw = base64.b64decode(encrypted)
        nonce, ct = raw[:12], raw[12:]
        cipher = AESGCM(key)
        return cipher.decrypt(nonce, ct, None).decode("utf-8")
    except Exception:
        # v1.3 batch6 · HIGH · 不洩漏 cryptography 內部訊息(nonce 長度 / tag mismatch)
        # 給呼叫方面向用戶安全字串 · debug 細節進 log
        logger.debug("[oauth] decrypt fail · key 不匹配 / token 損毀", exc_info=True)
        raise RuntimeError("token 解密失敗 · 請重新連結帳號")


# ============================================================
# Token CRUD
# ============================================================
def store_token(
    db,
    user_email: str,
    platform: str,
    access_token: str,
    refresh_token: Optional[str],
    expires_in_seconds: int,
    scopes: list,
    account_id: str,
    account_name: str = "",
) -> str:
    """upsert · 同 user + platform 取代舊 token"""
    user_email = user_email.strip().lower()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
    doc = {
        "user_email": user_email,
        "platform": platform,
        "access_token_encrypted": encrypt_token(access_token),
        "refresh_token_encrypted": encrypt_token(refresh_token or ""),
        "scopes": scopes,
        "account_id": account_id,
        "account_name": account_name,
        "expires_at": expires_at,
        "connected_at": datetime.now(timezone.utc),
        "last_refreshed_at": datetime.now(timezone.utc),
    }
    db.social_oauth_tokens.update_one(
        {"user_email": user_email, "platform": platform},
        {"$set": doc},
        upsert=True,
    )
    return account_id


def get_access_token(db, user_email: str, platform: str) -> Optional[str]:
    """取明文 access_token · 沒綁回 None"""
    doc = db.social_oauth_tokens.find_one(
        {"user_email": user_email.strip().lower(), "platform": platform}
    )
    if not doc:
        return None
    enc = doc.get("access_token_encrypted")
    if not enc:
        return None
    return decrypt_token(enc)


def revoke_token(db, user_email: str, platform: str) -> bool:
    """刪該 user + platform · 回 True 若刪了"""
    r = db.social_oauth_tokens.delete_one(
        {"user_email": user_email.strip().lower(), "platform": platform}
    )
    return r.deleted_count > 0


def list_connections(db, user_email: Optional[str] = None) -> list:
    """admin 看 status · 列所有(或某 user)綁的 platform · 不回 token 本身"""
    q = {}
    if user_email:
        q["user_email"] = user_email.strip().lower()
    items = []
    for doc in db.social_oauth_tokens.find(q):
        items.append({
            "user_email": doc.get("user_email"),
            "platform": doc.get("platform"),
            "scopes": doc.get("scopes", []),
            "account_id": doc.get("account_id"),
            "account_name": doc.get("account_name"),
            "expires_at": doc.get("expires_at").isoformat() if doc.get("expires_at") else None,
            "connected_at": doc.get("connected_at").isoformat() if doc.get("connected_at") else None,
            "last_refreshed_at": doc.get("last_refreshed_at").isoformat() if doc.get("last_refreshed_at") else None,
        })
    return items


def find_expiring_tokens(db, hours_until_expiry: int = 24) -> list:
    """cron 用 · 找 24h 內過期的 token · 該 refresh"""
    cutoff = datetime.now(timezone.utc) + timedelta(hours=hours_until_expiry)
    return list(db.social_oauth_tokens.find(
        {"expires_at": {"$lt": cutoff}}
    ))

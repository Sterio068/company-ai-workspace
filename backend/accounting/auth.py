"""JWT Auth middleware · 從 LibreChat session 解 token 驗 user。

v1.0 · 內網信任(不強制)
v2.0 · 部分 admin endpoint 強制(write 操作)
v3.0 · 全面強制 + RBAC

用法:
  from auth import require_user, require_admin

  @router.post("/something")
  def something(user = Depends(require_user)):
      return {"you_are": user["email"]}
"""
import os
from typing import Optional
from fastapi import HTTPException, Request, Depends
import jwt


JWT_SECRET = os.getenv("JWT_SECRET", "")
VERIFY_JWT = os.getenv("ENFORCE_JWT_AUTH", "false").lower() == "true"


def get_user_from_request(request: Request) -> Optional[dict]:
    """解析 Authorization header 或 cookie 的 JWT · 回傳 user dict 或 None。"""
    if not JWT_SECRET:
        return None  # 本機 dev 無 secret · 不驗證

    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else None

    if not token:
        # fallback · 從 cookie(LibreChat session)
        token = request.cookies.get("token") or request.cookies.get("refreshToken")

    if not token:
        return None

    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return {
            "id":    decoded.get("id") or decoded.get("sub"),
            "email": decoded.get("email"),
            "role":  decoded.get("role", "USER"),
            "name":  decoded.get("name"),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token 過期,請重新登入")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token 無效")


def require_user(request: Request) -> dict:
    """需要登入 user · 強制 endpoint 用。"""
    user = get_user_from_request(request)
    if not user:
        if VERIFY_JWT:
            raise HTTPException(401, "需要登入(Authorization header 或 session cookie)")
        # Dev 模式 · 回假 user
        return {"id": "dev", "email": "dev@chengfu.local", "role": "ADMIN", "name": "Dev"}
    return user


def require_admin(request: Request) -> dict:
    """需要 ADMIN 權限。"""
    user = require_user(request)
    if user.get("role") != "ADMIN":
        raise HTTPException(403, "需要 ADMIN 權限")
    return user

"""
Routers shared dependencies · Codex R7#6 / R8#8 推薦先建再抽 knowledge/admin

集中:
- _serialize · 從 main.py / feedback.py / tenders.py 重複 4 次抽出
- get_db / get_users_col · lazy 取 Mongo collection · 避免 router 啟動時 import main 有 cycle
- current_user_email_dep · 包成 Depends 給 router
- require_user_dep · 強制要 trusted user(沒 cookie/header 都 403)
- require_admin_dep · 包 require_admin

設計原則:
1. `from main import` 寫在 function body · 是 router import 後第一次 endpoint 註冊時觸發
   (FastAPI 把 default arg 中的 Depends 在 app 建立時解析 · 而非每 request)
   · R9#7 codex 修正:不是「每 request lazy」· 是「import time lazy」· 避免循環的是後者
2. dep factory 回 Depends() · 而非已 wrap 的 callable · 讓 FastAPI 正確 inject
3. 命名統一 · *_dep 後綴(可讀)
4. _serialize 與 main.serialize 行為一致(增 datetime ISO 處理)
"""
from datetime import datetime
from bson import ObjectId
from typing import Optional, Any
from fastapi import Depends, HTTPException, Request


# ============================================================
# Serialization · 從 5 處複製抽出
# ============================================================
def _serialize(doc: Any) -> Any:
    """ObjectId → str + datetime → ISO · 各 router 共用

    注意:main.serialize 不處理 datetime · 只處理 ObjectId
    這裡擴充 · 兩者語意不一致時改用此
    """
    if isinstance(doc, list):
        return [_serialize(d) for d in doc]
    if isinstance(doc, dict):
        return {k: _serialize(v) for k, v in doc.items()}
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc


# ============================================================
# Lazy Mongo collection getters · 避免 routers 啟動時 import main
# ============================================================
def get_db():
    """取主 db handle · 各 router 用 `from ._deps import get_db` 然後 `get_db().feedback`"""
    from main import db
    return db


def get_users_col():
    """LibreChat users collection · 用於 user lookup / role 查"""
    from main import _users_col
    return _users_col


# ============================================================
# Auth dep factories · 統一命名 · 避免每個 router 自己定義
# ============================================================
def current_user_email_dep():
    """factory: 包 current_user_email 成 Depends

    用法:
        @router.get("/foo")
        def foo(email: Optional[str] = current_user_email_dep()):
            ...
    """
    from main import current_user_email
    return Depends(current_user_email)


def require_user_dep():
    """factory: 強制要 trusted user · 沒 cookie/header → 403

    用法:
        @router.get("/private")
        def private(_user: str = require_user_dep()):
            ...
    """
    from main import current_user_email

    def _check(caller: Optional[str] = Depends(current_user_email)) -> str:
        if not caller:
            raise HTTPException(403, "未識別使用者 · 請從 launcher 登入")
        return caller

    return Depends(_check)


def require_admin_dep():
    """factory: 包 require_admin 成 Depends · admin 白名單 / role / internal token 三路徑

    用法:
        @router.get("/admin/foo")
        def foo(_admin: str = require_admin_dep()):
            ...
    """
    from main import require_admin
    return Depends(require_admin)

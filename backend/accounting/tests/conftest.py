"""
tests/ 共用 conftest · R27#2 後 router-wide require_user_dep 加上 · 必須開 LEGACY headers
否則 X-User-Email 會被忽略 · 全部 403

只給 test 環境用 · prod 預設關
"""
import os

# 全 tests/ 子目錄共用
os.environ.setdefault("ALLOW_LEGACY_AUTH_HEADERS", "1")
os.environ.setdefault("ECC_ENV", "development")  # 防 prod startup 強制 JWT_REFRESH_SECRET
# v1.3 batch6 · 移除 sterio068@gmail.com hardcode fallback 後 · test 必須明確設
os.environ.setdefault("ADMIN_EMAILS", "sterio068@gmail.com")

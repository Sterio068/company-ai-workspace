"""
v1.12 · i18n endpoint(architect R3 收尾)
=====================================
單一 source of truth 給 launcher + librechat-relabel.js 共用 TERMS dict
之前散在 librechat-relabel.js hardcode + util.js localizeVisibleText 重複

Endpoints:
  GET /api/i18n               · 公開 · 拿當前 locale + TERMS 字典 + 版本
  GET /api/i18n?locale=zh-CN  · (預留)其他 locale

設計:
  - 公開端點 · login 前可調(launcher / LibreChat 任何頁面都能 fetch)
  - 預設 zh-TW · 從 branding.locale 推
  - terms 字典 hash 當 etag(內容變才 cache miss · 304 friendly)
  - 不存 DB · TERMS 寫死 · v1.13 改 admin 可改
"""
import hashlib
import json
from typing import Optional

from fastapi import APIRouter, Header, Response


router = APIRouter(tags=["i18n"])


# ============================================================
# Default zh-TW dict · 對應 frontend/custom/librechat-relabel.js TERMS
# ============================================================
ZH_TW_TERMS = {
    # AI 引擎用語
    "Endpoint": "AI 引擎",
    "endpoint": "AI 引擎",
    "Preset": "助手模板",
    "presets": "助手模板",
    "Prompts": "快速指令",
    "Prompt": "指令",
    "Temperature": "創意程度",
    "Max Tokens": "最大輸出字數",
    "Max output tokens": "最大輸出字數",
    "Top P": "取樣範圍",
    "Agents": "助手",
    "Agent": "助手",
    "New Chat": "新對話",
    "New Agent": "新增助手",
    "Send a message": "把你想問的打進來…",
    "Search": "搜尋",
    "Conversations": "對話紀錄",
    "Conversation": "對話",
    # 通用 UI
    "Create": "建立",
    "Save": "儲存",
    "Cancel": "取消",
    "Delete": "刪除",
    "Edit": "編輯",
    "Continue": "繼續",
    "Submit": "送出",
    "Regenerate": "重新產生",
    "Stop generating": "停止",
    "Files": "檔案",
    "Upload File": "上傳檔案",
    "Upload files": "上傳檔案",
    # Auth
    "Email address": "電子郵件",
    "Email": "電子郵件",
    "Password": "密碼",
    "Forgot password?": "忘記密碼?",
    "Sign in": "登入",
    "Log in": "登入",
    "Login": "登入",
    "Register": "註冊",
    "Welcome back": "歡迎回來",
    "Continue with Google": "使用 Google 繼續",
    "Privacy policy": "隱私權政策",
    "Terms of service": "服務條款",
    # 設定
    "Settings": "設定",
    "Profile": "個人資料",
    "Logout": "登出",
    "Sign out": "登出",
    "Dark": "深色",
    "Light": "淺色",
    "System": "跟隨系統",
    "Toggle theme": "切換深淺色",
}


SUPPORTED_LOCALES = {
    "zh-TW": ZH_TW_TERMS,
}


def _calc_etag(terms: dict) -> str:
    """terms 字典內容變才 etag 變(client 304 friendly)"""
    raw = json.dumps(terms, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return f'W/"{hashlib.sha256(raw).hexdigest()[:16]}"'


def _detect_locale(db) -> str:
    """從 branding 推 locale · 預設 zh-TW"""
    try:
        doc = db.branding.find_one({"_id": "default"}) or {}
        loc = doc.get("locale", "zh-TW")
        return loc if loc in SUPPORTED_LOCALES else "zh-TW"
    except Exception:
        return "zh-TW"


@router.get("/api/i18n")
def get_i18n(
    response: Response,
    locale: Optional[str] = None,
    if_none_match: Optional[str] = Header(default=None, alias="If-None-Match"),
):
    """公開 · 給 launcher + librechat-relabel 共用 TERMS dict

    Args:
        locale: 強制指定 · 預設讀 branding.locale
        if_none_match: 若 hash 沒變 · 回 304(節流)
    """
    from main import db
    target = locale if locale in SUPPORTED_LOCALES else _detect_locale(db)
    terms = SUPPORTED_LOCALES[target]
    etag = _calc_etag(terms)

    if if_none_match == etag:
        response.status_code = 304
        return None

    response.headers["ETag"] = etag
    # i18n 不會頻繁變(版本變才變)· 安全 cache 5 min
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=3600"

    return {
        "locale": target,
        "terms": terms,
        "version": etag.strip('W/"'),
    }

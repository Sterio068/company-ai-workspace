"""
v1.7 · Multi-tenant Branding 設定
=====================================
讓系統可給多間公司用 · admin 在 UI 設定品牌名稱

Endpoints:
  GET  /admin/branding · 公開讀(login 前可調 · 顯示 app 名)
  PUT  /admin/branding · admin only · 改公司名 / app 名 / accent / tagline

Schema(branding collection · 單一 doc · _id="default"):
  {
    company_name: str,       # "承富創意整合行銷"(完整公司名 · 可選)
    company_short: str,      # "承富"(短名 · brand logo 用)
    app_name: str,           # "承富智慧助理"(完整 app 名 · menubar / title)
    tagline: str,            # "10 人協作平台"(brand-sub)
    accent_color: str,       # 預設 "#007AFF" · admin 可改品牌色
    locale: str,             # "zh-TW"
    updated_at: datetime,
    updated_by: str,
  }

預設值(未設定時):
  app_name = "智慧助理"
  company_short = ""
  tagline = "AI 協作平台"
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from .._deps import require_admin_dep


router = APIRouter(tags=["admin"])

DEFAULT_BRANDING = {
    "company_name": "",
    "company_short": "",
    "app_name": "智慧助理",
    "tagline": "AI 協作平台",
    "accent_color": "#007AFF",
    "locale": "zh-TW",
}


class BrandingUpdate(BaseModel):
    company_name: Optional[str] = None
    company_short: Optional[str] = None
    app_name: Optional[str] = None
    tagline: Optional[str] = None
    accent_color: Optional[str] = None
    locale: Optional[str] = None


def get_branding_doc(db) -> dict:
    """讀 branding · 缺欄位用預設補"""
    doc = db.branding.find_one({"_id": "default"}) or {}
    merged = {**DEFAULT_BRANDING, **{k: v for k, v in doc.items() if k != "_id" and v}}
    # 字串轉 ISO
    if "updated_at" in doc:
        merged["updated_at"] = (doc["updated_at"].isoformat()
                                if hasattr(doc["updated_at"], "isoformat")
                                else doc["updated_at"])
    return merged


@router.get("/admin/branding")
def get_branding(_request: Request):
    """公開 · login 前後皆可讀 · 給 launcher 顯示對的品牌"""
    from main import db
    return get_branding_doc(db)


@router.put("/admin/branding")
def update_branding(payload: BrandingUpdate, _admin: str = require_admin_dep()):
    """admin 改品牌設定"""
    from main import db
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if not update:
        return {"updated": False, "branding": get_branding_doc(db)}
    update["updated_at"] = datetime.now(timezone.utc)
    update["updated_by"] = _admin
    db.branding.update_one(
        {"_id": "default"},
        {"$set": update},
        upsert=True,
    )
    return {"updated": True, "branding": get_branding_doc(db)}

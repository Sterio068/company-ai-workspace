"""
NotebookLM Enterprise adapter.

The adapter is intentionally thin and optional.  If Google Cloud settings are
not present, callers get a structured "not configured" response and the local
source pack remains usable.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import httpx


class NotebookLMClientError(RuntimeError):
    def __init__(self, status_code: int, message: str, recovery_hint: str):
        super().__init__(message)
        self.status_code = status_code
        self.recovery_hint = recovery_hint
        self.message = message


@dataclass(frozen=True)
class NotebookLMConfig:
    enabled: bool
    project_number: str
    location: str
    endpoint_location: str
    access_token: str

    @property
    def configured(self) -> bool:
        return bool(
            self.enabled
            and self.project_number
            and self.location
            and self.endpoint_location
            and self.access_token
        )

    @property
    def base_url(self) -> str:
        return (
            f"https://{self.endpoint_location}-discoveryengine.googleapis.com/v1alpha/"
            f"projects/{self.project_number}/locations/{self.location}"
        )

    @property
    def upload_base_url(self) -> str:
        return (
            f"https://{self.endpoint_location}-discoveryengine.googleapis.com/upload/v1alpha/"
            f"projects/{self.project_number}/locations/{self.location}"
        )


def _setting_value(name: str, env_fallback: str = "") -> str:
    """Read runtime setting from Mongo first, then env.

    NotebookLM settings are admin-editable from the launcher, so the adapter
    must not require a container restart after the initial install.
    """
    try:
        from main import db
        doc = db.system_settings.find_one({"name": name}, {"value": 1})
        if doc is not None:
            return str(doc.get("value") or "").strip()
    except Exception:
        pass
    return os.getenv(name, env_fallback).strip()


def _token_preview(token: str) -> str:
    if not token:
        return "(未設)"
    if len(token) <= 12:
        return "(已設)"
    return f"{token[:8]}...{token[-4:]}"


def load_config() -> NotebookLMConfig:
    access_token = (
        _setting_value("NOTEBOOKLM_ACCESS_TOKEN")
        or os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN", "").strip()
    )
    return NotebookLMConfig(
        enabled=_setting_value("NOTEBOOKLM_ENTERPRISE_ENABLED", "0").lower() in {"1", "true", "yes", "on"},
        project_number=_setting_value("NOTEBOOKLM_PROJECT_NUMBER"),
        location=_setting_value("NOTEBOOKLM_LOCATION", "global") or "global",
        endpoint_location=_setting_value("NOTEBOOKLM_ENDPOINT_LOCATION", "global") or "global",
        access_token=access_token,
    )


def validate_config(cfg: Optional[NotebookLMConfig] = None) -> dict:
    """Lightweight NotebookLM credential check before saving admin settings."""
    cfg = cfg or load_config()
    if not cfg.configured:
        return {"configured": False, "ok": False, "reason": "NotebookLM Enterprise 設定未完整"}
    url = f"{cfg.base_url}/notebooks"
    with httpx.Client(timeout=15) as client:
        r = client.get(url, headers=_headers(cfg), params={"pageSize": 1})
        _raise_for_status(r, "驗證設定")
        data = r.json() if r.content else {}
    return {"configured": True, "ok": True, "sample_count": len(data.get("notebooks", []))}


def public_status() -> dict:
    cfg = load_config()
    missing = []
    if not cfg.enabled:
        missing.append("NOTEBOOKLM_ENTERPRISE_ENABLED=1")
    if not cfg.project_number:
        missing.append("NOTEBOOKLM_PROJECT_NUMBER")
    if not cfg.access_token:
        missing.append("NOTEBOOKLM_ACCESS_TOKEN")
    return {
        "mode": "enterprise-api",
        "configured": cfg.configured,
        "enabled": cfg.enabled,
        "project_number_configured": bool(cfg.project_number),
        "location": cfg.location,
        "endpoint_location": cfg.endpoint_location,
        "access_token_configured": bool(cfg.access_token),
        "missing": missing,
        "docs": {
            "notebooks": "https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks",
            "sources": "https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks-sources",
        },
    }


def admin_config_status() -> dict:
    cfg = load_config()
    return {
        **public_status(),
        "project_number": cfg.project_number,
        "access_token_preview": _token_preview(cfg.access_token),
        "source": "前端設定(Mongo system_settings)優先；未設定時使用 .env / Keychain",
    }


def _headers(cfg: NotebookLMConfig) -> dict:
    return {
        "Authorization": f"Bearer {cfg.access_token}",
        "Content-Type": "application/json",
    }


def _recovery_hint(status_code: int) -> str:
    if status_code == 401:
        return "token_expired"
    if status_code == 403:
        return "permission_denied"
    if status_code == 429:
        return "quota_exceeded"
    if status_code >= 500:
        return "api_down"
    return "request_rejected"


def _raise_for_status(response: httpx.Response, action: str):
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        hint = _recovery_hint(status)
        body = ""
        try:
            body = e.response.text[:300]
        except Exception:
            body = ""
        message = f"NotebookLM {action} 失敗({status})"
        if body:
            message = f"{message}:{body}"
        raise NotebookLMClientError(status, message, hint) from e


def create_notebook(title: str, cfg: Optional[NotebookLMConfig] = None) -> dict:
    cfg = cfg or load_config()
    if not cfg.configured:
        return {"configured": False, "reason": "NotebookLM Enterprise 尚未設定"}
    url = f"{cfg.base_url}/notebooks"
    with httpx.Client(timeout=30) as client:
        r = client.post(url, headers=_headers(cfg), json={"title": title})
        _raise_for_status(r, "建立筆記本")
        data = r.json()
    notebook_id = data.get("notebookId")
    if notebook_id:
        data["web_url"] = f"https://notebooklm.cloud.google.com/{cfg.location}/notebook/{notebook_id}?project={cfg.project_number}"
    return {"configured": True, "notebook": data}


def add_text_source(notebook_id: str, source_name: str, content: str,
                    cfg: Optional[NotebookLMConfig] = None) -> dict:
    cfg = cfg or load_config()
    if not cfg.configured:
        return {"configured": False, "reason": "NotebookLM Enterprise 尚未設定"}
    url = f"{cfg.base_url}/notebooks/{notebook_id}/sources:batchCreate"
    payload = {
        "userContents": [
            {
                "textContent": {
                    "sourceName": source_name,
                    "content": content,
                }
            }
        ]
    }
    with httpx.Client(timeout=60) as client:
        r = client.post(url, headers=_headers(cfg), json=payload)
        _raise_for_status(r, "新增文字來源")
        data = r.json()
    return {"configured": True, "sources": data.get("sources", []), "raw": data}


def upload_file_source(
    notebook_id: str,
    display_name: str,
    content: bytes,
    content_type: str,
    cfg: Optional[NotebookLMConfig] = None,
) -> dict:
    cfg = cfg or load_config()
    if not cfg.configured:
        return {"configured": False, "reason": "NotebookLM Enterprise 尚未設定"}
    safe_name = (display_name or "upload").replace("\r", " ").replace("\n", " ").strip()[:240]
    url = f"{cfg.upload_base_url}/notebooks/{notebook_id}/sources:uploadFile"
    headers = {
        "Authorization": f"Bearer {cfg.access_token}",
        "X-Goog-Upload-File-Name": safe_name,
        "X-Goog-Upload-Protocol": "raw",
        "Content-Type": content_type or "application/octet-stream",
    }
    with httpx.Client(timeout=120) as client:
        r = client.post(url, headers=headers, content=content)
        _raise_for_status(r, "上傳檔案來源")
        data = r.json() if r.content else {}
    return {"configured": True, "source": data}

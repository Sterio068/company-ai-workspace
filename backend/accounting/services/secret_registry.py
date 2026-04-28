"""
Central registry for runtime secrets and admin-editable settings.

The registry is intentionally data-only so routers, docs generators, and
installers can share one source of truth without importing FastAPI.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


SecretTier = Literal["T0_REQUIRED", "T1_RECOMMENDED", "T2_OPTIONAL"]


@dataclass(frozen=True)
class SecretMeta:
    label: str
    desc: str
    console_url: str
    frontend_writable: bool
    source: str
    required: bool
    tier: SecretTier
    reader: str
    writer: str

    def to_dict(self) -> dict:
        return asdict(self)


SECRET_REGISTRY: dict[str, dict] = {
    "OPENAI_API_KEY": SecretMeta(
        label="OpenAI API Key",
        desc="主力 AI 引擎 · 安裝時必填；也可供設計助手 / STT 使用",
        console_url="https://platform.openai.com/api-keys",
        frontend_writable=True,
        source="macOS Keychain / .env 為主；Mongo 設定供 accounting 工具補設",
        required=True,
        tier="T0_REQUIRED",
        reader="LibreChat + accounting tools",
        writer="installer/keychain 或 admin UI(accounting fallback)",
    ).to_dict(),
    "JWT_REFRESH_SECRET": SecretMeta(
        label="JWT Refresh Secret",
        desc="認證 cookie 用 · prod 必設 · 跟 LibreChat .env 同步",
        console_url="",
        frontend_writable=False,
        source="macOS Keychain(install 時自動產)",
        required=True,
        tier="T0_REQUIRED",
        reader="LibreChat + accounting auth",
        writer="installer/keychain only",
    ).to_dict(),
    "ECC_INTERNAL_TOKEN": SecretMeta(
        label="ECC Internal Token",
        desc="cron / internal Agent bridge → accounting endpoint 用 · prod 必設",
        console_url="",
        frontend_writable=False,
        source="macOS Keychain(install 時自動產)",
        required=True,
        tier="T0_REQUIRED",
        reader="accounting internal endpoints + scripts",
        writer="installer/keychain only",
    ).to_dict(),
    "ACTION_BRIDGE_TOKEN": SecretMeta(
        label="Action Bridge Token",
        desc="LibreChat Actions 專用低權限通行權杖 · 只可走 allowlist 工具端點",
        console_url="",
        frontend_writable=False,
        source="macOS Keychain(install/start 時自動產)",
        required=True,
        tier="T0_REQUIRED",
        reader="LibreChat Actions + accounting action bridge",
        writer="installer/keychain only",
    ).to_dict(),
    "MEILI_MASTER_KEY": SecretMeta(
        label="Meilisearch Master Key",
        desc="全文搜尋 index 管理 · 上線第一天後不該改",
        console_url="",
        frontend_writable=False,
        source="macOS Keychain(install 時自動產)",
        required=True,
        tier="T0_REQUIRED",
        reader="meilisearch + LibreChat",
        writer="installer/keychain only",
    ).to_dict(),
    "CREDS_KEY": SecretMeta(
        label="Credentials Encryption Key",
        desc="OAuth token AES-GCM 加密 · prod 必設",
        console_url="",
        frontend_writable=False,
        source="macOS Keychain(install 時自動產)",
        required=True,
        tier="T0_REQUIRED",
        reader="accounting oauth token service",
        writer="installer/keychain only",
    ).to_dict(),
    "ANTHROPIC_API_KEY": SecretMeta(
        label="Anthropic API Key",
        desc="Claude 備援 / 長文件工作流 · 選配但建議",
        console_url="https://console.anthropic.com/settings/keys",
        frontend_writable=False,
        source=".env + macOS Keychain",
        required=False,
        tier="T1_RECOMMENDED",
        reader="LibreChat",
        writer="installer/keychain",
    ).to_dict(),
    "NOTEBOOKLM_ACCESS_TOKEN": SecretMeta(
        label="NotebookLM Access Token",
        desc="NotebookLM Enterprise 同步與檔案上傳用 · 管理員可在前端設定",
        console_url="https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks",
        frontend_writable=True,
        source="Mongo system_settings 優先；未設定時使用 .env / Keychain",
        required=False,
        tier="T1_RECOMMENDED",
        reader="accounting NotebookLM bridge",
        writer="admin UI(寫入前驗證)或 keychain",
    ).to_dict(),
    "NOTEBOOKLM_PROJECT_NUMBER": SecretMeta(
        label="NotebookLM Project Number",
        desc="Google Cloud project number · NotebookLM Enterprise API 必填",
        console_url="https://console.cloud.google.com/",
        frontend_writable=True,
        source="Mongo system_settings 優先；未設定時使用 .env",
        required=False,
        tier="T1_RECOMMENDED",
        reader="accounting NotebookLM bridge",
        writer="admin UI 或 .env",
    ).to_dict(),
    "FAL_API_KEY": SecretMeta(
        label="Fal.ai API Key",
        desc="設計助手生圖(Recraft v3)· 一次 3 張",
        console_url="https://fal.ai/dashboard/keys",
        frontend_writable=True,
        source="Mongo system_settings(可前端改)",
        required=False,
        tier="T2_OPTIONAL",
        reader="accounting design route",
        writer="admin UI",
    ).to_dict(),
    "IMAGE_PROVIDER": SecretMeta(
        label="生圖 Provider",
        desc="選 fal 或 openai · 由 backend route 決定供應商",
        console_url="",
        frontend_writable=True,
        source="Mongo system_settings(可前端改)· 預設 fal",
        required=False,
        tier="T2_OPTIONAL",
        reader="accounting design route",
        writer="admin UI",
    ).to_dict(),
    "EMAIL_USERNAME": SecretMeta(
        label="SMTP Username",
        desc="月報自動寄信用(選配)",
        console_url="",
        frontend_writable=False,
        source=".env",
        required=False,
        tier="T2_OPTIONAL",
        reader="accounting mailer",
        writer=".env / keychain",
    ).to_dict(),
    "EMAIL_PASSWORD": SecretMeta(
        label="SMTP Password",
        desc="SMTP 密碼 · Gmail 用 App Password · 不是本密碼",
        console_url="https://myaccount.google.com/apppasswords",
        frontend_writable=False,
        source=".env + macOS Keychain",
        required=False,
        tier="T2_OPTIONAL",
        reader="accounting mailer",
        writer=".env / keychain",
    ).to_dict(),
}


def secret_meta(name: str) -> dict | None:
    return SECRET_REGISTRY.get(name)

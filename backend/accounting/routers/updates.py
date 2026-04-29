"""
Private Electron update proxy.

The desktop app never talks to private GitHub Releases directly. It calls
these authenticated endpoints with a proxy token; this server then reads
GitHub Releases using a server-side token and rewrites update feeds/assets
to proxy-hosted URLs.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional
from urllib.parse import quote, unquote, urlparse

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse, StreamingResponse

from auth_deps import _secrets_equal


router = APIRouter(prefix="/api/updates", tags=["updates"])

Platform = Literal["darwin", "win32"]
Arch = Literal["arm64", "x64"]

_CACHE_TTL_SECONDS = int(os.getenv("UPDATE_PROXY_CACHE_TTL_SECONDS", "60") or "60")
_release_cache: dict[str, tuple[float, dict]] = {}


@dataclass(frozen=True)
class UpdateSettings:
    proxy_url: str
    proxy_token: str
    github_token: str
    github_repository: str
    include_prerelease: bool = False


def _env_first(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _settings() -> UpdateSettings:
    proxy_url = _env_first("VOTER_SERVICE_UPDATE_PROXY_URL", "UPDATE_PROXY_URL").rstrip("/")
    proxy_token = _env_first("VOTER_SERVICE_UPDATE_PROXY_TOKEN", "UPDATE_PROXY_TOKEN")
    github_token = _env_first(
        "UPDATE_PROXY_GITHUB_TOKEN",
        "VOTER_SERVICE_GITHUB_TOKEN",
        "GITHUB_TOKEN",
    )
    github_repository = _env_first(
        "UPDATE_PROXY_GITHUB_REPOSITORY",
        "VOTER_SERVICE_GITHUB_REPOSITORY",
        "GITHUB_REPOSITORY",
    ) or "Sterio068/company-ai-workspace"
    include_prerelease = _env_first("UPDATE_PROXY_INCLUDE_PRERELEASE").lower() in {
        "1",
        "true",
        "yes",
    }
    return UpdateSettings(
        proxy_url=proxy_url,
        proxy_token=proxy_token,
        github_token=github_token,
        github_repository=github_repository,
        include_prerelease=include_prerelease,
    )


def _require_proxy_auth(authorization: Optional[str]) -> UpdateSettings:
    settings = _settings()
    if not settings.proxy_token:
        raise HTTPException(503, "update proxy token is not configured")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not _secrets_equal(token.strip(), settings.proxy_token):
        raise HTTPException(401, "invalid update proxy token")
    if not settings.github_token:
        raise HTTPException(503, "GitHub release token is not configured")
    if "/" not in settings.github_repository:
        raise HTTPException(503, "GitHub repository is not configured")
    return settings


def _base_proxy_url(request: Request, settings: UpdateSettings) -> str:
    if settings.proxy_url:
        return settings.proxy_url
    # Dev/test fallback. Production packages should receive a fixed proxy URL
    # from CI-generated update-proxy.json.
    return str(request.base_url).rstrip("/")


def _normalize_version(tag_or_version: str) -> str:
    value = (tag_or_version or "").strip()
    return value[1:] if value.lower().startswith("v") else value


def _version_tuple(version: str) -> tuple[int, int, int, tuple[str, ...]]:
    clean = _normalize_version(version)
    main, _, suffix = clean.partition("-")
    nums = []
    for part in main.split(".")[:3]:
        try:
            nums.append(int(re.sub(r"[^0-9].*$", "", part) or "0"))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2], tuple(suffix.split(".")) if suffix else ()


def _is_newer(latest: str, current: str) -> bool:
    return _version_tuple(latest) > _version_tuple(current)


def _github_headers(settings: UpdateSettings, accept: str = "application/vnd.github+json") -> dict:
    return {
        "Accept": accept,
        "Authorization": f"Bearer {settings.github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "company-ai-update-proxy",
    }


def _github_api_url(settings: UpdateSettings, path: str) -> str:
    return f"https://api.github.com/repos/{settings.github_repository}{path}"


def _fetch_release_from_github(settings: UpdateSettings) -> dict:
    if settings.include_prerelease:
        url = _github_api_url(settings, "/releases")
        with httpx.Client(timeout=20) as client:
            r = client.get(url, headers=_github_headers(settings), params={"per_page": 20})
            if r.status_code == 404:
                raise HTTPException(502, "private GitHub release not reachable")
            r.raise_for_status()
            releases = [
                item for item in r.json()
                if not item.get("draft") and (settings.include_prerelease or not item.get("prerelease"))
            ]
            if not releases:
                raise HTTPException(404, "no published release found")
            return releases[0]

    url = _github_api_url(settings, "/releases/latest")
    with httpx.Client(timeout=20) as client:
        r = client.get(url, headers=_github_headers(settings))
        if r.status_code == 404:
            raise HTTPException(502, "private GitHub latest release not reachable")
        r.raise_for_status()
        return r.json()


def _get_latest_release(settings: UpdateSettings, force_refresh: bool = False) -> dict:
    key = settings.github_repository
    now = time.time()
    cached = _release_cache.get(key)
    if not force_refresh and cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]
    release = _fetch_release_from_github(settings)
    _release_cache[key] = (now, release)
    return release


def _asset_names(release: dict) -> list[str]:
    return [str(asset.get("name") or "") for asset in release.get("assets", []) if asset.get("name")]


def _find_asset(release: dict, asset_name: str) -> Optional[dict]:
    safe_name = os.path.basename(asset_name)
    if safe_name != asset_name or not safe_name:
        return None
    for asset in release.get("assets", []):
        if asset.get("name") == safe_name:
            return asset
    return None


def _asset_proxy_url(base_url: str, asset_name: str) -> str:
    return f"{base_url}/api/updates/assets/{quote(asset_name)}"


def _feed_proxy_url(base_url: str, platform: Platform) -> str:
    feed_name = "mac/latest-mac.yml" if platform == "darwin" else "win/latest.yml"
    return f"{base_url}/api/updates/generic/{feed_name}"


def _arch_matches(name: str, arch: Arch) -> bool:
    lower = name.lower()
    if arch == "arm64":
        return any(mark in lower for mark in ("arm64", "aarch64", "universal"))
    return any(mark in lower for mark in ("x64", "x86_64", "amd64", "universal"))


def _platform_asset(release: dict, platform: Platform, arch: Arch) -> Optional[dict]:
    names = _asset_names(release)
    if platform == "darwin":
        candidates = [n for n in names if n.lower().endswith(".dmg")]
    else:
        candidates = [
            n for n in names
            if n.lower().endswith((".exe", ".msi", ".zip")) and "setup" in n.lower()
        ] or [n for n in names if n.lower().endswith((".exe", ".msi", ".zip"))]
    ordered = sorted(
        candidates,
        key=lambda n: (not _arch_matches(n, arch), "portable" in n.lower(), n.lower()),
    )
    return _find_asset(release, ordered[0]) if ordered else None


def _feed_asset_name(platform: Platform) -> str:
    return "latest-mac.yml" if platform == "darwin" else "latest.yml"


def _release_version(release: dict) -> str:
    return _normalize_version(str(release.get("tag_name") or release.get("name") or "0.0.0"))


def _release_summary(release: dict) -> dict:
    return {
        "tag_name": release.get("tag_name"),
        "name": release.get("name"),
        "published_at": release.get("published_at"),
        "html_url": release.get("html_url"),
        "prerelease": bool(release.get("prerelease")),
    }


def _force_refresh_requested(request: Request, refresh: bool) -> bool:
    cache_control = (request.headers.get("Cache-Control") or "").lower()
    pragma = (request.headers.get("Pragma") or "").lower()
    return refresh or "no-cache" in cache_control or "no-cache" in pragma


@router.get("/latest")
def latest_update(
    request: Request,
    current: str = Query(..., min_length=1),
    platform: Platform = Query(...),
    arch: Arch = Query(...),
    refresh: bool = Query(default=False),
    authorization: Optional[str] = Header(default=None),
):
    settings = _require_proxy_auth(authorization)
    release = _get_latest_release(
        settings,
        force_refresh=_force_refresh_requested(request, refresh),
    )
    base_url = _base_proxy_url(request, settings)
    latest = _release_version(release)
    platform_asset = _platform_asset(release, platform, arch)
    return {
        "success": True,
        "has_update": _is_newer(latest, current),
        "latest": latest,
        "current": _normalize_version(current),
        "platform": platform,
        "arch": arch,
        "release": _release_summary(release),
        "platform_asset": {
            "name": platform_asset.get("name"),
            "url": _asset_proxy_url(base_url, platform_asset.get("name")),
            "size": platform_asset.get("size"),
            "content_type": platform_asset.get("content_type"),
        } if platform_asset else None,
        "feeds": {
            "mac": _feed_proxy_url(base_url, "darwin"),
            "win": _feed_proxy_url(base_url, "win32"),
        },
    }


def _download_asset_bytes(settings: UpdateSettings, asset: dict) -> bytes:
    asset_id = asset.get("id")
    if not asset_id:
        raise HTTPException(404, "release asset id missing")
    url = _github_api_url(settings, f"/releases/assets/{asset_id}")
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        r = client.get(url, headers=_github_headers(settings, "application/octet-stream"))
        if r.status_code == 404:
            raise HTTPException(404, "release asset not found")
        r.raise_for_status()
        return r.content


def _rewrite_feed(feed_text: str, base_url: str) -> str:
    rewritten: list[str] = []
    for line in feed_text.splitlines():
        match = re.match(r"^(\s*(?:-\s*)?)(url|path):\s*(.+?)\s*$", line)
        if not match:
            rewritten.append(line)
            continue
        indent, key, raw_value = match.groups()
        quote_char = raw_value[0] if raw_value[:1] in {"'", '"'} else ""
        value = raw_value.strip().strip("'\"")
        parsed = urlparse(value)
        asset_name = unquote(os.path.basename(parsed.path or value))
        if not asset_name or asset_name.endswith((".yml", ".yaml")):
            rewritten.append(line)
            continue
        proxy_value = _asset_proxy_url(base_url, asset_name)
        if quote_char:
            proxy_value = f"{quote_char}{proxy_value}{quote_char}"
        rewritten.append(f"{indent}{key}: {proxy_value}")
    return "\n".join(rewritten) + ("\n" if feed_text.endswith("\n") else "")


def _latest_feed(
    request: Request,
    platform: Platform,
    authorization: Optional[str],
) -> PlainTextResponse:
    settings = _require_proxy_auth(authorization)
    release = _get_latest_release(settings)
    feed_name = _feed_asset_name(platform)
    asset = _find_asset(release, feed_name)
    if not asset:
        raise HTTPException(404, f"{feed_name} not found in latest release")
    feed_text = _download_asset_bytes(settings, asset).decode("utf-8", errors="replace")
    body = _rewrite_feed(feed_text, _base_proxy_url(request, settings))
    return PlainTextResponse(
        body,
        media_type="text/yaml",
        headers={"Cache-Control": f"private, max-age={_CACHE_TTL_SECONDS}"},
    )


def _latest_feed_head(platform: Platform, authorization: Optional[str]) -> Response:
    settings = _require_proxy_auth(authorization)
    release = _get_latest_release(settings)
    feed_name = _feed_asset_name(platform)
    if not _find_asset(release, feed_name):
        raise HTTPException(404, f"{feed_name} not found in latest release")
    return Response(
        status_code=200,
        media_type="text/yaml",
        headers={"Cache-Control": f"private, max-age={_CACHE_TTL_SECONDS}"},
    )


@router.get("/generic/mac/latest-mac.yml", response_class=PlainTextResponse)
def latest_mac_feed(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    return _latest_feed(request, "darwin", authorization)


@router.head("/generic/mac/latest-mac.yml")
def latest_mac_feed_head(authorization: Optional[str] = Header(default=None)):
    return _latest_feed_head("darwin", authorization)


@router.get("/generic/win/latest.yml", response_class=PlainTextResponse)
def latest_win_feed(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    return _latest_feed(request, "win32", authorization)


@router.head("/generic/win/latest.yml")
def latest_win_feed_head(authorization: Optional[str] = Header(default=None)):
    return _latest_feed_head("win32", authorization)


@router.get("/assets/{asset_name}")
def download_asset(
    asset_name: str,
    authorization: Optional[str] = Header(default=None),
):
    settings = _require_proxy_auth(authorization)
    release = _get_latest_release(settings)
    asset = _find_asset(release, asset_name)
    if not asset:
        raise HTTPException(404, "release asset not found")
    data = _download_asset_bytes(settings, asset)
    headers = {
        "Content-Disposition": f'attachment; filename="{asset.get("name")}"',
        "Cache-Control": "private, max-age=300",
    }
    return StreamingResponse(
        iter([data]),
        media_type=asset.get("content_type") or "application/octet-stream",
        headers=headers,
    )


def clear_update_proxy_cache() -> None:
    """Operational helper for tests or admin shell."""
    _release_cache.clear()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import updates


def _fake_release():
    return {
        "tag_name": "v1.3.0",
        "name": "v1.3.0",
        "published_at": "2026-04-29T00:00:00Z",
        "html_url": "https://github.example/releases/v1.3.0",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "id": 101,
                "name": "CompanyAI-1.3.0-arm64.dmg",
                "size": 123,
                "content_type": "application/x-apple-diskimage",
            },
            {
                "id": 102,
                "name": "CompanyAI Setup 1.3.0.exe",
                "size": 456,
                "content_type": "application/vnd.microsoft.portable-executable",
            },
            {"id": 103, "name": "latest-mac.yml", "size": 10, "content_type": "text/yaml"},
            {"id": 104, "name": "latest.yml", "size": 10, "content_type": "text/yaml"},
        ],
    }


def _client(monkeypatch):
    monkeypatch.setenv("VOTER_SERVICE_UPDATE_PROXY_URL", "https://updates.example.test")
    monkeypatch.setenv("VOTER_SERVICE_UPDATE_PROXY_TOKEN", "proxy-token")
    monkeypatch.setenv("UPDATE_PROXY_GITHUB_TOKEN", "github-token")
    monkeypatch.setenv("UPDATE_PROXY_GITHUB_REPOSITORY", "owner/private-repo")
    updates.clear_update_proxy_cache()
    app = FastAPI()
    app.include_router(updates.router)
    return TestClient(app)


def _auth():
    return {"Authorization": "Bearer proxy-token"}


def test_latest_requires_proxy_token(monkeypatch):
    client = _client(monkeypatch)
    r = client.get("/api/updates/latest?current=1.0.0&platform=darwin&arch=arm64")
    assert r.status_code == 401


def test_latest_reports_update_and_proxy_asset_url(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(updates, "_get_latest_release", lambda settings, force_refresh=False: _fake_release())

    r = client.get(
        "/api/updates/latest?current=1.2.0&platform=darwin&arch=arm64",
        headers=_auth(),
    )

    assert r.status_code == 200
    body = r.json()
    assert body["has_update"] is True
    assert body["latest"] == "1.3.0"
    assert body["platform_asset"]["name"] == "CompanyAI-1.3.0-arm64.dmg"
    assert body["platform_asset"]["url"] == (
        "https://updates.example.test/api/updates/assets/CompanyAI-1.3.0-arm64.dmg"
    )
    assert body["feeds"]["win"] == "https://updates.example.test/api/updates/generic/win/latest.yml"


def test_latest_current_version_has_no_update(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(updates, "_get_latest_release", lambda settings, force_refresh=False: _fake_release())

    r = client.get(
        "/api/updates/latest?current=v1.3.0&platform=win32&arch=x64",
        headers=_auth(),
    )

    assert r.status_code == 200
    assert r.json()["has_update"] is False
    assert r.json()["platform_asset"]["name"] == "CompanyAI Setup 1.3.0.exe"


def test_manual_refresh_bypasses_metadata_cache(monkeypatch):
    client = _client(monkeypatch)
    calls = []

    def fake_latest(settings, force_refresh=False):
        calls.append(force_refresh)
        return _fake_release()

    monkeypatch.setattr(updates, "_get_latest_release", fake_latest)
    r = client.get(
        "/api/updates/latest?current=1.0.0&platform=darwin&arch=arm64&refresh=true",
        headers=_auth(),
    )

    assert r.status_code == 200
    assert calls == [True]


def test_windows_feed_rewrites_asset_urls_to_proxy(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(updates, "_get_latest_release", lambda settings, force_refresh=False: _fake_release())
    feed = """version: 1.3.0
files:
  - url: https://github.com/owner/private-repo/releases/download/v1.3.0/CompanyAI%20Setup%201.3.0.exe
    sha512: abc
    size: 456
path: CompanyAI Setup 1.3.0.exe
sha512: abc
releaseDate: '2026-04-29T00:00:00.000Z'
"""
    monkeypatch.setattr(updates, "_download_asset_bytes", lambda settings, asset: feed.encode())

    r = client.get("/api/updates/generic/win/latest.yml", headers=_auth())

    assert r.status_code == 200
    assert "github.com" not in r.text
    assert "https://updates.example.test/api/updates/assets/CompanyAI%20Setup%201.3.0.exe" in r.text


def test_mac_feed_rewrites_dmg_url_to_proxy(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(updates, "_get_latest_release", lambda settings, force_refresh=False: _fake_release())
    feed = """version: 1.3.0
files:
  - url: CompanyAI-1.3.0-arm64.dmg
    sha512: abc
    size: 123
path: CompanyAI-1.3.0-arm64.dmg
sha512: abc
releaseDate: '2026-04-29T00:00:00.000Z'
"""
    monkeypatch.setattr(updates, "_download_asset_bytes", lambda settings, asset: feed.encode())

    r = client.get("/api/updates/generic/mac/latest-mac.yml", headers=_auth())

    assert r.status_code == 200
    assert "https://updates.example.test/api/updates/assets/CompanyAI-1.3.0-arm64.dmg" in r.text


def test_feed_head_supports_curl_header_checks(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(updates, "_get_latest_release", lambda settings, force_refresh=False: _fake_release())

    mac = client.head("/api/updates/generic/mac/latest-mac.yml", headers=_auth())
    win = client.head("/api/updates/generic/win/latest.yml", headers=_auth())

    assert mac.status_code == 200
    assert win.status_code == 200
    assert mac.headers["cache-control"] == "private, max-age=60"


def test_asset_download_streams_private_release_asset(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(updates, "_get_latest_release", lambda settings, force_refresh=False: _fake_release())
    monkeypatch.setattr(updates, "_download_asset_bytes", lambda settings, asset: b"dmg-bytes")

    r = client.get("/api/updates/assets/CompanyAI-1.3.0-arm64.dmg", headers=_auth())

    assert r.status_code == 200
    assert r.content == b"dmg-bytes"
    assert r.headers["content-disposition"] == 'attachment; filename="CompanyAI-1.3.0-arm64.dmg"'

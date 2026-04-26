"""
v1.12 · i18n endpoint tests
=====================================
GET /api/i18n · public · 給 launcher + librechat-relabel.js 共用 TERMS

跑:
  cd backend/accounting
  python3 -m pytest tests/test_v1_12_i18n.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestI18nDict:
    def test_zh_tw_terms_complete(self):
        from routers.i18n import ZH_TW_TERMS
        # 至少 30 個常用 term
        assert len(ZH_TW_TERMS) >= 30
        # 必有的關鍵 term
        for k in ["Endpoint", "Sign in", "Welcome back", "Settings", "Logout"]:
            assert k in ZH_TW_TERMS, f"missing key term: {k}"

    def test_no_empty_translations(self):
        from routers.i18n import ZH_TW_TERMS
        for k, v in ZH_TW_TERMS.items():
            assert v and len(v.strip()) > 0, f"empty translation for {k}"

    def test_supported_locales(self):
        from routers.i18n import SUPPORTED_LOCALES
        assert "zh-TW" in SUPPORTED_LOCALES


class TestEtagStability:
    def test_same_content_same_etag(self):
        from routers.i18n import _calc_etag, ZH_TW_TERMS
        a = _calc_etag(ZH_TW_TERMS)
        b = _calc_etag(ZH_TW_TERMS)
        assert a == b
        assert a.startswith('W/"')

    def test_different_content_different_etag(self):
        from routers.i18n import _calc_etag
        a = _calc_etag({"a": "1"})
        b = _calc_etag({"a": "2"})
        assert a != b


class TestLocaleDetection:
    def test_default_zh_tw_when_no_branding(self):
        from routers.i18n import _detect_locale

        class FakeDB:
            class branding:
                @staticmethod
                def find_one(_):
                    return None

        assert _detect_locale(FakeDB) == "zh-TW"

    def test_unsupported_locale_falls_back_zh_tw(self):
        from routers.i18n import _detect_locale

        class FakeDB:
            class branding:
                @staticmethod
                def find_one(_):
                    return {"locale": "fr-FR"}

        assert _detect_locale(FakeDB) == "zh-TW"

    def test_branding_locale_used_when_supported(self):
        from routers.i18n import _detect_locale, SUPPORTED_LOCALES
        SUPPORTED_LOCALES.setdefault("en-US", {"Hello": "Hello"})

        class FakeDB:
            class branding:
                @staticmethod
                def find_one(_):
                    return {"locale": "en-US"}

        try:
            assert _detect_locale(FakeDB) == "en-US"
        finally:
            SUPPORTED_LOCALES.pop("en-US", None)


class TestRouterRegistration:
    def test_get_i18n_route_defined(self):
        from routers.i18n import router
        # 確認 GET /api/i18n 註冊了
        paths = [r.path for r in router.routes]
        assert "/api/i18n" in paths

    def test_main_includes_i18n_router(self):
        """main.py 應 include i18n router · 否則前端 fetch 會 404 到 LibreChat"""
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "main.py")
        src = open(path).read()
        assert "from routers import i18n" in src
        assert "_i18n_router.router" in src


class TestNginxRouting:
    def test_nginx_routes_api_i18n_to_accounting(self):
        """nginx default.conf 應有 location = /api/i18n → accounting:8000"""
        # backend/accounting/tests/ → repo root → frontend/nginx/default.conf
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))))
        path = os.path.join(repo_root, "frontend", "nginx", "default.conf")
        src = open(path).read()
        assert "location = /api/i18n" in src
        assert "proxy_pass http://accounting:8000/api/i18n" in src
        # 必須在 /api/ catch-all 之前
        i18n_pos = src.find("location = /api/i18n")
        api_catchall_pos = src.find("location /api/ {")
        assert i18n_pos != -1 and api_catchall_pos != -1
        assert i18n_pos < api_catchall_pos, \
            "/api/i18n 必須在 /api/ catch-all 之前 · nginx prefix-longest match"

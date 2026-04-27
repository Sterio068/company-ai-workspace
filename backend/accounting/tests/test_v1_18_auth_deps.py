"""
v1.18 · auth_deps tests · architect R2 第一階段
=================================================
從 main.py 抽出的 5 個 env-based helper 必須行為與 main 完全一致

跑:
  cd backend/accounting
  python3 -m pytest tests/test_v1_18_auth_deps.py -v
"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestIsProd:
    def test_ecc_env_production(self):
        from auth_deps import _is_prod
        with patch.dict(os.environ, {"ECC_ENV": "production"}, clear=True):
            assert _is_prod() is True

    def test_node_env_production(self):
        from auth_deps import _is_prod
        with patch.dict(os.environ, {"NODE_ENV": "production"}, clear=True):
            assert _is_prod() is True

    def test_neither_set(self):
        from auth_deps import _is_prod
        with patch.dict(os.environ, {}, clear=True):
            assert _is_prod() is False

    def test_dev_mode(self):
        from auth_deps import _is_prod
        with patch.dict(os.environ, {"ECC_ENV": "development"}, clear=True):
            assert _is_prod() is False


class TestJwtRefreshConfigured:
    def test_real_secret(self):
        from auth_deps import _jwt_refresh_configured
        with patch.dict(os.environ, {"JWT_REFRESH_SECRET": "abc123"}, clear=True):
            assert _jwt_refresh_configured() is True

    def test_placeholder(self):
        from auth_deps import _jwt_refresh_configured
        with patch.dict(os.environ, {"JWT_REFRESH_SECRET": "<GENERATE_ME>"}, clear=True):
            assert _jwt_refresh_configured() is False

    def test_unset(self):
        from auth_deps import _jwt_refresh_configured
        with patch.dict(os.environ, {}, clear=True):
            assert _jwt_refresh_configured() is False


class TestLegacyAuthHeaders:
    def test_explicit_on(self):
        from auth_deps import _legacy_auth_headers_enabled
        with patch.dict(os.environ, {"ALLOW_LEGACY_AUTH_HEADERS": "1"}, clear=True):
            assert _legacy_auth_headers_enabled() is True

    def test_explicit_off(self):
        from auth_deps import _legacy_auth_headers_enabled
        # 即使 dev · explicit=0 也關
        with patch.dict(os.environ, {"ALLOW_LEGACY_AUTH_HEADERS": "0", "ECC_ENV": "development"}, clear=True):
            assert _legacy_auth_headers_enabled() is False

    def test_default_prod_off(self):
        from auth_deps import _legacy_auth_headers_enabled
        with patch.dict(os.environ, {"ECC_ENV": "production"}, clear=True):
            assert _legacy_auth_headers_enabled() is False

    def test_default_dev_on(self):
        from auth_deps import _legacy_auth_headers_enabled
        with patch.dict(os.environ, {}, clear=True):
            assert _legacy_auth_headers_enabled() is True


class TestEnvModeConfigured:
    def test_ecc_env_set(self):
        from auth_deps import _env_mode_configured
        with patch.dict(os.environ, {"ECC_ENV": "production"}, clear=True):
            assert _env_mode_configured() is True

    def test_node_env_set(self):
        from auth_deps import _env_mode_configured
        with patch.dict(os.environ, {"NODE_ENV": "development"}, clear=True):
            assert _env_mode_configured() is True

    def test_neither(self):
        from auth_deps import _env_mode_configured
        with patch.dict(os.environ, {}, clear=True):
            assert _env_mode_configured() is False


class TestSecretsEqual:
    def test_same(self):
        from auth_deps import _secrets_equal
        assert _secrets_equal("abc", "abc") is True

    def test_diff(self):
        from auth_deps import _secrets_equal
        assert _secrets_equal("abc", "abd") is False

    def test_empty(self):
        from auth_deps import _secrets_equal
        assert _secrets_equal("", "abc") is False
        assert _secrets_equal("abc", "") is False
        assert _secrets_equal("", "") is False


class TestMainBackwardCompat:
    """確保 main.py re-export 相容 · router 用 `from main import _is_prod` 仍能拿到"""

    def test_main_re_exports_is_prod(self):
        # 因為 main.py top-level 引入 fastapi/pymongo · import 會 trigger startup
        # 改驗 source code 有 re-export
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
        src = open(path).read()
        assert "from auth_deps import" in src
        assert "_is_prod" in src
        assert "_jwt_refresh_configured" in src
        assert "_legacy_auth_headers_enabled" in src
        assert "_env_mode_configured" in src
        assert "_secrets_equal" in src

    def test_main_no_inline_definitions(self):
        """main.py 不應再有 inline `def _is_prod():` 等"""
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
        src = open(path).read()
        # 抽出後 · main 不該再有這些 def
        for fn in ["_is_prod", "_jwt_refresh_configured", "_legacy_auth_headers_enabled",
                   "_env_mode_configured", "_secrets_equal"]:
            assert f"def {fn}(" not in src, f"main.py 仍有 inline def {fn} · 應只 import"

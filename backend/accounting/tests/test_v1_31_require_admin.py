"""
v1.31 · require_admin + load_admin_allowlist 抽出 · architect R2 round 5(R2 完整) tests
"""
import os
import sys
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_request(internal_token=None, trusted=False):
    req = MagicMock()
    req.headers = {}
    if internal_token is not None:
        req.headers["X-Internal-Token"] = internal_token
    req.state.email_trusted = trusted
    req.url.path = "/admin/test"
    return req


class TestLoadAdminAllowlist:
    def test_empty_when_no_env(self, monkeypatch):
        from auth_deps import load_admin_allowlist
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        monkeypatch.delenv("ADMIN_EMAIL", raising=False)
        assert load_admin_allowlist() == set()

    def test_admin_emails_csv(self, monkeypatch):
        from auth_deps import load_admin_allowlist
        monkeypatch.setenv("ADMIN_EMAILS", "alice@e.com,Bob@E.com,carol@e.com")
        result = load_admin_allowlist()
        assert result == {"alice@e.com", "bob@e.com", "carol@e.com"}

    def test_admin_email_singular_fallback(self, monkeypatch):
        from auth_deps import load_admin_allowlist
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        monkeypatch.setenv("ADMIN_EMAIL", "single@e.com")
        assert load_admin_allowlist() == {"single@e.com"}

    def test_strips_whitespace_and_lowercases(self, monkeypatch):
        from auth_deps import load_admin_allowlist
        monkeypatch.setenv("ADMIN_EMAILS", "  Foo@e.com  , Bar@E.com ")
        assert load_admin_allowlist() == {"foo@e.com", "bar@e.com"}


class TestRequireAdmin:
    def test_internal_token_match(self, monkeypatch):
        from auth_deps import make_require_admin
        monkeypatch.setenv("ECC_INTERNAL_TOKEN", "secret123")
        users = MagicMock()
        ra = make_require_admin(users, set())
        req = _make_request(internal_token="secret123")
        assert ra(req, None) == "internal:cron"
        users.find_one.assert_not_called()

    def test_no_email_raises(self, monkeypatch):
        from auth_deps import make_require_admin
        monkeypatch.setenv("ECC_INTERNAL_TOKEN", "")
        ra = make_require_admin(MagicMock(), {"a@e.com"})
        with pytest.raises(HTTPException) as exc:
            ra(_make_request(), None)
        assert exc.value.status_code == 403

    def test_jwt_configured_but_not_trusted_raises(self, monkeypatch):
        from auth_deps import make_require_admin
        monkeypatch.setenv("ECC_INTERNAL_TOKEN", "")
        monkeypatch.setenv("JWT_REFRESH_SECRET", "real-secret")
        ra = make_require_admin(MagicMock(), {"a@e.com"})
        req = _make_request(trusted=False)
        with pytest.raises(HTTPException) as exc:
            ra(req, "a@e.com")
        assert exc.value.status_code == 403

    def test_allowlist_trusted_passes(self, monkeypatch):
        from auth_deps import make_require_admin
        monkeypatch.setenv("ECC_INTERNAL_TOKEN", "")
        monkeypatch.setenv("JWT_REFRESH_SECRET", "real-secret")
        users = MagicMock()
        users.find_one.return_value = {"chengfu_active": True}
        ra = make_require_admin(users, {"a@e.com"})
        req = _make_request(trusted=True)
        assert ra(req, "a@e.com") == "a@e.com"

    def test_allowlist_inactive_user_raises(self, monkeypatch):
        from auth_deps import make_require_admin
        monkeypatch.setenv("ECC_INTERNAL_TOKEN", "")
        monkeypatch.setenv("JWT_REFRESH_SECRET", "real-secret")
        users = MagicMock()
        users.find_one.return_value = {"chengfu_active": False}
        ra = make_require_admin(users, {"a@e.com"})
        req = _make_request(trusted=True)
        with pytest.raises(HTTPException) as exc:
            ra(req, "a@e.com")
        assert exc.value.status_code == 403

    def test_db_role_admin_passes(self, monkeypatch):
        from auth_deps import make_require_admin
        monkeypatch.setenv("ECC_INTERNAL_TOKEN", "")
        monkeypatch.setenv("JWT_REFRESH_SECRET", "real-secret")
        users = MagicMock()
        users.find_one.return_value = {"role": "ADMIN", "chengfu_active": True}
        ra = make_require_admin(users, set())  # 不在 allowlist
        req = _make_request(trusted=True)
        assert ra(req, "x@e.com") == "x@e.com"

    def test_no_admin_anywhere_raises(self, monkeypatch):
        from auth_deps import make_require_admin
        monkeypatch.setenv("ECC_INTERNAL_TOKEN", "")
        monkeypatch.setenv("JWT_REFRESH_SECRET", "real-secret")
        users = MagicMock()
        users.find_one.return_value = {"role": "USER"}
        ra = make_require_admin(users, set())
        req = _make_request(trusted=True)
        with pytest.raises(HTTPException) as exc:
            ra(req, "x@e.com")
        assert exc.value.status_code == 403


class TestMainBackwardCompat:
    def test_main_imports_factory(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
        src = open(path).read()
        assert "from auth_deps import load_admin_allowlist" in src
        assert "from auth_deps import make_require_admin" in src

    def test_main_no_inline_email_csv(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
        src = open(path).read()
        # 不該再有 inline _admin_allowlist set comprehension
        assert "_admin_allowlist = {e.strip().lower() for e in" not in src

    def test_main_require_admin_thin_wrapper(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
        src = open(path).read()
        # require_admin 應只 thin wrap _require_admin_impl
        assert "_require_admin_impl(request, email)" in src

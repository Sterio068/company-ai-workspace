"""
v1.30 · make_cookie_verifier 抽出 · architect R2 round 4 tests

跑:
  cd backend/accounting
  python3 -m pytest tests/test_v1_30_cookie_verifier.py -v
"""
import os
import sys
import time
from unittest.mock import MagicMock
from bson import ObjectId

import jwt
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


SECRET = "test-secret-1234"


def _make_request(refresh_token=None):
    req = MagicMock()
    req.cookies = {}
    if refresh_token is not None:
        req.cookies["refreshToken"] = refresh_token
    return req


def _encode(payload):
    return jwt.encode(payload, SECRET, algorithm="HS256")


@pytest.fixture(autouse=True)
def env_secret(monkeypatch):
    monkeypatch.setenv("JWT_REFRESH_SECRET", SECRET)


class TestCookieVerify:
    def test_no_cookie_returns_none(self):
        from auth_deps import make_cookie_verifier
        users = MagicMock()
        verify, _ = make_cookie_verifier(users)
        assert verify(_make_request()) is None

    def test_payload_email_direct(self):
        from auth_deps import make_cookie_verifier
        users = MagicMock()
        verify, _ = make_cookie_verifier(users)
        token = _encode({"email": "alice@example.com"})
        assert verify(_make_request(token)) == "alice@example.com"
        users.find_one.assert_not_called()

    def test_payload_email_lowercase(self):
        from auth_deps import make_cookie_verifier
        users = MagicMock()
        verify, _ = make_cookie_verifier(users)
        token = _encode({"email": "BOB@Example.COM"})
        assert verify(_make_request(token)) == "bob@example.com"

    def test_payload_id_falls_to_users_lookup(self):
        from auth_deps import make_cookie_verifier
        oid = ObjectId()
        users = MagicMock()
        users.find_one.return_value = {"email": "carol@example.com"}
        verify, _ = make_cookie_verifier(users)
        token = _encode({"id": str(oid)})
        assert verify(_make_request(token)) == "carol@example.com"
        users.find_one.assert_called_once()

    def test_invalid_token_returns_none(self):
        from auth_deps import make_cookie_verifier
        users = MagicMock()
        verify, _ = make_cookie_verifier(users)
        assert verify(_make_request("garbage.token.here")) is None

    def test_no_payload_id_or_email(self):
        from auth_deps import make_cookie_verifier
        users = MagicMock()
        verify, _ = make_cookie_verifier(users)
        token = _encode({"sessionId": "abc"})  # 沒 id/email
        assert verify(_make_request(token)) is None

    def test_unset_secret_returns_none(self, monkeypatch):
        from auth_deps import make_cookie_verifier
        monkeypatch.setenv("JWT_REFRESH_SECRET", "")
        users = MagicMock()
        verify, _ = make_cookie_verifier(users)
        token = _encode({"email": "x@y.com"})
        assert verify(_make_request(token)) is None

    def test_placeholder_secret_returns_none(self, monkeypatch):
        from auth_deps import make_cookie_verifier
        monkeypatch.setenv("JWT_REFRESH_SECRET", "<GENERATE_ME>")
        users = MagicMock()
        verify, _ = make_cookie_verifier(users)
        token = _encode({"email": "x@y.com"})
        assert verify(_make_request(token)) is None


class TestLookupUserEmail:
    def test_lookup_hit(self):
        from auth_deps import make_cookie_verifier
        users = MagicMock()
        users.find_one.return_value = {"email": "Dave@example.com"}
        _, lookup = make_cookie_verifier(users)
        oid = ObjectId()
        assert lookup(str(oid)) == "dave@example.com"

    def test_lookup_user_not_found(self):
        from auth_deps import make_cookie_verifier
        users = MagicMock()
        users.find_one.return_value = None
        _, lookup = make_cookie_verifier(users)
        oid = ObjectId()
        assert lookup(str(oid)) is None

    def test_lookup_invalid_objectid(self):
        from auth_deps import make_cookie_verifier
        users = MagicMock()
        _, lookup = make_cookie_verifier(users)
        assert lookup("not-an-oid") is None
        users.find_one.assert_not_called()

    def test_lookup_caches(self):
        from auth_deps import make_cookie_verifier
        users = MagicMock()
        users.find_one.return_value = {"email": "x@y.com"}
        _, lookup = make_cookie_verifier(users)
        oid = str(ObjectId())
        lookup(oid)
        lookup(oid)
        # 命中 cache · 不會二次 query
        assert users.find_one.call_count == 1

    def test_lookup_evicts_oldest_when_full(self):
        from auth_deps import make_cookie_verifier
        users = MagicMock()
        users.find_one.side_effect = lambda q, p: {"email": f"u{q['_id']}@e.com"}
        _, lookup = make_cookie_verifier(users)
        # 灌 200 個進去
        ids = [str(ObjectId()) for _ in range(201)]
        for i in ids:
            lookup(i)
        # 第 1 個應被 evict · 再 lookup 會重新 find_one
        users.find_one.reset_mock()
        lookup(ids[0])
        assert users.find_one.call_count == 1


class TestMainBackwardCompat:
    def test_main_uses_make_cookie_verifier(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
        src = open(path).read()
        assert "from auth_deps import make_cookie_verifier" in src
        assert "_verify_librechat_cookie, _lookup_user_email_cached = make_cookie_verifier(" in src

    def test_main_no_inline_jwt_decode(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
        src = open(path).read()
        # main 不該有 jwt.decode 直接呼叫
        assert "_jwt.decode(refresh_token" not in src, "JWT decode 應在 auth_deps · 不在 main"

    def test_main_no_inline_user_email_cache(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
        src = open(path).read()
        assert "_USER_EMAIL_CACHE" not in src, "_USER_EMAIL_CACHE 應在 auth_deps closure"

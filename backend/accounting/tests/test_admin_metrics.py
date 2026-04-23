"""
services/admin_metrics.py · unit tests
不依賴 FastAPI / TestClient · 純資料 + mongomock
"""
import pytest
import mongomock
from datetime import datetime, timedelta, timezone
from services import admin_metrics


@pytest.fixture(autouse=True)
def _reset_cache():
    """每 test 前清 _SCHEMA_CACHED · 避免 cache 汙染"""
    admin_metrics.reset_cache()
    yield
    admin_metrics.reset_cache()


@pytest.fixture
def db():
    client = mongomock.MongoClient()
    return client.chengfu_test


@pytest.fixture
def users_col(db):
    return db.users


def test_price_ntd_haiku():
    cost = admin_metrics.price_ntd("claude-haiku-4-5", 1_000_000, 1_000_000, 32.5)
    # input 0.25 + output 1.25 = 1.5 USD × 32.5 = NT$ 48.75
    assert cost == 48.75


def test_price_ntd_unknown_model_fallback_to_sonnet():
    """未知模型用 Sonnet 中位數"""
    cost = admin_metrics.price_ntd("claude-unknown-x", 1_000_000, 1_000_000, 32.5)
    sonnet = admin_metrics.price_ntd("claude-sonnet-4-6", 1_000_000, 1_000_000, 32.5)
    assert cost == sonnet


def test_probe_tx_schema_empty(db):
    s = admin_metrics.probe_tx_schema(db)
    assert s["ok"] is True
    assert "尚無資料" in s["issue"]


def test_probe_tx_schema_ok(db):
    db.transactions.insert_one({
        "rawAmount": {"prompt": 100, "completion": 50},
        "model": "claude-haiku-4-5",
        "user": "user_abc",
        "createdAt": datetime.now(timezone.utc),
    })
    s = admin_metrics.probe_tx_schema(db)
    assert s["ok"] is True
    assert s["issue"] == ""


def test_probe_tx_schema_missing_field(db):
    """若 LibreChat 改 schema 去掉 rawAmount · ok=False"""
    db.transactions.insert_one({
        "amount": 100,  # 新 schema
        "model": "claude-haiku-4-5",
        "user": "x",
        "createdAt": datetime.now(timezone.utc),
    })
    s = admin_metrics.probe_tx_schema(db)
    assert s["ok"] is False
    assert "rawAmount" in s["issue"]


def test_budget_status_no_data(db):
    r = admin_metrics.budget_status(db, monthly_budget_ntd=12000)
    assert r["spent_ntd"] == 0
    assert r["alert_level"] == "ok"
    assert r["pricing_version"] == admin_metrics.PRICE_VERSION


def test_budget_status_with_data(db):
    now = datetime.now(timezone.utc)
    db.transactions.insert_one({
        "rawAmount": {"prompt": 4_000_000, "completion": 2_000_000},
        "model": "claude-sonnet-4-6",
        "user": "x",
        "createdAt": now,
    })
    r = admin_metrics.budget_status(db, monthly_budget_ntd=12000)
    # Sonnet: 4M × 3 + 2M × 15 = 12 + 30 = 42 USD × 32.5 = NT$ 1365
    assert r["spent_ntd"] == 1365
    assert r["alert_level"] == "ok"  # < 80%


def test_budget_status_over_budget(db):
    """超 100% · alert_level = over"""
    now = datetime.now(timezone.utc)
    # Opus: 100M × 15 + 50M × 75 = 1500 + 3750 = 5250 USD × 32.5 = NT$ 170625
    db.transactions.insert_one({
        "rawAmount": {"prompt": 100_000_000, "completion": 50_000_000},
        "model": "claude-opus-4-7",
        "user": "x",
        "createdAt": now,
    })
    r = admin_metrics.budget_status(db, monthly_budget_ntd=12000)
    assert r["alert_level"] == "over"
    assert r["pct"] > 100


def test_quota_check_off_mode(db, users_col):
    r = admin_metrics.quota_check(db, users_col, "a@b.com", mode="off")
    assert r["allowed"] is True


def test_quota_check_no_email_soft_warn_passes(db, users_col):
    """沒帶 email · soft_warn 模式放行 + 警告"""
    r = admin_metrics.quota_check(db, users_col, None, mode="soft_warn")
    assert r["allowed"] is True
    assert "warning" in r


def test_quota_check_no_email_hard_stop_blocks(db, users_col):
    """Codex Round 10.5 黃 5 · 沒帶 email + hard_stop 必須擋
    否則匿名呼叫繞過預算"""
    r = admin_metrics.quota_check(db, users_col, None, mode="hard_stop")
    assert r["allowed"] is False
    assert r.get("fail_safe") is True
    assert "email" in r["reason"].lower() or "重登入" in r["reason"]


def test_quota_check_override_admin(db, users_col):
    """admin 白名單永遠過"""
    r = admin_metrics.quota_check(
        db, users_col, "admin@x.com",
        mode="hard_stop",
        admin_allowlist={"admin@x.com"},
    )
    assert r["allowed"] is True
    assert r.get("override") is True


def test_quota_check_hard_stop_over(db, users_col):
    """超 100% + hard_stop = 擋"""
    uid = users_col.insert_one({"email": "staff@x.com"}).inserted_id
    db.transactions.insert_one({
        "rawAmount": {"prompt": 100_000_000, "completion": 50_000_000},
        "model": "claude-opus-4-7",
        "user": uid,
        "createdAt": datetime.now(timezone.utc),
    })
    r = admin_metrics.quota_check(
        db, users_col, "staff@x.com",
        mode="hard_stop",
        user_soft_cap_ntd=1200.0,
    )
    assert r["allowed"] is False
    assert "本月已用" in r["reason"]


def test_quota_check_soft_warn_over(db, users_col):
    """超 100% + soft_warn = 過 + warning"""
    uid = users_col.insert_one({"email": "staff@x.com"}).inserted_id
    db.transactions.insert_one({
        "rawAmount": {"prompt": 100_000_000, "completion": 50_000_000},
        "model": "claude-opus-4-7",
        "user": uid,
        "createdAt": datetime.now(timezone.utc),
    })
    r = admin_metrics.quota_check(
        db, users_col, "staff@x.com",
        mode="soft_warn",
        user_soft_cap_ntd=1200.0,
    )
    assert r["allowed"] is True
    assert "超預算" in r["warning"]


def test_librechat_contract_includes_fingerprint(db):
    db.transactions.insert_one({
        "rawAmount": {"prompt": 100, "completion": 50},
        "model": "claude-haiku-4-5",
        "user": "x",
        "createdAt": datetime.now(timezone.utc),
    })
    r = admin_metrics.librechat_contract(db)
    assert r["transactions_schema_ok"] is True
    assert r["price_version"] == admin_metrics.PRICE_VERSION
    assert isinstance(r["transactions_fingerprint_last10"], list)
    assert len(r["transactions_fingerprint_last10"]) == 1
    assert r["transactions_fingerprint_last10"][0]["has_rawAmount"] is True


def test_tender_funnel_empty(db):
    r = admin_metrics.tender_funnel(db)
    assert r["funnel"]["new_discovered"] == 0
    assert r["funnel"]["won"] == 0


# ============================================================
# Round 9 Q1 · fail-safe 策略(資料來源異常時)
# ============================================================
def test_user_month_spend_returns_dict_with_ok(db, users_col):
    """正常路徑回 ok=True · spent_ntd 數字"""
    r = admin_metrics.user_month_spend_ntd(db, users_col, "x@y.com")
    assert isinstance(r, dict)
    assert r["ok"] is True
    assert r["spent_ntd"] == 0.0
    assert r["user_found"] is False  # email 對不到 user · 這是合理 0


def test_user_month_spend_data_source_error_returns_ok_false(users_col):
    """傳壞掉的 db (例如 None.transactions) · ok=False"""
    class BrokenDB:
        @property
        def transactions(self):
            raise ConnectionError("Mongo down")
    r = admin_metrics.user_month_spend_ntd(BrokenDB(), users_col, "x@y.com")
    # users_col.find_one("x@y.com") 會回 None · 走 user_not_in_librechat
    # 改用 broken users_col 才會觸發 exception
    class BrokenUsers:
        def find_one(self, *a, **kw):
            raise ConnectionError("users col down")
    r = admin_metrics.user_month_spend_ntd(BrokenDB(), BrokenUsers(), "x@y.com")
    assert r["ok"] is False
    assert "data_source_error" in r["reason"]


def test_quota_hard_stop_fail_safe_blocks_normal_user(db, users_col):
    """資料來源異常 + hard_stop · 一般同仁被擋 · 跳找 Champion"""
    class BrokenDB:
        @property
        def transactions(self):
            raise ConnectionError("Mongo down")
    class BrokenUsers:
        def find_one(self, *a, **kw):
            raise ConnectionError("users col down")
    r = admin_metrics.quota_check(
        BrokenDB(), BrokenUsers(), "staff@x.com",
        mode="hard_stop", user_soft_cap_ntd=1200.0,
    )
    assert r["allowed"] is False
    assert r.get("fail_safe") is True
    assert "資料來源" in r["reason"]
    assert "Champion" in r["reason"]


def test_quota_hard_stop_fail_safe_admin_passes(db, users_col):
    """資料來源異常 + admin · 仍放行(維運不能斷)"""
    class BrokenDB:
        @property
        def transactions(self):
            raise ConnectionError("Mongo down")
    class BrokenUsers:
        def find_one(self, *a, **kw):
            raise ConnectionError("users col down")
    r = admin_metrics.quota_check(
        BrokenDB(), BrokenUsers(), "admin@chengfu.local",
        mode="hard_stop",
        admin_allowlist={"admin@chengfu.local"},
    )
    assert r["allowed"] is True
    assert r.get("override") is True


def test_quota_soft_warn_fail_safe_passes_with_warning(db, users_col):
    """資料來源異常 + soft_warn · 放行 + 警告(維持原邏輯)"""
    class BrokenUsers:
        def find_one(self, *a, **kw):
            raise ConnectionError("Mongo flaky")
    r = admin_metrics.quota_check(
        db, BrokenUsers(), "staff@x.com",
        mode="soft_warn", user_soft_cap_ntd=1200.0,
    )
    assert r["allowed"] is True
    assert "warning" in r
    assert "資料來源" in r["warning"]

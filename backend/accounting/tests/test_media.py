"""
Feature #6 · 媒體 CRM tests(R14 FEATURE-PROPOSALS v1.2)
"""
import os
import sys
import pytest
from fastapi.testclient import TestClient
import mongomock
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


ADMIN = {"X-User-Email": "sterio068@gmail.com"}
USER = {"X-User-Email": "pm@chengfu.local"}


@pytest.fixture
def client():
    with patch("pymongo.MongoClient", mongomock.MongoClient):
        import importlib
        import main
        importlib.reload(main)
        c = TestClient(main.app)
        c.get("/healthz")
        yield c


def test_create_contact_admin_only(client):
    """非 admin 不能建記者 · 403"""
    r = client.post(
        "/media/contacts",
        json={"name": "張記者", "outlet": "聯合報", "beats": ["環保"], "email": "zhang@udn.com"},
        headers=USER,
    )
    assert r.status_code == 403


def test_create_and_list_contact(client):
    r = client.post(
        "/media/contacts",
        json={"name": "李記者", "outlet": "商周", "beats": ["產業", "科技"],
              "email": "li@businessweekly.com.tw"},
        headers=ADMIN,
    )
    assert r.status_code == 200
    contact_id = r.json()["id"]

    # list
    r = client.get("/media/contacts", headers=USER)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(c["email"] == "li@businessweekly.com.tw" for c in items)


def test_duplicate_email_conflict(client):
    client.post("/media/contacts",
        json={"name": "A", "outlet": "X", "email": "dup@media.com"},
        headers=ADMIN)
    r = client.post("/media/contacts",
        json={"name": "B", "outlet": "Y", "email": "dup@media.com"},
        headers=ADMIN)
    assert r.status_code == 409


def test_phone_hidden_from_non_admin(client):
    """R14#2 PDPA · 非 admin 看不到 phone"""
    client.post("/media/contacts",
        json={"name": "C", "outlet": "Z", "email": "c@m.com", "phone": "0912-345-678"},
        headers=ADMIN)

    # admin 看得到
    r = client.get("/media/contacts", headers=ADMIN)
    admin_items = r.json()["items"]
    assert any(c.get("phone") == "0912-345-678" for c in admin_items)

    # 同事看不到(phone 被 projection 濾掉)
    r = client.get("/media/contacts", headers=USER)
    user_items = r.json()["items"]
    for c in user_items:
        assert "phone" not in c or c.get("phone") is None


def test_recommend_jaccard_match(client):
    """推薦:topic=[環保] · 有 beats=[環保] 的應上榜"""
    import main
    main.db.media_contacts.insert_many([
        {"name": "環保記者", "outlet": "綠報", "beats": ["環保", "減塑"],
         "email": "env@green.com", "is_active": True,
         "accepted_count": 5, "pitched_count": 8, "accepted_topics": ["環保"]},
        {"name": "科技記者", "outlet": "3C", "beats": ["科技", "AI"],
         "email": "tech@3c.com", "is_active": True,
         "accepted_count": 2, "pitched_count": 5, "accepted_topics": []},
        {"name": "inactive", "outlet": "X", "beats": ["環保"],
         "email": "ina@x.com", "is_active": False,
         "accepted_count": 0, "pitched_count": 0, "accepted_topics": []},
    ])

    # R21#3 · recommend admin-only(email PDPA L02)
    r = client.post("/media/recommend",
        json={"topic": ["環保"], "limit": 10},
        headers=ADMIN)
    assert r.status_code == 200
    items = r.json()["items"]
    # 環保記者應上榜(first · 分數高)
    assert len(items) >= 1
    assert items[0]["name"] == "環保記者"
    assert items[0]["score"] > 0
    # inactive 不應上榜
    assert not any(c["name"] == "inactive" for c in items)
    # 科技記者沒 match 應不上榜(jaccard=0)
    assert not any(c["name"] == "科技記者" for c in items)


def test_record_pitch_increments(client):
    """發稿紀錄 · pitched_count 遞增 · accepted 記 accepted_count"""
    import main
    cid = main.db.media_contacts.insert_one({
        "name": "test", "outlet": "X", "email": "p@x.com",
        "is_active": True, "pitched_count": 0, "accepted_count": 0,
        "accepted_topics": [],
    }).inserted_id

    r = client.post("/media/pitches",
        json={"contact_id": str(cid), "topic": "環保", "accepted": True},
        headers=USER)
    assert r.status_code == 200

    updated = main.db.media_contacts.find_one({"_id": cid})
    assert updated["pitched_count"] == 1
    assert updated["accepted_count"] == 1
    assert "環保" in updated["accepted_topics"]


def test_csv_import(client):
    """CSV 匯入 · upsert by email"""
    csv = """name,outlet,beats,email,phone,notes
張三,蘋果日報,政府|環保,zhang@apple.com,0911111,核心記者
李四,商業周刊,產業,li@biz.com,,重點
"""
    r = client.post("/media/contacts/import-csv",
        files={"file": ("media.csv", csv.encode("utf-8"), "text/csv")},
        headers=ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 2
    assert body["updated"] == 0

    # 驗 DB
    import main
    doc = main.db.media_contacts.find_one({"email": "zhang@apple.com"})
    assert doc is not None
    assert doc["beats"] == ["政府", "環保"]

    # 再匯入同 email · 應 update 不 duplicate
    r = client.post("/media/contacts/import-csv",
        files={"file": ("media.csv", csv.encode("utf-8"), "text/csv")},
        headers=ADMIN)
    body = r.json()
    assert body["imported"] == 0
    assert body["updated"] == 2


def test_csv_reject_bad_email(client):
    csv = """name,outlet,email
bad_row,X,not-an-email
good_row,X,good@m.com
"""
    r = client.post("/media/contacts/import-csv",
        files={"file": ("bad.csv", csv.encode("utf-8"), "text/csv")},
        headers=ADMIN)
    body = r.json()
    assert body["imported"] == 1  # good only
    assert len(body["errors"]) == 1
    assert "bad_row" not in str(body["errors"])  # errors 只列 row index / email


def test_deactivate_contact(client):
    """軟刪 · is_active=False · 不真 delete"""
    import main
    cid = main.db.media_contacts.insert_one({
        "name": "del", "outlet": "X", "email": "del@x.com",
        "is_active": True,
    }).inserted_id

    r = client.delete(f"/media/contacts/{cid}", headers=ADMIN)
    assert r.status_code == 200

    # 仍在 DB
    doc = main.db.media_contacts.find_one({"_id": cid})
    assert doc is not None
    assert doc["is_active"] is False

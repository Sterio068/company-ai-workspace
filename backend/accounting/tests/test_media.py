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


# ============================================================
# B3(v1.3)· /media/contacts/export.csv
# ============================================================
def test_export_csv_admin_only(client):
    """B3 · 匿名禁用(含 PII email/phone)"""
    r = client.get("/media/contacts/export.csv", headers={"X-User-Email": ""})
    assert r.status_code == 403


def test_export_csv_basic(client):
    """B3 · CSV 含全欄位 + UTF-8 BOM 中文不亂碼"""
    import main
    main.db.media_contacts.insert_one({
        "name": "張小編", "outlet": "中央社", "email": "zhang@cna.tw",
        "beats": ["環保", "政府"], "phone": "0912345678",
        "is_active": True,
    })
    r = client.get("/media/contacts/export.csv", headers=ADMIN)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    body = r.text
    assert body.startswith("\ufeff"), "必含 UTF-8 BOM 給 Excel"
    assert "name,outlet,beats" in body
    assert "張小編" in body
    assert "中央社" in body
    assert "環保;政府" in body  # beats 用 ; 分隔
    assert "zhang@cna.tw" in body


def test_export_csv_injection_defense(client):
    """B3 · =1+1 / @evil / +cmd 開頭加 ' 前綴 · 防 Excel 公式注入"""
    import main
    main.db.media_contacts.insert_one({
        "name": "=cmd|bad", "outlet": "+attack", "email": "@evil@x.com",
        "beats": ["-formula"], "is_active": True,
    })
    r = client.get("/media/contacts/export.csv", headers=ADMIN)
    body = r.text
    # 找到那行
    line = next(ln for ln in body.split("\r\n") if "cmd" in ln)
    # 必有 ' prefix · csv.writer 會 quote 含逗號或引號的欄位
    assert "'=cmd|bad" in line, "= 開頭必加 ' 前綴防注入"
    assert "'+attack" in line
    assert "'@evil@x.com" in line
    assert "'-formula" in line


def test_export_csv_excludes_inactive_by_default(client):
    """B3 · is_active=False 軟刪預設排除 · ?include_inactive=true 才含"""
    import main
    main.db.media_contacts.insert_one({
        "name": "active1", "outlet": "X", "email": "a1@x.com",
        "is_active": True,
    })
    main.db.media_contacts.insert_one({
        "name": "deleted1", "outlet": "X", "email": "d1@x.com",
        "is_active": False,
    })
    r = client.get("/media/contacts/export.csv", headers=ADMIN)
    assert "active1" in r.text
    assert "deleted1" not in r.text
    # include_inactive=true
    r2 = client.get("/media/contacts/export.csv?include_inactive=true", headers=ADMIN)
    assert "active1" in r2.text
    assert "deleted1" in r2.text

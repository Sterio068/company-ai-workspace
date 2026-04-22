"""Feature #7 · 場勘 PWA tests"""
import os
import sys
import pytest
from fastapi.testclient import TestClient
import mongomock
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


# Fake JPEG magic bytes(前 4 byte)+ padding
FAKE_JPG = b"\xff\xd8\xff\xe0" + b"x" * 2048


def test_survey_requires_image(client):
    r = client.post("/site-survey", data={"project_id": "x"},
                    headers=USER)
    # FastAPI 驗 File(...) 缺會 422
    assert r.status_code in (400, 422)


def test_survey_rejects_wrong_mime(client):
    r = client.post("/site-survey",
        files=[("images", ("f.txt", b"not image", "text/plain"))],
        headers=USER)
    assert r.status_code == 400


def test_survey_rejects_heic(client):
    """iPhone HEIC 不支援 Haiku Vision"""
    r = client.post("/site-survey",
        files=[("images", ("f.heic", FAKE_JPG, "image/heic"))],
        headers=USER)
    assert r.status_code == 400


def test_survey_rejects_too_many(client):
    files = [("images", (f"f{i}.jpg", FAKE_JPG, "image/jpeg")) for i in range(6)]
    r = client.post("/site-survey", files=files, headers=USER)
    assert r.status_code == 400


def test_survey_create_success_with_gps(client):
    """接受正常 JPG · 回 survey_id + GPS 存進 location.gps"""
    r = client.post("/site-survey",
        files=[("images", ("f.jpg", FAKE_JPG, "image/jpeg"))],
        data={"gps_lat": "25.0330", "gps_lng": "121.5654",
              "gps_accuracy": "10", "address_hint": "台北 101"},
        headers=USER)
    assert r.status_code == 200
    body = r.json()
    assert "survey_id" in body
    assert body["image_count"] == 1

    # 驗 DB
    import main
    doc = main.db.site_surveys.find_one({"owner": "pm@chengfu.local"})
    assert doc is not None
    assert doc["location"]["gps"]["lat"] == 25.0330
    assert doc["location"]["address_hint"] == "台北 101"


def test_survey_get_not_owner_403(client):
    import main
    from datetime import datetime
    sid = main.db.site_surveys.insert_one({
        "owner": "alice@chengfu.local",
        "status": "done",
        "created_at": datetime.utcnow(),
    }).inserted_id
    r = client.get(f"/site-survey/{sid}",
        headers={"X-User-Email": "bob@chengfu.local"})
    assert r.status_code == 403


def test_survey_list_owner_filter(client):
    import main
    from datetime import datetime
    main.db.site_surveys.insert_many([
        {"owner": "c@x.com", "status": "done", "image_count": 2,
         "created_at": datetime.utcnow(),
         "structured": {"venue": {"type": "室外"}, "issues": ["入口窄"]}},
        {"owner": "d@x.com", "status": "done", "image_count": 3,
         "created_at": datetime.utcnow()},
    ])
    r = client.get("/site-survey", headers={"X-User-Email": "c@x.com"})
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["venue_type"] == "室外"
    assert items[0]["issues_count"] == 1


def test_push_to_handoff(client):
    import main
    from datetime import datetime
    proj_id = main.projects_col.insert_one({
        "name": "場勘測試",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }).inserted_id

    sid = main.db.site_surveys.insert_one({
        "owner": "pm@chengfu.local",
        "project_id": str(proj_id),
        "status": "done",
        "structured": {
            "venue": {"type": "室內", "size_estimate": "50 坪"},
            "entrances": ["主入口"],
            "toilets_count": 3,
            "issues": ["入口有高差"],
        },
        "created_at": datetime.utcnow(),
    }).inserted_id

    r = client.post(f"/site-survey/{sid}/push-to-handoff", headers=USER)
    assert r.status_code == 200
    assert r.json()["pushed"] is True
    assert r.json()["issues_count"] == 1

    proj = main.projects_col.find_one({"_id": proj_id})
    assert proj["handoff"]["constraints"] == ["入口有高差"]
    assert "室內" in proj["handoff"]["asset_refs"][0]["ref"]

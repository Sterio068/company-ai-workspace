"""Feature #5 · 社群排程 tests"""
import os
import sys
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
import mongomock
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

USER = {"X-User-Email": "pm@chengfu.local"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ECC_INTERNAL_TOKEN", "test-internal-token")
    with patch("pymongo.MongoClient", mongomock.MongoClient):
        import importlib
        import main
        importlib.reload(main)
        c = TestClient(main.app)
        c.get("/healthz")
        yield c


def test_create_post_requires_user(client):
    r = client.post("/social/posts", json={
        "platform": "facebook", "content": "測試",
        "schedule_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    })
    assert r.status_code == 403


def test_create_and_list(client):
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    r = client.post("/social/posts",
        json={"platform": "facebook", "content": "中秋活動預告 · 下週四",
              "schedule_at": future},
        headers=USER)
    assert r.status_code == 200
    pid = r.json()["post_id"]

    r = client.get("/social/posts", headers=USER)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(p["_id"] == pid for p in items)


def test_ig_requires_image(client):
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    r = client.post("/social/posts",
        json={"platform": "instagram", "content": "IG 測試沒圖",
              "schedule_at": future},
        headers=USER)
    assert r.status_code == 400


def test_past_schedule_rejected(client):
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    r = client.post("/social/posts",
        json={"platform": "facebook", "content": "test", "schedule_at": past},
        headers=USER)
    assert r.status_code == 400


def test_publish_now_mock(client):
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    r = client.post("/social/posts",
        json={"platform": "linkedin", "content": "立刻發",
              "schedule_at": future},
        headers=USER)
    pid = r.json()["post_id"]

    r = client.post(f"/social/posts/{pid}/publish-now", headers=USER)
    assert r.status_code == 200
    body = r.json()
    assert body.get("published") is True
    assert body["post_id"].startswith("mock-li-")  # provider 回的 post_id(mock-li-xxx)


def test_publish_now_fail_retry(client):
    """content 含 fail_test · mock 丟 PublishError · attempts 遞增"""
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    r = client.post("/social/posts",
        json={"platform": "facebook", "content": "發文內含 fail_test 測試失敗",
              "schedule_at": future},
        headers=USER)
    pid = r.json()["post_id"]

    r = client.post(f"/social/posts/{pid}/publish-now", headers=USER)
    body = r.json()
    assert body["published"] is False
    assert body["attempts"] == 1
    assert body["status"] == "queued"  # 還沒到 3 次

    # 再跑 2 次 · attempts=3 → failed
    r = client.post(f"/social/posts/{pid}/publish-now", headers=USER)
    r = client.post(f"/social/posts/{pid}/publish-now", headers=USER)
    body = r.json()
    assert body["attempts"] == 3
    assert body["status"] == "failed"


def test_delete_published_409(client):
    """published 不能 cancel"""
    import main
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    r = client.post("/social/posts",
        json={"platform": "facebook", "content": "已發", "schedule_at": future},
        headers=USER)
    pid = r.json()["post_id"]
    # 手動標 published
    main.db.scheduled_posts.update_one(
        {"_id": __import__("bson").ObjectId(pid)},
        {"$set": {"status": "published"}},
    )
    r = client.delete(f"/social/posts/{pid}", headers=USER)
    assert r.status_code == 409


def test_run_queue_requires_internal_token(client):
    """無 internal token → 403"""
    r = client.post("/admin/social/run-queue")
    assert r.status_code == 403

    r = client.post("/admin/social/run-queue",
                    headers={"X-Internal-Token": "wrong"})
    assert r.status_code == 403


def test_run_queue_dispatches(client):
    """set 1 筆 schedule_at=now-1h · internal token 呼 · 應 dispatch"""
    import main
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    main.db.scheduled_posts.insert_one({
        "author": "pm@chengfu.local",
        "platform": "linkedin",
        "content": "排程過去的",
        "schedule_at": past,
        "status": "queued",
        "attempts": 0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    r = client.post("/admin/social/run-queue",
                    headers={"X-Internal-Token": "test-internal-token"})
    assert r.status_code == 200
    body = r.json()
    assert body["dispatched"] >= 1

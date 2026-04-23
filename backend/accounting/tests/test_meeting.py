"""
Feature #1 · 會議速記 tests(R14 FEATURE-PROPOSALS v1.2)

- test_transcribe_upload_success · mock Whisper + Haiku · 驗 JSON 結構化
- test_transcribe_rejects_oversized · > 25MB 回 413
- test_transcribe_rejects_wrong_mime · .txt 回 400
- test_get_meeting_not_owner_403 · 別人 id 拒絕
- test_push_to_handoff · action_items 進 project.handoff
"""
import os
import sys
import pytest
from fastapi.testclient import TestClient
import mongomock
from unittest.mock import patch, MagicMock

# 確保可 import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def client():
    with patch("pymongo.MongoClient", mongomock.MongoClient):
        import importlib
        import main
        importlib.reload(main)
        c = TestClient(main.app)
        c.get("/healthz")  # trigger startup
        yield c


def test_transcribe_rejects_wrong_mime(client):
    """非 audio mime · 400"""
    r = client.post(
        "/memory/transcribe",
        files={"audio": ("fake.txt", b"not audio", "text/plain")},
        headers={"X-User-Email": "pm@chengfu.local"},
    )
    assert r.status_code == 400


def test_transcribe_rejects_tiny(client):
    """< 1KB · 400(空檔)"""
    r = client.post(
        "/memory/transcribe",
        files={"audio": ("tiny.mp3", b"x", "audio/mpeg")},
        headers={"X-User-Email": "pm@chengfu.local"},
    )
    assert r.status_code == 400


def test_transcribe_rejects_oversized(client):
    """> 25MB · 413"""
    fake_big = b"x" * (26 * 1024 * 1024)
    r = client.post(
        "/memory/transcribe",
        files={"audio": ("big.mp3", fake_big, "audio/mpeg")},
        headers={"X-User-Email": "pm@chengfu.local"},
    )
    assert r.status_code == 413


def test_transcribe_success_returns_meeting_id(client):
    """有效 mime + size · 回 meeting_id + status=transcribing · DB 有紀錄"""
    fake_audio = b"ID3" + b"\x00" * 2048  # 2KB · MP3 header-like
    r = client.post(
        "/memory/transcribe",
        files={"audio": ("test.mp3", fake_audio, "audio/mpeg")},
        data={"project_id": "proj_abc"},
        headers={"X-User-Email": "pm@chengfu.local"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "meeting_id" in body
    assert body["status"] == "transcribing"

    # 驗 DB
    import main
    doc = main.db.meetings.find_one({"_id__from_str": body["meeting_id"]}) or \
          main.db.meetings.find_one({"owner": "pm@chengfu.local"})
    assert doc is not None
    assert doc["audio_size"] > 0
    assert doc["status"] in ("transcribing", "done", "failed")  # background 可能已動
    # PDPA · _tmp_audio_path 存在(還沒清)
    assert "_tmp_audio_path" in doc or doc.get("status") in ("done", "failed")


def test_get_meeting_not_owner_403(client):
    """別人 email 查不到自己會議 · 403"""
    import main
    from bson import ObjectId
    from datetime import datetime, timezone
    # seed 一筆 meeting 給 alice
    mid = main.db.meetings.insert_one({
        "owner": "alice@chengfu.local",
        "status": "done",
        "structured": {"title": "alice 的會議"},
        "created_at": datetime.now(timezone.utc),
    }).inserted_id

    # bob 查
    r = client.get(
        f"/memory/meetings/{mid}",
        headers={"X-User-Email": "bob@chengfu.local"},
    )
    assert r.status_code == 403


def test_list_meetings_owner_filter(client):
    """list · 只回自己的"""
    import main
    from datetime import datetime, timezone
    main.db.meetings.insert_many([
        {"owner": "c@chengfu.local", "status": "done",
         "structured": {"title": "c 會 1"}, "created_at": datetime.now(timezone.utc)},
        {"owner": "d@chengfu.local", "status": "done",
         "structured": {"title": "d 會 1"}, "created_at": datetime.now(timezone.utc)},
    ])
    r = client.get("/memory/meetings", headers={"X-User-Email": "c@chengfu.local"})
    assert r.status_code == 200
    body = r.json()
    titles = [m["title"] for m in body["items"]]
    assert "c 會 1" in titles
    assert "d 會 1" not in titles


def test_push_to_handoff(client):
    """done 狀態的會議 · action_items 推到 project.handoff.next_actions"""
    import main
    from bson import ObjectId
    from datetime import datetime, timezone

    # Seed project
    proj_id = main.projects_col.insert_one({
        "name": "push-handoff-test",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }).inserted_id

    mid = main.db.meetings.insert_one({
        "owner": "pm@chengfu.local",
        "project_id": str(proj_id),
        "status": "done",
        "structured": {
            "title": "專案會議",
            "action_items": [
                {"who": "Alice", "what": "寫提案", "due": "4/25"},
                {"who": "Bob", "what": "聯絡廠商"},
            ],
        },
        "created_at": datetime.now(timezone.utc),
    }).inserted_id

    r = client.post(
        f"/memory/meetings/{mid}/push-to-handoff",
        headers={"X-User-Email": "pm@chengfu.local"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["pushed"] is True
    assert body["next_actions_count"] == 2

    # 驗 project handoff
    proj = main.projects_col.find_one({"_id": proj_id})
    assert proj is not None
    actions = proj.get("handoff", {}).get("next_actions", [])
    assert len(actions) == 2
    assert "寫提案" in actions[0]
    assert "聯絡廠商" in actions[1]


def test_push_to_handoff_not_done_400(client):
    """status != done 拒絕"""
    import main
    from datetime import datetime, timezone
    mid = main.db.meetings.insert_one({
        "owner": "pm@chengfu.local",
        "status": "transcribing",
        "created_at": datetime.now(timezone.utc),
    }).inserted_id

    r = client.post(
        f"/memory/meetings/{mid}/push-to-handoff",
        headers={"X-User-Email": "pm@chengfu.local"},
    )
    assert r.status_code == 400

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
    from datetime import datetime, timezone
    sid = main.db.site_surveys.insert_one({
        "owner": "alice@chengfu.local",
        "status": "done",
        "created_at": datetime.now(timezone.utc),
    }).inserted_id
    r = client.get(f"/site-survey/{sid}",
        headers={"X-User-Email": "bob@chengfu.local"})
    assert r.status_code == 403


def test_survey_list_owner_filter(client):
    import main
    from datetime import datetime, timezone
    main.db.site_surveys.insert_many([
        {"owner": "c@x.com", "status": "done", "image_count": 2,
         "created_at": datetime.now(timezone.utc),
         "structured": {"venue": {"type": "室外"}, "issues": ["入口窄"]}},
        {"owner": "d@x.com", "status": "done", "image_count": 3,
         "created_at": datetime.now(timezone.utc)},
    ])
    r = client.get("/site-survey", headers={"X-User-Email": "c@x.com"})
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["venue_type"] == "室外"
    assert items[0]["issues_count"] == 1


def test_push_to_handoff(client):
    import main
    from datetime import datetime, timezone
    proj_id = main.projects_col.insert_one({
        "name": "場勘測試",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
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
        "created_at": datetime.now(timezone.utc),
    }).inserted_id

    r = client.post(f"/site-survey/{sid}/push-to-handoff", headers=USER)
    assert r.status_code == 200
    assert r.json()["pushed"] is True
    assert r.json()["issues_count"] == 1

    proj = main.projects_col.find_one({"_id": proj_id})
    # R23#4 · 獨立欄位不覆寫人工 constraints
    assert proj["handoff"]["site_issues"] == ["入口有高差"]
    # asset_refs 用 $push · append(原 project 沒 handoff · 從空 list 開始)
    refs = proj["handoff"]["asset_refs"]
    assert len(refs) == 1
    assert "室內" in refs[0]["ref"]


# ============================================================
# B4(v1.3)· audio_note · MediaRecorder + Whisper STT
# ============================================================
def test_audio_rejects_wrong_mime(client):
    """B4 · 上傳 text/plain · 應 400(白名單擋)"""
    import main
    sid = main.db.site_surveys.insert_one({
        "owner": "pm@chengfu.local", "status": "done",
        "audio_notes": [],
    }).inserted_id
    r = client.post(
        f"/site-survey/{sid}/audio",
        files={"audio": ("fake.txt", b"x" * 2048, "text/plain")},
        headers=USER,
    )
    assert r.status_code == 400
    assert "mime 不接受" in r.json()["detail"]


def test_audio_rejects_too_small(client):
    """B4 · audio < 1KB · 八成空檔 · 400"""
    import main
    sid = main.db.site_surveys.insert_one({
        "owner": "pm@chengfu.local", "status": "done", "audio_notes": [],
    }).inserted_id
    r = client.post(
        f"/site-survey/{sid}/audio",
        files={"audio": ("tiny.webm", b"x" * 100, "audio/webm")},
        headers=USER,
    )
    assert r.status_code == 400


def test_audio_rejects_oversized(client):
    """B4 · > 5 MB · 413"""
    import main
    sid = main.db.site_surveys.insert_one({
        "owner": "pm@chengfu.local", "status": "done", "audio_notes": [],
    }).inserted_id
    big = b"x" * (6 * 1024 * 1024)
    r = client.post(
        f"/site-survey/{sid}/audio",
        files={"audio": ("big.webm", big, "audio/webm")},
        headers=USER,
    )
    assert r.status_code == 413


def test_audio_rejects_not_owner(client):
    """B4 · 別人 owner 的 survey · 403"""
    import main
    sid = main.db.site_surveys.insert_one({
        "owner": "alice@chengfu.local", "status": "done", "audio_notes": [],
    }).inserted_id
    r = client.post(
        f"/site-survey/{sid}/audio",
        files={"audio": ("a.webm", b"x" * 2048, "audio/webm")},
        headers=USER,  # pm@chengfu.local
    )
    assert r.status_code == 403


def test_audio_caps_at_max_per_survey(client):
    """B4 · 已有 10 個 audio note · 第 11 個 429"""
    import main
    sid = main.db.site_surveys.insert_one({
        "owner": "pm@chengfu.local", "status": "done",
        "audio_notes": [{"_id": __import__("bson").ObjectId(), "transcript": f"n{i}"}
                         for i in range(10)],
    }).inserted_id
    r = client.post(
        f"/site-survey/{sid}/audio",
        files={"audio": ("a.webm", b"x" * 2048, "audio/webm")},
        headers=USER,
    )
    assert r.status_code == 429


def test_audio_success_processing(client, monkeypatch):
    """B4 · 成功上傳 · 回 processing · 背景跑 STT
    mock Whisper · 驗 audio_notes[].transcript 寫入
    本機沒裝 openai 時 skip(prod requirements.txt 含)"""
    openai = pytest.importorskip("openai")
    import main

    # mock Whisper · 同 test_meeting pattern
    from unittest.mock import MagicMock
    fake_resp = MagicMock()
    fake_resp.text = "這裡有 3 根柱子擋光線"

    class FakeClient:
        def __init__(self, *a, **kw): pass
        @property
        def audio(self):
            class _A:
                @property
                def transcriptions(self_):
                    class _T:
                        def create(__, **kw): return fake_resp
                    return _T()
            return _A()

    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    monkeypatch.setenv("OPENAI_API_KEY", "fake")

    sid = main.db.site_surveys.insert_one({
        "owner": "pm@chengfu.local", "status": "done", "audio_notes": [],
    }).inserted_id
    r = client.post(
        f"/site-survey/{sid}/audio",
        data={"duration_sec": "12.5"},
        files={"audio": ("a.webm", b"x" * 2048, "audio/webm")},
        headers=USER,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "processing"

    # 背景 task 應 push 到 audio_notes
    import time
    for _ in range(20):
        doc = main.db.site_surveys.find_one({"_id": sid})
        notes = doc.get("audio_notes", [])
        if notes and notes[0].get("status") == "done":
            break
        time.sleep(0.1)
    assert notes[0]["status"] == "done"
    assert notes[0]["transcript"] == "這裡有 3 根柱子擋光線"
    assert notes[0]["duration_sec"] == 12.5

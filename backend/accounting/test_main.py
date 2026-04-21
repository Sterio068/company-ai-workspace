"""
承富會計 + 統一後端 · 基礎測試
==================================
執行:
  cd backend/accounting
  pip install pytest mongomock fastapi httpx
  pytest test_main.py -v

或在 docker 環境:
  docker exec chengfu-accounting pytest /app/test_main.py -v
"""
import os
import pytest
from fastapi.testclient import TestClient
import mongomock
from unittest.mock import patch

# 用 mongomock 隔離真實 MongoDB(這個測試可在任何環境跑)
@pytest.fixture(scope="module")
def client():
    with patch("pymongo.MongoClient", mongomock.MongoClient):
        import importlib
        import main
        importlib.reload(main)
        c = TestClient(main.app)
        # 觸發 startup
        c.get("/healthz")
        yield c


# ============================================================
# A · 會計核心
# ============================================================
def test_health(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_seed_accounts(client):
    r = client.post("/accounts/seed")
    assert r.status_code == 200
    assert r.json()["total"] >= 20  # 台灣預設 25 個科目


def test_list_accounts(client):
    client.post("/accounts/seed")
    r = client.get("/accounts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 20
    # 必含常用科目
    codes = [a["code"] for a in data]
    assert "1102" in codes  # 銀行存款
    assert "4111" in codes  # 服務收入
    assert "5101" in codes  # 外包支出


def test_create_transaction(client):
    client.post("/accounts/seed")
    r = client.post("/transactions", json={
        "date": "2026-04-19",
        "memo": "測試:收環保局案期中款",
        "debit_account": "1102",
        "credit_account": "4111",
        "amount": 300000,
        "project_id": "proj_test",
        "customer": "環保局",
    })
    assert r.status_code == 200
    assert "id" in r.json()


def test_create_invoice(client):
    r = client.post("/invoices", json={
        "date": "2026-04-19",
        "customer": "環保局",
        "items": [
            {"description": "期中服務費", "quantity": 1, "unit_price": 300000}
        ],
        "tax_included": False,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["invoice_no"].startswith("INV-26-")
    assert body["total"] == 315000  # 300000 × 1.05


def test_create_quote(client):
    r = client.post("/quotes", json={
        "date": "2026-04-19",
        "customer": "文化局",
        "items": [
            {"description": "活動策劃", "quantity": 1, "unit_price": 500000}
        ],
        "valid_until": "2026-05-19",
    })
    assert r.status_code == 200
    assert r.json()["quote_no"].startswith("Q-26-")


def test_pnl_report(client):
    r = client.get("/reports/pnl?date_from=2026-04-01&date_to=2026-04-30")
    assert r.status_code == 200
    body = r.json()
    assert "total_income" in body
    assert "total_expense" in body
    assert "net_profit" in body


# ============================================================
# B · 專案管理(取代 localStorage)
# ============================================================
def test_create_project(client):
    r = client.post("/projects", json={
        "name": "2026 環保局海洋案",
        "client": "環境部環境管理署",
        "budget": 3800000,
        "deadline": "2026-10-31",
        "status": "active",
    })
    assert r.status_code == 200


def test_list_projects(client):
    r = client.get("/projects")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_handoff_card_roundtrip(client):
    """B2 · Handoff 4 格卡 · 存 + 取 + 預設值"""
    # 建一個 project
    r = client.post("/projects", json={"name": "handoff test proj"})
    pid = r.json()["id"]

    # 初始 handoff 應該是空
    r = client.get(f"/projects/{pid}/handoff")
    assert r.status_code == 200
    body = r.json()
    assert body["project_name"] == "handoff test proj"
    assert body["handoff"] == {} or body["handoff"].get("goal", "") == ""

    # 存卡
    card = {
        "goal": "中秋節社群活動主視覺",
        "constraints": ["品牌色橘黃", "預算 5 萬", "3 天內"],
        "asset_refs": [
            {"type": "nas", "label": "客戶舊包裝", "ref": "/Volumes/NAS/x/"},
            {"type": "url", "label": "競品參考", "ref": "https://example.com"},
        ],
        "next_actions": ["設計師產 3 方向 · 週四前", "PM 排與客戶提案會議"],
    }
    r = client.put(
        f"/projects/{pid}/handoff",
        json=card,
        headers={"X-User-Email": "pm@chengfu.local"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # 取回來必一致
    r = client.get(f"/projects/{pid}/handoff")
    h = r.json()["handoff"]
    assert h["goal"] == "中秋節社群活動主視覺"
    assert len(h["constraints"]) == 3
    assert len(h["asset_refs"]) == 2
    assert h["asset_refs"][0]["type"] == "nas"
    assert h["updated_by"] == "pm@chengfu.local"
    assert "updated_at" in h


def test_handoff_card_project_not_found(client):
    """送到不存在的 id · 回 404"""
    fake_id = "6070" + "0" * 20  # 24 hex chars · 但無此 doc
    r = client.put(
        f"/projects/{fake_id}/handoff",
        json={"goal": "x"},
    )
    assert r.status_code == 404


def test_handoff_card_bad_project_id(client):
    """非 ObjectId 格式 · 回 400"""
    r = client.put("/projects/not-an-objectid/handoff", json={"goal": "x"})
    assert r.status_code == 400


# ============================================================
# C · 回饋收集
# ============================================================
def test_create_feedback(client):
    r = client.post("/feedback", json={
        "message_id": "msg_001",
        "agent_name": "🎯 投標顧問",
        "verdict": "up",
        "note": "建議書結構很清楚",
        "user_email": "test@chengfu.local",
    })
    assert r.status_code == 200


def test_feedback_stats(client):
    client.post("/feedback", json={"message_id": "m2", "agent_name": "A", "verdict": "up"})
    client.post("/feedback", json={"message_id": "m3", "agent_name": "A", "verdict": "down"})
    r = client.get("/feedback/stats")
    assert r.status_code == 200


# ============================================================
# D · 管理 Dashboard
# ============================================================
def test_admin_dashboard_requires_admin(client):
    """沒帶 X-User-Email → 403。驗證 RBAC 生效。"""
    r = client.get("/admin/dashboard")
    assert r.status_code == 403


def test_admin_dashboard_with_admin(client):
    """白名單 admin email → 200。"""
    r = client.get(
        "/admin/dashboard",
        headers={"X-User-Email": "sterio068@gmail.com"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "accounting" in body
    assert "projects" in body
    assert "feedback" in body
    assert "conversations" in body


def test_admin_dashboard_rejects_non_admin(client):
    """非白名單 email → 403。"""
    r = client.get(
        "/admin/dashboard",
        headers={"X-User-Email": "random-staff@chengfu.local"},
    )
    assert r.status_code == 403


# ============================================================
# E · Level 03 classifier
# ============================================================
def test_l3_classifier_safe_content(client):
    r = client.post("/safety/classify", json={"text": "寫一則中秋節的祝賀訊息"})
    assert r.status_code == 200
    assert r.json()["level"] == "01"


def test_l3_classifier_detects_selection(client):
    r = client.post("/safety/classify", json={
        "text": "幫我分析這次選情,下次候選人策略要怎麼定"
    })
    assert r.status_code == 200
    assert r.json()["level"] == "03"
    assert len(r.json()["triggers"]) > 0


def test_l3_classifier_detects_phone(client):
    r = client.post("/safety/classify", json={
        "text": "客戶電話 0912345678 要 call"
    })
    assert r.status_code == 200
    assert r.json()["level"] == "03"


def test_l3_classifier_detects_unit_internal(client):
    r = client.post("/safety/classify", json={
        "text": "這個是未公告標案,評審名單我還沒查"
    })
    assert r.status_code == 200
    assert r.json()["level"] == "03"


# ============================================================
# F · Fal.ai 設計助手(V1.1-SPEC §A · Q2 num_images=3)
# ============================================================
def test_design_recraft_without_api_key(client):
    """FAL_API_KEY 未設 → 503 + friendly_message"""
    import main as main_mod
    saved = main_mod.FAL_KEY
    main_mod.FAL_KEY = ""
    try:
        r = client.post("/design/recraft", json={
            "prompt": "中秋節品牌主視覺 · 橘黃色調 · 現代簡潔",
            "image_size": "square_hd",
        })
        assert r.status_code == 503
        body = r.json()
        # FastAPI 把 detail 包一層
        detail = body.get("detail", {})
        if isinstance(detail, dict):
            assert "未啟用" in detail.get("friendly_message", "")
            assert detail.get("status") == "unconfigured"
        else:
            # 若 detail 是字串 · 至少要有訊息
            assert "未啟用" in str(detail) or "FAL" in str(detail)
    finally:
        main_mod.FAL_KEY = saved


def test_design_recraft_rejects_short_prompt(client):
    """prompt < 4 字 → 422 pydantic validation"""
    r = client.post("/design/recraft", json={"prompt": "abc"})
    assert r.status_code == 422


def test_design_recraft_rejects_bad_size(client):
    """image_size 不在 enum → 422"""
    r = client.post("/design/recraft", json={
        "prompt": "a reasonable prompt here",
        "image_size": "ultra_wide_xyz",
    })
    assert r.status_code == 422


def test_design_recraft_status_without_api_key(client):
    """status 端點 · 無 key 也 503"""
    import main as main_mod
    saved = main_mod.FAL_KEY
    main_mod.FAL_KEY = ""
    try:
        r = client.get("/design/recraft/status/req_fake")
        assert r.status_code == 503
    finally:
        main_mod.FAL_KEY = saved


def test_design_recraft_success_mocked(client, monkeypatch):
    """Mock httpx · 驗收 done 路徑 + log 寫進 design_jobs"""
    import main as main_mod

    class FakeResp:
        def __init__(self, status_code, data):
            self.status_code = status_code
            self._data = data
        def json(self): return self._data
        def raise_for_status(self):
            if self.status_code >= 400:
                import httpx
                raise httpx.HTTPStatusError("", request=None, response=self)

    class FakeClient:
        def __init__(self, *a, **kw): self.calls = []
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, url, **kw):
            return FakeResp(200, {"request_id": "req_fake_123"})
        async def get(self, url, **kw):
            if url.endswith("/status"):
                return FakeResp(200, {"status": "COMPLETED"})
            return FakeResp(200, {"images": [
                {"url": "https://fal.cdn/a.png", "width": 1024, "height": 1024},
                {"url": "https://fal.cdn/b.png", "width": 1024, "height": 1024},
                {"url": "https://fal.cdn/c.png", "width": 1024, "height": 1024},
            ]})

    monkeypatch.setattr(main_mod, "FAL_KEY", "fake-key-for-test")
    monkeypatch.setattr(main_mod.httpx, "AsyncClient", FakeClient)
    # asyncio.sleep → 立刻 return · 避免測試等 12 秒
    async def _nop(x): return
    monkeypatch.setattr(main_mod.asyncio, "sleep", _nop)

    r = client.post("/design/recraft", json={
        "prompt": "中秋節品牌主視覺 橘黃調",
        "image_size": "square_hd",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["job_id"] == "req_fake_123"
    assert len(body["images"]) == 3  # Q2 · 老闆要 3 張


# ============================================================
# G · 多來源知識庫(V1.1-SPEC §E · 老闆 Q3)
# ============================================================
import tempfile, os as _os

ADMIN_HEADERS = {"X-User-Email": "sterio068@gmail.com"}


@pytest.fixture
def tmp_source_dir():
    """在 /tmp/chengfu-test-sources 下建臨時目錄 · 路徑白名單內"""
    _os.makedirs("/tmp/chengfu-test-sources", exist_ok=True)
    d = tempfile.mkdtemp(dir="/tmp/chengfu-test-sources")
    # 建幾個測試檔
    _os.makedirs(_os.path.join(d, "projects", "海廢案"), exist_ok=True)
    with open(_os.path.join(d, "projects", "海廢案", "建議書.txt"), "w") as f:
        f.write("承富創意 · 2024 環保署海洋廢棄物專案建議書")
    with open(_os.path.join(d, ".DS_Store"), "w") as f:
        f.write("mac system file")
    with open(_os.path.join(d, "readme.md"), "w") as f:
        f.write("測試來源 root")
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)


def test_knowledge_source_create_and_list(client, tmp_source_dir):
    """建 source + list · 驗路徑白名單 + readable"""
    # 無 admin header → 403
    r = client.post("/admin/sources", json={"name": "x", "path": tmp_source_dir})
    assert r.status_code == 403

    # 建立 source
    r = client.post(
        "/admin/sources",
        json={
            "name": "測試來源",
            "type": "local",
            "path": tmp_source_dir,
            "max_size_mb": 10,
        },
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    sid = r.json()["id"]
    assert r.json()["validation"]["path_exists"] is True

    # list 應該看得到
    r = client.get("/admin/sources", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    sources = r.json()
    assert any(s["id"] == sid for s in sources)
    mine = [s for s in sources if s["id"] == sid][0]
    assert mine["name"] == "測試來源"
    assert mine["enabled"] is True


def test_knowledge_source_reject_bad_path(client):
    """路徑不在白名單 · 400"""
    r = client.post(
        "/admin/sources",
        json={"name": "bad", "path": "/etc/passwd-like"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 400


def test_knowledge_source_reject_nonexistent(client):
    """路徑白名單內但不存在 · 400"""
    r = client.post(
        "/admin/sources",
        json={"name": "nope", "path": "/tmp/chengfu-test-sources/definitely-not-exist-xyz"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 400


def test_knowledge_source_reject_duplicate_path(client, tmp_source_dir):
    """同路徑兩次 · 409"""
    body = {"name": "dup1", "path": tmp_source_dir}
    r1 = client.post("/admin/sources", json=body, headers=ADMIN_HEADERS)
    assert r1.status_code == 200
    r2 = client.post("/admin/sources", json={**body, "name": "dup2"},
                     headers=ADMIN_HEADERS)
    assert r2.status_code == 409


def test_knowledge_source_patch_and_delete(client, tmp_source_dir):
    """patch 啟用/停用 + delete"""
    r = client.post(
        "/admin/sources",
        json={"name": "patch test", "path": tmp_source_dir},
        headers=ADMIN_HEADERS,
    )
    sid = r.json()["id"]

    # patch · 停用
    r = client.patch(f"/admin/sources/{sid}", json={"enabled": False},
                     headers=ADMIN_HEADERS)
    assert r.status_code == 200

    # reindex disabled source → 400
    r = client.post(f"/admin/sources/{sid}/reindex", headers=ADMIN_HEADERS)
    assert r.status_code == 400

    # delete
    r = client.delete(f"/admin/sources/{sid}", headers=ADMIN_HEADERS)
    assert r.status_code == 200

    # delete 再一次 → 404
    r = client.delete(f"/admin/sources/{sid}", headers=ADMIN_HEADERS)
    assert r.status_code == 404


def test_knowledge_list_public(client, tmp_source_dir):
    """/knowledge/list · 同仁可叫 · 列 enabled sources"""
    r = client.post(
        "/admin/sources",
        json={"name": "list test", "path": tmp_source_dir},
        headers=ADMIN_HEADERS,
    )
    sid = r.json()["id"]

    # 列所有 sources(無 source_id)
    r = client.get("/knowledge/list")
    assert r.status_code == 200
    body = r.json()
    assert "sources" in body
    assert any(s["id"] == sid for s in body["sources"])

    # 列某 source 的 top-level
    r = client.get(f"/knowledge/list?source_id={sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["source_id"] == sid
    # projects/ 與 readme.md 應該在 · .DS_Store 要被排除
    names = [e["name"] for e in body["entries"]]
    assert "projects" in names
    assert "readme.md" in names
    assert ".DS_Store" not in names


def test_knowledge_read_path_traversal_blocked(client, tmp_source_dir):
    """../../../etc/passwd 被擋"""
    r = client.post(
        "/admin/sources",
        json={"name": "traversal test", "path": tmp_source_dir},
        headers=ADMIN_HEADERS,
    )
    sid = r.json()["id"]

    # 合法 read
    r = client.get(f"/knowledge/read?source_id={sid}&rel_path=readme.md")
    assert r.status_code == 200
    assert r.json()["filename"] == "readme.md"
    assert r.json()["size"] > 0

    # 越界 read
    r = client.get(f"/knowledge/read?source_id={sid}&rel_path=../../etc/passwd")
    assert r.status_code == 403

    # excluded pattern 擋
    r = client.get(f"/knowledge/read?source_id={sid}&rel_path=.DS_Store")
    assert r.status_code == 403


def test_knowledge_agent_access_whitelist(client, tmp_source_dir):
    """source 有 agent_access 白名單 · 非清單 Agent 擋"""
    r = client.post(
        "/admin/sources",
        json={
            "name": "whitelist test",
            "path": tmp_source_dir,
            "agent_access": ["01", "03"],  # 只給招標 + 結案
        },
        headers=ADMIN_HEADERS,
    )
    sid = r.json()["id"]

    # Agent #05(公關)沒在清單 → 403
    r = client.get(
        f"/knowledge/read?source_id={sid}&rel_path=readme.md",
        headers={"X-Agent-Num": "05"},
    )
    assert r.status_code == 403

    # Agent #01(招標)在清單 → 200
    r = client.get(
        f"/knowledge/read?source_id={sid}&rel_path=readme.md",
        headers={"X-Agent-Num": "01"},
    )
    assert r.status_code == 200

    # 沒帶 X-Agent-Num(同仁直接叫)不擋
    r = client.get(f"/knowledge/read?source_id={sid}&rel_path=readme.md")
    assert r.status_code == 200


def test_knowledge_search_stub(client):
    """E-1 階段 /knowledge/search 回 stub · 不 crash 就 OK"""
    r = client.get("/knowledge/search?q=建議書")
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "建議書"
    assert body["hits"] == []
    assert "E-2" in body["message"]


def test_design_recraft_moderation_rejected(client, monkeypatch):
    """Mock 422 · 驗 moderation 路徑回 rejected + 人話"""
    import main as main_mod
    import httpx

    class RejResp:
        status_code = 422
        def json(self): return {"detail": "moderation"}
        def raise_for_status(self):
            raise httpx.HTTPStatusError("", request=None, response=self)

    class FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, *a, **kw): return RejResp()
        async def get(self, *a, **kw): return RejResp()

    monkeypatch.setattr(main_mod, "FAL_KEY", "fake-key-for-test")
    monkeypatch.setattr(main_mod.httpx, "AsyncClient", FakeClient)

    r = client.post("/design/recraft", json={
        "prompt": "真人總統肖像 寫實",  # 被 moderation 的假例
        "image_size": "square_hd",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "rejected"
    assert "抽象" in body["friendly_message"] or "敏感" in body["friendly_message"]

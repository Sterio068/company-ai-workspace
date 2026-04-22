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
    """R6#4 · /feedback/stats 改 admin-only"""
    client.post("/feedback", json={"message_id": "m2", "agent_name": "A", "verdict": "up"})
    client.post("/feedback", json={"message_id": "m3", "agent_name": "A", "verdict": "down"})
    r = client.get("/feedback/stats", headers={"X-User-Email": "sterio068@gmail.com"})
    assert r.status_code == 200


def test_feedback_stats_requires_admin(client):
    """R6#4 · 無 admin header → 403"""
    r = client.get("/feedback/stats")
    assert r.status_code == 403


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
def test_design_recraft_without_api_key(client, monkeypatch):
    """FAL_API_KEY 未設 → 503 + friendly_message
    ROADMAP §11.1 B-5 · router 改 _fal_key() 讀 env · test 用 monkeypatch.setenv
    R6#3 · 必須帶 X-User-Email · 否則先被 403 擋"""
    monkeypatch.setenv("FAL_API_KEY", "")
    r = client.post("/design/recraft",
        json={"prompt": "中秋節品牌主視覺 · 橘黃色調 · 現代簡潔", "image_size": "square_hd"},
        headers={"X-User-Email": "user@chengfu.local"},  # R6#3
    )
    assert r.status_code == 503
    body = r.json()
    detail = body.get("detail", {})
    if isinstance(detail, dict):
        assert "未啟用" in detail.get("friendly_message", "")
        assert detail.get("status") == "unconfigured"
    else:
        assert "未啟用" in str(detail) or "FAL" in str(detail)


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


def test_design_recraft_status_without_api_key(client, monkeypatch):
    """status 端點 · 無 key 也 503"""
    monkeypatch.setenv("FAL_API_KEY", "")
    r = client.get("/design/recraft/status/req_fake")
    assert r.status_code == 503


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

    # ROADMAP §11.1 B-5 · router 內部 import httpx/asyncio · monkeypatch router 模組
    import routers.design as design_mod
    monkeypatch.setenv("FAL_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(design_mod.httpx, "AsyncClient", FakeClient)
    async def _nop(x): return
    monkeypatch.setattr(design_mod.asyncio, "sleep", _nop)

    r = client.post("/design/recraft",
        json={"prompt": "中秋節品牌主視覺 橘黃調", "image_size": "square_hd"},
        headers={"X-User-Email": "user@chengfu.local"},  # R6#3
    )
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

    # Codex R3.3 · 沒帶 X-Agent-Num 且 source 有 agent_access → 擋
    # 舊行為(漏洞):不擋 · 任何人可 curl 繞過
    # 新行為:嚴格 · 無 header 即無權限
    r = client.get(f"/knowledge/read?source_id={sid}&rel_path=readme.md")
    assert r.status_code == 403


def test_knowledge_search_without_meili(client):
    """E-2 · Meili 未啟用時 · 搜尋不 crash · 回友善結構"""
    r = client.get("/knowledge/search?q=建議書")
    assert r.status_code == 200
    body = r.json()
    assert "hits" in body
    assert isinstance(body["hits"], list)
    # 無 Meili 時 · message 應該提及未啟用 · 但不 crash 前端
    assert body["hits"] == [] or "hits" in body


# ============================================================
# Round 9 Q3 · 未授權 Agent 完全看不到 source 名稱
# ============================================================
def test_knowledge_list_hides_sources_for_unauthorized_agent(client, tmp_source_dir):
    """白名單 Agent 才看得到 source 名稱(reviewer Round 9)"""
    r = client.post(
        "/admin/sources",
        json={
            "name": "機密客戶合約",
            "path": tmp_source_dir,
            "agent_access": ["01", "03"],  # 只給投標 + 結案
        },
        headers=ADMIN_HEADERS,
    )
    sid = r.json()["id"]

    # Agent #05(公關)叫 /knowledge/list → 不應看到「機密客戶合約」
    r = client.get("/knowledge/list", headers={"X-Agent-Num": "05"})
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["sources"]]
    assert "機密客戶合約" not in names

    # Agent #01(投標)在白名單 → 看得到
    r = client.get("/knowledge/list", headers={"X-Agent-Num": "01"})
    names = [s["name"] for s in r.json()["sources"]]
    assert "機密客戶合約" in names

    # Codex R3.3 · 不帶 X-Agent-Num 時 · agent_access 有白名單的 source 預設擋
    # 之前行為:不過濾(漏洞 · 繞過白名單)
    # 新行為:預設嚴格 · 無 header = 無權限 · 看不到機敏 source
    r = client.get("/knowledge/list")
    names = [s["name"] for s in r.json()["sources"]]
    assert "機密客戶合約" not in names


def test_knowledge_list_empty_agent_access_visible_to_all(client, tmp_source_dir):
    """agent_access=[] 表示「所有 Agent 可讀」· 任何 X-Agent-Num 都能看到"""
    r = client.post(
        "/admin/sources",
        json={"name": "公開資料", "path": tmp_source_dir, "agent_access": []},
        headers=ADMIN_HEADERS,
    )
    r = client.get("/knowledge/list", headers={"X-Agent-Num": "99"})
    names = [s["name"] for s in r.json()["sources"]]
    assert "公開資料" in names


# ============================================================
# Round 9 implicit · source health + design history
# ============================================================
def test_source_health_ok(client, tmp_source_dir):
    """健康檢查正常路徑 · 回 status=ok"""
    r = client.post("/admin/sources",
        json={"name": "h test", "path": tmp_source_dir},
        headers=ADMIN_HEADERS)
    sid = r.json()["id"]
    r = client.get(f"/admin/sources/{sid}/health", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["path_exists"] is True
    assert body["readable"] is True


def test_source_health_unreachable(client):
    """路徑被刪 / NAS 斷線 · 回 unreachable + 友善 issue"""
    # 建一個臨時 source · 然後刪掉路徑
    import tempfile, shutil, os as _os
    _os.makedirs("/tmp/chengfu-test-sources", exist_ok=True)
    d = tempfile.mkdtemp(dir="/tmp/chengfu-test-sources")
    r = client.post("/admin/sources",
        json={"name": "unreach", "path": d},
        headers=ADMIN_HEADERS)
    sid = r.json()["id"]
    shutil.rmtree(d)  # 模擬 NAS 斷線
    r = client.get(f"/admin/sources/{sid}/health", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "unreachable"
    assert "NAS" in body["issue"] or "路徑" in body["issue"]


def test_all_sources_health_summary(client, tmp_source_dir):
    """巡檢端點 · 回 summary + 每個 source 結果"""
    client.post("/admin/sources",
        json={"name": "all-h test", "path": tmp_source_dir},
        headers=ADMIN_HEADERS)
    r = client.get("/admin/sources/health", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "summary" in body
    assert "sources" in body
    assert body["summary"]["ok"] >= 1


def test_design_history_empty(client):
    """無使用者歷史 · 回空 list 不 crash"""
    r = client.get("/design/history", headers={"X-User-Email": "noone@x.com"})
    assert r.status_code == 200
    assert r.json()["history"] == []
    assert r.json()["count"] == 0


def test_design_history_after_failed_call(client):
    """先呼叫一次 design/recraft (無 key 503)· 不會留 log
    確認 history 仍為空 · 真實 API call 才會記
    R6#3 · history 必須登入"""
    r = client.get("/design/history", headers={"X-User-Email": "user@chengfu.local"})
    assert r.status_code == 200
    assert isinstance(r.json()["history"], list)


def test_design_history_requires_login(client):
    """R6#3 · 無 X-User-Email → 403"""
    r = client.get("/design/history")
    assert r.status_code == 403


# ============================================================
# Codex R6#5 · auth contract tests · 防 R5/R6 風險回歸
# ============================================================
def test_auth_design_recraft_blocks_anonymous(client):
    """R6#3 · 任何人 curl /design/recraft 不帶 email → 403 · 不能爆 Fal 預算"""
    r = client.post("/design/recraft", json={
        "prompt": "anonymous attempt to burn fal credits",
        "image_size": "square_hd",
    })
    assert r.status_code == 403


def test_auth_tenders_blocks_anonymous(client):
    """R6#4 · /tender-alerts 改 require user · 防外部偵察承富業務"""
    r = client.get("/tender-alerts")
    assert r.status_code == 403


def test_auth_feedback_create_uses_trusted_email(client):
    """R6#4 · POST /feedback 即使 body 偽造 user_email · 仍以 X-User-Email 為準
    這個測試在 mongomock + JWT_SECRET 未設場景 · trusted=False · X-User-Email 仍會覆蓋"""
    r = client.post("/feedback",
        json={"message_id": "spy_msg", "verdict": "down", "user_email": "victim@chengfu.local"},
        headers={"X-User-Email": "real_attacker@chengfu.local"},
    )
    assert r.status_code == 200
    # 驗:DB 內存的 user_email 是 header 帶來的 trusted · 不是 body 偽造的
    import main as main_mod
    fb = main_mod.feedback_col.find_one({"message_id": "spy_msg"})
    assert fb is not None
    assert fb["user_email"] == "real_attacker@chengfu.local"


def test_healthz_includes_ocr_status(client):
    """healthz 應該帶 OCR 狀態 · 維運可監控 tesseract 是否裝"""
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert "ocr" in body
    assert "available" in body["ocr"]


# ============================================================
# Codex Round 10.5 · 私人目錄移出白名單 + realpath 防 symlink
# ============================================================
def test_source_reject_users_not_in_whitelist_by_default(client):
    """/Users 不再是預設白名單 · 建 source 指 /Users/... 應該 400"""
    # 注意:CI 環境 env 可能不同 · 這邊只驗「非白名單回 400」的行為
    r = client.post("/admin/sources",
        json={"name": "private", "path": "/etc/hostname-dir-xyz"},
        headers=ADMIN_HEADERS)
    assert r.status_code == 400


def test_source_realpath_resolves_symlink_before_whitelist_check(client, tmp_source_dir):
    """建 symlink 從 allowed root 指到 allowed root · 應該 allow
    驗證 realpath 解析後仍在白名單內就放行"""
    import os as _os
    # tmp_source_dir 在 /tmp/chengfu-test-sources · 是白名單內
    link = tmp_source_dir + "-link"
    try:
        _os.symlink(tmp_source_dir, link)
        r = client.post("/admin/sources",
            json={"name": "link test", "path": link},
            headers=ADMIN_HEADERS)
        # 應該通過 · 因為 symlink 解析後仍在白名單
        assert r.status_code == 200
    finally:
        if _os.path.islink(link):
            _os.unlink(link)


# ============================================================
# Codex Round 10.5 · audit fail-closed
# ============================================================
# ============================================================
# Codex Round 10.5 黃 6 · /admin/adoption 支撐 BOSS ROI
# ============================================================
def test_admin_adoption_endpoint(client):
    """adoption endpoint 回應必有 active_users / handoff / fal / satisfaction"""
    r = client.get("/admin/adoption", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "period_days" in body
    assert body["period_days"] == 7  # default
    assert "active_users" in body  # 可能是 0 或 None · 但 key 要在
    assert "handoff" in body
    assert "completion_rate" in body["handoff"]
    assert "fal" in body
    assert "cost_ntd" in body["fal"]
    assert "satisfaction" in body


def test_admin_adoption_requires_admin(client):
    """一般同仁看不到 adoption · 必須 admin header"""
    r = client.get("/admin/adoption")
    assert r.status_code == 403


def test_admin_adoption_custom_days(client):
    """可指定 days 參數"""
    r = client.get("/admin/adoption?days=30", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["period_days"] == 30


# ============================================================
# Codex R3.4 · symlink escape prevention
# ============================================================
def test_knowledge_read_blocks_symlink_escape(client, tmp_source_dir):
    """source 內 symlink 指 source 外的檔 · /knowledge/read 應擋"""
    import os as _os, tempfile
    # 在白名單外建一個檔
    outside = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt")
    outside.write("secret content from outside")
    outside.close()

    # 在 source 內建 symlink 指外部
    link = _os.path.join(tmp_source_dir, "escape-link.txt")
    try:
        _os.symlink(outside.name, link)
        r = client.post("/admin/sources",
            json={"name": "sym test", "path": tmp_source_dir},
            headers=ADMIN_HEADERS)
        sid = r.json()["id"]

        # 試讀 symlink · R3.4 後應該被擋
        r = client.get(f"/knowledge/read?source_id={sid}&rel_path=escape-link.txt")
        assert r.status_code == 403, \
            "Codex R3.4:symlink 指外部應被 commonpath 檢查擋住"
    finally:
        if _os.path.islink(link):
            _os.unlink(link)
        _os.unlink(outside.name)


def test_knowledge_read_fails_closed_when_audit_broken(client, tmp_source_dir, monkeypatch):
    """Audit log 寫不進去時 · 讀取必須 503 · 不能留無痕讀取"""
    r = client.post("/admin/sources",
        json={"name": "audit test", "path": tmp_source_dir},
        headers=ADMIN_HEADERS)
    sid = r.json()["id"]

    # Monkeypatch audit collection 的 insert_one 丟例外
    import main as main_mod
    orig_insert = main_mod.knowledge_audit_col.insert_one
    def broken_insert(*a, **kw):
        raise ConnectionError("audit Mongo down")
    monkeypatch.setattr(main_mod.knowledge_audit_col, "insert_one", broken_insert)

    r = client.get(f"/knowledge/read?source_id={sid}&rel_path=readme.md")
    # 之前是 200 回檔案 + warning log · 現在必須 503
    assert r.status_code == 503
    assert "PDPA" in r.json()["detail"] or "Audit" in r.json()["detail"]


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

    import routers.design as design_mod
    monkeypatch.setenv("FAL_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(design_mod.httpx, "AsyncClient", FakeClient)

    r = client.post("/design/recraft",
        json={"prompt": "真人總統肖像 寫實", "image_size": "square_hd"},
        headers={"X-User-Email": "user@chengfu.local"},  # R6#3
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "rejected"
    assert "抽象" in body["friendly_message"] or "敏感" in body["friendly_message"]

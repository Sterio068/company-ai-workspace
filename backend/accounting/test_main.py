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
# R27#2 · router-wide require_user_dep · TestClient 必帶 X-User-Email · ENV 必開 LEGACY headers
@pytest.fixture(scope="module")
def client():
    import os
    os.environ["ALLOW_LEGACY_AUTH_HEADERS"] = "1"
    os.environ["ECC_ENV"] = "development"  # 防 prod startup 強制 JWT_REFRESH_SECRET
    # v1.3 batch6 · 移除 sterio068@gmail.com hardcode fallback 後 · test 必須明確設
    # 只給 sterio068@gmail.com · test@chengfu.local 用來測 non-admin → 403 場景
    os.environ["ADMIN_EMAILS"] = "sterio068@gmail.com"
    with patch("pymongo.MongoClient", mongomock.MongoClient):
        import importlib
        import main
        importlib.reload(main)
        c = TestClient(main.app, headers={"X-User-Email": "test@chengfu.local"})
        # 觸發 startup
        c.get("/healthz")
        main.db.users.update_one(
            {"email": "test@chengfu.local"},
            {"$set": {
                "email": "test@chengfu.local",
                "name": "Test User",
                "role": "USER",
                "chengfu_active": True,
                "chengfu_permissions": [
                    "accounting.view", "accounting.edit",
                    "project.create", "project.edit_own",
                    "social.post_own", "site.survey",
                    "knowledge.search", "design.generate",
                    "meeting.upload", "press.draft",
                ],
            }},
            upsert=True,
        )
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


def test_accounting_overview(client):
    client.post("/accounts/seed")
    r = client.get("/reports/overview")
    assert r.status_code == 200
    body = r.json()
    assert "pnl" in body
    assert "aging" in body
    assert "unpaid" in body
    assert "quotes" in body


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


def test_notebooklm_status_local_parallel(client):
    r = client.get("/notebooklm/status")
    assert r.status_code == 200
    body = r.json()
    assert body["local"]["source_of_truth"] == "MongoDB / 本地檔案"
    assert body["notebooklm"]["mode"] == "enterprise-api"


def test_notebooklm_project_source_pack_create(client):
    r = client.post("/projects", json={
        "name": "NotebookLM 並行測試案",
        "client": "文化局",
        "budget": 1200000,
        "deadline": "2026-05-31",
        "status": "active",
    })
    assert r.status_code == 200
    project_id = r.json()["id"]
    client.put(f"/projects/{project_id}/handoff", json={
        "goal": "整理提案素材給 NotebookLM 深讀",
        "constraints": ["不可同步 Level 03 機敏資料"],
        "asset_refs": [{"type": "note", "label": "素材", "ref": "本地知識庫"}],
        "next_actions": ["確認 source pack 後再同步"],
    })
    r = client.post("/notebooklm/source-packs", json={
        "scope": "project",
        "project_id": project_id,
        "sensitivity": "L2",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "local_ready"
    assert "NotebookLM 並行測試案" in body["content_md"]
    assert body["content_hash"]


def test_notebooklm_project_source_pack_acl(client):
    import main as main_mod
    for email in ["alice@company.local", "bob@company.local"]:
        main_mod.db.users.update_one(
            {"email": email},
            {"$set": {
                "email": email,
                "name": email.split("@")[0],
                "role": "USER",
                "chengfu_active": True,
                "chengfu_permissions": ["knowledge.search", "project.create", "project.edit_own"],
            }},
            upsert=True,
        )

    alice_headers = {"X-User-Email": "alice@company.local"}
    bob_headers = {"X-User-Email": "bob@company.local"}
    r = client.post("/projects", json={
        "name": "Alice NotebookLM 私有工作包",
        "client": "文化局",
        "status": "active",
    }, headers=alice_headers)
    assert r.status_code == 200
    project_id = r.json()["id"]

    r = client.post("/notebooklm/source-packs", json={
        "scope": "project",
        "project_id": project_id,
        "sensitivity": "all",
    }, headers=alice_headers)
    assert r.status_code == 200
    pack_id = r.json()["_id"]

    r = client.get("/notebooklm/source-packs", headers=bob_headers)
    assert r.status_code == 200
    assert pack_id not in [item["_id"] for item in r.json()["items"]]

    r = client.get(f"/notebooklm/source-packs/{pack_id}", headers=bob_headers)
    assert r.status_code == 403


def test_notebooklm_agent_source_pack_uses_acting_user_acl(client):
    """Agent action 不能用 admin 身分繞過工作包 owner/collaborator 邊界."""
    import main as main_mod
    for email in ["agent-alice@company.local", "agent-bob@company.local"]:
        main_mod.db.users.update_one(
            {"email": email},
            {"$set": {
                "email": email,
                "name": email.split("@")[0],
                "role": "USER",
                "chengfu_active": True,
                "chengfu_permissions": ["knowledge.search", "project.create", "project.edit_own"],
            }},
            upsert=True,
        )

    alice_headers = {"X-User-Email": "agent-alice@company.local"}
    r = client.post("/projects", json={
        "name": "Agent ACL 私有工作包",
        "client": "文化局",
        "status": "active",
    }, headers=alice_headers)
    assert r.status_code == 200
    project_id = r.json()["id"]

    admin_as_bob = {
        "X-User-Email": "sterio068@gmail.com",
        "X-Acting-User": "agent-bob@company.local",
    }
    r = client.post("/notebooklm/agent/source-packs", json={
        "scope": "project",
        "project_id": project_id,
        "sensitivity": "all",
    }, headers=admin_as_bob)
    assert r.status_code == 403

    admin_as_alice = {
        "X-User-Email": "sterio068@gmail.com",
        "X-Acting-User": "agent-alice@company.local",
    }
    r = client.post("/notebooklm/agent/source-packs", json={
        "scope": "project",
        "project_id": project_id,
        "sensitivity": "L3",
    }, headers=admin_as_alice)
    assert r.status_code == 200
    body = r.json()
    assert body["created_by"] == "agent:agent-alice@company.local"
    assert body["sensitivity"] == "L3"

    r = client.get("/notebooklm/agent/source-packs", headers=admin_as_bob)
    assert r.status_code == 200
    assert body["_id"] not in [item["_id"] for item in r.json()["items"]]


def test_notebooklm_project_pack_hash_stable_and_combines_next_actions(client):
    import main as main_mod
    from bson import ObjectId
    r = client.post("/projects", json={
        "name": "NotebookLM hash stable",
        "client": "文化局",
        "status": "active",
    })
    assert r.status_code == 200
    project_id = r.json()["id"]
    main_mod.db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {
            "handoff": {
                "goal": "整理成 NotebookLM 資料包",
                "next_actions": ["manual action"],
                "meeting_next_actions": ["meeting action"],
            }
        }},
    )

    payload = {"scope": "project", "project_id": project_id, "sensitivity": "all"}
    first = client.post("/notebooklm/source-packs", json=payload)
    second = client.post("/notebooklm/source-packs", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["content_hash"] == second.json()["content_hash"]
    assert second.json()["deduped"] is True
    content = second.json()["content_md"]
    assert "manual action" in content
    assert "meeting action" in content


def test_notebooklm_project_pack_hash_ignores_same_day_time_and_finance_noise(client):
    """資料包 hash 應代表業務內容,不該因同日時間或小數財務雜訊改變."""
    import main as main_mod
    from bson import ObjectId
    from datetime import datetime, timezone

    r = client.post("/projects", json={
        "name": "NotebookLM stable hash noise",
        "client": "文化局",
        "status": "active",
    })
    assert r.status_code == 200
    project_id = r.json()["id"]
    main_mod.db.meetings.insert_one({
        "project_id": project_id,
        "status": "done",
        "created_at": datetime(2026, 4, 28, 9, 30, tzinfo=timezone.utc),
        "structured": {
            "title": "同日時間不應改 hash",
            "decisions": ["方向確認"],
        },
    })
    main_mod.db.accounting_projects_finance.insert_one({
        "project_id": project_id,
        "income": 1000.49,
        "expense": 400.41,
        "margin": 600.08,
        "margin_rate": 60.01234,
    })

    payload = {"scope": "project", "project_id": project_id, "sensitivity": "all"}
    first = client.post("/notebooklm/source-packs", json=payload)
    assert first.status_code == 200
    first_hash = first.json()["content_hash"]

    main_mod.db.meetings.update_one(
        {"project_id": project_id},
        {"$set": {"created_at": datetime(2026, 4, 28, 17, 45, tzinfo=timezone.utc)}},
    )
    main_mod.db.accounting_projects_finance.update_one(
        {"project_id": project_id},
        {"$set": {
            "income": 1000.44,
            "expense": 400.49,
            "margin": 600.02,
            "margin_rate": 60.01,
        }},
    )
    second = client.post("/notebooklm/source-packs", json=payload)
    assert second.status_code == 200
    assert second.json()["content_hash"] == first_hash
    assert second.json()["deduped"] is True


def test_notebooklm_source_pack_creation_writes_sensitivity_audit(client):
    import main as main_mod
    r = client.post("/notebooklm/source-packs", json={
        "scope": "training",
        "sensitivity": "L3",
    })
    assert r.status_code == 200
    body = r.json()
    audit = main_mod.db.audit_log.find_one({
        "action": "notebooklm_source_pack_create",
        "resource": body["_id"],
    })
    assert audit
    assert audit["details"]["sensitivity"] == "L3"
    assert audit["details"]["content_hash"] == body["content_hash"]


def test_notebooklm_one_project_one_notebook_unconfigured(client):
    r = client.post("/projects", json={
        "name": "NotebookLM 專案筆記本測試",
        "client": "文化局",
        "status": "active",
    })
    assert r.status_code == 200
    project_id = r.json()["id"]

    r = client.post(f"/notebooklm/projects/{project_id}/notebook")
    assert r.status_code == 200
    body = r.json()
    assert body["project_id"] == project_id
    assert body["notebook_id"] is None
    assert body["configured"] is False

    r = client.get(f"/notebooklm/projects/{project_id}/notebook")
    assert r.status_code == 200
    assert r.json()["project_id"] == project_id


def test_notebooklm_file_upload_auto_to_project_unconfigured(client):
    r = client.post("/projects", json={
        "name": "NotebookLM 檔案歸檔測試",
        "client": "文化局",
        "status": "active",
    })
    assert r.status_code == 200
    project_id = r.json()["id"]

    r = client.post(
        "/notebooklm/uploads/auto",
        data={
            "project_id": project_id,
            "relative_paths": "NotebookLM 檔案歸檔測試/proposal.md",
        },
        files=[("files", ("proposal.md", b"# proposal\nhello", "text/markdown"))],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["project_id"] == project_id
    assert body["configured"] is False
    assert body["skipped"] == 1
    assert body["items"][0]["status"] == "skipped_unconfigured"


def test_notebooklm_upload_batch_resume_skips_already_uploaded(client):
    import main as main_mod
    from services.notebooklm_client import NotebookLMClientError

    r = client.post("/projects", json={
        "name": "NotebookLM 批次續傳測試",
        "client": "文化局",
        "status": "active",
    })
    assert r.status_code == 200
    project_id = r.json()["id"]
    notebook = {
        "project_id": project_id,
        "title": "NotebookLM 批次續傳測試",
        "notebook_id": "nb-batch",
        "configured": True,
    }

    calls: list[str] = []

    def upload_side_effect(_notebook_id, display_name, _content, _content_type):
        calls.append(display_name)
        if display_name == "folder/b.md" and calls.count("folder/b.md") == 1:
            raise NotebookLMClientError(429, "NotebookLM 上傳檔案來源 失敗(429):quota", "quota_exceeded")
        return {"configured": True, "source": {"name": display_name}}

    with patch("routers.notebooklm._ensure_project_notebook", return_value=notebook):
        with patch("routers.notebooklm.upload_file_source", side_effect=upload_side_effect):
            r = client.post(
                "/notebooklm/uploads/auto",
                data={
                    "project_id": project_id,
                    "relative_paths": ["folder/a.md", "folder/b.md"],
                },
                files=[
                    ("files", ("a.md", b"# a", "text/markdown")),
                    ("files", ("b.md", b"# b", "text/markdown")),
                ],
            )
            assert r.status_code == 200
            first = r.json()
            assert first["uploaded"] == 1
            assert first["failed"] == 1
            assert first["batch_id"]

            r = client.post(
                "/notebooklm/uploads/auto",
                data={
                    "project_id": project_id,
                    "batch_id": first["batch_id"],
                    "resume_failed_only": "true",
                    "relative_paths": ["folder/a.md", "folder/b.md"],
                },
                files=[
                    ("files", ("a.md", b"# a", "text/markdown")),
                    ("files", ("b.md", b"# b", "text/markdown")),
                ],
            )
    assert r.status_code == 200
    second = r.json()
    statuses = {item["relative_path"]: item["status"] for item in second["items"]}
    assert statuses["folder/a.md"] == "skipped_already_uploaded"
    assert statuses["folder/b.md"] == "uploaded"
    assert calls == ["folder/a.md", "folder/b.md", "folder/b.md"]
    uploaded_records = list(main_mod.db.notebooklm_file_uploads.find({
        "batch_id": first["batch_id"],
        "relative_path": "folder/a.md",
        "status": "uploaded",
    }))
    assert len(uploaded_records) == 1


def test_notebooklm_upload_resume_scoped_by_project_and_notebook(client):
    created = []
    for name in ["NotebookLM 續傳 A", "NotebookLM 續傳 B"]:
        r = client.post("/projects", json={"name": name, "client": "文化局", "status": "active"})
        assert r.status_code == 200
        created.append(r.json()["id"])

    def notebook_for(_db, project_id, *_args, **_kwargs):
        return {
            "project_id": project_id,
            "title": f"Notebook {project_id}",
            "notebook_id": f"nb-{project_id}",
            "configured": True,
        }

    calls: list[tuple[str, str]] = []

    def upload_side_effect(notebook_id, display_name, _content, _content_type):
        calls.append((notebook_id, display_name))
        return {"configured": True, "source": {"name": display_name}}

    shared_batch = "shared-batch"
    with patch("routers.notebooklm._ensure_project_notebook", side_effect=notebook_for):
        with patch("routers.notebooklm.upload_file_source", side_effect=upload_side_effect):
            r = client.post(
                "/notebooklm/uploads/auto",
                data={
                    "project_id": created[0],
                    "batch_id": shared_batch,
                    "relative_paths": ["folder/a.md"],
                },
                files=[("files", ("a.md", b"# a", "text/markdown"))],
            )
            assert r.status_code == 200
            assert r.json()["uploaded"] == 1

            r = client.post(
                "/notebooklm/uploads/auto",
                data={
                    "project_id": created[1],
                    "batch_id": shared_batch,
                    "resume_failed_only": "true",
                    "relative_paths": ["folder/a.md"],
                },
                files=[("files", ("a.md", b"# a", "text/markdown"))],
            )

    assert r.status_code == 200
    body = r.json()
    assert body["uploaded"] == 1
    assert body["skipped"] == 0
    assert calls == [
        (f"nb-{created[0]}", "folder/a.md"),
        (f"nb-{created[1]}", "folder/a.md"),
    ]


def test_internal_token_with_acting_user_satisfies_user_permission(client, monkeypatch):
    monkeypatch.setenv("ECC_INTERNAL_TOKEN", "test-internal-token")
    headers = {
        "X-Internal-Token": "test-internal-token",
        "X-Acting-User": "test@chengfu.local",
    }
    r = client.get("/transactions", headers=headers)
    assert r.status_code == 200


def test_action_bridge_token_with_acting_user_satisfies_action_permission(client, monkeypatch):
    monkeypatch.setenv("ACTION_BRIDGE_TOKEN", "test-action-bridge-token")
    headers = {
        "X-Internal-Token": "test-action-bridge-token",
        "X-Acting-User": "test@chengfu.local",
    }
    r = client.get("/transactions", headers=headers)
    assert r.status_code == 200


def test_action_bridge_token_is_scoped_to_action_paths(client, monkeypatch):
    monkeypatch.setenv("ACTION_BRIDGE_TOKEN", "test-action-bridge-token")
    headers = {
        "X-Internal-Token": "test-action-bridge-token",
        "X-Acting-User": "sterio068@gmail.com",
    }
    r = client.get("/admin/audit-log", headers=headers)
    assert r.status_code == 403


def test_notebooklm_agent_routes_accept_action_bridge_token(client, monkeypatch):
    monkeypatch.setenv("ACTION_BRIDGE_TOKEN", "test-action-bridge-token")
    headers = {
        "X-Internal-Token": "test-action-bridge-token",
        "X-Acting-User": "test@chengfu.local",
    }
    r = client.get("/notebooklm/agent/source-packs", headers=headers)
    assert r.status_code == 200


def test_notebooklm_settings_bad_token_does_not_write(client):
    import main as main_mod
    from services.notebooklm_client import NotebookLMClientError

    with patch(
        "routers.notebooklm.validate_config",
        side_effect=NotebookLMClientError(403, "NotebookLM 驗證設定 失敗(403):denied", "permission_denied"),
    ):
        r = client.put(
            "/notebooklm/settings",
            json={
                "enabled": True,
                "project_number": "123456789012",
                "location": "global",
                "endpoint_location": "global",
                "access_token": "bad-token",
            },
            headers={"X-User-Email": "sterio068@gmail.com"},
        )
    assert r.status_code == 412
    assert r.json()["detail"]["recovery_hint"] == "permission_denied"
    assert main_mod.db.system_settings.find_one({"name": "NOTEBOOKLM_ACCESS_TOKEN"}) is None


def test_notebooklm_settings_validates_then_writes(client):
    import main as main_mod

    with patch("routers.notebooklm.validate_config", return_value={"configured": True, "ok": True}):
        r = client.put(
            "/notebooklm/settings",
            json={
                "enabled": True,
                "project_number": "123456789012",
                "location": "global",
                "endpoint_location": "global",
                "access_token": "good-token",
            },
            headers={"X-User-Email": "sterio068@gmail.com"},
        )
    assert r.status_code == 200
    assert main_mod.db.system_settings.find_one({"name": "NOTEBOOKLM_ACCESS_TOKEN"})["value"] == "good-token"
    main_mod.db.system_settings.delete_many({"name": {"$in": [
        "NOTEBOOKLM_ENTERPRISE_ENABLED",
        "NOTEBOOKLM_PROJECT_NUMBER",
        "NOTEBOOKLM_LOCATION",
        "NOTEBOOKLM_ENDPOINT_LOCATION",
        "NOTEBOOKLM_ACCESS_TOKEN",
    ]}})


def test_secret_registry_exposes_tiers_and_writers(client):
    from services.secret_registry import SECRET_REGISTRY

    assert SECRET_REGISTRY["OPENAI_API_KEY"]["tier"] == "T0_REQUIRED"
    assert SECRET_REGISTRY["OPENAI_API_KEY"]["frontend_writable"] is True
    assert SECRET_REGISTRY["JWT_REFRESH_SECRET"]["writer"] == "installer/keychain only"
    assert SECRET_REGISTRY["NOTEBOOKLM_ACCESS_TOKEN"]["frontend_writable"] is True


def test_retention_registry_recreates_stale_ttl(client):
    import main as main_mod
    from infra.retention_policy import apply_retention_indexes

    main_mod.db.frontend_errors.drop_indexes()
    main_mod.db.frontend_errors.create_index(
        [("created_at", 1)],
        expireAfterSeconds=999,
        name="ttl_30d",
    )
    apply_retention_indexes(main_mod.db)
    info = main_mod.db.frontend_errors.index_information()["ttl_30d"]
    assert info["expireAfterSeconds"] == 30 * 24 * 3600


def test_notebooklm_sync_unconfigured_returns_local_ready(client):
    r = client.post("/notebooklm/source-packs", json={
        "scope": "tenders",
        "sensitivity": "L2",
    })
    assert r.status_code == 200
    pack_id = r.json()["_id"]
    r = client.post(
        f"/notebooklm/source-packs/{pack_id}/sync",
        json={"create_notebook": True},
        headers={"X-User-Email": "sterio068@gmail.com"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is False
    assert body["state"] == "local_ready"


def test_notebooklm_sync_failure_marks_run_failed(client):
    import main as main_mod
    r = client.post("/notebooklm/source-packs", json={
        "scope": "tenders",
        "sensitivity": "all",
    })
    assert r.status_code == 200
    pack_id = r.json()["_id"]
    with patch("routers.notebooklm.public_status", return_value={"configured": True}):
        with patch("routers.notebooklm.create_notebook", return_value={"notebook": {"notebookId": "nb-test"}}):
            with patch("routers.notebooklm.add_text_source", side_effect=RuntimeError("upstream boom")):
                r = client.post(
                    f"/notebooklm/source-packs/{pack_id}/sync",
                    json={"create_notebook": True},
                    headers={"X-User-Email": "sterio068@gmail.com"},
                )
    assert r.status_code == 502
    run = main_mod.db.notebooklm_sync_runs.find_one({"pack_id": pack_id}, sort=[("created_at", -1)])
    assert run["status"] == "failed"
    assert run.get("finished_at")
    assert "upstream boom" in run["error"]


def test_notebooklm_sync_client_error_returns_recovery_hint(client):
    import main as main_mod
    from services.notebooklm_client import NotebookLMClientError

    r = client.post("/notebooklm/source-packs", json={
        "scope": "tenders",
        "sensitivity": "L2",
    })
    assert r.status_code == 200
    pack_id = r.json()["_id"]

    with patch("routers.notebooklm.public_status", return_value={"configured": True}):
        with patch("routers.notebooklm.create_notebook", return_value={"notebook": {"notebookId": "nb-test"}}):
            with patch(
                "routers.notebooklm.add_text_source",
                side_effect=NotebookLMClientError(
                    401,
                    "NotebookLM 新增文字來源 失敗(401):expired",
                    "token_expired",
                ),
            ):
                r = client.post(
                    f"/notebooklm/source-packs/{pack_id}/sync",
                    json={"create_notebook": True},
                    headers={"X-User-Email": "sterio068@gmail.com"},
                )
    assert r.status_code == 401
    assert r.json()["detail"]["recovery_hint"] == "token_expired"
    assert r.json()["detail"]["provider_status"] == 401
    run = main_mod.db.notebooklm_sync_runs.find_one({"pack_id": pack_id}, sort=[("created_at", -1)])
    assert run["status"] == "failed"
    assert run["recovery_hint"] == "token_expired"
    assert run["provider_status"] == 401


def test_notebooklm_l3_sync_requires_second_confirm(client):
    import main as main_mod

    r = client.post("/notebooklm/source-packs", json={
        "scope": "training",
        "sensitivity": "L3",
    })
    assert r.status_code == 200
    pack_id = r.json()["_id"]

    with patch("routers.notebooklm.public_status", return_value={"configured": True}):
        r = client.post(
            f"/notebooklm/source-packs/{pack_id}/sync",
            json={"create_notebook": True},
            headers={"X-User-Email": "sterio068@gmail.com"},
        )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "notebooklm_confirm_required"
    run = main_mod.db.notebooklm_sync_runs.find_one({"pack_id": pack_id}, sort=[("created_at", -1)])
    assert run["status"] == "confirm_required"

    with patch("routers.notebooklm.public_status", return_value={"configured": True}):
        with patch("routers.notebooklm.create_notebook", return_value={"notebook": {"notebookId": "nb-l3"}}):
            with patch("routers.notebooklm.add_text_source", return_value={"sources": [{"sourceId": {"id": "src-l3"}}]}):
                r = client.post(
                    f"/notebooklm/source-packs/{pack_id}/sync",
                    json={"create_notebook": True, "confirm_send_to_notebooklm": True},
                    headers={"X-User-Email": "sterio068@gmail.com"},
                )
    assert r.status_code == 200
    assert r.json()["state"] == "synced"


def test_handoff_card_roundtrip(client):
    """B2 · Handoff 4 格卡 · 存 + 取 + 預設值"""
    # 建一個 project
    r = client.post(
        "/projects",
        json={"name": "handoff test proj"},
        headers={"X-User-Email": "pm@chengfu.local"},
    )
    pid = r.json()["id"]

    # 初始 handoff 應該是空
    r = client.get(f"/projects/{pid}/handoff", headers={"X-User-Email": "pm@chengfu.local"})
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
    r = client.get(f"/projects/{pid}/handoff", headers={"X-User-Email": "pm@chengfu.local"})
    h = r.json()["handoff"]
    assert h["goal"] == "中秋節社群活動主視覺"
    assert len(h["constraints"]) == 3
    assert len(h["asset_refs"]) == 2
    assert h["asset_refs"][0]["type"] == "nas"
    assert h["updated_by"] == "pm@chengfu.local"
    assert "updated_at" in h


def test_handoff_card_update_preserves_system_handoff_fields(client):
    """Round 2 · PM 手動更新 4 格卡時,不得清掉場勘 / workflow 等系統交棒欄位"""
    import main as main_mod
    from bson import ObjectId

    r = client.post(
        "/projects",
        json={"name": "handoff preserve test"},
        headers={"X-User-Email": "pm@chengfu.local"},
    )
    pid = r.json()["id"]
    main_mod.db.projects.update_one(
        {"_id": ObjectId(pid)},
        {"$set": {
            "handoff.site_issues": ["入口有高差"],
            "handoff.site_venue": "松菸 4 號倉庫",
            "handoff.workflow_draft": {"preset_id": "tender-full", "step_count": 3},
            "handoff.site_asset_refs": [
                {"type": "note", "label": "場勘彙整", "ref": "室內 · 50 坪"},
            ],
            "handoff.asset_refs": [
                {"type": "url", "label": "舊素材", "ref": "https://old.example.com"},
            ],
            "handoff.meeting_next_actions": ["寫提案 · Alice · 期限 4/25"],
            "handoff.next_actions": ["舊人工待辦"],
        }},
    )

    r = client.put(
        f"/projects/{pid}/handoff",
        json={
            "goal": "只更新人工交棒卡",
            "asset_refs": [{"type": "url", "label": "新素材", "ref": "https://new.example.com"}],
            "next_actions": ["PM 確認需求"],
        },
        headers={"X-User-Email": "pm@chengfu.local"},
    )
    assert r.status_code == 200

    proj = main_mod.db.projects.find_one({"_id": ObjectId(pid)})
    handoff = proj["handoff"]
    assert handoff["goal"] == "只更新人工交棒卡"
    assert handoff["site_issues"] == ["入口有高差"]
    assert handoff["site_venue"] == "松菸 4 號倉庫"
    assert handoff["workflow_draft"]["preset_id"] == "tender-full"
    assert {"type": "url", "label": "新素材", "ref": "https://new.example.com"} in handoff["asset_refs"]
    assert {"type": "url", "label": "舊素材", "ref": "https://old.example.com"} not in handoff["asset_refs"]
    assert {"type": "note", "label": "場勘彙整", "ref": "室內 · 50 坪"} in handoff["site_asset_refs"]
    assert "舊人工待辦" not in handoff["next_actions"]
    assert "寫提案 · Alice · 期限 4/25" in handoff["meeting_next_actions"]
    assert "PM 確認需求" in handoff["next_actions"]

    r = client.get(f"/projects/{pid}/handoff", headers={"X-User-Email": "pm@chengfu.local"})
    merged = r.json()["handoff"]
    assert {"type": "note", "label": "場勘彙整", "ref": "室內 · 50 坪"} in merged["asset_refs"]
    assert "寫提案 · Alice · 期限 4/25" in merged["next_actions"]


def test_handoff_card_forbids_non_owner(client):
    """知道 project id 也不能改別人的交棒卡"""
    r = client.post(
        "/projects",
        json={"name": "owner only"},
        headers={"X-User-Email": "alice@chengfu.local"},
    )
    pid = r.json()["id"]

    r = client.put(
        f"/projects/{pid}/handoff",
        json={"goal": "偷改"},
        headers={"X-User-Email": "bob@chengfu.local"},
    )
    assert r.status_code == 403


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


def test_project_collaborator_can_access_and_update_handoff(client):
    """vNext · project collaborators 是真正協作邊界,不是只顯示在 UI"""
    r = client.post(
        "/projects",
        json={
            "name": "collab handoff project",
            "collaborators": ["bob@chengfu.local"],
            "next_owner": "bob@chengfu.local",
        },
        headers={"X-User-Email": "alice@chengfu.local"},
    )
    assert r.status_code == 200
    pid = r.json()["id"]

    r = client.get("/projects", headers={"X-User-Email": "bob@chengfu.local"})
    assert r.status_code == 200
    assert any(p["_id"] == pid for p in r.json())

    r = client.put(
        f"/projects/{pid}/handoff",
        json={"goal": "Bob 接手整理送件清單"},
        headers={"X-User-Email": "bob@chengfu.local"},
    )
    assert r.status_code == 200

    r = client.get(f"/projects/{pid}/handoff", headers={"X-User-Email": "bob@chengfu.local"})
    assert r.status_code == 200
    assert r.json()["handoff"]["goal"] == "Bob 接手整理送件清單"

    r = client.get(f"/projects/{pid}/handoff", headers={"X-User-Email": "charlie@chengfu.local"})
    assert r.status_code == 403


def test_project_collaborator_cannot_delete_project(client):
    """vNext · 協作者可交棒,但專案刪除仍保留給 owner/admin."""
    r = client.post(
        "/projects",
        json={
            "name": "collab protected delete",
            "collaborators": ["bob@chengfu.local"],
            "next_owner": "bob@chengfu.local",
        },
        headers={"X-User-Email": "alice@chengfu.local"},
    )
    assert r.status_code == 200
    pid = r.json()["id"]

    r = client.delete(f"/projects/{pid}", headers={"X-User-Email": "bob@chengfu.local"})
    assert r.status_code == 403

    r = client.delete(f"/projects/{pid}", headers={"X-User-Email": "alice@chengfu.local"})
    assert r.status_code == 200
    assert r.json()["deleted"] == 1


def test_handoff_append_from_chat_answer(client):
    """vNext · Chat 回答可一鍵存回專案 handoff,形成 GPT 網頁版沒有的接續閉環"""
    r = client.post(
        "/projects",
        json={"name": "chat append project"},
        headers={"X-User-Email": "pm@chengfu.local"},
    )
    pid = r.json()["id"]

    r = client.post(
        f"/projects/{pid}/handoff/append",
        json={
            "target": "next_action",
            "text": "PM 明天 10:00 前補齊預算表",
            "source_conversation_id": "conv-chat-1",
        },
        headers={"X-User-Email": "pm@chengfu.local"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True

    r = client.post(
        f"/projects/{pid}/handoff/append",
        json={
            "target": "asset_ref",
            "label": "AI 回答摘要",
            "text": "建議書應先補受眾分層與 KPI",
            "source_conversation_id": "conv-chat-1",
        },
        headers={"X-User-Email": "pm@chengfu.local"},
    )
    assert r.status_code == 200

    r = client.get(f"/projects/{pid}/handoff", headers={"X-User-Email": "pm@chengfu.local"})
    h = r.json()["handoff"]
    assert "PM 明天 10:00 前補齊預算表" in h["next_actions"]
    assert {"type": "note", "label": "AI 回答摘要", "ref": "建議書應先補受眾分層與 KPI"} in h["asset_refs"]
    assert h["source_conversation_id"] == "conv-chat-1"


# ============================================================
# C · 回饋收集
# ============================================================
def test_create_feedback(client):
    """R7#4 · /feedback 必須登入 · 用 X-User-Email header 才行"""
    r = client.post("/feedback",
        json={
            "message_id": "msg_001",
            "agent_name": "🎯 投標顧問",
            "verdict": "up",
            "note": "建議書結構很清楚",
            "user_email": "test@chengfu.local",
        },
        headers={"X-User-Email": "test@chengfu.local"},
    )
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


def test_admin_storage_stats_shape(client):
    """P2 · admin 可看 Mongo collection/storage health,用於交付後維運。"""
    r = client.get("/admin/storage-stats", headers={"X-User-Email": "sterio068@gmail.com"})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "totals" in body
    assert body["totals"]["documents"] >= 0
    project_item = next(i for i in body["items"] if i["collection"] == "projects")
    assert "count" in project_item
    assert "index_count" in project_item
    assert "alert_level" in project_item


def test_admin_storage_stats_requires_admin(client):
    """P2 · storage stats 屬維運資訊,一般使用者不可讀。"""
    r = client.get("/admin/storage-stats")
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
    # v1.3 batch6 · M-1 · response 不再回 triggers list(防 attacker enumerate pattern)
    # 改驗 hit_count
    assert r.json()["hit_count"] > 0


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
# v1.3 A3 · CRITICAL C-3 · L3 server-side wall + audit
# ============================================================
def test_l3_preflight_safe_content_passes(client):
    """L1/L2 內容 · preflight 直接 allowed=True · 不 audit"""
    r = client.post("/safety/l3-preflight", json={"text": "幫我寫一段中秋節祝福"})
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is True
    assert body["hit_count"] == 0


def test_l3_preflight_l3_audit_only_default(client):
    """L3 內容 · 預設 audit-only · 回 200 + warning · 不擋"""
    import os
    os.environ.pop("L3_HARD_STOP", None)  # 確保關
    r = client.post("/safety/l3-preflight", json={"text": "請分析選情 · 候選人策略"})
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is True
    assert body["level"] == "03"
    assert body["hit_count"] > 0
    assert "warning" in body


def test_l3_preflight_hard_stop_blocks(client, monkeypatch):
    """L3_HARD_STOP=1 + L3 內容 · 回 403 擋送"""
    monkeypatch.setenv("L3_HARD_STOP", "1")
    r = client.post("/safety/l3-preflight", json={"text": "內定廠商評審名單"})
    assert r.status_code == 403
    body = r.json()
    assert body["detail"]["reason"] == "L3_HARD_STOP_ENABLED"


def test_l3_preflight_writes_audit_log(client):
    """L3 偵測時 audit_log 必寫(用 verified cookie or fallback header)"""
    from main import audit_col
    before = audit_col.count_documents({"action": "l3_send_attempt"})
    r = client.post("/safety/l3-preflight",
        json={"text": "客戶機敏帳戶資料"},
        headers={"X-User-Email": "user@chengfu.local"},
    )
    assert r.status_code == 200
    after = audit_col.count_documents({"action": "l3_send_attempt"})
    assert after == before + 1


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
    """prompt < 4 字 → 422 pydantic validation
    v1.2 §11.1 B-1.5 · design.py 改 require_user_dep · 必須帶 X-User-Email 才到 validation"""
    r = client.post("/design/recraft", json={"prompt": "abc"},
                    headers={"X-User-Email": "test@chengfu.local"})
    assert r.status_code == 422


def test_design_recraft_rejects_bad_size(client):
    """image_size 不在 enum → 422"""
    r = client.post("/design/recraft", json={
        "prompt": "a reasonable prompt here",
        "image_size": "ultra_wide_xyz",
    }, headers={"X-User-Email": "test@chengfu.local"})
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
    assert body.get("provider") == "fal"  # v1.2 多 provider · Fal 路徑


def test_design_openai_provider_success(client, monkeypatch):
    """v1.2 · IMAGE_PROVIDER=openai · gpt-image-2 同步路徑(不 queue)"""
    import main as main_mod

    class FakeResp:
        def __init__(self, status_code, data):
            self.status_code = status_code
            self._data = data
            self.text = str(data)
        def json(self): return self._data

    class FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, url, **kw):
            # OpenAI /v1/images/generations
            assert "images/generations" in url
            payload = kw.get("json", {})
            assert payload.get("model") == "gpt-image-2"
            assert payload.get("n") == 3
            return FakeResp(200, {
                "created": 1745400000,
                "data": [
                    {"b64_json": "iVBORw0KGgo="},
                    {"b64_json": "iVBORw0KGgo="},
                    {"b64_json": "iVBORw0KGgo="},
                ],
            })
        async def get(self, *a, **kw): raise AssertionError("OpenAI 路徑不該 GET")

    import routers.design as design_mod
    # Mongo settings IMAGE_PROVIDER=openai · OPENAI_API_KEY=fake
    main_mod.db.system_settings.delete_many({})
    main_mod.db.system_settings.insert_many([
        {"name": "IMAGE_PROVIDER", "value": "openai"},
        {"name": "OPENAI_API_KEY", "value": "sk-fake-openai"},
    ])
    monkeypatch.setattr(design_mod.httpx, "AsyncClient", FakeClient)

    r = client.post("/design/recraft",
        json={"prompt": "中秋節品牌主視覺 橘黃調", "image_size": "square_hd"},
        headers={"X-User-Email": "user@chengfu.local"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body.get("provider") == "openai"
    assert len(body["images"]) == 3  # Q7 · 3 張
    # OpenAI 回 b64 · design router 轉 data URL
    assert body["images"][0]["url"].startswith("data:image/png;base64,")
    assert body["images"][0]["b64"] is True

    # 清 Mongo 不影響其他 test
    main_mod.db.system_settings.delete_many({})


def test_design_openai_no_key_503(client, monkeypatch):
    """v1.2 · IMAGE_PROVIDER=openai 但 OPENAI_API_KEY 未設 → 503"""
    import main as main_mod
    main_mod.db.system_settings.delete_many({})
    main_mod.db.system_settings.insert_one({"name": "IMAGE_PROVIDER", "value": "openai"})
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    r = client.post("/design/recraft",
        json={"prompt": "test openai no key", "image_size": "square_hd"},
        headers={"X-User-Email": "user@chengfu.local"},
    )
    assert r.status_code == 503
    detail = r.json().get("detail", {})
    assert "OPENAI_API_KEY" in detail.get("friendly_message", "") or "未設定" in detail.get("friendly_message", "")
    main_mod.db.system_settings.delete_many({})


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


def test_knowledge_read_api_requires_login(client, tmp_source_dir):
    """知識庫名稱 / 搜尋 / 讀檔都屬內部資料 · 未登入不可讀"""
    r = client.post(
        "/admin/sources",
        json={"name": "auth required test", "path": tmp_source_dir},
        headers=ADMIN_HEADERS,
    )
    sid = r.json()["id"]
    no_user = {"X-User-Email": ""}

    assert client.get("/knowledge/list", headers=no_user).status_code == 403
    assert client.get("/knowledge/search?q=建議書", headers=no_user).status_code == 403
    assert client.get(
        f"/knowledge/read?source_id={sid}&rel_path=readme.md",
        headers=no_user,
    ).status_code == 403


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
# ROADMAP §10.3 · X-Agent-Num server-side derivation(R7#11 + R8#9)
# ============================================================
def test_agent_num_derive_from_conversation_id(client, tmp_source_dir):
    """§10.3 · 給 conversation_id · server 反查 LibreChat agent → derive #NN"""
    import main as main_mod
    # 建一個有 agent_access 限制的 source
    r = client.post(
        "/admin/sources",
        json={"name": "投標機敏", "path": tmp_source_dir, "agent_access": ["11"]},
        headers=ADMIN_HEADERS,
    )

    # 手動 seed mongomock convos + agents
    main_mod.convos_col.insert_one({
        "conversationId": "test-convo-001",
        "agent_id": "agent_xxx_test",
    })
    main_mod.db.agents.insert_one({
        "id": "agent_xxx_test",
        "name": "🎯 投標 #11 · 招標須知解析器",
        "description": "投標 Workspace 第 11 號助手",
    })

    # 清 cache 防干擾
    from routers import knowledge as _kr
    _kr._AGENT_NUM_FROM_CONVO_CACHE.clear()

    # 帶 conversation_id 的 user · derive 應拿到 "11" · 看得到 source
    r = client.get("/knowledge/list?conversation_id=test-convo-001")
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["sources"]]
    assert "投標機敏" in names


def test_agent_num_spoof_via_header_blocked_in_prod(client, tmp_source_dir, monkeypatch):
    """§10.3 · prod mode + 沒 conversation_id · X-Agent-Num header 被忽略
    user 改 header = 11 也拿不到 source"""
    import main as main_mod
    r = client.post(
        "/admin/sources",
        json={"name": "機敏勿擾", "path": tmp_source_dir, "agent_access": ["11"]},
        headers=ADMIN_HEADERS,
    )

    # 強制 prod mode · _legacy_auth_headers_enabled() → False
    monkeypatch.setenv("ECC_ENV", "production")
    monkeypatch.setenv("ALLOW_LEGACY_AUTH_HEADERS", "0")
    from routers import knowledge as _kr
    _kr._AGENT_NUM_FROM_CONVO_CACHE.clear()
    _kr._AGENT_FORBIDDEN_CACHE["ts"] = 0.0  # 清 cache

    # 攻擊者只送 X-Agent-Num · 沒 conversation_id · prod mode 完全忽略 header;
    # v1.3 hardening 後 knowledge API 也必須先登入,因此直接 403。
    r = client.get("/knowledge/list", headers={"X-Agent-Num": "11"})
    assert r.status_code == 403


def test_agent_num_derive_unknown_conversation_returns_none(client, tmp_source_dir):
    """§10.3 · conversation_id 不存在 · derive 回 None · 沒 agent_access 的 source 仍可見"""
    import main as main_mod
    r = client.post(
        "/admin/sources",
        json={"name": "公開測試 §10.3", "path": tmp_source_dir, "agent_access": []},
        headers=ADMIN_HEADERS,
    )
    from routers import knowledge as _kr
    _kr._AGENT_NUM_FROM_CONVO_CACHE.clear()
    r = client.get("/knowledge/list?conversation_id=nonexistent-xyz")
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["sources"]]
    assert "公開測試 §10.3" in names


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
    # R27 · 必須清掉 fixture 預設 X-User-Email · 模擬真匿名
    r = client.get("/design/history", headers={"X-User-Email": ""})
    assert r.status_code == 403


# ============================================================
# Codex R6#5 · auth contract tests · 防 R5/R6 風險回歸
# ============================================================
def test_auth_design_recraft_blocks_anonymous(client):
    """R6#3 · 任何人 curl /design/recraft 不帶 email → 403 · 不能爆 Fal 預算"""
    r = client.post("/design/recraft", json={
        "prompt": "anonymous attempt to burn fal credits",
        "image_size": "square_hd",
    }, headers={"X-User-Email": ""})  # R27 · 清匿名
    assert r.status_code == 403


def test_auth_tenders_blocks_anonymous(client):
    """R6#4 · /tender-alerts 改 require user · 防外部偵察承富業務"""
    r = client.get("/tender-alerts", headers={"X-User-Email": ""})  # R27 · 清匿名
    assert r.status_code == 403


def test_tender_monitor_settings_roundtrip(client):
    r = client.put("/tender-alerts/settings", json={
        "enabled": True,
        "keywords": ["活動", "行銷", "活動"],
        "counties": ["臺北市", "新北市"],
        "units": ["文化局"],
        "exclude_keywords": ["工程"],
        "daily_hour": 8,
        "auto_import_interested": False,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["keywords"] == ["活動", "行銷"]
    assert body["counties"] == ["臺北市", "新北市"]
    assert body["units"] == ["文化局"]
    assert body["daily_hour"] == 8

    r = client.get("/tender-alerts/settings")
    assert r.status_code == 200
    assert r.json()["exclude_keywords"] == ["工程"]


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


def test_auth_feedback_blocks_anonymous(client):
    """R7#4 · 沒有 trusted_email 時 · 即使 body 自己塞 user_email 也擋
    防匿名偽造 feedback 給競爭對手做負評刷"""
    r = client.post("/feedback",
        json={"message_id": "anon_attack", "verdict": "down",
              "note": "這個 agent 很爛", "user_email": "victim@chengfu.local"},
        headers={"X-User-Email": ""},  # R27 · 清 fixture 預設 · 模擬真匿名
    )
    assert r.status_code == 403
    # 驗:DB 不該有這筆
    import main as main_mod
    fb = main_mod.feedback_col.find_one({"message_id": "anon_attack"})
    assert fb is None


def test_auth_quota_preflight_dev_mode_passes_anonymous(client):
    """R7#9 · /quota/preflight nginx auth_request 用
    dev mode(沒設 ECC_ENV=production)· 沒 user 時應放行 · 給 launcher 開發空間"""
    r = client.get("/quota/preflight")
    assert r.status_code == 204


def test_auth_quota_preflight_returns_204_when_within_budget(client):
    """R7#9 · 有 user + 在預算內 → 204"""
    r = client.get("/quota/preflight", headers={"X-User-Email": "test@chengfu.local"})
    assert r.status_code in (204, 429)  # 預算 logic 視 admin_metrics 而定 · 不該 401/403


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


# ============================================================
# 技術債#5 · PDPA delete-on-request
# ============================================================
def test_pdpa_dry_run_counts(client):
    """admin POST /admin/users/{email}/delete-all dry_run=true · 只算 count 不刪"""
    import main as main_mod
    from datetime import datetime, timezone
    target = "leaving@chengfu.local"
    # seed 跨 collection 假資料
    main_mod.db.user_preferences.insert_one(
        {"user_email": target, "key": "tone", "value": "formal",
         "updated_at": datetime.now(timezone.utc)})
    main_mod.feedback_col.insert_one(
        {"message_id": "x", "user_email": target, "verdict": "up",
         "created_at": datetime.now(timezone.utc)})
    main_mod.db.scheduled_posts.insert_one(
        {"author": target, "platform": "facebook", "content": "x",
         "schedule_at": datetime.now(timezone.utc), "status": "queued"})
    main_mod.db.crm_leads.insert_one(
        {"title": "lead", "owner": target, "stage": "lead"})

    r = client.post(
        f"/admin/users/{target}/delete-all",
        json={"confirm_email": target, "dry_run": True},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dry_run"] is True
    assert body["counts"]["user_preferences"] >= 1
    assert body["counts"]["feedback"] >= 1
    assert body["counts"]["scheduled_posts"] >= 1
    # R30 · 命名 col_unset_field 因為一個 col 可有多個欄位被清
    assert body["counts"]["crm_leads_unset_owner"] >= 1
    # dry_run · 資料應仍在
    assert main_mod.db.user_preferences.count_documents({"user_email": target}) >= 1


def test_pdpa_real_delete(client):
    """admin POST dry_run=false · 真刪 + 多 col owner/by/created_by unset · audit 記下
    R30 補:7 額外漏網欄位(knowledge_sources/projects/handoff/stage_history/notes[]/agent editor/system)
    """
    import main as main_mod
    from datetime import datetime, timezone
    target = "real-delete@chengfu.local"
    # 刪除類 sample
    main_mod.db.user_preferences.insert_one(
        {"user_email": target, "key": "lang", "value": "tw"})
    main_mod.db.design_jobs.insert_one(
        {"user": target, "prompt_preview": "client A", "created_at": datetime.now(timezone.utc)})
    main_mod.db.agent_overrides.insert_one(
        {"user_email": target, "agent_num": "01", "prompt": "x"})
    # 切關聯類 sample
    main_mod.db.crm_leads.insert_one(
        {"title": "real lead", "owner": target, "stage": "lead",
         "notes": [{"text": "n1", "by": target, "at": "2026-04-01"}]})
    main_mod.db.media_pitch_history.insert_one(
        {"contact_id": "x", "pitched_by": target, "topic": "y"})
    main_mod.db.media_contacts.insert_one(
        {"name": "記者 A", "outlet": "中時", "created_by": target})
    # R30 補 · 7 漏網欄位
    main_mod.db.knowledge_sources.insert_one(
        {"name": "kbA", "path": "/x", "created_by": target})
    main_mod.db.projects.insert_one(
        {"name": "projA", "owner": target,
         "handoff": {"goal": "g", "updated_by": target}})
    main_mod.db.crm_stage_history.insert_one(
        {"lead_id": "L1", "old_stage": "lead", "new_stage": "won", "changed_by": target})
    main_mod.db.agent_overrides.insert_one(
        {"agent_num": "01", "user_email": "other@x.com", "editor": target, "prompt": "g"})
    main_mod.db.system_settings.insert_one(
        {"key": "x", "value": "y", "updated_by": target})

    r = client.post(
        f"/admin/users/{target}/delete-all",
        json={"confirm_email": target, "dry_run": False},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dry_run"] is False
    # 刪除類 · 真刪
    assert main_mod.db.user_preferences.count_documents({"user_email": target}) == 0
    assert main_mod.db.design_jobs.count_documents({"user": target}) == 0
    assert main_mod.db.agent_overrides.count_documents({"user_email": target}) == 0
    # 切關聯類 · 資料留 · 個人欄被清
    assert main_mod.db.crm_leads.find_one({"title": "real lead"})["owner"] is None
    assert main_mod.db.media_pitch_history.find_one({"contact_id": "x"})["pitched_by"] is None
    assert main_mod.db.media_contacts.find_one({"name": "記者 A"})["created_by"] is None
    # R30 補 · 7 漏網欄位驗收
    assert main_mod.db.knowledge_sources.find_one({"name": "kbA"})["created_by"] is None
    proj = main_mod.db.projects.find_one({"name": "projA"})
    assert proj["owner"] is None
    assert proj["handoff"]["updated_by"] is None
    assert main_mod.db.crm_stage_history.find_one({"lead_id": "L1"})["changed_by"] is None
    other_override = main_mod.db.agent_overrides.find_one({"user_email": "other@x.com"})
    assert other_override["editor"] is None  # 別人的設定資料留 · editor 殘 email 清
    assert main_mod.db.system_settings.find_one({"key": "x"})["updated_by"] is None
    # crm_leads.notes[].by · array element
    notes = main_mod.db.crm_leads.find_one({"title": "real lead"})["notes"]
    assert notes[0]["by"] is None, "notes[].by 必清"
    # audit 記下
    audit = main_mod.audit_col.find_one({"action": "pdpa_delete", "resource": target})
    assert audit is not None, "PDPA audit 必寫 main.audit_col(db.audit_log)"


def test_pdpa_includes_tender_alerts_reviewed_by(client):
    """R31#1 · tender_alerts.reviewed_by 漏 · 真刪後仍殘 target email"""
    import main as main_mod
    target = "tender-reviewer@chengfu.local"
    main_mod.db.tender_alerts.insert_one(
        {"tender_key": "T123", "title": "x", "status": "interested",
         "reviewed_by": target}
    )
    r = client.post(
        f"/admin/users/{target}/delete-all",
        json={"confirm_email": target, "dry_run": False},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200, r.text
    # tender 資料留 · reviewed_by 清
    t = main_mod.db.tender_alerts.find_one({"tender_key": "T123"})
    assert t is not None
    assert t["reviewed_by"] is None, "tender_alerts.reviewed_by 必清"


def test_pdpa_case_insensitive(client):
    """R31#3 · target email 規範化 lower · 但 legacy 資料可能存大小寫混合
    必 case-insensitive 才不漏"""
    import main as main_mod
    # 故意存 mixed case · 模擬 legacy 資料
    target = "case-test@chengfu.local"
    main_mod.db.user_preferences.insert_one(
        {"user_email": "Case-Test@ChengFu.Local", "key": "lang", "value": "en"}
    )
    main_mod.db.crm_leads.insert_one(
        {"title": "lead-mixed", "owner": "Case-Test@ChengFu.Local", "stage": "lead"}
    )
    r = client.post(
        f"/admin/users/{target}/delete-all",
        json={"confirm_email": target, "dry_run": False},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200, r.text
    # mixed-case 必清
    assert main_mod.db.user_preferences.count_documents(
        {"user_email": "Case-Test@ChengFu.Local"}
    ) == 0, "case-insensitive 必清 legacy mixed-case"
    assert main_mod.db.crm_leads.find_one({"title": "lead-mixed"})["owner"] is None


def test_pii_audit_writes_log(client):
    """R29 紅 · /safety/pii-audit 須真寫 audit_log
    原 __import__ datetime + bare except 吞掉 NameError · audit 從未寫"""
    import main as main_mod
    before = main_mod.audit_col.count_documents({"action": "pii_warning_dismissed"})
    r = client.post(
        "/safety/pii-audit",
        json={"text": "我的 email test@example.com · 手機 0912345678"},
        headers={"X-User-Email": "user@chengfu.local"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["audited"] is True
    assert body["hit_count"] >= 1
    after = main_mod.audit_col.count_documents({"action": "pii_warning_dismissed"})
    assert after == before + 1, "audit_log 必須真寫(R29 修)"


def test_pdpa_confirm_email_mismatch(client):
    """confirm_email 不匹配 → 400(防 mis-click)"""
    r = client.post(
        "/admin/users/oops@chengfu.local/delete-all",
        json={"confirm_email": "wrong@chengfu.local", "dry_run": True},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 400
    assert "confirm_email" in r.json()["detail"]


def test_pdpa_admin_cannot_self_delete(client):
    """admin 不能刪自己 · 防 lockout"""
    r = client.post(
        "/admin/users/sterio068@gmail.com/delete-all",
        json={"confirm_email": "sterio068@gmail.com", "dry_run": True},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 400
    assert "admin 不能刪自己" in r.json()["detail"]


# ============================================================
# 技術債#6 · router-wide auth contract tests · 防有人移除 dependencies 後沒人發現
# (R27#2 加 require_user_dep · 沒對應測 · 將來改 deps 不會被擋)
# ============================================================
def test_anonymous_blocked_on_accounting(client):
    """R27#2 · /accounts 沒登入 → 403"""
    r = client.get("/accounts", headers={"X-User-Email": ""})
    assert r.status_code == 403


def test_anonymous_blocked_on_projects(client):
    """R27#2 · /projects 沒登入 → 403"""
    r = client.get("/projects", headers={"X-User-Email": ""})
    assert r.status_code == 403


def test_anonymous_blocked_on_crm(client):
    """R27#2 · /crm/leads 沒登入 → 403"""
    r = client.get("/crm/leads", headers={"X-User-Email": ""})
    assert r.status_code == 403


def test_crm_import_from_tenders_sets_owner(client):
    import main as main_mod
    key = "文化局:CRM-IMPORT-OWNER"
    main_mod.db.tender_alerts.delete_many({"tender_key": key})
    main_mod.db.crm_leads.delete_many({"tender_key": key})
    main_mod.db.tender_alerts.insert_one({
        "tender_key": key,
        "title": "文化活動委託案",
        "unit_name": "臺北市文化局",
        "keyword": "活動",
        "status": "interested",
    })
    r = client.post("/crm/import-from-tenders")
    assert r.status_code == 200
    lead = main_mod.db.crm_leads.find_one({"tender_key": key})
    assert lead["owner"] == "test@chengfu.local"


def test_crm_note_accepts_json_body(client):
    r = client.post("/crm/leads", json={
        "title": "文化節提案",
        "client": "文化局",
        "budget": 500000,
    })
    assert r.status_code == 200
    lead_id = r.json()["id"]
    r = client.post(f"/crm/leads/{lead_id}/notes", json={"note": "已電話確認截止日"})
    assert r.status_code == 200
    import main as main_mod
    lead = main_mod.db.crm_leads.find_one({"title": "文化節提案"})
    assert lead["notes"][-1]["text"] == "已電話確認截止日"


def test_healthz_remains_public(client):
    """技術債#2 · /healthz 必須匿名(docker / nginx 每分鐘打)
    抽 router 後不能誤套 require_user_dep"""
    r = client.get("/healthz", headers={"X-User-Email": ""})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ============================================================
# C2(v1.3)· /admin/audit-log filter + distinct actions
# ============================================================
def test_audit_log_action_filter_single(client):
    """C2 · ?action=xxx 單一 action 過濾"""
    import main as main_mod
    from datetime import datetime, timezone
    # seed 不同 action 的 audit
    for action in ["test_a", "test_a", "test_b"]:
        main_mod.audit_col.insert_one(
            {"action": action, "user": "x", "resource": "y",
             "created_at": datetime.now(timezone.utc)}
        )
    r = client.get("/admin/audit-log?action=test_a", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    # 全部 items 都該 test_a
    assert all(i["action"] == "test_a" for i in body["items"])
    assert body["total"] >= 2


def test_audit_log_action_filter_multi(client):
    """C2 · ?action=a,b 多 action 過濾(逗號分隔 · pdpa_delete + dryrun 一起看)"""
    import main as main_mod
    from datetime import datetime, timezone
    for action in ["multi_a", "multi_b", "multi_c"]:
        main_mod.audit_col.insert_one(
            {"action": action, "user": "x", "resource": "y",
             "created_at": datetime.now(timezone.utc)}
        )
    r = client.get("/admin/audit-log?action=multi_a,multi_b", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    actions = {i["action"] for i in r.json()["items"]}
    assert "multi_c" not in actions  # 沒被選的不該出現
    assert actions <= {"multi_a", "multi_b"}


def test_audit_log_actions_distinct_endpoint(client):
    """C2 · GET /admin/audit-log/actions · 列 distinct + count · sort by count desc
    R35 · 加 days/returned_count/truncated 欄位驗收"""
    import main as main_mod
    from datetime import datetime, timezone
    # seed · pop_a 5 筆 · pop_b 3 筆 · pop_c 1 筆
    for _ in range(5):
        main_mod.audit_col.insert_one(
            {"action": "pop_a", "user": "x", "created_at": datetime.now(timezone.utc)}
        )
    for _ in range(3):
        main_mod.audit_col.insert_one(
            {"action": "pop_b", "user": "x", "created_at": datetime.now(timezone.utc)}
        )
    main_mod.audit_col.insert_one(
        {"action": "pop_c", "user": "x", "created_at": datetime.now(timezone.utc)}
    )
    r = client.get("/admin/audit-log/actions", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    actions_dict = {a["action"]: a["count"] for a in body["actions"]}
    assert actions_dict["pop_a"] >= 5
    assert actions_dict["pop_b"] >= 3
    assert actions_dict["pop_c"] >= 1
    # sort by count desc · pop_a 應在 pop_b 之前
    pop_a_idx = next(i for i, a in enumerate(body["actions"]) if a["action"] == "pop_a")
    pop_b_idx = next(i for i, a in enumerate(body["actions"]) if a["action"] == "pop_b")
    assert pop_a_idx < pop_b_idx, "should sort by count desc"
    # R35 · 新欄位
    assert body["returned_count"] == len(body["actions"])
    assert body["limit"] == 50
    assert body["truncated"] is False
    assert body["days"] == 90  # default


def test_audit_log_actions_days_param_filter(client):
    """R35 · ?days=1 只看最近 1 天 · 老資料(91 天前)應排除"""
    import main as main_mod
    from datetime import datetime, timezone, timedelta
    # 91 天前的舊資料
    main_mod.audit_col.insert_one(
        {"action": "old_only_action", "user": "x",
         "created_at": datetime.now(timezone.utc) - timedelta(days=91)}
    )
    # 今天
    main_mod.audit_col.insert_one(
        {"action": "fresh_only_action", "user": "x",
         "created_at": datetime.now(timezone.utc)}
    )
    r = client.get("/admin/audit-log/actions?days=1", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    actions = {a["action"] for a in r.json()["actions"]}
    assert "fresh_only_action" in actions
    assert "old_only_action" not in actions, "days=1 必排除 91 天前資料"


def test_audit_log_actions_requires_admin(client):
    """C2 · /admin/audit-log/actions 必須 admin · 不能匿名打"""
    r = client.get("/admin/audit-log/actions", headers={"X-User-Email": ""})
    assert r.status_code == 403


def test_admin_metrics_days_bounded(client):
    """R37 · /admin/cost /adoption /top-users days 加上下限 · 防裸 int 探勘
    days=0 / 999 應 422"""
    for path in ["/admin/cost", "/admin/adoption", "/admin/top-users"]:
        # days=0 應 422
        r = client.get(f"{path}?days=0", headers=ADMIN_HEADERS)
        assert r.status_code == 422, f"{path}?days=0 應 422 (ge=1)"
        # days=999 應 422
        r = client.get(f"{path}?days=999", headers=ADMIN_HEADERS)
        assert r.status_code == 422, f"{path}?days=999 應 422 (le=365)"
        # 正常範圍應 200
        r = client.get(f"{path}?days=7", headers=ADMIN_HEADERS)
        assert r.status_code == 200, f"{path}?days=7 應 200"


def test_audit_log_default_days_window(client):
    """R36 · /admin/audit-log GET 不帶 start_date/end_date 時 · 預設 90 天窗口
    · 防 admin 透過 ?skip 探勘全 1 年 audit history"""
    import main as main_mod
    from datetime import datetime, timezone, timedelta
    # seed · 一筆 91 天前 + 一筆今天
    main_mod.audit_col.insert_one(
        {"action": "audit_old_only", "user": "x", "resource": "y",
         "created_at": datetime.now(timezone.utc) - timedelta(days=91)}
    )
    main_mod.audit_col.insert_one(
        {"action": "audit_fresh_only", "user": "x", "resource": "y",
         "created_at": datetime.now(timezone.utc)}
    )
    # 不帶 start_date/end_date · 預設 days=90 窗口
    r = client.get(
        "/admin/audit-log?action=audit_old_only,audit_fresh_only",
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    actions = {i["action"] for i in body["items"]}
    assert "audit_fresh_only" in actions
    assert "audit_old_only" not in actions, "R36 · 預設 90 天窗口必排除 91 天前資料"
    assert body["days_window"] == 90  # default 顯示

    # 顯式帶 start_date · 應覆蓋 default
    old_date = (datetime.now(timezone.utc) - timedelta(days=200)).strftime("%Y-%m-%d")
    r2 = client.get(
        f"/admin/audit-log?action=audit_old_only&start_date={old_date}",
        headers=ADMIN_HEADERS,
    )
    actions2 = {i["action"] for i in r2.json()["items"]}
    assert "audit_old_only" in actions2, "明確 start_date 應覆寫 default 窗口"
    assert r2.json()["days_window"] is None  # 不顯示 default


# ============================================================
# B5(v1.3)· LibreChat conversation + PDPA 整合
# ============================================================
def test_pdpa_librechat_user_not_found(client):
    """include_librechat=true 但 LibreChat users 沒此 email · status user_not_found"""
    target = "never-logged-in@chengfu.local"
    r = client.post(
        f"/admin/users/{target}/delete-all",
        json={"confirm_email": target, "dry_run": True, "include_librechat": True},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["librechat"] is not None
    assert body["librechat"]["status"] == "user_not_found"


def test_pdpa_librechat_dry_run_counts(client):
    """include_librechat=true dry_run · 列各 collection 的 doc 數 · 不真刪"""
    import main as main_mod
    from bson import ObjectId
    target = "alice-lc@chengfu.local"
    # seed LibreChat user + 對話 + 訊息
    uid = main_mod.db.users.insert_one({
        "email": target, "name": "Alice", "role": "USER",
    }).inserted_id
    main_mod.db.conversations.insert_one({"user": uid, "title": "test"})
    main_mod.db.conversations.insert_one({"user": uid, "title": "test2"})
    main_mod.db.messages.insert_one({"user": uid, "text": "hi"})

    r = client.post(
        f"/admin/users/{target}/delete-all",
        json={"confirm_email": target, "dry_run": True, "include_librechat": True},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    lc = r.json()["librechat"]
    assert lc["status"] == "dry_run"
    assert lc["counts"]["conversations"] == 2
    assert lc["counts"]["messages"] == 1
    # dry_run · 資料應仍在
    assert main_mod.db.conversations.count_documents({"user": uid}) == 2


def test_pdpa_librechat_real_delete_archives_first(client, tmp_path, monkeypatch):
    """include_librechat=true real · archive 寫到 tmp · 然後刪光"""
    import main as main_mod
    from datetime import datetime, timezone
    target = "bob-lc@chengfu.local"
    uid = main_mod.db.users.insert_one({"email": target, "name": "Bob", "role": "USER"}).inserted_id
    main_mod.db.conversations.insert_one({"user": uid, "title": "t1"})
    main_mod.db.messages.insert_one({"user": uid, "text": "x"})
    main_mod.db.files.insert_one({"user": uid, "filename": "a.pdf"})

    # patch archive_dir 到 tmp_path · 不污染 ~/chengfu-backups
    from services import librechat_admin
    orig_archive = librechat_admin.archive_librechat_data
    def patched(db, user_id, email, archive_dir=None):
        return orig_archive(db, user_id, email, archive_dir=str(tmp_path))
    monkeypatch.setattr(librechat_admin, "archive_librechat_data", patched)

    r = client.post(
        f"/admin/users/{target}/delete-all",
        json={"confirm_email": target, "dry_run": False, "include_librechat": True},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200, r.text
    lc = r.json()["librechat"]
    assert lc["status"] == "deleted"
    assert lc["counts"]["conversations"] == 1
    assert lc["counts"]["messages"] == 1
    assert lc["counts"]["files"] == 1
    assert lc["counts"]["users"] == 1  # user 本人也刪
    # 真刪
    assert main_mod.db.conversations.count_documents({"user": uid}) == 0
    assert main_mod.db.messages.count_documents({"user": uid}) == 0
    assert main_mod.db.users.count_documents({"_id": uid}) == 0
    # archive 檔存在
    archive_path = lc["archived_at"]
    assert archive_path
    import os
    assert os.path.exists(archive_path), f"archive 必生成 {archive_path}"


def test_pdpa_librechat_default_skipped_when_flag_off(client):
    """include_librechat=false(default)· LibreChat 不動 · 提示 librechat_warning"""
    import main as main_mod
    target = "cathy-lc@chengfu.local"
    uid = main_mod.db.users.insert_one({"email": target, "name": "Cathy"}).inserted_id
    main_mod.db.conversations.insert_one({"user": uid, "title": "stay"})

    r = client.post(
        f"/admin/users/{target}/delete-all",
        json={"confirm_email": target, "dry_run": False, "include_librechat": False},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["librechat"] is None  # 不 touch
    assert body["librechat_warning"] is not None
    assert "include_librechat=true" in body["librechat_warning"]
    # LibreChat 對話應仍在
    assert main_mod.db.conversations.count_documents({"user": uid}) == 1


def test_librechat_user_id_case_insensitive(client):
    """find_librechat_user_id · 'Bob@X.com' 應找到 'bob@x.com' user"""
    import main as main_mod
    from services import librechat_admin
    main_mod.db.users.insert_one({"email": "Mixed@Case.Com", "name": "Mix"})
    uid = librechat_admin.find_librechat_user_id(main_mod.db, "mixed@case.com")
    assert uid is not None
    uid2 = librechat_admin.find_librechat_user_id(main_mod.db, "MIXED@CASE.COM")
    assert uid2 == uid


# ============================================================
# A5(v1.3)· Social OAuth infra(無真 Meta call · v1.4 補)
# ============================================================
USER_HEADERS = {"X-User-Email": "alice@chengfu.local"}


def test_oauth_start_requires_app_credentials(client):
    """A5 · 沒設 FACEBOOK_APP_ID env → 503"""
    import os
    # 確保沒設
    os.environ.pop("FACEBOOK_APP_ID", None)
    os.environ.pop("FACEBOOK_APP_SECRET", None)
    r = client.get("/social/oauth/start?platform=facebook",
                   headers=USER_HEADERS, follow_redirects=False)
    assert r.status_code == 503
    assert "FACEBOOK_APP_ID" in r.json()["detail"]


def test_oauth_start_redirects_when_creds_present(client, monkeypatch):
    """A5 · 有 app creds → 302 redirect to platform auth + state 寫 db"""
    import main as main_mod
    monkeypatch.setenv("FACEBOOK_APP_ID", "test-app-id")
    monkeypatch.setenv("FACEBOOK_APP_SECRET", "test-app-secret")
    r = client.get("/social/oauth/start?platform=facebook",
                   headers=USER_HEADERS, follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    assert "facebook.com/v18.0/dialog/oauth" in loc
    assert "client_id=test-app-id" in loc
    assert "state=" in loc
    # state 寫進 db
    state_doc = main_mod.db.social_oauth_states.find_one(
        {"user_email": "alice@chengfu.local", "platform": "facebook"}
    )
    assert state_doc is not None


# v1.3 A3 · CRITICAL C-8 · OAuth URL encode + 不信 forwarded-host
def test_oauth_start_url_encodes_query_params(client, monkeypatch):
    """A3 · 含特殊字元的 app_id 不能破壞 query string · urlencode"""
    monkeypatch.setenv("FACEBOOK_APP_ID", "test+app&special=chars")
    monkeypatch.setenv("FACEBOOK_APP_SECRET", "secret")
    r = client.get("/social/oauth/start?platform=facebook",
                   headers=USER_HEADERS, follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    # urlencode 後 + 變 %2B · & 變 %26 · = 變 %3D
    assert "client_id=test%2Bapp%26special%3Dchars" in loc
    # 確認 state 仍是獨立 query 參數(沒被 inject 破壞)
    assert "&state=" in loc


def test_oauth_redirect_uri_uses_env_whitelist(client, monkeypatch):
    """A3 · OAUTH_REDIRECT_BASE_URL 設了就用 env · 不從 X-Forwarded-Host 取"""
    monkeypatch.setenv("FACEBOOK_APP_ID", "test-id")
    monkeypatch.setenv("FACEBOOK_APP_SECRET", "secret")
    monkeypatch.setenv("OAUTH_REDIRECT_BASE_URL", "https://chengfu-ai.com")
    # 必須 reload module 因為 _OAUTH_BASE_URL 在 import 時讀
    import importlib
    from routers import social_oauth
    importlib.reload(social_oauth)
    r = client.get(
        "/social/oauth/start?platform=facebook",
        headers={**USER_HEADERS, "X-Forwarded-Host": "evil.attacker.com"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    loc = r.headers["location"]
    # redirect_uri 必須是 env 設的 chengfu-ai.com · 不是 evil.attacker.com
    assert "chengfu-ai.com" in loc
    assert "evil.attacker.com" not in loc


def test_oauth_redirect_uri_rejects_bad_env_format(client, monkeypatch):
    """A3 · OAUTH_REDIRECT_BASE_URL 設 javascript:alert 等惡意值 · 500"""
    monkeypatch.setenv("FACEBOOK_APP_ID", "test-id")
    monkeypatch.setenv("FACEBOOK_APP_SECRET", "secret")
    monkeypatch.setenv("OAUTH_REDIRECT_BASE_URL", "javascript:alert(1)")
    import importlib
    from routers import social_oauth
    importlib.reload(social_oauth)
    r = client.get("/social/oauth/start?platform=facebook",
                   headers=USER_HEADERS, follow_redirects=False)
    assert r.status_code == 500
    assert "OAUTH_REDIRECT_BASE_URL" in r.json()["detail"]
    # cleanup · 否則影響後續 test
    monkeypatch.delenv("OAUTH_REDIRECT_BASE_URL")
    importlib.reload(social_oauth)


def test_oauth_redirect_uri_requires_env_in_prod(client, monkeypatch):
    """prod 未設固定 callback base 時應 fail closed,不再信任 forwarded host。"""
    monkeypatch.setenv("FACEBOOK_APP_ID", "test-id")
    monkeypatch.setenv("FACEBOOK_APP_SECRET", "secret")
    monkeypatch.delenv("OAUTH_REDIRECT_BASE_URL", raising=False)
    monkeypatch.setenv("ECC_ENV", "production")
    import importlib
    from routers import social_oauth
    importlib.reload(social_oauth)
    r = client.get(
        "/social/oauth/start?platform=facebook",
        headers={**USER_HEADERS, "X-Forwarded-Host": "evil.attacker.com"},
        follow_redirects=False,
    )
    assert r.status_code == 500
    assert "OAUTH_REDIRECT_BASE_URL" in r.json()["detail"]
    monkeypatch.setenv("ECC_ENV", "development")
    importlib.reload(social_oauth)


def test_oauth_callback_stores_token_mock(client, monkeypatch):
    """A5 · callback 收 code + state · mock 模擬成功 store token"""
    import main as main_mod
    from datetime import datetime, timezone, timedelta
    # seed state
    main_mod.db.social_oauth_states.insert_one({
        "state": "test-state-xyz",
        "user_email": "alice@chengfu.local",
        "platform": "facebook",
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
    })
    r = client.get("/social/oauth/callback?code=test-code&state=test-state-xyz",
                   follow_redirects=False)
    assert r.status_code == 302
    assert "/#social?connected=facebook" in r.headers["location"]
    # token 寫進 db
    token_doc = main_mod.db.social_oauth_tokens.find_one(
        {"user_email": "alice@chengfu.local", "platform": "facebook"}
    )
    assert token_doc is not None
    assert token_doc["account_id"] == "mock-facebook-account-id"
    # state 已 cleanup
    assert main_mod.db.social_oauth_states.count_documents({"state": "test-state-xyz"}) == 0


def test_oauth_callback_rejects_unknown_state(client):
    """A5 · 假 state → 400(防 CSRF)"""
    r = client.get("/social/oauth/callback?code=x&state=fake-state-not-in-db",
                   follow_redirects=False)
    assert r.status_code == 400


def test_oauth_callback_rejects_expired_state(client):
    """A5 · state 過期(>10 min)→ 400 + cleanup"""
    import main as main_mod
    from datetime import datetime, timezone, timedelta
    main_mod.db.social_oauth_states.insert_one({
        "state": "expired-state",
        "user_email": "alice@chengfu.local",
        "platform": "facebook",
        "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
    })
    r = client.get("/social/oauth/callback?code=x&state=expired-state",
                   follow_redirects=False)
    assert r.status_code == 400
    assert main_mod.db.social_oauth_states.count_documents({"state": "expired-state"}) == 0


def test_oauth_disconnect(client):
    """A5 · POST disconnect 刪 token(用 instagram 避免跟 callback test 撞)"""
    import main as main_mod
    main_mod.db.social_oauth_tokens.insert_one({
        "user_email": "alice@chengfu.local",
        "platform": "instagram",
        "access_token_encrypted": "PLAIN:fake-ig-token",
    })
    r = client.post("/social/oauth/disconnect?platform=instagram", headers=USER_HEADERS)
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    assert main_mod.db.social_oauth_tokens.count_documents(
        {"user_email": "alice@chengfu.local", "platform": "instagram"}
    ) == 0


def test_oauth_status_admin_only(client):
    """A5 · /social/oauth/status 必 admin · 不能匿名/一般 user"""
    r = client.get("/social/oauth/status", headers={"X-User-Email": ""})
    assert r.status_code == 403


def test_oauth_status_lists_connections(client):
    """A5 · admin 看到所有同事連的 platform · 不回 token"""
    import main as main_mod
    from datetime import datetime, timezone
    main_mod.db.social_oauth_tokens.insert_one({
        "user_email": "alice@chengfu.local",
        "platform": "facebook",
        "access_token_encrypted": "PLAIN:secret",
        "account_id": "fb-1",
        "account_name": "Alice FB",
        "expires_at": datetime.now(timezone.utc),
        "connected_at": datetime.now(timezone.utc),
        "last_refreshed_at": datetime.now(timezone.utc),
        "scopes": ["pages_manage_posts"],
    })
    r = client.get("/social/oauth/status", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    conns = r.json()["connections"]
    assert any(c["user_email"] == "alice@chengfu.local"
               and c["platform"] == "facebook" for c in conns)
    # 不該回 token 本身
    for c in conns:
        assert "access_token" not in c
        assert "access_token_encrypted" not in c


def test_oauth_token_encrypt_decrypt_roundtrip():
    """A5 · encrypt → decrypt 來回一致 · 沒 CREDS_KEY 退化 PLAIN: 前綴"""
    from services import oauth_tokens
    plain = "secret-token-123"
    enc = oauth_tokens.encrypt_token(plain)
    dec = oauth_tokens.decrypt_token(enc)
    assert dec == plain


def test_oauth_token_plaintext_fallback_rejected_in_prod(monkeypatch):
    from services import oauth_tokens
    monkeypatch.delenv("CREDS_KEY", raising=False)
    monkeypatch.setenv("ECC_ENV", "production")
    with pytest.raises(RuntimeError, match="CREDS_KEY required"):
        oauth_tokens.encrypt_token("secret-token-123")


# ============================================================
# v1.3 · User Management UI · admin 在前端建同仁帳號
# ============================================================
def test_um_get_permission_catalog(client):
    """admin 可拿 catalog · 28 permissions + 7 presets"""
    r = client.get("/admin/users/permission-catalog", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "catalog" in body
    assert "presets" in body
    assert body["enforcement"]["mode"] == "progressive"
    assert "knowledge.manage" in body["enforcement"]["enforced_permissions"]
    assert "accounting.edit" in body["enforcement"]["enforced_permissions"]
    assert "site.survey" in body["enforcement"]["enforced_permissions"]
    # 至少 7 組 · 全部攤平至少 20 個 permission
    assert len(body["catalog"]) >= 7
    all_keys = [item["key"] for g in body["catalog"] for item in g["items"]]
    assert len(all_keys) >= 20
    # presets 包含 7 個常見頭銜
    assert "老闆 / Champion" in body["presets"]
    assert "會計 / 財務" in body["presets"]


def test_um_get_permission_catalog_user_denied(client):
    """一般 USER 不能拿 catalog"""
    r = client.get("/admin/users/permission-catalog",
                   headers={"X-User-Email": "alice@chengfu.local"})
    assert r.status_code == 403


def test_um_create_user_success(client):
    """admin 建新同仁 · 回 user 物件 · 寫 users collection"""
    import main as main_mod
    r = client.post("/admin/users", headers=ADMIN_HEADERS, json={
        "email": "newguy@chengfu.com",
        "name": "新同仁",
        "password": "super-secure-pwd-2026",
        "title": "設計師",
        "permissions": ["design.generate", "project.edit_own", "knowledge.search"],
        "role": "USER",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "newguy@chengfu.com"
    assert body["title"] == "設計師"
    assert body["role"] == "USER"
    assert len(body["permissions"]) == 3
    # DB 真有寫入
    doc = main_mod.db.users.find_one({"email": "newguy@chengfu.com"})
    assert doc is not None
    assert doc["chengfu_title"] == "設計師"
    assert doc["chengfu_active"] is True
    # 密碼不能明文
    assert doc["password"] != "super-secure-pwd-2026"
    assert doc["password"].decode("utf-8").startswith("$2")  # bcrypt


def test_um_create_user_rejects_duplicate_email(client):
    """建重複 email · 回 409"""
    client.post("/admin/users", headers=ADMIN_HEADERS, json={
        "email": "dupe@chengfu.com", "name": "A", "password": "Strong!Pass2026",
    })
    r = client.post("/admin/users", headers=ADMIN_HEADERS, json={
        "email": "dupe@chengfu.com", "name": "B", "password": "Strong!Pass2026",
    })
    assert r.status_code == 409


def test_um_create_user_rejects_invalid_permission(client):
    """不合法 permission key · 400"""
    r = client.post("/admin/users", headers=ADMIN_HEADERS, json={
        "email": "invalid@chengfu.com", "name": "X", "password": "Strong!Pass2026",
        "permissions": ["fake.permission.key"],
    })
    assert r.status_code == 400
    assert "不合法" in r.json()["detail"]


def test_um_create_user_rejects_weak_password(client):
    """密碼太短或未達複雜度 · pydantic 422"""
    r = client.post("/admin/users", headers=ADMIN_HEADERS, json={
        "email": "weak@chengfu.com", "name": "X", "password": "123",
    })
    assert r.status_code == 422


def test_um_list_users(client):
    """GET /admin/users · 列全部 · 不含密碼 hash"""
    client.post("/admin/users", headers=ADMIN_HEADERS, json={
        "email": "list-test@chengfu.com", "name": "列表測", "password": "Strong!Pass2026",
        "title": "企劃",
    })
    r = client.get("/admin/users", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    # 找剛建的
    found = [u for u in body["items"] if u["email"] == "list-test@chengfu.com"]
    assert len(found) == 1
    assert found[0]["title"] == "企劃"
    # 密碼絕對不在 response 裡
    assert "password" not in found[0]


def test_um_update_user(client):
    """PATCH /admin/users/:email · 改 title + permissions"""
    client.post("/admin/users", headers=ADMIN_HEADERS, json={
        "email": "update-me@chengfu.com", "name": "測", "password": "Strong!Pass2026",
        "title": "實習生",
    })
    r = client.patch("/admin/users/update-me@chengfu.com",
                     headers=ADMIN_HEADERS,
                     json={"title": "資深企劃",
                           "permissions": ["project.create", "press.draft"]})
    assert r.status_code == 200
    # 驗
    r2 = client.get("/admin/users", headers=ADMIN_HEADERS)
    user = [u for u in r2.json()["items"] if u["email"] == "update-me@chengfu.com"][0]
    assert user["title"] == "資深企劃"
    assert set(user["permissions"]) == {"project.create", "press.draft"}


def test_um_deactivate_user(client):
    """DELETE /admin/users/:email · soft deactivate · active=false"""
    client.post("/admin/users", headers=ADMIN_HEADERS, json={
        "email": "kill-me@chengfu.com", "name": "測", "password": "Strong!Pass2026",
    })
    r = client.delete("/admin/users/kill-me@chengfu.com", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["active"] is False
    # 預設 list 不回 inactive
    r2 = client.get("/admin/users", headers=ADMIN_HEADERS)
    emails = [u["email"] for u in r2.json()["items"]]
    assert "kill-me@chengfu.com" not in emails
    # 加 include_inactive=true 才看到
    r3 = client.get("/admin/users?include_inactive=true", headers=ADMIN_HEADERS)
    emails3 = [u["email"] for u in r3.json()["items"]]
    assert "kill-me@chengfu.com" in emails3


def test_um_admin_cannot_deactivate_self(client):
    """admin 不能停用自己 · 防 lockout"""
    r = client.delete("/admin/users/sterio068@gmail.com", headers=ADMIN_HEADERS)
    assert r.status_code == 400
    assert "lockout" in r.json()["detail"].lower()


# ============================================================
# I · Orchestrator / Workflow(vNext Phase E)
# ============================================================
def test_orchestrator_preset_detail(client):
    """Phase E · workflow preset 回傳 step 明細供前端人工確認"""
    r = client.get("/orchestrator/workflow/presets/tender-full")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "tender-full"
    assert body["mode"] == "draft_first"
    assert body["requires_human_review"] is True
    assert len(body["steps"]) >= 3
    assert body["steps"][0]["id"] == "step_0"


def test_orchestrator_prepare_preset(client):
    """Phase E · prepare 不直接送 Agent,只產生主管家草稿 prompt"""
    r = client.post(
        "/orchestrator/workflow/prepare-preset/tender-full",
        json={"initial_input": "測試標案:活動企劃與媒體宣傳"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "draft_first"
    assert body["requires_human_review"] is True
    assert "supervisor_prompt" in body
    assert "測試標案" in body["supervisor_prompt"]
    assert all(step["human_review"] is True for step in body["steps"])


def test_orchestrator_prepare_preset_can_save_project_workflow_draft(client):
    """Round 2 · workflow 仍是 draft-first,但可先寫入專案交棒卡供 PM 接續"""
    import main as main_mod
    from bson import ObjectId

    r = client.post("/projects", json={"name": "workflow draft project"})
    pid = r.json()["id"]

    r = client.post(
        "/orchestrator/workflow/prepare-preset/tender-full",
        json={
            "initial_input": "測試標案:文化局活動整合",
            "project_id": pid,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "draft_first"
    assert body["saved_to_project"]["project_id"] == pid

    proj = main_mod.db.projects.find_one({"_id": ObjectId(pid)})
    draft = proj["handoff"]["workflow_draft"]
    assert draft["preset_id"] == "tender-full"
    assert "主管家" in draft["supervisor_prompt"]
    assert draft["created_by"] == "test@chengfu.local"
    assert main_mod.db.audit_log.count_documents({
        "action": "workflow_prepare_preset",
        "resource": pid,
    }) == 1


def test_orchestrator_can_save_workflow_result_to_project(client):
    """vNext · workflow 真執行結果可沉澱成專案素材,讓工作包不是一次性 prompt."""
    import main as main_mod
    from bson import ObjectId
    from orchestrator import PRESET_WORKFLOWS, _save_workflow_result_to_project

    r = client.post("/projects", json={"name": "workflow result project"})
    pid = r.json()["id"]
    saved = _save_workflow_result_to_project(
        pid,
        "test@chengfu.local",
        "tender-full",
        PRESET_WORKFLOWS["tender-full"],
        {
            "steps_executed": 4,
            "rounds": 3,
            "final_output": "最終整合結果: 建議投標,但需補報價風險。",
            "results": [],
        },
        "507f1f77bcf86cd799439011",
    )

    assert saved["project_id"] == pid
    assert saved["handoff_field"] == "workflow_result"
    proj = main_mod.db.projects.find_one({"_id": ObjectId(pid)})
    handoff = proj["handoff"]
    assert handoff["workflow_result"]["preset_id"] == "tender-full"
    assert handoff["workflow_result"]["run_id"] == "507f1f77bcf86cd799439011"
    assert any(
        a["label"] == "Workflow 結果 · 投標完整閉環"
        and "建議投標" in a["ref"]
        for a in handoff["asset_refs"]
    )
    assert main_mod.db.audit_log.count_documents({
        "action": "workflow_run_saved_to_project",
        "resource": pid,
    }) == 1


def test_orchestrator_prepare_preset_forbids_other_project(client):
    """workflow draft 不能寫入別人的 project handoff"""
    r = client.post(
        "/projects",
        json={"name": "alice workflow project"},
        headers={"X-User-Email": "alice@chengfu.local"},
    )
    pid = r.json()["id"]

    r = client.post(
        "/orchestrator/workflow/prepare-preset/tender-full",
        json={
            "initial_input": "測試標案:跨專案偷寫",
            "project_id": pid,
        },
        headers={"X-User-Email": "bob@chengfu.local"},
    )
    assert r.status_code == 403


def test_orchestrator_prepare_preset_allows_project_collaborator(client):
    """vNext · workflow draft 可由下一棒/協作者寫入專案交棒卡."""
    import main as main_mod
    from bson import ObjectId

    r = client.post(
        "/projects",
        json={
            "name": "collab workflow project",
            "collaborators": ["bob@chengfu.local"],
            "next_owner": "bob@chengfu.local",
        },
        headers={"X-User-Email": "alice@chengfu.local"},
    )
    pid = r.json()["id"]

    r = client.post(
        "/orchestrator/workflow/prepare-preset/tender-full",
        json={
            "initial_input": "測試標案:協作者接續 workflow",
            "project_id": pid,
        },
        headers={"X-User-Email": "bob@chengfu.local"},
    )
    assert r.status_code == 200

    proj = main_mod.db.projects.find_one({"_id": ObjectId(pid)})
    assert proj["handoff"]["workflow_draft"]["created_by"] == "bob@chengfu.local"


def test_orchestrator_records_workflow_adoption(client):
    """vNext · Workflow 草稿被採用/拒絕要能進月報與學習迴路"""
    import main as main_mod

    r = client.post(
        "/projects",
        json={"name": "workflow adoption project"},
        headers={"X-User-Email": "pm@chengfu.local"},
    )
    pid = r.json()["id"]

    r = client.post(
        "/orchestrator/workflow/adoptions",
        json={
            "preset_id": "tender-full",
            "preset_name": "投標完整閉環",
            "status": "adopted",
            "project_id": pid,
            "note": "主管家草稿可直接接續",
        },
        headers={"X-User-Email": "pm@chengfu.local"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["status"] == "adopted"
    assert main_mod.db.workflow_adoptions.count_documents({
        "preset_id": "tender-full",
        "status": "adopted",
        "user": "pm@chengfu.local",
    }) == 1
    assert main_mod.db.audit_log.count_documents({
        "action": "workflow_adoption",
        "user": "pm@chengfu.local",
    }) == 1


def test_orchestrator_workflow_adoption_forbids_other_project(client):
    """workflow adoption 若綁 project_id,不可污染別人的專案採用紀錄."""
    r = client.post(
        "/projects",
        json={"name": "alice adoption project"},
        headers={"X-User-Email": "alice@chengfu.local"},
    )
    pid = r.json()["id"]

    r = client.post(
        "/orchestrator/workflow/adoptions",
        json={
            "preset_id": "tender-full",
            "status": "adopted",
            "project_id": pid,
        },
        headers={"X-User-Email": "bob@chengfu.local"},
    )
    assert r.status_code == 403


def test_orchestrator_extract_agent_text_from_sse():
    """LibreChat v0.8 /api/agents/chat SSE parser · 取最後 text"""
    from orchestrator import _extract_agent_text

    raw = (
        'data: {"text":"你"}\n\n'
        'data: {"text":"你好"}\n\n'
        'data: [DONE]\n\n'
    )
    assert _extract_agent_text(raw) == "你好"


def test_orchestrator_run_workflow_disabled_by_default(client):
    """Phase E · 直接多 Agent 執行預設關閉,避免繞過人審草稿"""
    r = client.post("/orchestrator/workflow/run", json={
        "name": "x",
        "steps": [{"agent_id": "01", "prompt_template": "{initial_input}"}],
        "initial_input": "hello",
    })
    assert r.status_code == 403
    assert "prepare-preset" in r.json()["detail"]


def test_orchestrator_run_preset_disabled_by_default(client):
    """Phase E · preset run 也預設關閉,只開 prepare-preset"""
    r = client.post(
        "/orchestrator/workflow/run-preset/tender-full",
        json={"initial_input": "測試標案"},
    )
    assert r.status_code == 403
    assert "prepare-preset" in r.json()["detail"]


# ============================================================
# J · Fine-grained permissions(vNext Round 2)
# ============================================================
def test_permission_accounting_edit_denied_without_permission(client):
    """沒有 accounting.edit 的同仁不能新增交易"""
    import main as main_mod
    main_mod.db.users.update_one(
        {"email": "noperm@chengfu.local"},
        {"$set": {
            "email": "noperm@chengfu.local",
            "role": "USER",
            "chengfu_active": True,
            "chengfu_permissions": ["knowledge.search"],
        }},
        upsert=True,
    )
    r = client.post("/transactions", headers={"X-User-Email": "noperm@chengfu.local"}, json={
        "date": "2026-04-24",
        "memo": "no permission test",
        "debit_account": "1102",
        "credit_account": "4111",
        "amount": 1,
    })
    assert r.status_code == 403
    assert "accounting.edit" in r.json()["detail"]


def test_permission_inactive_user_blocked_globally(client):
    """停用帳號即使有 permission 也不能打一般受保護 endpoint"""
    import main as main_mod
    main_mod.db.users.update_one(
        {"email": "inactive@chengfu.local"},
        {"$set": {
            "email": "inactive@chengfu.local",
            "role": "USER",
            "chengfu_active": False,
            "chengfu_permissions": ["accounting.view", "accounting.edit"],
        }},
        upsert=True,
    )
    r = client.get("/accounts", headers={"X-User-Email": "inactive@chengfu.local"})
    assert r.status_code == 403
    assert "停用" in r.json()["detail"]


def test_permission_inactive_admin_allowlist_blocked(client):
    """停用管理員即使在 ADMIN_EMAILS allowlist 也不能進 admin endpoint"""
    import main as main_mod
    main_mod.db.users.update_one(
        {"email": "sterio068@gmail.com"},
        {"$set": {
            "email": "sterio068@gmail.com",
            "role": "ADMIN",
            "chengfu_active": False,
        }},
        upsert=True,
    )
    try:
        r = client.get("/admin/adoption", headers=ADMIN_HEADERS)
        assert r.status_code == 403
        assert "停用" in r.json()["detail"]
        r2 = client.get("/accounts", headers=ADMIN_HEADERS)
        assert r2.status_code == 403
        assert "停用" in r2.json()["detail"]
    finally:
        main_mod.db.users.update_one(
            {"email": "sterio068@gmail.com"},
            {"$set": {
                "email": "sterio068@gmail.com",
                "role": "ADMIN",
                "chengfu_active": True,
            }},
            upsert=True,
        )


def test_permission_user_lookup_failure_fails_closed(client, monkeypatch):
    """users collection 查詢失敗時不能 fallback 成 legacy 權限"""
    import routers._deps as deps

    class BrokenUsers:
        def find_one(self, *args, **kwargs):
            raise RuntimeError("mongo unavailable")

    monkeypatch.setattr(deps, "get_users_col", lambda: BrokenUsers())
    r = client.get("/accounts", headers={"X-User-Email": "legacy@chengfu.local"})
    assert r.status_code == 503
    assert "權限查詢失敗" in r.json()["detail"]


def test_permission_admin_bypasses_accounting_permission(client):
    """ADMIN 即使未設定 chengfu_permissions 仍可進高風險 endpoint"""
    r = client.get("/accounts", headers=ADMIN_HEADERS)
    assert r.status_code == 200


# ============================================================
# v1.69 batch · access-urls / health / reset-password / permanent-delete
# 對應 Codex review 12 條 + Anthropic 補強
# ============================================================
class TestAccessUrls:
    def test_requires_admin(self, client):
        """non-admin → 403(require_admin gate)"""
        r = client.get("/admin/access-urls")
        assert r.status_code == 403

    def test_admin_can_read(self, client):
        """admin 可讀 · 至少回 lan_urls / mdns_url / tunnel_urls / guidance"""
        r = client.get("/admin/access-urls", headers=ADMIN_HEADERS)
        assert r.status_code == 200
        body = r.json()
        for k in ("lan_urls", "mdns_url", "tunnel_urls", "guidance", "current_origin"):
            assert k in body, f"missing key {k}"
        assert isinstance(body["lan_urls"], list)
        assert "account_source" in body["guidance"]

    def test_x_forwarded_host_validated(self, client):
        """C8 · 偽造惡意 X-Forwarded-Host 應被 regex 擋(不 reflect 進 current_origin)"""
        evil_host = "<script>alert(1)</script>"
        r = client.get(
            "/admin/access-urls",
            headers={**ADMIN_HEADERS, "X-Forwarded-Host": evil_host},
        )
        assert r.status_code == 200
        co = r.json().get("current_origin") or ""
        assert "<script>" not in co
        assert "alert" not in co


class TestAIProvidersHealth:
    def test_requires_login(self, client):
        """C2 · 匿名請求 → 401(防探測 key 是否存在)"""
        # 移除 X-User-Email 模擬匿名
        c = TestClient(__import__("main").app)
        r = c.get("/health/ai-providers")
        assert r.status_code == 401

    def test_user_redacted_view(self, client):
        """C2 · 一般同仁登入只看 state · 不揭露 reason / configured / 長度"""
        r = client.get("/health/ai-providers")
        assert r.status_code == 200
        providers = r.json().get("providers", {})
        assert "openai" in providers
        # USER 視角:只有 state 欄位 · 沒有 reason/configured
        for p in providers.values():
            assert "state" in p
            assert "reason" not in p
            assert "configured" not in p

    def test_admin_full_view(self, client):
        """admin 看完整 reason / configured"""
        r = client.get("/health/ai-providers", headers=ADMIN_HEADERS)
        assert r.status_code == 200
        providers = r.json().get("providers", {})
        for p in providers.values():
            assert "state" in p
            assert "reason" in p
            assert "configured" in p


class TestSecretsMetadata:
    """服務金鑰管理 UI 文案 · 必須符合 OpenAI 主力 / Claude 備援決議"""

    def test_openai_primary_anthropic_backup_metadata(self, client):
        r = client.get("/admin/secrets/status", headers=ADMIN_HEADERS)
        assert r.status_code == 200
        secrets = {s["name"]: s for s in r.json()["secrets"]}

        assert secrets["OPENAI_API_KEY"]["required"] is True
        assert "主力" in secrets["OPENAI_API_KEY"]["desc"]
        assert secrets["OPENAI_API_KEY"]["console_url"] == "https://platform.openai.com/api-keys"

        assert secrets["ANTHROPIC_API_KEY"]["required"] is False
        assert "備援" in secrets["ANTHROPIC_API_KEY"]["desc"]
        assert secrets["ANTHROPIC_API_KEY"]["console_url"] == "https://console.anthropic.com/settings/keys"

        assert secrets["FAL_API_KEY"]["console_url"] == "https://fal.ai/dashboard/keys"


class TestRagAdapter:
    """LibreChat RAG_API_URL adapter · auth boundary + retrieval smoke"""

    def test_embed_requires_auth(self, client):
        r = client.post(
            "/rag/embed",
            data={"file_id": "rag-auth-required"},
            files={"file": ("rag.txt", b"secret text", "text/plain")},
            headers={"X-User-Email": ""},
        )
        assert r.status_code == 401

    def test_embed_query_delete_with_authenticated_user(self, client):
        file_id = "rag-unit-20260428"
        text = "RAG-AUTH-UNIT brand color #0F766E KPI 800 people"

        r = client.post(
            "/rag/embed",
            data={"file_id": file_id, "entity_id": "agent_unit"},
            files={"file": ("rag-unit.txt", text.encode("utf-8"), "text/plain")},
        )
        assert r.status_code == 200
        assert r.json()["file_id"] == file_id
        assert r.json()["chunk_count"] >= 1

        r = client.post(
            "/rag/query",
            json={"file_id": file_id, "entity_id": "agent_unit", "query": "brand color KPI"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body
        assert "#0F766E" in body[0][0]["page_content"]

        r = client.request("DELETE", "/rag/documents", json=[file_id])
        assert r.status_code == 200
        assert r.json()["deleted"] >= 1


class TestPasswordPolicy:
    """C4 · 密碼複雜度 · create + reset 共用"""

    def _make_user(self, client):
        r = client.post(
            "/admin/users",
            json={
                "email": "policy@chengfu.local",
                "name": "Policy Test",
                "password": "Strong!Pass2026",
                "role": "USER",
            },
            headers=ADMIN_HEADERS,
        )
        assert r.status_code in (200, 409)  # 409 = already exists from prev test

    def test_create_rejects_short(self, client):
        r = client.post(
            "/admin/users",
            json={"email": "short@x.com", "name": "X", "password": "Aa1!aaaa"},
            headers=ADMIN_HEADERS,
        )
        assert r.status_code == 422  # < 10 字

    def test_create_rejects_weak_class(self, client):
        r = client.post(
            "/admin/users",
            json={"email": "weak@x.com", "name": "X", "password": "alllowercase1"},
            headers=ADMIN_HEADERS,
        )
        # 只 1 大寫類 + 數字 = 2 類 < 3
        assert r.status_code == 422

    def test_create_rejects_common_weak(self, client):
        r = client.post(
            "/admin/users",
            json={"email": "common@x.com", "name": "X", "password": "Password1234!"[:10]},
            headers=ADMIN_HEADERS,
        )
        # 不該被擋 · 改試一個常見弱
        r = client.post(
            "/admin/users",
            json={"email": "common2@x.com", "name": "X", "password": "password"},
            headers=ADMIN_HEADERS,
        )
        assert r.status_code == 422

    def test_create_rejects_repeat_4(self, client):
        r = client.post(
            "/admin/users",
            json={"email": "rep@x.com", "name": "X", "password": "Aaaaa1!@bC"},
            headers=ADMIN_HEADERS,
        )
        # aaaa 重複 4 次 → reject
        assert r.status_code == 422

    def test_reset_password_enforces_policy(self, client):
        """C4 · reset 跟 create 用同一個 validator"""
        self._make_user(client)
        r = client.post(
            "/admin/users/policy@chengfu.local/reset-password",
            json={"new_password": "weak"},
            headers=ADMIN_HEADERS,
        )
        assert r.status_code == 422


class TestResetPassword:
    """reset-password 端點 · session 失效 + audit + lockout"""

    def test_requires_admin(self, client):
        r = client.post(
            "/admin/users/anyone@x.com/reset-password",
            json={"new_password": "Strong!Pass2026"},
        )
        assert r.status_code == 403

    def test_cant_reset_self(self, client):
        r = client.post(
            "/admin/users/sterio068@gmail.com/reset-password",
            json={"new_password": "Strong!Pass2026"},
            headers=ADMIN_HEADERS,
        )
        assert r.status_code == 400

    def test_404_on_unknown_user(self, client):
        r = client.post(
            "/admin/users/notexist@x.com/reset-password",
            json={"new_password": "Strong!Pass2026"},
            headers=ADMIN_HEADERS,
        )
        assert r.status_code == 404


class TestPermanentDelete:
    """permanent delete 端點 · CAS + cleanup-first guard"""

    def test_requires_admin(self, client):
        r = client.delete("/admin/users/anyone@x.com/permanent")
        assert r.status_code == 403

    def test_cant_delete_self(self, client):
        r = client.delete(
            "/admin/users/sterio068@gmail.com/permanent",
            headers=ADMIN_HEADERS,
        )
        assert r.status_code == 400

    def test_must_deactivate_first(self, client):
        """C6 · 二段式 · 沒先停用就刪 → 400"""
        # 確保 test user 是 active
        import main
        main.db.users.update_one(
            {"email": "test@chengfu.local"},
            {"$set": {"chengfu_active": True}},
        )
        r = client.delete(
            "/admin/users/test@chengfu.local/permanent",
            headers=ADMIN_HEADERS,
        )
        assert r.status_code == 400

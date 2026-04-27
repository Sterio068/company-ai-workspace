"""
v1.8 hardening · regression tests
=====================================
覆蓋 PR #52 修的 4 sec + perf 相關保證

避開 routers.admin import 的 circular(那條路會 evaluate main.py)
直接測 services/ 與獨立 helper

跑:
  cd backend/accounting
  python3 -m pytest tests/test_v1_8_hardening.py -v
"""
import sys
import os
import hashlib
import importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# 1. ai_detectors id 必須 stable(sha256, 不是 hash())
# ============================================================
class TestStableSuggestionId:
    """跨 process 重啟,同 conv_id × type 必須產出同一 id

    舊 bug:Python hash() 是 process-randomized · 重啟後 dismiss/cache 失效
    """

    def _calc_id(self, cid: str, type_: str) -> int:
        """重現 ai_detectors.detect_all 內部公式"""
        h = hashlib.sha256(f"{cid}:{type_}".encode("utf-8")).digest()
        return int.from_bytes(h[:8], "big") & ((1 << 53) - 1)

    def test_sha256_deterministic(self):
        a = self._calc_id("abc123", "deadline")
        b = self._calc_id("abc123", "deadline")
        assert a == b

    def test_id_within_js_safe_range(self):
        n = self._calc_id("a" * 64, "reply")
        assert 0 < n < (1 << 53), f"id {n} out of JS safe int range"

    def test_different_types_different_ids(self):
        d = self._calc_id("conv-1", "deadline")
        r = self._calc_id("conv-1", "reply")
        s = self._calc_id("conv-1", "stale")
        assert len({d, r, s}) == 3

    def test_ai_detectors_module_uses_same_formula(self):
        """確認 ai_detectors.py 真的用 sha256 · 不是 hash()"""
        import services.ai_detectors as mod
        src = open(mod.__file__).read()
        assert "hashlib.sha256" in src, "ai_detectors 應用 sha256 stable hash"
        assert "abs(hash(r" not in src, "ai_detectors 不應再用 Python hash()"


# ============================================================
# 2. conversation_meta · _ensure_aware 處理 naive datetime
# ============================================================
class TestEnsureAware:
    def test_naive_datetime_becomes_aware(self):
        from datetime import datetime, timezone
        from services.conversation_meta import _ensure_aware
        naive = datetime(2026, 4, 26, 12, 0, 0)
        aware = _ensure_aware(naive)
        assert aware.tzinfo == timezone.utc

    def test_already_aware_unchanged(self):
        from datetime import datetime, timezone
        from services.conversation_meta import _ensure_aware
        aware_in = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
        aware_out = _ensure_aware(aware_in)
        assert aware_in is aware_out

    def test_none_passes_through(self):
        from services.conversation_meta import _ensure_aware
        assert _ensure_aware(None) is None


# ============================================================
# 3. iter_user_conversations 用 $in 兼容 ObjectId / str
# ============================================================
class TestUserConversationCompat:
    def test_query_includes_both_types(self):
        """確認 query 用 $in [ObjectId, str] · 否則 LibreChat 不同版本會掃 0 筆"""
        from bson import ObjectId
        captured = {}

        class FakeCol:
            def find(self, query, projection=None):
                # v1.44 perf F-9 修 · find() 接受 projection 第 2 arg
                captured["query"] = query
                captured["projection"] = projection
                class Cur:
                    def sort(s, *a, **k): return s
                    def limit(s, *a, **k): return s
                    def __iter__(s): return iter([])
                return Cur()

        class FakeDB:
            conversations = FakeCol()

        from services.conversation_meta import iter_user_conversations
        oid = ObjectId()
        list(iter_user_conversations(FakeDB, oid))

        # query 形如 {"user": {"$in": [ObjectId, str]}}
        q = captured["query"]
        assert "user" in q
        assert "$in" in q["user"]
        in_list = q["user"]["$in"]
        assert oid in in_list, "應含 ObjectId"
        assert str(oid) in in_list, "應含 str(ObjectId)"


# ============================================================
# 4. 靜態檢查:smart_folders limit 有 ge/le bound
# ============================================================
class TestSmartFolderLimitStaticCheck:
    """避開 admin __init__ circular · 直接讀 smart_folders.py 源碼確認 ge/le 在"""
    def test_preview_request_has_le_bound(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "routers", "admin", "smart_folders.py")
        src = open(path).read()
        assert "Field(default=3, ge=1, le=20)" in src, "PreviewRequest.limit 應有 ge=1, le=20 bound"

    def test_get_items_endpoint_has_query_bound(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "routers", "admin", "smart_folders.py")
        src = open(path).read()
        assert "Query(default=50, ge=1, le=200)" in src, \
            "get_smart_folder_items limit 應有 Query bound"


# ============================================================
# 5. 靜態檢查:branding 公開白名單存在
# ============================================================
class TestBrandingPublicWhitelist:
    def test_public_field_whitelist_exists(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "routers", "admin", "branding.py")
        src = open(path).read()
        assert "PUBLIC_BRANDING_FIELDS" in src
        assert "include_admin_metadata" in src, \
            "get_branding_doc 應該有 include_admin_metadata 參數區分 public/admin"
        # 公開 endpoint 不傳 metadata
        assert "include_admin_metadata=False" in src


# ============================================================
# 6. 靜態檢查:ai_suggestions resolve admin
# ============================================================
class TestCronAdminResolveStatic:
    def test_resolve_helper_exists(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "routers", "admin", "ai_suggestions.py")
        src = open(path).read()
        assert "_resolve_admin_email" in src
        assert "internal:cron" in src
        assert "X-User-Email" in src

    def test_scan_all_endpoint_exists(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "routers", "admin", "ai_suggestions.py")
        src = open(path).read()
        assert "/admin/ai-suggestions/scan-all" in src
        assert 'role": "ADMIN"' in src or "'role': 'ADMIN'" in src, \
            "scan-all 應該從 _users_col 列 ADMIN role 的 user"

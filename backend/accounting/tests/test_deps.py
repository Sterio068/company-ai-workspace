"""
Routers _deps unit tests · v1.2 §11.1 B-1.5

驗證 routers/_deps.py 共用 helper 行為:
- _serialize 處理 ObjectId / datetime / nested dict / list
- get_db / get_users_col 拿到 main 的 collection
- require_user_dep / require_admin_dep 在沒身份時 403

跑法:
  cd backend/accounting
  python3 -m pytest tests/test_deps.py -v
"""
from datetime import datetime
from bson import ObjectId
import pytest

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routers._deps import _serialize


# ============================================================
# _serialize · 各型別
# ============================================================
class TestSerialize:
    def test_objectid_to_str(self):
        oid = ObjectId()
        assert _serialize(oid) == str(oid)

    def test_datetime_to_iso(self):
        dt = datetime(2026, 4, 22, 12, 0, 0)
        assert _serialize(dt) == "2026-04-22T12:00:00"

    def test_dict_recurses(self):
        oid = ObjectId()
        dt = datetime(2026, 4, 22)
        out = _serialize({"_id": oid, "created_at": dt, "name": "test"})
        assert out["_id"] == str(oid)
        assert out["created_at"] == "2026-04-22T00:00:00"
        assert out["name"] == "test"

    def test_list_recurses(self):
        oid1 = ObjectId()
        oid2 = ObjectId()
        out = _serialize([{"_id": oid1}, {"_id": oid2}])
        assert out[0]["_id"] == str(oid1)
        assert out[1]["_id"] == str(oid2)

    def test_nested_list_in_dict(self):
        oids = [ObjectId(), ObjectId()]
        out = _serialize({"refs": oids, "label": "x"})
        assert out["refs"] == [str(o) for o in oids]
        assert out["label"] == "x"

    def test_primitive_passthrough(self):
        assert _serialize("hello") == "hello"
        assert _serialize(42) == 42
        assert _serialize(3.14) == 3.14
        assert _serialize(None) is None
        assert _serialize(True) is True

    def test_empty_collections(self):
        assert _serialize([]) == []
        assert _serialize({}) == {}


# ============================================================
# get_db / get_users_col · lazy import
# 注意:這兩個 getter 只在 main.py 已 import 後才有意義
# 整合測試在 test_main.py 已涵蓋(用 mongomock fixture)
# 這裡只做 import 不炸 + 函數簽名正確
# ============================================================
class TestLazyGetters:
    def test_get_db_function_exists(self):
        from routers._deps import get_db
        assert callable(get_db)

    def test_get_users_col_function_exists(self):
        from routers._deps import get_users_col
        assert callable(get_users_col)

    def test_dep_factories_exist(self):
        from routers._deps import (
            current_user_email_dep, require_user_dep, require_admin_dep,
        )
        # 三個都應該是 factory · call 後回 Depends 物件
        assert callable(current_user_email_dep)
        assert callable(require_user_dep)
        assert callable(require_admin_dep)


# 注意:dep 的 integration 測試(require_user_dep blocks anonymous · admin allowlist 行為)
# 已在 test_main.py 涵蓋:
#   - test_auth_tenders_blocks_anonymous (tenders router 用 require_user_dep)
#   - test_auth_feedback_blocks_anonymous (feedback router R7#4)
#   - test_feedback_stats_requires_admin (feedback router 用 require_admin_dep)
#   - test_admin_dashboard_requires_admin (main.py admin endpoint)
# 不重複 · 此檔只測 _deps.py 自己的 unit-level 行為(_serialize / 函數存在)

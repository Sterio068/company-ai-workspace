"""
v1.10 · perf regression tests
=====================================
覆蓋:
- get_recent_metas batch query(N+1 → 3)
- detect_all 用 _cached_msgs 不 redundant query
- _scan_locks per-user lock 防 thundering herd

跑:
  cd backend/accounting
  python3 -m pytest tests/test_v1_10_perf.py -v
"""
import sys
import os
from unittest.mock import MagicMock, call
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# 1. get_recent_metas N+1 → batch
# ============================================================
class TestBatchMessages:
    """確認 get_recent_metas 一次撈 messages · 不是 per-conv N+1"""

    def _make_db(self, conv_count: int = 5):
        """fake DB with N conversations + 0 messages"""
        db = MagicMock()
        db.user_preferences.find_one.return_value = None
        # iter_user_conversations 用的 .find().sort().limit()
        convs = [
            {"conversationId": f"c{i}", "title": f"Conv {i}", "user": "uid1"}
            for i in range(conv_count)
        ]
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = iter(convs)
        db.conversations.find.return_value = cursor

        # messages.find for batch query · 回空
        msg_cursor = MagicMock()
        msg_cursor.sort.return_value = iter([])
        db.messages.find.return_value = msg_cursor
        return db

    def test_messages_query_count_constant(self):
        """5 conv 應該只 1 次 messages.find · 不是 5 次"""
        from services.conversation_meta import get_recent_metas
        db = self._make_db(conv_count=5)

        get_recent_metas(db, "test@example.com", "uid1", limit=5)

        # messages.find 應 == 1(batch · 不是 5)
        assert db.messages.find.call_count == 1, (
            f"Expected 1 batch messages.find, got {db.messages.find.call_count}"
        )

    def test_messages_uses_in_filter(self):
        """確認 batch query 用 $in [conv_id list]"""
        from services.conversation_meta import get_recent_metas
        db = self._make_db(conv_count=3)

        get_recent_metas(db, "test@example.com", "uid1", limit=3)

        call_args = db.messages.find.call_args
        query = call_args[0][0] if call_args[0] else call_args[1].get("filter")
        assert "conversationId" in query
        assert "$in" in query["conversationId"]
        in_list = query["conversationId"]["$in"]
        assert "c0" in in_list
        assert "c1" in in_list
        assert "c2" in in_list


# ============================================================
# 2. _cached_msgs 黏在 meta 上 · detect_all 重用不 redundant query
# ============================================================
class TestCachedMsgsReuse:
    def test_meta_carries_cached_msgs(self):
        """get_recent_metas 回的 meta 要含 _cached_msgs"""
        from services.conversation_meta import get_recent_metas

        db = MagicMock()
        db.user_preferences.find_one.return_value = None

        convs = [{"conversationId": "c1", "title": "T", "user": "u1"}]
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = iter(convs)
        db.conversations.find.return_value = cursor

        # 1 條 message in batch
        msgs = [{"conversationId": "c1", "text": "hi", "createdAt": None}]
        msg_cursor = MagicMock()
        msg_cursor.sort.return_value = iter(msgs)
        db.messages.find.return_value = msg_cursor

        metas = get_recent_metas(db, "u@e.com", "u1", limit=1)
        assert len(metas) == 1
        assert "_cached_msgs" in metas[0]
        assert metas[0]["_cached_msgs"] == msgs

    def test_detect_deadline_uses_cached(self):
        """detect_deadline 收到 _msgs 後不 query db"""
        from services.ai_detectors import detect_deadline

        db = MagicMock()
        db.messages.find.side_effect = AssertionError(
            "detect_deadline 不應 query · 應用 _msgs cache"
        )

        meta = {
            "conversation_id": "c1",
            "title": "test",
        }
        # 給 cached_msgs · 不應觸發 db.messages.find
        result = detect_deadline(db, meta, _msgs=[])
        # 空 messages · 預期 None
        assert result is None
        assert db.messages.find.call_count == 0


# ============================================================
# 3. ai_suggestions per-user scan lock
# ============================================================
class TestScanLock:
    """避開 routers.admin 的 circular import · 用靜態源碼檢查"""

    def _src(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "routers", "admin", "ai_suggestions.py")
        return open(path).read()

    def test_scan_lock_module_var_exists(self):
        assert "_scan_locks: Dict[str, asyncio.Lock]" in self._src(), \
            "_scan_locks 應該是 module-level Dict[str, asyncio.Lock]"

    def test_get_scan_lock_helper_exists(self):
        assert "def _get_scan_lock(" in self._src()

    def test_list_endpoint_is_async(self):
        """v1.10 · list_ai_suggestions 必須 async def"""
        src = self._src()
        assert "async def list_ai_suggestions(" in src, \
            "list_ai_suggestions 應該是 async def · 才能 await scan lock"

    def test_uses_run_in_executor(self):
        """sync _run_scan 應透過 run_in_executor 走 thread pool · 不阻塞 event loop"""
        src = self._src()
        assert "run_in_executor" in src, \
            "scan 應走 run_in_executor · 否則 sync pymongo 阻塞 uvicorn worker"

    def test_double_checked_cache(self):
        """拿 lock 後再 check cache · 防 N 個並發都掃"""
        src = self._src()
        # 簡易檢查 · 應有兩個 _get_cache call(double-checked locking)
        assert src.count("_get_cache(db, _admin)") >= 2, \
            "lock 內外都要 check cache · double-checked locking pattern"

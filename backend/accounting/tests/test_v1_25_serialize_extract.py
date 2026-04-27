"""
v1.25 · serialize() 抽到 auth_deps.py · architect R2 round 2 tests

跑:
  cd backend/accounting
  python3 -m pytest tests/test_v1_25_serialize_extract.py -v
"""
import os
import sys
from bson import ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSerializeBehavior:
    def test_objectid_to_str(self):
        from auth_deps import serialize
        oid = ObjectId()
        result = serialize({"_id": oid, "name": "x"})
        assert result["_id"] == str(oid)
        assert result["name"] == "x"

    def test_nested_list(self):
        from auth_deps import serialize
        oid1, oid2 = ObjectId(), ObjectId()
        result = serialize([{"_id": oid1}, {"_id": oid2}])
        assert result[0]["_id"] == str(oid1)
        assert result[1]["_id"] == str(oid2)

    def test_nested_dict(self):
        from auth_deps import serialize
        oid = ObjectId()
        result = serialize({"outer": {"inner": {"_id": oid}}})
        assert result["outer"]["inner"]["_id"] == str(oid)

    def test_none_passthrough(self):
        from auth_deps import serialize
        assert serialize(None) is None
        assert serialize({}) == {}
        assert serialize([]) == []

    def test_primitives_passthrough(self):
        from auth_deps import serialize
        assert serialize({"a": 1, "b": "x", "c": True, "d": None})["d"] is None

    def test_no_datetime_handling(self):
        """v1.25 注意 · main.py 原 serialize 不處理 datetime · 維持原行為
        (routers/_deps._serialize 才有 datetime · 已分開)
        """
        from datetime import datetime
        from auth_deps import serialize
        dt = datetime(2026, 4, 27)
        # datetime 應該被原樣回(不轉 isoformat)
        result = serialize({"ts": dt})
        assert result["ts"] is dt


class TestMainBackwardCompat:
    def test_main_re_exports_serialize(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
        src = open(path).read()
        assert "from auth_deps import serialize" in src

    def test_main_no_inline_serialize(self):
        """main.py 不應再有 inline `def serialize(`"""
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
        src = open(path).read()
        assert "def serialize(" not in src, "main.py 應只 import auth_deps.serialize · 不再 inline def"

    def test_routers_deps_serialize_intact(self):
        """routers/_deps.py 的 _serialize(含 datetime)應保留 · 不影響"""
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "routers", "_deps.py")
        src = open(path).read()
        assert "def _serialize(" in src
        # _deps.py 的 _serialize 是另一個版本(處理 datetime)· 不能被誤刪
        assert "isinstance(doc, datetime)" in src

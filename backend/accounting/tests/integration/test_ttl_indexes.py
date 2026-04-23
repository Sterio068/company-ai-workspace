"""
v1.3 C1#2 · TTL index 真會 expire(mongomock 不會)

main.py 設了多個 TTL index:
- knowledge_audit · 90d
- meetings · 365d
- site_surveys · 2y
- design_jobs · 180d

R14#4 fail-loud 確保 TTL 真生效 · 但只在啟動時驗 index spec
本 test 真插一筆 expired doc · 等 60s · 驗 Mongo 真砍掉

⚠ Mongo TTL background task 預設每 60s 跑一次 · 故 sleep 70s 抓
"""
import pytest
import time
from datetime import datetime, timezone, timedelta


@pytest.mark.slow
def test_short_ttl_actually_expires(real_db):
    """建 TTL=10s index · 插過期 doc · 等 70s · 應消失
    驗證 Mongo TTL background task 真會跑(對比 mongomock 不會)"""
    col = real_db.short_ttl_test
    col.create_index([("created_at", 1)], expireAfterSeconds=10, name="ttl_10s")

    # 過去 60s 的 doc · 應立刻被視為過期
    col.insert_one({
        "_id": "expired_doc",
        "created_at": datetime.now(timezone.utc) - timedelta(seconds=60),
    })
    assert col.count_documents({}) == 1

    # Mongo TTL monitor 每 60s 掃一次 · 給 70s 緩衝
    waited = 0
    while col.count_documents({}) > 0 and waited < 75:
        time.sleep(5)
        waited += 5

    assert col.count_documents({}) == 0, \
        f"TTL 應在 70s 內砍掉 expired doc · 實際 {waited}s 還有"


def test_ttl_index_spec_persists(real_db):
    """TTL index 的 expireAfterSeconds 真存到 system.indexes"""
    col = real_db.ttl_spec_test
    col.create_index([("created_at", 1)], expireAfterSeconds=86400, name="ttl_1d")
    info = col.index_information()
    assert "ttl_1d" in info
    assert info["ttl_1d"]["expireAfterSeconds"] == 86400


def test_ttl_index_recreate_with_different_seconds(real_db):
    """R14#4 場景 · TTL 改秒數需 drop+recreate · 不能直接 createIndex 同名"""
    col = real_db.ttl_change_test
    col.create_index([("created_at", 1)], expireAfterSeconds=86400, name="ttl_change")
    # 直接改秒數 · Mongo 應 raise IndexOptionsConflict 而非靜默
    from pymongo.errors import OperationFailure
    with pytest.raises(OperationFailure):
        col.create_index(
            [("created_at", 1)], expireAfterSeconds=43200, name="ttl_change"
        )
    # 必先 drop 再 create
    col.drop_index("ttl_change")
    col.create_index([("created_at", 1)], expireAfterSeconds=43200, name="ttl_change")
    assert col.index_information()["ttl_change"]["expireAfterSeconds"] == 43200

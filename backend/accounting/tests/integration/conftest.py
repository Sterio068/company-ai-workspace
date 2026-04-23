"""
v1.3 C1 · Real Mongo 整合 test conftest

mongomock 跟真 Mongo 行為差(R30/R31 證實):
- arrayFilters($[n]) → mongomock NotImplementedError · prod 走 atomic
- TTL index 真會自動 expire(mongomock 不會)
- collation case-insensitive · partialFilterExpression 部分支援

# 用法
本地手動:
    docker run -d --rm -p 27017:27017 --name chengfu-test-mongo mongo:7.0
    INTEGRATION_MONGO_URL=mongodb://localhost:27017 \\
        python3 -m pytest tests/integration -v
    docker stop chengfu-test-mongo

CI(.github/workflows/ci.yml):
    services:
      mongo:
        image: mongo:7.0
        ports: ['27017:27017']
    env:
      INTEGRATION_MONGO_URL: mongodb://localhost:27017

預設行為:
- 沒設 INTEGRATION_MONGO_URL → integration tests 全 skip(mongomock 不能 run)
- 不阻擋 dev / 一般 CI 跑單元測試
"""
import os
import pytest
import pymongo


def pytest_collection_modifyitems(config, items):
    """沒設 INTEGRATION_MONGO_URL · skip 整 tests/integration/"""
    if os.getenv("INTEGRATION_MONGO_URL"):
        return  # 真 Mongo 可用 · 不 skip
    skip_marker = pytest.mark.skip(
        reason="INTEGRATION_MONGO_URL 未設 · skip(本地需 docker run mongo:7.0)"
    )
    for item in items:
        if "integration" in item.nodeid:
            item.add_marker(skip_marker)


@pytest.fixture(scope="module")
def real_mongo():
    """真 Mongo client · 每個 test module 獨立 db(防汙染)"""
    url = os.getenv("INTEGRATION_MONGO_URL")
    if not url:
        pytest.skip("INTEGRATION_MONGO_URL not set")
    client = pymongo.MongoClient(url, serverSelectionTimeoutMS=3000)
    # 確認 Mongo 真在
    try:
        client.admin.command("ping")
    except Exception as e:
        pytest.skip(f"Mongo unreachable at {url}: {e}")
    yield client
    client.close()


@pytest.fixture
def real_db(real_mongo, request):
    """每 test module 獨立 db · 名稱含 module name 防衝突 · test 結束 drop"""
    db_name = f"chengfu_int_{request.module.__name__.split('.')[-1]}"
    db = real_mongo[db_name]
    # 清乾淨(防上次 test 失敗殘留)
    real_mongo.drop_database(db_name)
    yield db
    # cleanup
    real_mongo.drop_database(db_name)

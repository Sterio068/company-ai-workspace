"""
v1.3 C1#4 · 技術債#9 · main.py media_contacts.email_1 偵測舊 sparse 並 drop+recreate
真 Mongo 行為 vs mongomock 差別:真 Mongo 會 raise IndexOptionsConflict
mongomock 直接成功(不檢查 conflict)
"""
import pytest
from pymongo.errors import OperationFailure


def test_sparse_to_partialfilter_requires_drop(real_db):
    """老 sparse=True email_1 · 直接 createIndex partialFilter 同名應 raise"""
    col = real_db.media_contacts

    # 模擬舊 sparse 設定(v1.0/v1.1 留下)
    col.create_index([("email", 1)], unique=True, sparse=True, name="email_1")
    info = col.index_information()
    assert "email_1" in info
    assert info["email_1"].get("sparse") is True
    assert "partialFilterExpression" not in info["email_1"]

    # 直接 createIndex 同名 + partialFilter · 應 raise(真 Mongo 嚴格)
    with pytest.raises(OperationFailure):
        col.create_index(
            [("email", 1)],
            unique=True,
            partialFilterExpression={"email": {"$type": "string", "$gt": ""}},
            name="email_1",
        )

    # main.py 修補 · drop 後 create 才行
    col.drop_index("email_1")
    col.create_index(
        [("email", 1)],
        unique=True,
        partialFilterExpression={"email": {"$type": "string", "$gt": ""}},
        name="email_1",
    )
    info2 = col.index_information()
    assert "partialFilterExpression" in info2["email_1"]


def test_partial_filter_excludes_empty_string(real_db):
    """partialFilter $type:string $gt:'' 應接受 1 個空 string + 1 個 None
    (vs sparse=True 只擋 None)"""
    col = real_db.media_contacts2
    col.create_index(
        [("email", 1)],
        unique=True,
        partialFilterExpression={"email": {"$type": "string", "$gt": ""}},
        name="email_partial",
    )

    # 兩個 None 應 OK(不在 filter 範圍)
    col.insert_one({"name": "a", "email": None})
    col.insert_one({"name": "b", "email": None})

    # 兩個空 string 應 OK(不在 filter 範圍 · `$gt: ''` 排除空)
    col.insert_one({"name": "c", "email": ""})
    col.insert_one({"name": "d", "email": ""})

    # 兩個 same valid email · 應 raise
    col.insert_one({"name": "e", "email": "alice@x.com"})
    from pymongo.errors import DuplicateKeyError
    with pytest.raises(DuplicateKeyError):
        col.insert_one({"name": "f", "email": "alice@x.com"})

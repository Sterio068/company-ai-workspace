"""
v1.3 C1#3 · Case-insensitive regex 行為(R31#3)

PDPA delete-all 用 `{"$regex": f"^{re.escape(target)}$", "$options": "i"}`
mongomock 對 regex case-insensitive 部分支援 · 可能漏 case · 必真 Mongo 驗
"""
import re
import pytest


def _ci(value: str):
    """同 admin.py PDPA endpoint 邏輯 · case-insensitive 完整 match"""
    return {"$regex": f"^{re.escape(value)}$", "$options": "i"}


def test_ci_regex_matches_mixed_case(real_db):
    """target 'leaving@x.com' 必匹配 'Leaving@X.Com' / 'LEAVING@X.COM'"""
    col = real_db.user_preferences
    target = "leaving@chengfu.local"

    col.insert_many([
        {"user_email": "leaving@chengfu.local", "key": "a"},
        {"user_email": "Leaving@ChengFu.Local", "key": "b"},
        {"user_email": "LEAVING@CHENGFU.LOCAL", "key": "c"},
        {"user_email": "leaving@CHENGFU.local", "key": "d"},
        # 不該匹配
        {"user_email": "other@chengfu.local", "key": "e"},
        {"user_email": "leavingleaving@chengfu.local", "key": "f"},  # 部分含 leaving
    ])

    matched = list(col.find({"user_email": _ci(target)}))
    matched_keys = {d["key"] for d in matched}
    assert matched_keys == {"a", "b", "c", "d"}, \
        f"應匹配 abcd · 實際 {matched_keys}"


def test_ci_regex_with_special_chars_safe(real_db):
    """target 含 regex meta(. + ?)· re.escape 防 injection"""
    col = real_db.test_ci_meta
    target = "user.with.dots@x.com"  # `.` 是 regex meta

    col.insert_many([
        {"user_email": "user.with.dots@x.com", "key": "exact"},
        {"user_email": "userXwithXdotsXxXcom", "key": "false_match_no_escape"},  # 沒 escape `.` 會匹配 X
    ])

    matched = list(col.find({"user_email": _ci(target)}))
    matched_keys = {d["key"] for d in matched}
    # re.escape 後 · `.` 是 literal · 不該匹配 X
    assert matched_keys == {"exact"}, \
        f"re.escape 必擋 regex meta · 實際 {matched_keys}"


def test_ci_regex_doesnt_match_substring(real_db):
    """`^...$` 完整 match · 不該 substring 匹配"""
    col = real_db.test_ci_anchor
    target = "alice@x.com"

    col.insert_many([
        {"email": "alice@x.com"},
        {"email": "alice@x.com.tw"},  # 後綴
        {"email": "xalice@x.com"},   # 前綴
    ])

    matched = list(col.find({"email": _ci(target)}))
    assert len(matched) == 1
    assert matched[0]["email"] == "alice@x.com"

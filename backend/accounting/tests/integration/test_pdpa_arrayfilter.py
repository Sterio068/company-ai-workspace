"""
v1.3 C1#1 · PDPA crm_leads.notes[].by arrayFilter atomic 真 Mongo 行為

R31#2 修補:Mongo $[n] arrayFilters atomic + mongomock NotImplementedError fallback Python
prod path 在 mongomock 永遠走不到 · 必真 Mongo 才能驗
"""
import pytest


def test_array_filter_unsets_target_only(real_db):
    """update_many + arrayFilters $[n] · 只清 by==target 的 note · 其他保留"""
    real_db.crm_leads.insert_one({
        "title": "lead-x",
        "owner": "boss@x.com",
        "notes": [
            {"text": "a", "by": "leaving@x.com", "at": "2026-01-01"},
            {"text": "b", "by": "stay@x.com", "at": "2026-01-02"},
            {"text": "c", "by": "leaving@x.com", "at": "2026-01-03"},
        ],
    })
    target = "leaving@x.com"
    r = real_db.crm_leads.update_many(
        {"notes.by": target},
        {"$set": {"notes.$[n].by": None}},
        array_filters=[{"n.by": target}],
    )
    assert r.modified_count == 1
    notes = real_db.crm_leads.find_one({"title": "lead-x"})["notes"]
    # leaving 兩個變 None · stay 不動
    assert notes[0]["by"] is None
    assert notes[1]["by"] == "stay@x.com"
    assert notes[2]["by"] is None


def test_array_filter_no_race_with_concurrent_push(real_db):
    """sim concurrent push 同時 unset · arrayFilter atomic 不該掉新 note
    (vs Python 端 read-modify-write 會掉)"""
    import threading
    target = "leaving@x.com"
    real_db.crm_leads.insert_one({
        "title": "lead-race",
        "notes": [{"text": "old", "by": target, "at": "2026-01-01"}],
    })

    def push_new_note():
        for i in range(20):
            real_db.crm_leads.update_one(
                {"title": "lead-race"},
                {"$push": {"notes": {"text": f"new-{i}", "by": "stay@x.com", "at": f"2026-01-{i:02d}"}}},
            )

    def unset_target():
        # arrayFilter atomic · 不該影響同時 push
        real_db.crm_leads.update_many(
            {"notes.by": target},
            {"$set": {"notes.$[n].by": None}},
            array_filters=[{"n.by": target}],
        )

    t1 = threading.Thread(target=push_new_note)
    t2 = threading.Thread(target=unset_target)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    notes = real_db.crm_leads.find_one({"title": "lead-race"})["notes"]
    # 至少有原本的 1 + 後 push 的 20 = 21
    assert len(notes) >= 21, f"race 掉了 note · 實際 {len(notes)} 個"
    # 原 leaving 的 by 已被清
    leaving_left = [n for n in notes if n.get("by") == target]
    assert len(leaving_left) == 0, "target 應全清"

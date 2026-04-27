"""
v1.38 perf F-3 · import_leads_from_tenders N+1 → 3 query test
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_n_plus_1_eliminated():
    """確認 import_leads_from_tenders 不再 per-row find_one"""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "routers", "crm.py")
    src = open(path).read()
    # 找 import_leads_from_tenders body
    fn_start = src.find("def import_leads_from_tenders(")
    fn_end = src.find("\n@router", fn_start) if fn_start > -1 else -1
    body = src[fn_start:fn_end] if fn_start > -1 else ""

    # 不該有 per-iteration find_one 在 for 內
    assert "db.crm_leads.find_one(" not in body, (
        "import_leads 不該有 find_one(N+1) · 應 batch $in"
    )
    # 應有 $in 批次撈
    assert "$in" in body
    # 應 batch insert
    assert "insert_many" in body
    # 應 ordered=False(部分失敗不擋整批)
    assert "ordered=False" in body


def test_keeps_dedup_logic():
    """確保 dedup by tender_key 仍在"""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "routers", "crm.py")
    src = open(path).read()
    assert "existing_keys" in src
    assert "tk in existing_keys" in src

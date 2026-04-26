"""
v1.14 · i18n sync test · backend ZH_TW_TERMS ↔ frontend librechat-relabel fallback

兩處 dict 必須對齊 · 否則:
- backend 改 term · 前端 fallback 顯示舊值(若 backend down)
- 前端 fallback 加 term · backend 不知道 · 拉到後 term 消失

跑:
  cd backend/accounting
  python3 -m pytest tests/test_v1_14_i18n_sync.py -v
"""
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _extract_terms_from_relabel():
    """從 librechat-relabel.js 抓 fallback TERMS dict 的 keys"""
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    path = os.path.join(repo_root, "frontend", "custom", "librechat-relabel.js")
    src = open(path).read()
    # 抓 let TERMS = { ... } 區塊(到下一個 `};`)
    m = re.search(r"let TERMS = \{([\s\S]+?)\n  \};", src)
    assert m, "找不到 librechat-relabel.js TERMS · sync test 失敗"
    block = m.group(1)
    # 抓 "key": ... 模式
    keys = re.findall(r'"([^"]+)":\s*"', block)
    return set(keys)


class TestI18nSync:
    def test_backend_and_relabel_keys_match(self):
        """backend ZH_TW_TERMS keys 必須 = frontend fallback TERMS keys"""
        from routers.i18n import ZH_TW_TERMS
        backend_keys = set(ZH_TW_TERMS.keys())
        frontend_keys = _extract_terms_from_relabel()

        only_backend = backend_keys - frontend_keys
        only_frontend = frontend_keys - backend_keys

        assert not only_backend, (
            f"backend 多出 frontend 沒的 keys: {sorted(only_backend)} · "
            f"請同步 frontend/custom/librechat-relabel.js"
        )
        assert not only_frontend, (
            f"frontend 多出 backend 沒的 keys: {sorted(only_frontend)} · "
            f"請同步 backend/accounting/routers/i18n.py ZH_TW_TERMS"
        )

    def test_relabel_uses_loadI18nFromBackend(self):
        """librechat-relabel.js 應該真的 await loadI18nFromBackend · 不只 fallback"""
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))))
        path = os.path.join(repo_root, "frontend", "custom", "librechat-relabel.js")
        src = open(path).read()
        assert "loadI18nFromBackend" in src
        assert "/api/i18n" in src
        # 確認用 sessionStorage cache(不是 localStorage · 跨分頁影響)
        assert "sessionStorage" in src

    def test_relabel_init_async(self):
        """init() 必須改 async · 才能 await loadI18nFromBackend"""
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))))
        path = os.path.join(repo_root, "frontend", "custom", "librechat-relabel.js")
        src = open(path).read()
        assert "async function init()" in src

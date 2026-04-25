/**
 * Projects 模組 · MongoDB API 優先 · localStorage fallback(離線)
 * v4.5:加 BroadcastChannel · 多分頁變動會即時同步(避免髒資料)
 */
import { authFetch } from "./auth.js";

const API = "/api-accounting/projects";
const FALLBACK_KEY = "chengfu-projects-v1";

// 多分頁同步 channel(舊瀏覽器無 BroadcastChannel 走 storage event fallback)
const _bc = ("BroadcastChannel" in self) ? new BroadcastChannel("chengfu-projects") : null;
function _broadcast(type) {
  if (_bc) {
    _bc.postMessage({ type, ts: Date.now() });
  } else {
    // storage event fallback(舊 Safari)
    try { localStorage.setItem("chengfu-projects-bus", JSON.stringify({ type, ts: Date.now() })); } catch {}
  }
}

export const Projects = {
  _cache: [],
  _online: true,
  _authBlocked: false,
  _lastError: null,
  _onChange: null,  // app 注入 callback · 收到其他分頁變動時 re-render

  bindOnChange(cb) { this._onChange = cb; },

  async refresh() {
    try {
      const r = await authFetch(API);
      if (!r.ok) {
        const err = new Error(r.statusText || `HTTP ${r.status}`);
        err.status = r.status;
        throw err;
      }
      this._cache = (await r.json()).map(p => ({ ...p, id: p._id }));
      this._online = true;
      this._authBlocked = false;
      this._lastError = null;
      localStorage.setItem(FALLBACK_KEY, JSON.stringify(this._cache));
    } catch (e) {
      this._online = false;
      this._lastError = e;
      if (e?.status === 401 || e?.status === 403) {
        this._authBlocked = true;
        this._cache = [];
      } else {
        this._authBlocked = false;
        try { this._cache = JSON.parse(localStorage.getItem(FALLBACK_KEY) || "[]"); } catch { this._cache = []; }
      }
    }
    return this._cache;
  },

  load() { return this._cache; },
  get(id) { return this._cache.find(p => p.id === id || p._id === id); },

  // Codex R3.7 · 檢查 r.ok · server 500 不應誤報成功
  async add(data) {
    if (this._authBlocked) throw new Error("登入已過期或權限不足 · 請重新登入後再儲存專案");
    if (this._online) {
      const r = await authFetch(API, { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(data) });
      if (!r.ok) {
        const err = await r.text().catch(() => r.statusText);
        throw new Error(`新建專案失敗(${r.status}):${err.substring(0, 100)}`);
      }
      await this.refresh();
    } else {
      const proj = { id: "proj_" + Date.now(), _id: "proj_" + Date.now(), ...data,
                      created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
      this._cache.push(proj);
      localStorage.setItem(FALLBACK_KEY, JSON.stringify(this._cache));
    }
    _broadcast("add");
  },

  async update(id, data) {
    if (this._authBlocked) throw new Error("登入已過期或權限不足 · 請重新登入後再儲存專案");
    if (this._online) {
      const r = await authFetch(`${API}/${id}`, { method: "PUT", headers: {"Content-Type":"application/json"}, body: JSON.stringify(data) });
      if (!r.ok) {
        const err = await r.text().catch(() => r.statusText);
        throw new Error(`更新專案失敗(${r.status}):${err.substring(0, 100)}`);
      }
      await this.refresh();
    } else {
      const idx = this._cache.findIndex(p => p.id === id);
      if (idx >= 0) this._cache[idx] = { ...this._cache[idx], ...data, updated_at: new Date().toISOString() };
      localStorage.setItem(FALLBACK_KEY, JSON.stringify(this._cache));
    }
    _broadcast("update");
  },

  async remove(id) {
    if (this._authBlocked) throw new Error("登入已過期或權限不足 · 請重新登入後再刪除專案");
    if (this._online) {
      const r = await authFetch(`${API}/${id}`, { method: "DELETE" });
      if (!r.ok) {
        const err = await r.text().catch(() => r.statusText);
        throw new Error(`刪除專案失敗(${r.status}):${err.substring(0, 100)}`);
      }
      await this.refresh();
    } else {
      this._cache = this._cache.filter(p => p.id !== id);
      localStorage.setItem(FALLBACK_KEY, JSON.stringify(this._cache));
    }
    _broadcast("remove");
  },
};

// 收聽其他分頁的變動 · refresh 自己 + 通知 app re-render
async function _onRemoteChange() {
  await Projects.refresh();
  Projects._onChange?.();
}
if (_bc) {
  _bc.onmessage = (e) => { if (e.data?.type) _onRemoteChange(); };
} else {
  window.addEventListener("storage", (e) => {
    if (e.key === "chengfu-projects-bus") _onRemoteChange();
  });
}

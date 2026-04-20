/**
 * Projects 模組 · MongoDB API 優先 · localStorage fallback(離線)
 */
const API = "/api-accounting/projects";
const FALLBACK_KEY = "chengfu-projects-v1";

export const Projects = {
  _cache: [],
  _online: true,

  async refresh() {
    try {
      const r = await fetch(API);
      if (!r.ok) throw new Error(r.statusText);
      this._cache = (await r.json()).map(p => ({ ...p, id: p._id }));
      this._online = true;
      localStorage.setItem(FALLBACK_KEY, JSON.stringify(this._cache));
    } catch {
      this._online = false;
      try { this._cache = JSON.parse(localStorage.getItem(FALLBACK_KEY) || "[]"); } catch { this._cache = []; }
    }
    return this._cache;
  },

  load() { return this._cache; },
  get(id) { return this._cache.find(p => p.id === id || p._id === id); },

  async add(data) {
    if (this._online) {
      await fetch(API, { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(data) });
      await this.refresh();
      return;
    }
    const proj = { id: "proj_" + Date.now(), _id: "proj_" + Date.now(), ...data,
                    created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
    this._cache.push(proj);
    localStorage.setItem(FALLBACK_KEY, JSON.stringify(this._cache));
  },

  async update(id, data) {
    if (this._online) {
      await fetch(`${API}/${id}`, { method: "PUT", headers: {"Content-Type":"application/json"}, body: JSON.stringify(data) });
      await this.refresh();
      return;
    }
    const idx = this._cache.findIndex(p => p.id === id);
    if (idx >= 0) this._cache[idx] = { ...this._cache[idx], ...data, updated_at: new Date().toISOString() };
    localStorage.setItem(FALLBACK_KEY, JSON.stringify(this._cache));
  },

  async remove(id) {
    if (this._online) {
      await fetch(`${API}/${id}`, { method: "DELETE" });
      await this.refresh();
      return;
    }
    this._cache = this._cache.filter(p => p.id !== id);
    localStorage.setItem(FALLBACK_KEY, JSON.stringify(this._cache));
  },
};

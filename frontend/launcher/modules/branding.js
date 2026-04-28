/**
 * Branding · v1.7 · 多公司租戶 · 動態讀後端 · cache localStorage
 * =====================================
 * 用法:
 *   import { brand } from "./modules/branding.js";
 *   await brand.load();      // app init 時呼叫
 *   brand.appName            // "智慧助理"(default)
 *   brand.companyShort       // "AI"(logo 用 1-2 字)
 *   brand.tagline            // "AI 協作平台"
 *   brand.accent             // "#3F86C9"
 *   brand.subscribe(cb)      // 訂閱變動(設定改 → re-render UI)
 */

const STORAGE_KEY = "chengfu_branding_v1";

const DEFAULT = {
  company_name: "公司名稱",
  company_short: "AI",
  app_name: "智慧助理",
  tagline: "AI 協作平台",
  accent_color: "#3F86C9",
  locale: "zh-TW",
};

let _state = { ...DEFAULT };
const _listeners = new Set();

function _loadCached() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      _state = { ..._state, ...JSON.parse(raw) };
    }
  } catch {}
}

function _persist() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(_state)); } catch {}
}

function _normalizeBranding(data = {}) {
  const next = { ...DEFAULT, ...data };
  for (const key of Object.keys(DEFAULT)) {
    if (typeof next[key] === "string") next[key] = next[key].trim();
  }
  if (!next.app_name) next.app_name = DEFAULT.app_name;
  if (!next.company_short) next.company_short = DEFAULT.company_short;
  if (!next.company_name) next.company_name = DEFAULT.company_name;
  if (!next.tagline) next.tagline = DEFAULT.tagline;
  if (!next.accent_color) next.accent_color = DEFAULT.accent_color;
  return next;
}

function _emit() {
  _listeners.forEach(cb => { try { cb(_state); } catch (e) { console.warn("[brand] listener fail", e); } });
  // 同步 CSS var(讓 accent 全域生效)
  document.documentElement.style.setProperty("--accent", _state.accent_color);
}

export const brand = {
  /** 從後端拉最新 · 失敗 fallback cache · 失敗 fallback default */
  async load() {
    _loadCached();
    _emit();
    try {
      const r = await fetch("/api-accounting/admin/branding", {
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (r.ok) {
        const data = await r.json();
        _state = _normalizeBranding(data);
        _persist();
        _emit();
      }
    } catch {
      // 後端沒 ready · 用 cache / default
    }
    return _state;
  },

  /** admin 改設定 · PUT(用 window.authFetch 帶 X-User-Email · 避免 plain fetch 403) */
  async update(patch) {
    const cleanPatch = {};
    for (const [key, value] of Object.entries(patch || {})) {
      cleanPatch[key] = typeof value === "string" ? value.trim() : value;
    }
    const fetcher = window.authFetch || fetch;
    const r = await fetcher("/api-accounting/admin/branding", {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cleanPatch),
    });
    if (!r.ok) {
      const err = await r.text().catch(() => "");
      throw new Error(`Branding update failed (${r.status}): ${err.slice(0, 100)}`);
    }
    const data = await r.json();
    _state = _normalizeBranding(data.branding);
    _persist();
    _emit();
    return _state;
  },

  /** 訂閱品牌變動 · 回 unsubscribe */
  subscribe(cb) {
    _listeners.add(cb);
    return () => _listeners.delete(cb);
  },

  // shortcut accessors
  get companyName() { return _state.company_name || DEFAULT.company_name; },
  get companyShort() { return _state.company_short || DEFAULT.company_short; },
  get appName() { return _state.app_name || DEFAULT.app_name; },
  get tagline() { return _state.tagline || "AI 協作平台"; },
  get accent() { return _state.accent_color || "#3F86C9"; },
  get locale() { return _state.locale || "zh-TW"; },
  get state() { return { ..._state }; },
};

if (typeof window !== "undefined") window.brand = brand;

/**
 * Branding · v1.7 · 多公司租戶 · 動態讀後端 · cache localStorage
 * =====================================
 * 用法:
 *   import { brand } from "./modules/branding.js";
 *   await brand.load();      // app init 時呼叫
 *   brand.appName            // "承富智慧助理" 或 "智慧助理"(default)
 *   brand.companyShort       // "承"(logo 用 1-2 字)
 *   brand.tagline            // "10 人協作平台"
 *   brand.accent             // "#007AFF"
 *   brand.subscribe(cb)      // 訂閱變動(設定改 → re-render UI)
 */

const STORAGE_KEY = "chengfu_branding_v1";

const DEFAULT = {
  company_name: "",
  company_short: "",
  app_name: "智慧助理",
  tagline: "AI 協作平台",
  accent_color: "#007AFF",
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
        _state = { ...DEFAULT, ...data };
        _persist();
        _emit();
      }
    } catch {
      // 後端沒 ready · 用 cache / default
    }
    return _state;
  },

  /** admin 改設定 · PUT */
  async update(patch) {
    const r = await fetch("/api-accounting/admin/branding", {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (!r.ok) throw new Error("Branding update failed");
    const data = await r.json();
    _state = { ...DEFAULT, ...data.branding };
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
  get companyName() { return _state.company_name || ""; },
  get companyShort() { return _state.company_short || _state.app_name?.charAt(0) || "智"; },
  get appName() { return _state.app_name || "智慧助理"; },
  get tagline() { return _state.tagline || "AI 協作平台"; },
  get accent() { return _state.accent_color || "#007AFF"; },
  get locale() { return _state.locale || "zh-TW"; },
  get state() { return { ..._state }; },
};

if (typeof window !== "undefined") window.brand = brand;

/**
 * v1.11 · Central state store(architect R1 第一階段)
 * =====================================================
 * 把 app.js god object 內 cross-module 共用的 state 抽出來
 * 取代:
 *   - app.aiProvider         → store.get("engine") / store.set("engine", ...)
 *   - app.activeWorkspace    → store.get("activeWorkspace")
 *   - app.activeProjectId    → store.get("activeProjectId")
 * 並統一 cross-module event:
 *   - "engine-changed"       → store.subscribe("engine", cb)
 *   - "ws-changed"           → store.subscribe("activeWorkspace", cb)
 *
 * 設計:
 *   - 單一 source of truth · localStorage backed
 *   - subscribe(key, cb)·回 unsubscribe(key 變動才 fire)
 *   - subscribeAll(cb)·任一 key 變都 fire(給 dev tool)
 *   - 派發 CustomEvent 給舊聽眾相容(engine-changed / ws-changed)
 *   - 不引入 framework · 純 ES module · ~120 行
 *
 * 未來:user / brand / suppressed 也可進來 · v1.12 一起搬
 */

const STORAGE_PREFIX = "chengfu_store_v1__";

// 註冊 schema · 限制 key 集合 + default + localStorage 綁定 + cross-module event 名
const SCHEMA = {
  engine: {
    default: "openai",
    validate: v => typeof v === "string" && v.length > 0,
    legacyEvent: "engine-changed",
    legacyKey: "chengfu-ai-provider",  // 跟 app.js AI_PROVIDER_KEY 對齊
  },
  activeWorkspace: {
    default: null,
    validate: v => v === null || (typeof v === "string" && v.length <= 32),
    legacyEvent: "ws-changed",
    legacyKey: null,  // 不持久化(URL hash 為 truth)
  },
  activeProjectId: {
    default: null,
    validate: v => v === null || typeof v === "string",
    legacyEvent: null,
    legacyKey: "chengfu-active-project",
  },
};

const _state = {};
const _listeners = new Map();  // Map<key, Set<cb>>
const _allListeners = new Set();

function _readLegacy(key) {
  const def = SCHEMA[key];
  if (!def?.legacyKey) return def?.default ?? null;
  try {
    const raw = localStorage.getItem(def.legacyKey);
    if (raw === null || raw === undefined) return def.default;
    // null sentinel(避免 "null" 字串)
    if (raw === "null") return null;
    return raw;
  } catch {
    return def.default;
  }
}

function _writeLegacy(key, val) {
  const def = SCHEMA[key];
  if (!def?.legacyKey) return;
  try {
    if (val === null || val === undefined) {
      localStorage.removeItem(def.legacyKey);
    } else {
      localStorage.setItem(def.legacyKey, String(val));
    }
  } catch {}
}

function _fire(key, val) {
  // key-level subscribe
  const set = _listeners.get(key);
  if (set) {
    for (const cb of set) {
      try { cb(val, key); } catch (e) { console.warn("[store]", key, "listener fail", e); }
    }
  }
  // global subscribe
  for (const cb of _allListeners) {
    try { cb(val, key); } catch (e) { console.warn("[store] all listener fail", e); }
  }
  // legacy CustomEvent · 給沒換過來的舊 module
  const def = SCHEMA[key];
  if (def?.legacyEvent && typeof document !== "undefined") {
    let detail;
    if (key === "engine") {
      detail = { id: val };
    } else if (key === "activeWorkspace") {
      // v1.13 · dock.js / mobile.js 需要 { ws, view } · 維持原 ws-changed event 契約
      detail = { ws: val == null ? "" : String(val), view: "workspace" };
    } else {
      detail = { value: val };
    }
    document.dispatchEvent(new CustomEvent(def.legacyEvent, { detail }));
  }
}

// ============================================================
// Public API
// ============================================================
export const store = {
  /** 讀目前值 · 不存在回 default */
  get(key) {
    if (!(key in SCHEMA)) {
      console.warn("[store] unknown key:", key);
      return null;
    }
    if (!(key in _state)) {
      _state[key] = _readLegacy(key);
    }
    return _state[key];
  },

  /** 設值 · 過 validate · 寫 localStorage · 派 listener + legacy event */
  set(key, val) {
    if (!(key in SCHEMA)) {
      console.warn("[store] unknown key:", key);
      return;
    }
    const def = SCHEMA[key];
    if (def.validate && !def.validate(val)) {
      console.warn("[store] invalid value for", key, ":", val);
      return;
    }
    const prev = this.get(key);
    if (prev === val) return;  // no-op
    _state[key] = val;
    _writeLegacy(key, val);
    _fire(key, val);
  },

  /** subscribe key · 回 unsubscribe */
  subscribe(key, cb) {
    if (!_listeners.has(key)) _listeners.set(key, new Set());
    _listeners.get(key).add(cb);
    return () => _listeners.get(key)?.delete(cb);
  },

  /** subscribe 所有 key 變動 · 給 devtools / debug */
  subscribeAll(cb) {
    _allListeners.add(cb);
    return () => _allListeners.delete(cb);
  },

  /** debug · 看當前所有 state(snapshot) */
  snapshot() {
    const out = {};
    for (const key in SCHEMA) out[key] = this.get(key);
    return out;
  },
};

// 暴露給非 ESM module(librechat-relabel / dashboard-fpp 等)
if (typeof window !== "undefined") {
  window.chengfuStore = store;
}

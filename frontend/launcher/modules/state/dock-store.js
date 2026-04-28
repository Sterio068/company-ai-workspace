/**
 * Dock Store · v1.4 macOS · Phase 2.1
 * =====================================
 * 持久化 dock 狀態 · localStorage(個人化 · 不跨裝置)
 *
 * 為何不入 Mongo:
 *   - 10 人小團隊 · 個人 dock 偏好不需跨裝置同步
 *   - Mongo 多一個 collection + API endpoint = 半天工 · 不划算
 *   - 既有 localStorage pattern(theme / projects)已建立
 *
 * Schema:
 *   chengfu_dock_v1 = {
 *     items: [
 *       { type: "agent", id: "00", pinned: true },
 *       { type: "agent", id: "09", pinned: true },
 *       ...
 *     ],
 *     version: 1
 *   }
 *
 * Default seed(Issue 1 修 · USER 視角):
 *   開機就有 7 個常用 icon · 老闆登入立即看到滿 dock · 不空
 */

const STORAGE_KEY = "chengfu_dock_v1";

// Default seed · 7 個核心 agent(對應 sidebar 工作區捷徑)
// USER 可右鍵移除 · 動作會 persist · 不會 reset
const DEFAULT_SEED = {
  version: 1,
  items: [
    { type: "agent", id: "00", pinned: true, label: "主管家", icon: "🤖", color: "#5856D6" },
    { type: "agent", id: "01", pinned: true, label: "投標顧問", icon: "🎯", color: "#D14B43" },
    { type: "agent", id: "02", pinned: true, label: "活動策劃", icon: "🎪", color: "#D8851E" },
    { type: "agent", id: "03", pinned: true, label: "設計夥伴", icon: "🎨", color: "#8C5CB1" },
    { type: "agent", id: "04", pinned: true, label: "公關文案", icon: "📣", color: "#5AB174" },
    { type: "agent", id: "06", pinned: true, label: "財務報價", icon: "📊", color: "#3F86C9" },
    { type: "agent", id: "09", pinned: true, label: "知識查手", icon: "📚", color: "#5AC8FA" },
  ],
};

class DockStore extends EventTarget {
  constructor() {
    super();
    this._state = this._load();
  }

  _load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) {
        // 第一次 · 寫 default seed
        this._save(DEFAULT_SEED);
        return structuredClone(DEFAULT_SEED);
      }
      const parsed = JSON.parse(raw);
      // 版本不對 · 棄舊用 default
      if (!parsed || parsed.version !== 1 || !Array.isArray(parsed.items)) {
        return structuredClone(DEFAULT_SEED);
      }
      return parsed;
    } catch (e) {
      console.warn("[dock-store] load failed · 用 default seed", e);
      return structuredClone(DEFAULT_SEED);
    }
  }

  _save(state) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) {
      console.warn("[dock-store] save failed", e);
    }
  }

  _emit() {
    this.dispatchEvent(new CustomEvent("change", { detail: { items: this._state.items } }));
  }

  /** 拿目前 dock items(複本 · 不可外部 mutate) */
  getItems() {
    return structuredClone(this._state.items);
  }

  /** 加一個 item(若不存在)· 例 agent 從 sidebar 拖入 */
  pin(type, id, meta = {}) {
    const exists = this._state.items.find(i => i.type === type && i.id === id);
    if (exists) return false;
    this._state.items.push({ type, id, pinned: true, ...meta });
    this._save(this._state);
    this._emit();
    return true;
  }

  /** 移除 item(右鍵 · 從 Dock 移除) */
  unpin(type, id) {
    const before = this._state.items.length;
    this._state.items = this._state.items.filter(i => !(i.type === type && i.id === id));
    if (this._state.items.length === before) return false;
    this._save(this._state);
    this._emit();
    return true;
  }

  /** 重排 · drag drop 用 · 把 fromIdx 的 item 移到 toIdx */
  reorder(fromIdx, toIdx) {
    const items = this._state.items;
    if (fromIdx < 0 || fromIdx >= items.length || toIdx < 0 || toIdx >= items.length) return;
    if (fromIdx === toIdx) return;
    const [moved] = items.splice(fromIdx, 1);
    items.splice(toIdx, 0, moved);
    this._save(this._state);
    this._emit();
  }

  /** 重設 · 回 default seed(右鍵 dock 空白 → 重設 · Sprint A 暫不做 UI) */
  reset() {
    this._state = structuredClone(DEFAULT_SEED);
    this._save(this._state);
    this._emit();
  }

  /** 訂閱 change · 給 dock.js render 用 */
  subscribe(callback) {
    const handler = (e) => callback(e.detail.items);
    this.addEventListener("change", handler);
    return () => this.removeEventListener("change", handler);
  }
}

export const dockStore = new DockStore();

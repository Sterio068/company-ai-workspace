/**
 * macOS Keyboard Shortcuts · v1.4 Sprint C Phase 6
 * =====================================
 * 全套對齊 menubar 顯示的 shortcut · 全域 listen
 *
 * 已分散在各 module 的 shortcut(避免衝突):
 *   - ⌘W · window.js · 關 active window
 *   - ⌃⌘N · notification-center.js · 開 NC
 *   - ⌃⌘C · control-center.js · 開 CC
 *   - ⌘K · 既有 palette.js
 *   - ⌘1-5 · 既有 keyboard.js / shortcuts.js workspace 切
 *
 * 此檔加 menubar dropdown 對應的:
 *   - ⌘N · 新對話(主管家)
 *   - ⌘⇧N · 新工作包
 *   - ⌘O · 開啟工作包
 *   - ⌘E · 匯出對話
 *   - ⌘P · 工作包頁
 *   - ⌘0 · 今日
 *   - ⌘⇧L · 切深淺色
 *   - ⌃⌘F · 全螢幕
 *   - ⌘? · 教學
 *   - ⌘, · 偏好設定(中控)
 *   - ⌘⇧Q · 登出
 *
 * 衝突處理:
 *   - 若 chat input focus · ⌘N 等讓給 OS / browser
 *   - 若 modal / dropdown 開著 · 部分 disable
 */

// v1.50 · 共享 actions.js · 不再各自重寫 theme/fullscreen/logout
import { toggleTheme as _toggleTheme, toggleFullscreen as _toggleFullscreen, confirmLogout as _confirmLogout } from "./actions.js";

// v1.49 · ⌘0 / ⌘P / ⌘1-5 / ⌘L 已由 keyboard.js 處理 · 移除重複避免 double-fire
// 此處只放 keyboard.js 沒有的:⌘N / ⇧⌘N / ⌃⌘F / ⌘/ / ⌘, / ⇧⌘Q
const SHORTCUTS = [
  // 新建
  { key: "n",     mod: "meta",                   action: () => window.app?.openAgent?.("00") },
  { key: "n",     mod: "meta+shift",             action: () => window.app?.showView?.("projects") },
  // 主題 / 顯示
  { key: "l",     mod: "meta+shift",             action: () => _toggleTheme() },
  { key: "f",     mod: "ctrl+meta",              action: () => _toggleFullscreen() },
  // 教學 / 設定
  { key: "/",     mod: "meta",                   action: () => window.app?.showView?.("help") },
  { key: ",",     mod: "meta",                   action: () => window.app?.showView?.("admin") },
  // 登出
  { key: "q",     mod: "meta+shift",             action: () => _confirmLogout() },
];

function _matches(e, shortcut) {
  if (e.key.toLowerCase() !== shortcut.key.toLowerCase()) return false;
  const meta = e.metaKey || e.ctrlKey;
  const shift = e.shiftKey;
  const ctrl = e.ctrlKey;
  switch (shortcut.mod) {
    case "meta":           return meta && !shift && !(e.altKey);
    case "meta+shift":     return meta && shift;
    case "ctrl+meta":      return e.metaKey && ctrl;
    default: return false;
  }
}

function _isInputActive() {
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName?.toLowerCase();
  return tag === "input" || tag === "textarea" || el.isContentEditable;
}

document.addEventListener("keydown", (e) => {
  // 不處理修飾鍵單按
  if (!e.metaKey && !e.ctrlKey) return;
  for (const sc of SHORTCUTS) {
    if (!_matches(e, sc)) continue;
    if (sc.noInput && _isInputActive()) continue;
    e.preventDefault();
    try { sc.action(); } catch (err) { console.warn("[shortcut] action failed", err); }
    return;
  }
}, { capture: true });

if (typeof window !== "undefined") {
  window.macShortcuts = { SHORTCUTS };
}

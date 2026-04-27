/**
 * macOS shell · 共享 chrome 動作
 * v1.50 · 從 menubar.js / shortcuts.js / control-center.js 各自重複的實作抽出
 *
 * 之前狀態:
 *   - shortcuts.js _toggleTheme 寫 localStorage('chengfu-theme', ...) · toast
 *   - menubar.js   _toggleTheme 寫 localStorage('chengfu-theme', ...) · toast
 *   - control-center.js _setTheme 寫 localStorage('chengfu-theme', ...) · 不 toast · 還 _render
 *   → 三套各漂移 · 容易出 bug · CC 改 theme 時 menubar 不 sync
 *
 * 抽出後:
 *   - 單一 setTheme(id) · 單一 toggleTheme() · 單一 fullscreen toggle · 單一 logout
 *   - 派 'theme-changed' CustomEvent · 任何想 sync 的模組 listen 即可
 */

const THEME_KEY = "chengfu-theme";

export function setTheme(id) {
  const html = document.documentElement;
  html.dataset.theme = id;
  localStorage.setItem(THEME_KEY, id);
  document.dispatchEvent(new CustomEvent("theme-changed", { detail: { theme: id } }));
}

export function toggleTheme() {
  const cur = document.documentElement.dataset.theme || "light";
  // auto 視為 light → dark · 第一次切會 lock 到 dark
  const next = cur === "dark" ? "light" : "dark";
  setTheme(next);
  window.toast?.info?.(`已切到 ${next === "dark" ? "深色" : "淺色"}`);
}

export function isFullscreen() {
  return Boolean(document.fullscreenElement);
}

export function toggleFullscreen() {
  if (isFullscreen()) {
    document.exitFullscreen?.();
  } else {
    document.documentElement.requestFullscreen?.();
  }
}

export function confirmLogout(message = "確定要登出?未送出的對話會丟失。") {
  if (confirm(message)) {
    window.location.href = "/chat/logout";
  }
}

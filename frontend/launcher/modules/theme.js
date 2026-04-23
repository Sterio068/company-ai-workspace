/**
 * v1.3 A2 · Theme module(從 app.js 抽出 · 純 DOM 操作)
 *
 * 用法:
 *   import { theme } from "./modules/theme.js";
 *   theme.apply();        // 載 localStorage 偏好
 *   theme.toggle();       // auto → light → dark → auto loop
 *
 * 配合 launcher.css :root[data-theme="dark"] { ... } 套色
 * auto 跟系統 prefers-color-scheme(launcher.css 已 @media 處理)
 */
const STORAGE_KEY = "chengfu-theme";
const VALUES = ["auto", "light", "dark"];

export const theme = {
  apply() {
    const saved = localStorage.getItem(STORAGE_KEY) || "auto";
    document.documentElement.dataset.theme = saved;
  },

  toggle() {
    const cur = document.documentElement.dataset.theme || "auto";
    const idx = VALUES.indexOf(cur);
    const next = VALUES[(idx + 1) % VALUES.length];
    document.documentElement.dataset.theme = next;
    localStorage.setItem(STORAGE_KEY, next);
    return next;
  },

  current() {
    return document.documentElement.dataset.theme || "auto";
  },
};

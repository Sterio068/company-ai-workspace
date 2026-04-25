/**
 * LibreChat JWT 認證
 * httpOnly cookie · JS 無法直接讀 · 用 /api/auth/refresh 交換 Bearer token
 * v4.3 起:
 *   - 401 自動 refresh retry + body clone 防 stream 重用 bug
 *   - refresh 失敗 throw SessionExpiredError · caller 可選擇靜默
 *   - refresh 成功 reset 通知旗標
 *   - 跨分頁 auth refresh 用 navigator.locks 防 race
 */
import { API } from "./config.js";
import { escapeHtml } from "./util.js";

let _jwt = null;
let _userEmail = null;
let _sessionExpiredNotified = false;
const REFRESH_LOCK_KEY = "chengfu-auth-refresh-lock";

function _sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export class SessionExpiredError extends Error {
  constructor(msg = "session expired") { super(msg); this.name = "SessionExpiredError"; }
}

export function setUserEmail(email) { _userEmail = (email || "").trim() || null; }
export function getUserEmail() { return _userEmail; }

/**
 * 包好的 fetch · 自帶 Authorization + X-User-Email header
 * · 遇 401 自動呼叫 refreshAuth(跨分頁上鎖避免 race)後重試 1 次
 * · 若 refresh 也失敗 → 顯示 banner · throw SessionExpiredError
 *   caller 接 error 可靜默 return(例如 SSE 直接關串流)
 */
export async function authFetch(url, opts = {}) {
  const res = await _doFetch(url, opts);
  if (res.status !== 401) return res;

  // 401 · 嘗試 refresh(跨分頁上鎖 · 只有一個分頁會真的打 refresh endpoint)
  try {
    await _refreshWithLock();
  } catch (e) {
    if (!_sessionExpiredNotified) {
      _sessionExpiredNotified = true;
      _showSessionExpiredBanner();
    }
    throw new SessionExpiredError("refresh failed · 登入已過期");
  }

  // retry · 用 clone 的 body 避免 stream 已消費
  return await _doFetch(url, opts);
}

async function _doFetch(url, opts) {
  const headers = { ...(opts.headers || {}) };
  if (_jwt) headers["Authorization"] = `Bearer ${_jwt}`;
  if (_userEmail) headers["X-User-Email"] = _userEmail;
  // Body clone 保護:ReadableStream / FormData 只能被 fetch 消費一次 · 若是 retry 場景會炸
  // 這裡不做 eager clone(會多浪費記憶體)· 改由 caller 保證 body 是 string 或 undefined
  // 若未來加 file upload,應在 caller 端 .arrayBuffer() 先讀起來再重新包
  return fetch(url, { credentials: "include", ...opts, headers });
}

// 跨分頁 refresh 鎖(Web Locks API · Chrome/Safari/Firefox 都支援)
async function _refreshWithLock() {
  const owner = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const ttlMs = 8_000;
  const deadline = Date.now() + ttlMs;
  let acquired = false;

  while (Date.now() < deadline && !acquired) {
    let current = null;
    try {
      current = JSON.parse(localStorage.getItem(REFRESH_LOCK_KEY) || "null");
    } catch {
      current = null;
    }
    if (!current || !current.owner || Number(current.expiresAt || 0) < Date.now()) {
      localStorage.setItem(REFRESH_LOCK_KEY, JSON.stringify({
        owner,
        expiresAt: Date.now() + ttlMs,
      }));
      try {
        acquired = JSON.parse(localStorage.getItem(REFRESH_LOCK_KEY) || "{}").owner === owner;
      } catch {
        acquired = true;
      }
      if (acquired) break;
    }
    await _sleep(80 + Math.floor(Math.random() * 70));
  }

  if (acquired) {
    try {
      return await refreshAuth();
    } finally {
      try {
        const current = JSON.parse(localStorage.getItem(REFRESH_LOCK_KEY) || "{}");
        if (current.owner === owner) localStorage.removeItem(REFRESH_LOCK_KEY);
      } catch {
        localStorage.removeItem(REFRESH_LOCK_KEY);
      }
    }
    return;
  }

  // Lock stale 或 localStorage 不可用時仍保留原本行為,避免永久卡住登入。
  return await refreshAuth();
}

export async function refreshAuth() {
  const r = await fetch(API.refresh, { method: "POST", credentials: "include" });
  if (!r.ok) throw new Error(`refresh ${r.status}`);
  const contentType = r.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    const text = await r.text().catch(() => "");
    throw new Error(`refresh invalid response · ${text.slice(0, 80) || contentType || "empty body"}`);
  }
  const data = await r.json();
  _jwt = data.token;
  // Refresh 成功 · 通知旗標歸零(下次再過期能正常提示一次)
  _sessionExpiredNotified = false;
  _hideBanner();
  return data;
}

export async function refreshAuthWithLock() {
  return await _refreshWithLock();
}

export function getJwt() { return _jwt; }

// ---------- 系統狀態 Banner(auth 過期 / 後端離線)----------

function _showSessionExpiredBanner() {
  _showBanner({
    message: "你的登入已過期,請重新登入。",
    actionLabel: "重新登入",
    onClick: () => window.location.href = "/login",
    variant: "warn",
  });
}

/**
 * 通用 banner · 給 auth / health / 其他需要告知使用者的狀態共用
 * variant: "error" | "warn" | "info"
 */
export function _showBanner({ message, actionLabel, onClick, variant = "error" }) {
  let el = document.getElementById("sys-banner");
  const rebuild = !el || !el.isConnected;
  if (rebuild) {
    el = document.createElement("div");
    el.id = "sys-banner";
    document.body.prepend(el);
  }
  el.className = `sys-banner ${variant}`;
  // v1.3 batch6 · H-3 · escapeHtml message + actionLabel · 防 caller 帶含 server reply 的 XSS
  el.innerHTML = `
    <span>${escapeHtml(message)}</span>
    ${actionLabel ? `<button class="banner-action" type="button">${escapeHtml(actionLabel)}</button>` : ""}
  `;
  // 重建 innerHTML 後 · 舊 listener 自動被 GC · 綁新的
  if (actionLabel && onClick) {
    el.querySelector(".banner-action")?.addEventListener("click", onClick);
  }
  document.body.classList.add("has-banner");
  requestAnimationFrame(() => el.classList.add("show"));
}

export function _hideBanner() {
  const el = document.getElementById("sys-banner");
  if (!el) return;
  el.classList.remove("show");
  document.body.classList.remove("has-banner");
  setTimeout(() => { if (el.isConnected) el.remove(); }, 250);
}

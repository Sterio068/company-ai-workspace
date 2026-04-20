/**
 * LibreChat JWT 認證
 * httpOnly cookie · JS 無法直接讀 · 用 /api/auth/refresh 交換 Bearer token
 */
import { API } from "./config.js";

let _jwt = null;

export async function authFetch(url, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (_jwt) headers["Authorization"] = `Bearer ${_jwt}`;
  return fetch(url, { credentials: "include", ...opts, headers });
}

export async function refreshAuth() {
  const r = await fetch(API.refresh, { method: "POST", credentials: "include" });
  if (!r.ok) throw new Error(`refresh ${r.status}`);
  const data = await r.json();
  _jwt = data.token;
  return data;
}

export function getJwt() { return _jwt; }

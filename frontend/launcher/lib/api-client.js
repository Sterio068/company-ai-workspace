/**
 * Thin OpenAPI-oriented client for launcher modules.
 *
 * The project is still vanilla ES modules, so this intentionally stays small:
 * - one authFetch entrypoint
 * - consistent JSON parsing
 * - ApiError carries status + response body
 *
 * Types are generated into `api-types.ts` by `npm run generate:api-types`.
 */
import { authFetch } from "../modules/auth.js";

export const ACCOUNTING_API = "/api-accounting";
export const LIBRECHAT_API = "/api";

export class ApiError extends Error {
  constructor(message, { status = 0, body = null, url = "" } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
    this.url = url;
  }
}

export async function apiGet(path, options = {}) {
  return apiRequest(path, { ...options, method: "GET" });
}

export async function apiPost(path, body, options = {}) {
  return apiRequest(path, {
    ...options,
    method: "POST",
    body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
    headers: body instanceof FormData ? options.headers : {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
}

export async function apiPut(path, body, options = {}) {
  return apiRequest(path, {
    ...options,
    method: "PUT",
    body: JSON.stringify(body ?? {}),
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
}

export async function apiDelete(path, options = {}) {
  return apiRequest(path, { ...options, method: "DELETE" });
}

export async function apiRequest(path, options = {}) {
  const base = options.base === "librechat" ? LIBRECHAT_API : ACCOUNTING_API;
  const url = path.startsWith("http") || path.startsWith("/")
    ? (path.startsWith("/api") ? path : `${base}${path}`)
    : `${base}/${path}`;
  const { base: _base, ...fetchOptions } = options;
  const response = await authFetch(url, fetchOptions);
  const body = await parseBody(response);
  if (!response.ok) {
    throw new ApiError(`API ${response.status}: ${response.statusText}`, {
      status: response.status,
      body,
      url,
    });
  }
  return body;
}

async function parseBody(response) {
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json().catch(() => null);
  }
  return response.text().catch(() => "");
}

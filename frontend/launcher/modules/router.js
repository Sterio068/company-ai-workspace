/**
 * Launcher view routing.
 *
 * Keeps hash parsing and active-view DOM state out of app.js. View-specific
 * loading still lives in app.js so modules can migrate one by one.
 */
export const ROUTED_VIEWS = [
  "projects",
  "skills",
  "dashboard",
  "workspace",
  "accounting",
  "admin",
  "tenders",
  "workflows",
  "crm",
  "knowledge",
  "help",
  "meeting",
  "media",
  "social",
  "site",
  "users",
];

const VIEW_TO_WS = {
  dashboard: "0",
};

export function routeFromHash(hash = window.location.hash) {
  const route = String(hash || "").replace("#", "");
  if (/^workspace-[1-5]$/.test(route)) return "workspace";
  return route;
}

export function isRoutableView(view) {
  return ROUTED_VIEWS.includes(view);
}

export function activateLauncherView(view) {
  document.querySelectorAll(".view").forEach(el => {
    el.classList.toggle("active", el.dataset.view === view);
  });
  document.querySelectorAll(".nav-item").forEach(el => {
    el.classList.toggle("active", el.dataset.view === view);
  });

  if (view === "dashboard") {
    history.pushState("", document.title, window.location.pathname);
  } else if (view !== "workspace" && !window.location.hash.startsWith(`#${view}`)) {
    window.location.hash = view;
  }

  const ws = VIEW_TO_WS[view] || "0";
  document.dispatchEvent(new CustomEvent("ws-changed", { detail: { ws, view } }));
  setTimeout(() => document.getElementById("main-content")?.focus(), 50);
}

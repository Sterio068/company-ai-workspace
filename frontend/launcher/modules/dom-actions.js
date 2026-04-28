/**
 * Delegated DOM actions for static index.html.
 *
 * Replaces historical inline onclick/onsubmit handlers with explicit
 * allowlisted data-action names. This keeps CSP/XSS posture tighter while
 * preserving the same UX.
 */
const ACTIONS = {
  "app.toggleTheme": () => window.app?.toggleTheme?.(),
  "app.openPalette": () => window.app?.openPalette?.(),
  "app.newProject": () => window.app?.newProject?.(),
  "app.openWorkspace": arg => window.app?.openWorkspace?.(Number(arg)),
  "app.openAgent": arg => window.app?.openAgent?.(arg),
  "app.showView": arg => window.app?.showView?.(arg),
  "app.startWorkspaceDraft": () => window.app?.startWorkspaceDraft?.(),
  "app.openCreateSource": () => window.app?.openCreateSource?.(),
  "app.loadConversations": () => window.app?.loadConversations?.(),
  "app.openProjectDrawer": arg => window.app?.openProjectDrawer?.(arg),
  "app.startProjectPlanner": () => window.app?.startProjectPlanner?.(),
  "app.runWorkAction": arg => window.app?.runWorkAction?.(arg),
  "app.closeProjectDrawer": () => window.app?.closeProjectDrawer?.(),
  "app.editProjectFromDrawer": () => window.app?.editProjectFromDrawer?.(),
  "app.summarizeProjectWithAI": () => window.app?.summarizeProjectWithAI?.(),
  "app.saveHandoff": () => window.app?.saveHandoff?.(),
  "app.copyHandoff": arg => window.app?.copyHandoff?.(arg),
  "app.insertHandoffToChat": () => window.app?.insertHandoffToChat?.(),
  "app.closeProjectModal": () => window.app?.closeProjectModal?.(),
  "app.deleteProject": () => window.app?.deleteProject?.(),
  "app.closePalette": () => window.app?.closePalette?.(),
  "chat.close": () => window.chat?.close?.(),
  "chat.newConversation": () => window.chat?.newConversation?.(),
  "chat.history": () => window.chat?.history?.(),
  "chat.toggleFullscreen": () => window.chat?.toggleFullscreen?.(),
  "chat.pickFile": () => window.chat?.pickFile?.(),
  "tour.skip": () => window.tour?.skip?.(),
  "tour.next": () => window.tour?.next?.(),
  "accounting.newInvoice": async () => (await window._loadView?.("accounting"))?.newInvoice?.(),
  "accounting.newQuote": async () => (await window._loadView?.("accounting"))?.newQuote?.(),
  "accounting.newTransaction": async () => (await window._loadView?.("accounting"))?.newTransaction?.(),
  "tenders.runNow": async () => (await window._loadView?.("tenders"))?.runNow?.(),
  "tenders.refresh": async () => (await window._loadView?.("tenders"))?.refresh?.(),
  "crm.importFromTenders": async () => (await window._loadView?.("crm"))?.importFromTenders?.(),
  "crm.newLead": async () => (await window._loadView?.("crm"))?.newLead?.(),
  "admin.refresh": async () => (await window._loadView?.("admin"))?.refresh?.(),
  "workflows.load": async () => (await window._loadView?.("workflows"))?.load?.(),
  "knowledge.loadAdmin": () => window.knowledge?.loadAdmin?.(),
  "knowledge.loadBrowser": () => window.knowledge?.loadBrowser?.(),
  "siteSurvey.loadHistory": async () => (await window._loadView?.("siteSurvey"))?._loadHistory?.(),
  "window.reload": () => window.location.reload(),
};

const SUBMIT_ACTIONS = {
  "app.submitHeroInput": event => window.app?.submitHeroInput?.(event),
  "app.saveProject": event => window.app?.saveProject?.(event),
  "chat.send": event => window.chat?.send?.(event),
  "brand.update": async event => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await window.brand?.update?.(Object.fromEntries(new FormData(form)));
      window.toast?.success?.("品牌已更新");
    } catch (e) {
      window.toast?.error?.("品牌更新失敗", { detail: e?.message || String(e) });
    }
  },
};

const INPUT_ACTIONS = {
  "app.searchProjects": event => window.app?.searchProjects?.(event),
  "chat.onInput": event => window.chat?.onInput?.(event),
};

const KEYDOWN_ACTIONS = {
  "chat.onKey": event => window.chat?.onKey?.(event),
};

const CHANGE_ACTIONS = {
  "app.addTodayFiles": event => {
    const input = event.currentTarget;
    window.app?.addTodayFiles?.(Array.from(input.files || []));
    input.value = "";
  },
};

let installed = false;

export function installDomActions() {
  if (installed) return;
  installed = true;
  document.addEventListener("click", handleClick);
  document.addEventListener("submit", handleSubmit);
  document.addEventListener("input", handleInput);
  document.addEventListener("keydown", handleKeydown);
  document.addEventListener("change", handleChange);
}

async function handleClick(event) {
  const el = event.target.closest("[data-action]");
  if (!el) return;
  const action = ACTIONS[el.dataset.action];
  if (!action) return;
  if (el.tagName === "A") event.preventDefault();
  await action(el.dataset.actionArg, event);
}

function handleSubmit(event) {
  const form = event.target.closest("[data-submit-action]");
  if (!form) return;
  const action = SUBMIT_ACTIONS[form.dataset.submitAction];
  if (!action) return;
  action(event);
}

function handleInput(event) {
  const actionName = event.target?.dataset?.inputAction;
  const action = INPUT_ACTIONS[actionName];
  if (action) action(event);
}

function handleKeydown(event) {
  const actionName = event.target?.dataset?.keydownAction;
  const action = KEYDOWN_ACTIONS[actionName];
  if (action) {
    action(event);
    return;
  }
  const clickable = event.target?.closest?.('[role="button"][data-action]');
  if (!clickable || !["Enter", " "].includes(event.key)) return;
  event.preventDefault();
  clickable.click();
}

function handleChange(event) {
  const actionName = event.target?.dataset?.changeAction;
  const action = CHANGE_ACTIONS[actionName];
  if (action) action(event);
}

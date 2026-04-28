/**
 * Global keyboard shortcuts for Launcher.
 *
 * app.js injects behavior so this module can stay independent from view modules.
 */
export function setupGlobalKeyboard(actions = {}) {
  document.addEventListener("keydown", event => {
    const mod = event.metaKey || event.ctrlKey;
    const target = event.target;
    const inEditable = target instanceof Element
      && target.matches("input,textarea,[contenteditable]");

    if (mod && event.key === "k") {
      event.preventDefault();
      actions.openPalette?.();
      return;
    }
    if (mod && event.key === "0") {
      event.preventDefault();
      actions.showView?.("dashboard");
      return;
    }
    if (mod && event.key === "p") {
      event.preventDefault();
      actions.showView?.("projects");
      return;
    }
    if (mod && event.key === "l") {
      event.preventDefault();
      actions.showView?.("skills");
      return;
    }
    if (mod && "12345".includes(event.key) && !inEditable) {
      event.preventDefault();
      actions.openWorkspace?.(parseInt(event.key, 10));
      return;
    }
    if (mod && "6789".includes(event.key) && !inEditable) {
      event.preventDefault();
      actions.openAgent?.(`0${event.key}`);
      return;
    }
    if (mod && event.key === "a" && !inEditable) {
      event.preventDefault();
      actions.openAccounting?.();
      return;
    }
    if (mod && event.key === "m" && !inEditable && actions.isAdmin?.()) {
      event.preventDefault();
      actions.openAdmin?.();
      return;
    }
    if (mod && event.key === "u" && !inEditable && actions.isAdmin?.()) {
      event.preventDefault();
      actions.showView?.("users");
      return;
    }
    if (mod && event.key === "t" && !inEditable) {
      event.preventDefault();
      actions.openTenders?.();
      return;
    }
    if (mod && event.key === "w" && !inEditable) {
      event.preventDefault();
      actions.openWorkflows?.();
      return;
    }
    if (mod && event.key === "i" && !inEditable) {
      event.preventDefault();
      actions.openCrm?.();
      return;
    }

    if ((event.key === "?" || (event.key === "/" && event.shiftKey)) && !inEditable) {
      event.preventDefault();
      actions.toggleShortcuts?.();
      return;
    }

    if (event.key === "Escape") {
      actions.closePalette?.();
      actions.closeProjectModal?.();
      if (!document.getElementById("project-modal")?.classList.contains("open")) {
        actions.closeProjectDrawer?.();
      }
      if (document.getElementById("chat-pane")?.classList.contains("open")
          && !document.querySelector(".modal2-box.open")
          && !document.querySelector(".palette.open")) {
        actions.closeChat?.();
      }
    }
  });
}

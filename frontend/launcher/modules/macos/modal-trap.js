/**
 * v1.32 · Modal focus trap utility(architect A4 修)
 * v1.35 · F1 + F2 強化 · 加 contenteditable / summary / iframe / radio group
 *         + 修 offsetParent fixed bug + 0-focusable fallback + dialog role
 * =====================================================
 * 給 fpp-builder / fpp-inbox / 任何 modal 用
 * WCAG 2.4.3 Focus Order + 4.1.2 Name/Role/Value
 *
 * 行為:
 *   - trap(overlayEl, options)
 *     · 記下開 modal 前 focused 的 element(returnFocus 用)
 *     · 第一個 focusable 自動 focus(initialFocusSelector 可指定)
 *     · Tab/Shift+Tab 在 modal 內 cycle · 不會逃出
 *     · 0 focusable 時 focus 到 overlay 本體(防 user Tab 走)
 *     · 標 role="dialog" + aria-modal="true"(若 overlay 還沒設)
 *     · #app inert(讓 SR + 鍵盤都不跑出 modal · v1.35 F1 修)
 *     · 回 release() · close 時呼叫 · 恢復原 focus + 解除 inert
 */

// v1.35 F2 修 · 加 contenteditable / summary / iframe / audio,video[controls]
// （radio group 不在這裡 trap · 用 role="radiogroup" 自管方向鍵 · 但 radio 仍可 Tab 進來)
const FOCUSABLE_SELECTOR = [
  'a[href]:not([disabled])',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'summary',
  'iframe',
  'audio[controls]',
  'video[controls]',
  '[contenteditable=""]',
  '[contenteditable="true"]',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

// v1.35 F2 修 · 比 offsetParent 安全的 visible 偵測
// fixed/sticky 元素 offsetParent 永遠 null · 會誤判為 hidden
function _isVisible(el) {
  if (!el) return false;
  if (el.hasAttribute("hidden") || el.getAttribute("aria-hidden") === "true") return false;
  if (el.disabled) return false;
  // getClientRects 在 fixed / sticky 都正確 · 純 display:none 才回空
  return el.getClientRects().length > 0;
}

/**
 * @param {HTMLElement} overlay - modal 根元素
 * @param {{ initialFocusSelector?: string }} options
 * @returns {() => void} release 函式 · close 時呼叫恢復 focus
 */
export function trap(overlay, options = {}) {
  if (!overlay) return () => {};
  const { initialFocusSelector, labelledBy, label } = options;

  // 記錄開 modal 前 focused element · 關時回復
  const previousFocus = document.activeElement;

  // v1.35 F1 修 · 加 dialog role + aria-modal · SR 知道是 modal
  // 不覆蓋已設的 role(caller 可能用 alertdialog)
  const _setAttrs = {};
  if (!overlay.hasAttribute("role")) {
    overlay.setAttribute("role", "dialog");
    _setAttrs.role = true;
  }
  if (!overlay.hasAttribute("aria-modal")) {
    overlay.setAttribute("aria-modal", "true");
    _setAttrs.ariaModal = true;
  }
  if (labelledBy && !overlay.hasAttribute("aria-labelledby")) {
    overlay.setAttribute("aria-labelledby", labelledBy);
    _setAttrs.labelledBy = true;
  } else if (label && !overlay.hasAttribute("aria-label")) {
    overlay.setAttribute("aria-label", label);
    _setAttrs.label = true;
  }

  // v1.35 F1 修 · #app inert · SR 不會跑出 modal · 鍵盤 Tab 也擋
  // (overlay 通常 append 到 body 外層 · 跟 #app 平行 · inert 不影響它本身)
  const appEl = document.getElementById("app");
  let _appInertAdded = false;
  if (appEl && !appEl.hasAttribute("inert")) {
    appEl.setAttribute("inert", "");
    _appInertAdded = true;
  }

  // 第一個 focus
  let initial = null;
  if (initialFocusSelector) {
    initial = overlay.querySelector(initialFocusSelector);
  }
  if (!initial) {
    const all = Array.from(overlay.querySelectorAll(FOCUSABLE_SELECTOR)).filter(_isVisible);
    initial = all[0];
  }
  // v1.35 F2 修 · 0 focusable 時 fallback focus overlay 本體(防 user Tab 走)
  if (!initial && !overlay.hasAttribute("tabindex")) {
    overlay.setAttribute("tabindex", "-1");
    _setAttrs.tabindex = true;
    initial = overlay;
  }
  if (initial) {
    requestAnimationFrame(() => {
      try { initial.focus(); } catch {}
    });
  }

  // Tab trap handler
  function _onKeydown(e) {
    if (e.key !== "Tab") return;
    // v1.35 F2 修 · 用 _isVisible(支援 fixed) · 不再用 offsetParent
    const focusable = Array.from(overlay.querySelectorAll(FOCUSABLE_SELECTOR)).filter(_isVisible);
    if (focusable.length === 0) {
      // 0 focusable · 鎖在 overlay 本體
      e.preventDefault();
      try { overlay.focus(); } catch {}
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;

    if (e.shiftKey) {
      if (active === first || !overlay.contains(active)) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (active === last || !overlay.contains(active)) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  overlay.addEventListener("keydown", _onKeydown);

  return function release() {
    overlay.removeEventListener("keydown", _onKeydown);
    // 解除 #app inert
    if (_appInertAdded && appEl) appEl.removeAttribute("inert");
    // 還原 trap 自動加的屬性(caller 自己加的不動)
    if (_setAttrs.role) overlay.removeAttribute("role");
    if (_setAttrs.ariaModal) overlay.removeAttribute("aria-modal");
    if (_setAttrs.labelledBy) overlay.removeAttribute("aria-labelledby");
    if (_setAttrs.label) overlay.removeAttribute("aria-label");
    if (_setAttrs.tabindex) overlay.removeAttribute("tabindex");
    // 恢復 focus 到開 modal 前的 element(若仍存在 + 在 DOM)
    if (previousFocus && document.body.contains(previousFocus)) {
      try { previousFocus.focus(); } catch {}
    }
  };
}

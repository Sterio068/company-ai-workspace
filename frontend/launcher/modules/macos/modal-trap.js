/**
 * v1.32 · Modal focus trap utility(architect A4 修)
 * =====================================================
 * 給 fpp-builder / fpp-inbox / 任何 modal 用 · WCAG 2.4.3 Focus Order
 *
 * 行為:
 *   - trap(overlayEl, options)
 *     · 記下開 modal 前 focused 的 element(returnFocus 用)
 *     · 第一個 focusable 自動 focus(initialFocusSelector 可指定)
 *     · Tab/Shift+Tab 在 modal 內 cycle · 不會逃出
 *     · 回 release() · close 時呼叫 · 恢復原 focus
 *
 * 使用:
 *   const release = trap(overlay, { initialFocusSelector: '#fpp-builder-name' });
 *   // ... user 互動
 *   release();  // close 時
 */

const FOCUSABLE_SELECTOR = [
  'a[href]:not([disabled])',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

/**
 * @param {HTMLElement} overlay - modal 根元素
 * @param {{ initialFocusSelector?: string }} options
 * @returns {() => void} release 函式 · close 時呼叫恢復 focus
 */
export function trap(overlay, options = {}) {
  if (!overlay) return () => {};
  const { initialFocusSelector } = options;

  // 記錄開 modal 前 focused element · 關時回復
  const previousFocus = document.activeElement;

  // 第一個 focus
  let initial = null;
  if (initialFocusSelector) {
    initial = overlay.querySelector(initialFocusSelector);
  }
  if (!initial) {
    const all = overlay.querySelectorAll(FOCUSABLE_SELECTOR);
    initial = all[0];
  }
  if (initial) {
    // 等 modal 動畫完才 focus(避免動畫期間 layout shift)
    requestAnimationFrame(() => {
      try { initial.focus(); } catch {}
    });
  }

  // Tab trap handler
  function _onKeydown(e) {
    if (e.key !== "Tab") return;
    const focusable = Array.from(overlay.querySelectorAll(FOCUSABLE_SELECTOR))
      .filter(el => el.offsetParent !== null);  // 過濾 hidden
    if (focusable.length === 0) {
      e.preventDefault();
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
    // 恢復 focus 到開 modal 前的 element(若仍存在 + 在 DOM)
    if (previousFocus && document.body.contains(previousFocus)) {
      try { previousFocus.focus(); } catch {}
    }
  };
}

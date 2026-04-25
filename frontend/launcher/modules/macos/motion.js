/**
 * macOS Motion · v1.4 · Phase 2 動畫 helper
 * =====================================
 * 用 Web Animations API · 0 dependency
 * Spring 用 cubic-bezier(0.34, 1.56, 0.64, 1)模仿 SwiftUI .spring()
 *
 * 為何不引 Motion One / GSAP:
 *   - 此 launcher 場景 · spring + slide + fade 用 WAAPI 已夠
 *   - 0 KB extra · Native API 60fps GPU 加速
 *   - prefers-reduced-motion 自動 respect
 *
 * 公開 API:
 *   springEnter(el, options)  · dock 從底滑入
 *   fadeIn(el, options)
 *   slideUp(el, options)
 *   pulse(el)                 · 注意點動畫
 */

const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Spring approximation cubic · 對齊 SwiftUI .spring(.gentle) */
const SPRING_EASING = "cubic-bezier(0.34, 1.56, 0.64, 1)";
const EXPO_OUT = "cubic-bezier(0.16, 1, 0.3, 1)";

/** Dock 從底部彈起 · macOS Sequoia App opening 風格 */
export function springEnter(el, {
  fromY = 80,
  toY = 0,
  fromOpacity = 0,
  toOpacity = 1,
  duration = REDUCED ? 0 : 500,
  delay = 0,
} = {}) {
  if (!el || !el.animate) return null;
  return el.animate(
    [
      { transform: `translateX(-50%) translateY(${fromY}px)`, opacity: fromOpacity },
      { transform: `translateX(-50%) translateY(${toY}px)`, opacity: toOpacity },
    ],
    {
      duration,
      delay,
      easing: SPRING_EASING,
      fill: "both",
    },
  );
}

/** 通用 fade in */
export function fadeIn(el, { duration = REDUCED ? 0 : 200, delay = 0 } = {}) {
  if (!el || !el.animate) return null;
  return el.animate(
    [{ opacity: 0 }, { opacity: 1 }],
    { duration, delay, easing: EXPO_OUT, fill: "both" },
  );
}

/** Slide up 從底滑入(non-spring · 給 menu / sheet 用) */
export function slideUp(el, { duration = REDUCED ? 0 : 280, delay = 0, distance = 12 } = {}) {
  if (!el || !el.animate) return null;
  return el.animate(
    [
      { transform: `translateY(${distance}px)`, opacity: 0 },
      { transform: "translateY(0)", opacity: 1 },
    ],
    { duration, delay, easing: EXPO_OUT, fill: "both" },
  );
}

/** Pulse · 注意點 · 例 unpinned successful */
export function pulse(el, { duration = REDUCED ? 0 : 480 } = {}) {
  if (!el || !el.animate) return null;
  return el.animate(
    [
      { transform: "scale(1)" },
      { transform: "scale(1.15)" },
      { transform: "scale(1)" },
    ],
    { duration, easing: SPRING_EASING },
  );
}

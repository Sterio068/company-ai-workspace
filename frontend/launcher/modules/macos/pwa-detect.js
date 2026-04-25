/**
 * macOS · PWA detection
 *
 * 偵測 launcher 是否運行於 PWA 全螢幕模式(加到主畫面 / Chrome 安裝)
 * → toggle <html data-pwa="1"> · CSS var --menubar-h 自動切到 24px
 * → menubar 才會顯示(Sprint B 才 render 內容)
 *
 * Sprint A · 只佈線(detection + var)· 內容 Sprint B
 */

const STANDALONE = "(display-mode: standalone)";
const FULLSCREEN = "(display-mode: fullscreen)";

function isPWA() {
  // matchMedia · standalone 或 fullscreen 任一 = PWA
  if (window.matchMedia(STANDALONE).matches) return true;
  if (window.matchMedia(FULLSCREEN).matches) return true;
  // iOS Safari 加到主畫面後 navigator.standalone = true
  if (typeof navigator !== "undefined" && navigator.standalone) return true;
  return false;
}

function applyPWAState() {
  const pwa = isPWA();
  document.documentElement.dataset.pwa = pwa ? "1" : "0";
  return pwa;
}

export const pwaDetect = {
  /** init · 載入時偵測 + 監聽 displaymode 切換 */
  init() {
    applyPWAState();

    // 動態切換(Chrome 用戶從瀏覽器進到「安裝」app · 或反之)
    [STANDALONE, FULLSCREEN].forEach(query => {
      const mql = window.matchMedia(query);
      // addEventListener('change') 比 deprecated addListener 新
      if (typeof mql.addEventListener === "function") {
        mql.addEventListener("change", applyPWAState);
      } else {
        mql.addListener(applyPWAState);
      }
    });
  },

  /** 是否目前為 PWA(給其他 module 查) */
  is: isPWA,
};

// 自動 init · launcher 主檔不用記得 import
if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => pwaDetect.init());
  } else {
    pwaDetect.init();
  }
}

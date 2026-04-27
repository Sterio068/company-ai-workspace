/**
 * macOS Dock Icons · v1.4 · 真 macOS Sequoia 風格 SVG
 * =====================================
 * 取代 emoji · 每 icon 走 macOS native 設計語言:
 *   - True squircle 形狀(SVG path · 比 border-radius 圓潤)
 *   - 多層 gradient(top-left light · bottom-right shadow)
 *   - Inner highlight(top 1px white)+ inner shadow(bottom 1px black)
 *   - Outer drop shadow
 *   - 白色 SF Symbols 風 pictogram 在中央
 *
 * 設計參考:macOS Sequoia / iOS 18 · App icon spec
 * 1024 × 1024 base · 渲染時 56 × 56(default)or 80 × 80(hover)
 */

/** Sequoia 圓角矩形 · smoothing 0.30 = ~25% radius · 接近真實 macOS 15 dock icon
 *  之前 0.6 太圓 · USER 反饋「icon 不要圓的」
 *  改用 SVG path with rounded corners(rx=22% of size)
 */
function squirclePath(size = 100, _legacy_smoothing) {
  // 對齊 macOS Sequoia · radius = 22% of size
  const radius = size * 0.225;
  return `M ${radius} 0
          L ${size - radius} 0
          Q ${size} 0 ${size} ${radius}
          L ${size} ${size - radius}
          Q ${size} ${size} ${size - radius} ${size}
          L ${radius} ${size}
          Q 0 ${size} 0 ${size - radius}
          L 0 ${radius}
          Q 0 0 ${radius} 0 Z`;
}

/** Common defs · gradients + filters · 跨 icon 共用 */
const COMMON_DEFS = `
  <defs>
    <!-- 通用 gradient · 從 top-left 亮 → bottom-right 暗 -->
    <linearGradient id="bg-grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="white" stop-opacity="0.15"/>
      <stop offset="100%" stop-color="black" stop-opacity="0.15"/>
    </linearGradient>
    <!-- Top highlight · 1px inner white -->
    <linearGradient id="hl-grad" x1="50%" y1="0%" x2="50%" y2="100%">
      <stop offset="0%" stop-color="white" stop-opacity="0.4"/>
      <stop offset="50%" stop-color="white" stop-opacity="0"/>
    </linearGradient>
    <!-- Bottom shadow · 1px inner black -->
    <linearGradient id="sh-grad" x1="50%" y1="0%" x2="50%" y2="100%">
      <stop offset="50%" stop-color="black" stop-opacity="0"/>
      <stop offset="100%" stop-color="black" stop-opacity="0.2"/>
    </linearGradient>
    <!-- Inner shadow filter · 給 colored bg 用 -->
    <filter id="inner-shadow">
      <feGaussianBlur stdDeviation="2"/>
    </filter>
  </defs>
`;

/** 包裝 wrapper · 套 squircle + 多層 gradient · 中央放 glyph */
function iconWrapper(color, glyph, viewBox = 100) {
  const path = squirclePath(viewBox);
  return `<svg viewBox="0 0 ${viewBox} ${viewBox}" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  ${COMMON_DEFS}
  <!-- 主背景 squircle · 帶顏色 -->
  <path d="${path}" fill="${color}"/>
  <!-- Gradient overlay · 立體感 -->
  <path d="${path}" fill="url(#bg-grad)"/>
  <!-- Top highlight -->
  <path d="${path}" fill="url(#hl-grad)" opacity="0.6"/>
  <!-- Bottom shadow -->
  <path d="${path}" fill="url(#sh-grad)" opacity="0.7"/>
  <!-- Pictogram on top -->
  <g transform="translate(${viewBox * 0.225}, ${viewBox * 0.225}) scale(${viewBox * 0.0055})">
    ${glyph}
  </g>
</svg>`;
}

// ============================================================
// 7 個agent 圖示(SF Symbols 風 pictogram · 白色)
// ============================================================
// 每 glyph 用 100 × 100 設計 · 白色 fill · 透明描邊
// stroke-width 6 · 視覺重量平衡 macOS native

const GLYPHS = {
  // 主管家 #00 · 王冠(orchestrator · 統籌)
  "00": `<path fill="white" d="M50 15 L60 35 L82 32 L75 55 L88 70 L65 72 L57 90 L50 75 L43 90 L35 72 L12 70 L25 55 L18 32 L40 35 Z"/>`,

  // 投標 #01 · 同心圓靶(精準命中)
  "01": `<circle cx="50" cy="50" r="40" fill="none" stroke="white" stroke-width="6"/>
         <circle cx="50" cy="50" r="26" fill="none" stroke="white" stroke-width="6"/>
         <circle cx="50" cy="50" r="12" fill="white"/>`,

  // 活動 #02 · 日曆(規劃 + 時間)
  "02": `<rect x="15" y="22" width="70" height="63" rx="6" fill="none" stroke="white" stroke-width="6"/>
         <line x1="15" y1="38" x2="85" y2="38" stroke="white" stroke-width="6"/>
         <rect x="28" y="14" width="6" height="14" rx="2" fill="white"/>
         <rect x="66" y="14" width="6" height="14" rx="2" fill="white"/>
         <circle cx="35" cy="55" r="4" fill="white"/>
         <circle cx="50" cy="55" r="4" fill="white"/>
         <circle cx="65" cy="55" r="4" fill="white"/>
         <circle cx="35" cy="70" r="4" fill="white"/>`,

  // 設計 #03 · 顏料盤(創意)
  "03": `<path fill="white" d="M50 12 C 28 12 12 30 12 50 C 12 65 22 75 35 75 C 38 75 40 73 40 70 C 40 68 38 66 38 63 C 38 60 40 58 43 58 L 55 58 C 73 58 88 50 88 38 C 88 22 70 12 50 12 Z"/>
         <circle cx="32" cy="38" r="5" fill="${"#D14B43"}"/>
         <circle cx="48" cy="28" r="5" fill="${"#D8851E"}"/>
         <circle cx="65" cy="32" r="5" fill="${"#FFD60A"}"/>
         <circle cx="72" cy="48" r="5" fill="${"#5AB174"}"/>`,

  // 公關 #04 · 喊話喇叭(對外發聲)
  "04": `<path fill="white" d="M15 38 L15 62 L 35 62 L 65 80 L 65 20 L 35 38 Z"/>
         <path fill="none" stroke="white" stroke-width="5" stroke-linecap="round" d="M75 35 Q 88 50 75 65"/>
         <path fill="none" stroke="white" stroke-width="5" stroke-linecap="round" d="M82 25 Q 100 50 82 75"/>`,

  // 財務 #06 · 折線圖向上(成長)
  "06": `<polyline fill="none" stroke="white" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" points="15,75 35,55 50,65 70,30 85,40"/>
         <line x1="15" y1="85" x2="85" y2="85" stroke="white" stroke-width="4" stroke-linecap="round"/>
         <line x1="15" y1="85" x2="15" y2="20" stroke="white" stroke-width="4" stroke-linecap="round"/>
         <circle cx="70" cy="30" r="4" fill="white"/>`,

  // 知識 #09 · 開書 + 放大鏡(查 + 學)
  "09": `<path fill="white" d="M15 25 L 50 32 L 50 78 L 15 70 Z"/>
         <path fill="white" d="M50 32 L 85 25 L 85 70 L 50 78 Z" opacity="0.85"/>
         <line x1="50" y1="32" x2="50" y2="78" stroke="${"#5AC8FA"}" stroke-width="2"/>
         <circle cx="68" cy="55" r="11" fill="none" stroke="${"#5AC8FA"}" stroke-width="3"/>
         <line x1="76" y1="63" x2="83" y2="70" stroke="${"#5AC8FA"}" stroke-width="3" stroke-linecap="round"/>`,

  // Fallback(未知 agent)· macOS 預設 app 風格
  "default": `<rect x="20" y="20" width="60" height="60" rx="8" fill="white" opacity="0.9"/>
              <line x1="35" y1="42" x2="65" y2="42" stroke="${"#888"}" stroke-width="4"/>
              <line x1="35" y1="55" x2="65" y2="55" stroke="${"#888"}" stroke-width="4"/>
              <line x1="35" y1="68" x2="55" y2="68" stroke="${"#888"}" stroke-width="4"/>`,

  // ============================================================
  // Workspace icon(對應 sidebar 5 工作區 · ⌘1-5)· v1.4 polish
  // ============================================================
  "ws1": `<circle cx="50" cy="50" r="40" fill="none" stroke="white" stroke-width="6"/>
          <circle cx="50" cy="50" r="26" fill="none" stroke="white" stroke-width="6"/>
          <circle cx="50" cy="50" r="12" fill="white"/>`,  // 投標 · 同心圓靶

  "ws2": `<rect x="15" y="22" width="70" height="63" rx="6" fill="none" stroke="white" stroke-width="6"/>
          <line x1="15" y1="38" x2="85" y2="38" stroke="white" stroke-width="6"/>
          <rect x="28" y="14" width="6" height="14" rx="2" fill="white"/>
          <rect x="66" y="14" width="6" height="14" rx="2" fill="white"/>
          <circle cx="35" cy="55" r="4" fill="white"/>
          <circle cx="50" cy="55" r="4" fill="white"/>
          <circle cx="65" cy="55" r="4" fill="white"/>`,  // 活動 · 日曆

  "ws3": `<path fill="white" d="M50 12 C 28 12 12 30 12 50 C 12 65 22 75 35 75 C 38 75 40 73 40 70 C 40 68 38 66 38 63 C 38 60 40 58 43 58 L 55 58 C 73 58 88 50 88 38 C 88 22 70 12 50 12 Z"/>
          <circle cx="32" cy="38" r="5" fill="${"#D14B43"}"/>
          <circle cx="48" cy="28" r="5" fill="${"#D8851E"}"/>
          <circle cx="65" cy="32" r="5" fill="${"#FFD60A"}"/>`,  // 設計 · 顏料盤

  "ws4": `<path fill="white" d="M15 38 L15 62 L 35 62 L 65 80 L 65 20 L 35 38 Z"/>
          <path fill="none" stroke="white" stroke-width="5" stroke-linecap="round" d="M75 35 Q 88 50 75 65"/>`,  // 公關 · 喇叭

  "ws5": `<polyline fill="none" stroke="white" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" points="15,75 35,55 50,65 70,30 85,40"/>
          <line x1="15" y1="85" x2="85" y2="85" stroke="white" stroke-width="4" stroke-linecap="round"/>
          <line x1="15" y1="85" x2="15" y2="20" stroke="white" stroke-width="4" stroke-linecap="round"/>
          <circle cx="70" cy="30" r="4" fill="white"/>`,  // 營運 · 折線圖
};

/** 拿 workspace icon SVG · 給 sidebar 用 */
export function getWorkspaceIconSVG(wsId, color) {
  const glyph = GLYPHS[`ws${wsId}`] || GLYPHS.default;
  return iconWrapper(color, glyph);
}

/** 取得指定 agent id 的完整 SVG icon string · 套 squircle + gradient + glyph
 *  @param {string} agentId · "00" ~ "09"
 *  @param {string} color · CSS color · 例 #D14B43
 */
export function getDockIconSVG(agentId, color) {
  const glyph = GLYPHS[agentId] || GLYPHS.default;
  return iconWrapper(color, glyph);
}

/** 列出有對應 SVG 的 agent ids */
export function getSupportedIcons() {
  return Object.keys(GLYPHS).filter(k => k !== "default");
}

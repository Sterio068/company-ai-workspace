/**
 * Help Tip · view 內 inline 教學 tip
 * ==========================================================
 * 對應 vNext C
 *
 * 用法:
 *   1. 在 app.showView() 後 call helpTip.maybeShow(viewId)
 *   2. 第一次進該 view 自動 fade-in tip(右上角 toast 樣式)
 *   3. 已看過自動 skip
 *   4. 每個 view 右上角放 ❓ 按鈕(class="view-help-btn")
 *      點擊強制顯示(即使已看過)
 */
import { shouldShowTip, markTipSeen, resetTipsSeen } from "./help-state.js";
import { escapeHtml } from "./util.js";

const TIPS = {
  dashboard: {
    title: "今日工作台",
    body: "首頁是你「今天要做什麼」的入口。把任何工作丟進輸入框 · 系統會幫你拆步驟、找來源、產出草稿。下方的專案是你接續的事。",
    cta: "看 5 分鐘快速開始",
    cta_action: () => location.hash = "#help",
  },
  projects: {
    title: "專案 · 你的案子容器",
    body: "每個案子用一個專案裝。客戶、預算、期限、AI 對話、附件、下一棒、交棒卡都在裡面。不用每次跟 AI 從頭講背景。",
    cta: "了解交棒卡 4 格",
    cta_action: () => location.hash = "#help-doc-handoff-card",
  },
  workspaces: {
    title: "5 個工作區",
    body: "投標 / 活動 / 設計 / 公關 / 營運 · 每個工作區有對應助手 + 起手草稿。不知道用哪個 → 直接到首頁打字 · 主管家會分派。",
    cta: "看 10 個助手介紹",
    cta_action: () => { document.querySelector('[data-section="agents"]')?.click(); },
  },
  tenders: {
    title: "新標案通知",
    body: "每天清晨 06:00 自動從政府電子採購網挑出符合承富關鍵字的新標案。看到喜歡的按 ⭐ 興趣 · 就會自動進商機追蹤。",
    cta: "看標案 Go/No-Go 範本",
    cta_action: () => location.hash = "#help-doc-quickstart-v1.3",
  },
  workflows: {
    title: "下一步建議",
    body: "點任一模板 · AI 會先產出「步驟草稿」給你看 · 你確認後才會送出。不會一鍵全自動 · 永遠是 draft-first。",
    cta: "了解 draft-first",
    cta_action: () => location.hash = "#help",
  },
  crm: {
    title: "商機追蹤",
    body: "8 階段 kanban:新機會 → 評估 → 提案 → 已送件 → 得標 / 未得標 → 執行 → 結案。拖卡片切換階段。從標案直接匯入。",
    cta: "了解 CRM 流程",
    cta_action: () => location.hash = "#help-doc-quickstart-v1.3",
  },
  knowledge: {
    title: "公司知識庫",
    body: "承富過往標書、結案報告、品牌規則。AI 對話會自動引用。也可以直接搜「中秋節活動」找過往案例。",
    cta: "看搜尋 5 範例",
    cta_action: () => location.hash = "#help-doc-knowledge-search",
  },
  meeting: {
    title: "會議速記",
    body: "上傳音檔(m4a/mp3/wav) · 1-3 分鐘 · 系統會幫你整理逐字稿 + 決策 + 待辦。一鍵推到專案。",
    cta: "看會議速記 SOP",
    cta_action: () => location.hash = "#help-doc-quickstart-v1.3",
  },
  media: {
    title: "媒體名單",
    body: "記者 + 媒體別 + 主題 + 接受率。寫新聞稿時用「推薦記者」找最有可能寫的 5-10 位。",
    cta: "了解媒體推薦",
    cta_action: () => location.hash = "#help",
  },
  social: {
    title: "社群排程",
    body: "臉書 / Instagram / 領英排程貼文。先寫 + 排時間 · 系統自動發。失敗會 retry · 連 3 次失敗會通知。",
    cta: "看社群授權說明",
    cta_action: () => location.hash = "#help-doc-social-oauth-fallback",
  },
  site: {
    title: "場勘 · 活動現場神器",
    body: "iPhone 拍 1-5 張現場照 + GPS + 30 秒語音 · AI 自動結構化「場地 / 入口 / 風險 / 廠商需求」 · 一鍵推專案。",
    cta: "看 iPhone 設定",
    cta_action: () => location.hash = "#help-doc-mobile-ios",
  },
  accounting: {
    title: "會計",
    body: "台灣統編發票 + 報價單 + 月損益表 + 應收應付 + 預算追蹤。不取代會計軟體 · 是 PM 隨手算數的小工具。",
    cta: "了解會計助手",
    cta_action: () => location.hash = "#help",
  },
  admin: {
    title: "管理面板",
    body: "看全公司:本月成本 / 標案漏斗 / 用量 Top / 採納率 / 預算進度 / 員工活躍度。匯出 PDF 月報給老闆。",
    cta: "了解儀表板指標",
    cta_action: () => location.hash = "#help-doc-dashboard-metrics",
  },
  users: {
    title: "同仁管理",
    body: "建新同仁帳號 · 選頭銜 preset(會計 / PM / 設計師等)· 28 細部權限可勾選。系統產隨機密碼 · 一鍵複製分發。",
    cta: "看權限對照表",
    cta_action: () => location.hash = "#help-doc-admin-permissions",
  },
};

let _tipEl = null;

function _ensureTipEl() {
  if (_tipEl) return _tipEl;
  _tipEl = document.createElement("div");
  _tipEl.id = "view-help-tip";
  _tipEl.setAttribute("role", "complementary");
  _tipEl.setAttribute("aria-label", "本頁教學提示");
  document.body.appendChild(_tipEl);
  return _tipEl;
}

function _renderTip(viewId, opts = {}) {
  const tip = TIPS[viewId];
  if (!tip) return false;
  const el = _ensureTipEl();
  el.innerHTML = `
    <div class="tip-head">
      <span class="tip-icon" aria-hidden="true">💡</span>
      <h3 class="tip-title">${escapeHtml(tip.title)}</h3>
      <button class="tip-close" type="button" aria-label="關閉">×</button>
    </div>
    <p class="tip-body">${escapeHtml(tip.body)}</p>
    ${tip.cta ? `<button class="tip-cta" type="button">${escapeHtml(tip.cta)} →</button>` : ""}
    <div class="tip-foot">
      <small>之後不再顯示此頁提示 · 右上 ❓ 隨時叫回來</small>
    </div>
  `;
  el.classList.add("open");
  el.dataset.viewId = viewId;

  el.querySelector(".tip-close").onclick = () => {
    el.classList.remove("open");
    if (!opts.force) markTipSeen(viewId);
  };
  if (tip.cta_action) {
    el.querySelector(".tip-cta").onclick = () => {
      el.classList.remove("open");
      markTipSeen(viewId);
      try { tip.cta_action(); } catch (e) { console.warn("[help-tip] cta failed", e); }
    };
  }
  return true;
}

export const helpTip = {
  /** showView 後 call · 第一次進自動 show · 已看過 skip */
  maybeShow(viewId) {
    if (!shouldShowTip(viewId)) return false;
    // 給 view 一點時間 render 完
    setTimeout(() => _renderTip(viewId), 600);
    return true;
  },

  /** 強制 show(右上角 ❓ 按鈕用)*/
  showFor(viewId) {
    return _renderTip(viewId, { force: true });
  },

  /** 關掉 */
  close() {
    if (_tipEl) {
      _tipEl.classList.remove("open");
      const v = _tipEl.dataset.viewId;
      if (v) markTipSeen(v);
    }
  },

  /** 重設(讓 user 重新看)*/
  resetAll() {
    resetTipsSeen();
  },
};

/** 對外暴露給 onclick · 給 index.html 用 */
window.helpTip = helpTip;

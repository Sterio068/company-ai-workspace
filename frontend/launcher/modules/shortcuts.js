/**
 * 鍵盤快捷鍵 overlay (按 ? 打開)
 * v1.3 batch3 P1#11 · 分組顯示完整快捷鍵
 */
import { escapeHtml } from "./util.js";

const GROUPS = [
  {
    title: "🧭 導覽",
    items: [
      ["⌘K",     "全域搜尋 / 指令面板"],
      ["⌘0",     "回今日首頁"],
      ["⌘1-5",   "切 5 個工作區(投標 / 活動 / 設計 / 公關 / 營運)"],
      ["⌘6-9",   "切進階助手 06-09(會議 / 媒體 / 社群 / 場勘)"],
      ["⌘P",     "專案"],
      ["⌘L",     "技能庫"],
      ["⌘A",     "會計"],
      ["⌘T",     "標案監測"],
      ["⌘I",     "商機漏斗"],
      ["⌘W",     "自動化流程"],
      ["⌘M",     "管理面板(限管理員)"],
      ["⌘U",     "同仁管理(建同仁 / 改頭銜 + 權限 · 限管理員)"],
      ["⌘B",     "切深 / 淺色"],
    ],
  },
  {
    title: "💬 對話",
    items: [
      ["⌘Enter", "送出首頁輸入"],
      ["Enter",  "送出對話訊息"],
      ["Shift+Enter", "對話訊息換行"],
      ["⌘N",     "新對話"],
      ["⌘H",     "歷史對話"],
    ],
  },
  {
    title: "⚙️ 系統",
    items: [
      ["?",      "打開本快捷鍵清單"],
      ["Esc",    "關閉指令面板 / 視窗 / 引導"],
      ["Tab",    "在視窗內循環焦點"],
      ["⌘⇧R",   "強制重新整理(避開瀏覽器快取)"],
    ],
  },
];

export const shortcuts = {
  dialog: null,
  backdrop: null,

  toggle() {
    if (!this.dialog) this._build();
    const open = this.dialog.classList.toggle("open");
    this.backdrop.classList.toggle("open", open);
    if (open) this.dialog.focus();
  },

  _build() {
    this.backdrop = document.createElement("div");
    this.backdrop.className = "shortcuts-backdrop";
    this.backdrop.onclick = () => this.toggle();
    document.body.appendChild(this.backdrop);

    this.dialog = document.createElement("div");
    this.dialog.className = "shortcuts";
    // v1.3 batch3 · a11y · 對話框 role + tabindex 讓鍵盤可進入
    this.dialog.setAttribute("role", "dialog");
    this.dialog.setAttribute("aria-modal", "true");
    this.dialog.setAttribute("aria-label", "鍵盤快捷鍵說明");
    this.dialog.tabIndex = -1;
    this.dialog.innerHTML = `
      <h3>⌨️ 鍵盤快捷鍵</h3>
      ${GROUPS.map(g => `
        <h4 style="margin:14px 0 6px;font-size:13px;color:var(--text-secondary)">${g.title}</h4>
        <div class="shortcuts-list">
          ${g.items.map(([k, d]) => `
            <div class="shortcuts-item">
              <span>${escapeHtml(d)}</span>
              <kbd>${k}</kbd>
            </div>
          `).join("")}
        </div>
      `).join("")}
      <p style="margin-top:14px;font-size:11px;color:var(--text-tertiary);text-align:center">
        Esc 關閉 · 點空白處關閉
      </p>
    `;
    document.body.appendChild(this.dialog);
    // ESC 關
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.dialog.classList.contains("open")) {
        this.toggle();
      }
    });
  },
};

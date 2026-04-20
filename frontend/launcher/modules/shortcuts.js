/**
 * 鍵盤快捷鍵 overlay (按 ? 打開)
 */
import { escapeHtml } from "./util.js";

const LIST = [
  ["⌘K",     "全域搜尋 / palette"],
  ["⌘Enter", "送出 Hero 輸入"],
  ["⌘0",     "Dashboard 首頁"],
  ["⌘1-5",   "切 Workspace 1-5"],
  ["⌘6-9",   "切 Agent 06-09"],
  ["⌘P",     "專案"],
  ["⌘L",     "技能庫"],
  ["⌘A",     "會計"],
  ["⌘T",     "標案監測"],
  ["⌘I",     "商機 Pipeline"],
  ["⌘W",     "自動化流程"],
  ["⌘M",     "管理面板(Admin)"],
  ["?",      "打開本快捷鍵清單"],
  ["Esc",    "關閉 palette / modal / tour"],
];

export const shortcuts = {
  dialog: null,
  backdrop: null,

  toggle() {
    if (!this.dialog) this._build();
    const open = this.dialog.classList.toggle("open");
    this.backdrop.classList.toggle("open", open);
  },

  _build() {
    this.backdrop = document.createElement("div");
    this.backdrop.className = "shortcuts-backdrop";
    this.backdrop.onclick = () => this.toggle();
    document.body.appendChild(this.backdrop);

    this.dialog = document.createElement("div");
    this.dialog.className = "shortcuts";
    this.dialog.innerHTML = `
      <h3>⌨️ 鍵盤快捷鍵</h3>
      <div class="shortcuts-list">
        ${LIST.map(([k, d]) => `
          <div class="shortcuts-item">
            <span>${escapeHtml(d)}</span>
            <kbd>${k}</kbd>
          </div>
        `).join("")}
      </div>
    `;
    document.body.appendChild(this.dialog);
  },
};

/**
 * 承富 AI · Onboarding(v4.3 · 任務型 3 步)
 *
 * 對齊老闆 top 3 任務:設計 / 提案撰寫 / 廠商聯繫
 * 不嚇跑資深同仁:不講 Level 03、不露技術字
 * localStorage 記進度 · 中途離開可繼續
 */

const STEPS = [
  {
    title: "🎨 任務 1/3:設計 Brief 一鍵到位",
    body: `資深設計師 90 分鐘寫 Brief、你 3 分鐘搞定。<br><br>
      <strong>試試:</strong>按 <kbd>⌘3</kbd> 進設計協作,告訴助手:<br>
      <code>「幫我想 3 個中秋節 FB / IG / LINE 主視覺方向,
      品牌是 XX 客戶,預算 5 萬,3 天要」</code><br><br>
      它會直接產出:3 組方向 + 色調建議 + 每個尺寸的素材清單。`,
    next: "試了 · 下一步",
    action: () => {
      document.querySelector('[data-ws="3"]')?.scrollIntoView({ block: "center" });
      highlight('[data-ws="3"]');
    },
  },
  {
    title: "🎯 任務 2/3:貼一段招標看值不值得投",
    body: `60 頁招標須知,10 分鐘判斷 Go / No-Go。<br><br>
      <strong>試試:</strong>按 <kbd>⌘1</kbd> 進投標,把招標須知整段貼進對話,說:<br>
      <code>「幫我 Go/No-Go · 我們有 8 週準備」</code><br><br>
      它會回:8 維度評分 + 明確建議 + 如果 Go 要先做什麼。`,
    next: "試了 · 下一步",
    action: () => {
      document.querySelector('[data-ws="1"]')?.scrollIntoView({ block: "center" });
      highlight('[data-ws="1"]');
    },
  },
  {
    title: "🎪 任務 3/3:廠商比價信一鍵產",
    body: `發 10 家廠商問報價,不用再複製貼上 10 次。<br><br>
      <strong>試試:</strong>按 <kbd>⌘2</kbd> 進活動執行,說:<br>
      <code>「請 5 家音響廠商報『200 人記者會 · 3 小時 · 台北』,
      給我比價信範本」</code><br><br>
      送前人工看一次,再手動送(v1.1 會加自動群發)。<br><br>
      <strong>⌨️ 按 ? 看所有快捷鍵 · 按 ⌘K 全域搜尋</strong>`,
    next: "開始工作 🚀",
    action: () => {
      document.querySelector('[data-ws="2"]')?.scrollIntoView({ block: "center" });
      highlight('[data-ws="2"]');
    },
  },
];

function highlight(selector) {
  document.querySelectorAll(".onboarding-highlight").forEach(el => el.classList.remove("onboarding-highlight"));
  const el = document.querySelector(selector);
  if (el) {
    el.classList.add("onboarding-highlight");
    setTimeout(() => el.classList.remove("onboarding-highlight"), 3000);
  }
}

const tour = {
  idx: 0,

  start() {
    const savedIdx = parseInt(localStorage.getItem("chengfu-tour-idx") || "0");
    this.idx = (savedIdx > 0 && savedIdx < STEPS.length) ? savedIdx : 0;
    document.getElementById("tour-backdrop").classList.add("open");
    document.getElementById("tour-bubble").classList.add("open");
    document.getElementById("tour-step-total").textContent = STEPS.length;
    this.render();
  },

  render() {
    const step = STEPS[this.idx];
    document.getElementById("tour-step-n").textContent = this.idx + 1;
    document.getElementById("tour-title").innerHTML = step.title;
    document.getElementById("tour-body").innerHTML = step.body;
    document.getElementById("tour-next").textContent = step.next;
    if (step.action) {
      try { step.action(); } catch (e) {}
    }
    localStorage.setItem("chengfu-tour-idx", this.idx);
  },

  next() {
    this.idx++;
    if (this.idx >= STEPS.length) this.finish();
    else this.render();
  },

  skip() { this.finish(); },

  finish() {
    document.getElementById("tour-backdrop").classList.remove("open");
    document.getElementById("tour-bubble").classList.remove("open");
    localStorage.setItem("chengfu-tour-done", new Date().toISOString());
    localStorage.removeItem("chengfu-tour-idx");
    document.querySelectorAll(".onboarding-highlight").forEach(el => el.classList.remove("onboarding-highlight"));
    if (window.toast) toast.success("🎉 完成!有問題隨時按 ? 查快捷鍵,或 ⌘K 全域搜尋");
  },
};

window.tour = tour;

document.addEventListener("keydown", e => {
  if (e.key === "Escape" && document.getElementById("tour-bubble")?.classList.contains("open")) {
    tour.skip();
  }
});

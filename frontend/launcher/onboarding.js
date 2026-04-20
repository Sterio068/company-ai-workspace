/**
 * 承富 AI · 擴充版 Onboarding(互動式教學 · 10 步)
 *
 * 從單純 4 步介紹 → 10 步互動任務 · 讓使用者真的會用
 * localStorage 記進度 · 中途離開可繼續
 */

const STEPS = [
  {
    title: "👋 歡迎使用承富 AI",
    body: "我是你的 AI 小幫手。接下來 5 分鐘,我帶你做 10 個小任務,做完就會用了。<br><br><strong>承諾:</strong>所有對話都能重來 · 不會影響別人 · 錯了也沒事。",
    next: "開始 · 5 分鐘",
    action: null,
  },
  {
    title: "🎯 10 個 AI 專家各司其職",
    body: "承富 AI 不是一個聊天機器人,是 10 位專家。你不用記名字 —— 直接把事情丟給「主管家」(⌘0 或首頁),它會判斷該用誰。<br><br>右邊 Sidebar 你會看到所有專家。",
    next: "懂了",
    action: () => highlight(".sidebar-section"),
  },
  {
    title: "📝 任務 1:用人話問主管家",
    body: "不用學 prompt。直接在首頁輸入框,用你平常講話的方式問。<br><br><strong>試試:</strong>在首頁輸入<br><code>「幫我想一則中秋節給客戶的訊息」</code><br>然後按 <kbd>⌘Enter</kbd>。",
    next: "我試了",
    action: () => highlight(".hero-input-card"),
  },
  {
    title: "📁 任務 2:建立第一個專案",
    body: "每個標案 / 活動當作一個「專案」,對話跟檔案都綁專案,交接、回顧都方便。<br><br><strong>試試:</strong>按 <kbd>⌘P</kbd> 進專案頁 → 點「+ 新專案」。",
    next: "建好了",
    action: () => { app?.showView?.("projects"); highlight('[data-view="projects"]'); },
  },
  {
    title: "📚 任務 3:查承富過往知識",
    body: "10 年累積的建議書、結案、新聞稿,都可以用人話問。<br><br><strong>試試:</strong>找「📚 知識庫查詢」Agent,問<br><code>「我們做過什麼環保類的案?」</code>",
    next: "下一步",
    action: () => highlight('[data-view="skills"]'),
  },
  {
    title: "🔒 重要:資料分級",
    body: "<strong>⚠️ Level 03 機敏資料絕對不可用 AI</strong>:<br>• 選情分析 / 政治敏感<br>• 未公告的標案內情<br>• 客戶個資(身份證 / 電話 / 私密訊息)<br><br>不確定?問管理員或牆上海報。系統會自動偵測,但你的判斷是第一道關。",
    next: "記住了",
    action: null,
  },
  {
    title: "📢 任務 4:看新標案",
    body: "系統每天早上自動掃政府採購網,找到承富關鍵字的標案。<br><br><strong>試試:</strong>按 <kbd>⌘T</kbd> 進標案監測頁,看看最近有沒有感興趣的。",
    next: "看過了",
    action: () => { app?.showView?.("tenders"); highlight('[data-view="tenders"]'); },
  },
  {
    title: "💼 任務 5:商機 Pipeline",
    body: "把投標看成漏斗:<br>新機會 → 評估 → 提案 → 送件 → 得/落標 → 執行 → 結案<br><br><strong>試試:</strong>按 <kbd>⌘I</kbd> 進 Pipeline。喜歡的標案匯入後,拖拉卡片到對應階段。",
    next: "酷",
    action: () => { app?.showView?.("crm"); highlight('[data-view="crm"]'); },
  },
  {
    title: "👍 任務 6:給 AI 回饋",
    body: "每個 AI 回應下面都有 👍 / 👎。<strong>幫我們越用越準!</strong><br><br>• 👍 好用的 → 系統學起來,以後優先用類似 pattern<br>• 👎 不好的 → 月底 AI 會分析,調整 Agent<br><br><strong>試試:</strong>下次對話,記得給個 👍 或 👎。",
    next: "好",
    action: null,
  },
  {
    title: "🎤 任務 7:語音輸入",
    body: "不想打字?首頁輸入框旁邊有 🎤 按鈕,按下說話,繁中辨識。<br><br>適合:<br>• 通勤時想到 idea<br>• 開會中快速筆記<br>• 打字慢的資深同仁",
    next: "下一步",
    action: null,
  },
  {
    title: "✨ 完成!你已經會用了",
    body: "其他快捷鍵按 <kbd>?</kbd> 隨時看。<br><br>有問題找:<br>• AI Champion:__________(分機 __)<br>• Sterio:__________<br>• LINE 群組:承富 AI 互助<br><br><strong>現在去做你真正的工作,讓 AI 幫你省時間。</strong>",
    next: "開始使用 🚀",
    action: null,
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
    if (window.toast) toast.success("🎉 Onboarding 完成 · 可隨時按 ? 看快捷鍵");
  },
};

window.tour = tour;

document.addEventListener("keydown", e => {
  if (e.key === "Escape" && document.getElementById("tour-bubble")?.classList.contains("open")) {
    tour.skip();
  }
});

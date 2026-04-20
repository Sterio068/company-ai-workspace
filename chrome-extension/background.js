// ============================================================
// 承富 AI Chrome Extension · 背景服務
// ============================================================
// 功能:
//   1. 右鍵選單「送到承富 AI」
//   2. ⌘+Shift+C 快捷鍵送選取文字
//   3. 上下文偵測(標書 PDF / 新聞稿 / Email)自動建議 Agent

const CHENGFU_URL_KEY = "chengfu_base_url";
const DEFAULT_URL = "http://localhost";

// ---------- 取得承富 URL(使用者可設) ----------
async function getBaseURL() {
  const { [CHENGFU_URL_KEY]: url } = await chrome.storage.sync.get(CHENGFU_URL_KEY);
  return url || DEFAULT_URL;
}

// ---------- 送到承富(建 conversation + 填入文字)----------
async function sendToChengfu(text, sourceUrl = "") {
  const base = await getBaseURL();
  const prompt = sourceUrl
    ? `來源:${sourceUrl}\n\n${text}`
    : text;
  // 用 localStorage 把文字暫存(Launcher 讀取)
  const url = `${base}/?pending=${encodeURIComponent(prompt.substring(0, 1000))}`;
  chrome.tabs.create({ url });
}

// ---------- 建立右鍵選單 ----------
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "chengfu-send-selection",
    title: "送到承富 AI · 主管家",
    contexts: ["selection"],
  });
  chrome.contextMenus.create({
    id: "chengfu-send-tender",
    title: "當作標案 PDF 送出(投標顧問)",
    contexts: ["selection", "link"],
  });
  chrome.contextMenus.create({
    id: "chengfu-send-news",
    title: "當作事實稿送公關寫手",
    contexts: ["selection"],
  });
  chrome.contextMenus.create({
    id: "chengfu-send-page",
    title: "把整頁網址送出(讓 AI 讀取)",
    contexts: ["page"],
  });
});

// ---------- 點擊處理 ----------
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  let text = info.selectionText || "";
  const url = tab?.url || "";

  switch (info.menuItemId) {
    case "chengfu-send-selection":
      await sendToChengfu(text, url);
      break;
    case "chengfu-send-tender":
      await sendToChengfu(`[招標資料]\n${text}\n\n請用「投標顧問」分析這份內容。`, url);
      break;
    case "chengfu-send-news":
      await sendToChengfu(`[事實陳述 · 請寫新聞稿]\n${text}`, url);
      break;
    case "chengfu-send-page":
      await sendToChengfu(`請幫我分析這個網頁:${url}`, url);
      break;
  }
});

// ---------- 鍵盤快捷鍵 ----------
chrome.commands.onCommand.addListener(async (command) => {
  if (command === "send-to-chengfu") {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => window.getSelection()?.toString() || "",
    });
    if (result) await sendToChengfu(result, tab.url);
    else chrome.tabs.create({ url: await getBaseURL() });
  }
});

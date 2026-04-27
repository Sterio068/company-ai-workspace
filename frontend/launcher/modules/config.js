/**
 * Launcher · 靜態常數與設定
 * 無副作用 · 純 data module
 */

// LibreChat API endpoints
export const API = {
  refresh: "/api/auth/refresh",
  me:      "/api/user",
  agents:  "/api/agents",
  convos:  "/api/convos?pageSize=5",
  balance: "/api-accounting/usage-summary",
};

// AI 引擎切換 · 前端 preference,新對話生效
// 實際可用模型仍由 LibreChat / Keychain / create-agents.py 建立的 Agent 決定。
export const AI_PROVIDER_KEY = "chengfu-ai-provider";
export const DEFAULT_AI_PROVIDER = "openai";
export const AI_PROVIDERS = {
  openai: {
    id: "openai",
    label: "主力引擎",
    short: "主力",
    badge: "主力",
    // v1.54 · 升 GPT-5.5 · 增強推理 + 原生多模態 + 強化 function calling
    high: "gpt-5.5",
    standard: "gpt-5.5-mini",
    fast: "gpt-5.5-nano",
    desc: "GPT-5.5 主力引擎 · 推理 + 多模態 + 工具呼叫全面升級",
  },
  anthropic: {
    id: "anthropic",
    label: "備援引擎",
    short: "備援",
    badge: "備援",
    high: "claude-opus-4-7",
    standard: "claude-sonnet-4-6",
    fast: "claude-haiku-4-5",
    desc: "備援引擎 · 適合長文件與既有工作流程",
  },
};

// 10 職能 Agent · Router + 9 專家
export const CORE_AGENTS = [
  { num: "00", name: "主管家",        roleName: "主管家",   emoji: "✨", color: "#0F2340", model: "高階模型", desc: "不知道用哪個?直接丟給它,它判斷要用哪個專家 — 或自己幫你做",      workspace: "入口" },
  { num: "01", name: "投標顧問",      roleName: "投標顧問",     emoji: "🎯", color: "#D14B43", model: "標準模型", desc: "文件解析 · 承接評估 · 建議書 · 簡報架構 · 競品研究",             workspace: "投標" },
  { num: "02", name: "活動規劃師",    roleName: "活動規劃師",   emoji: "🎪", color: "#D8851E", model: "標準模型", desc: "立體場景需求單 · 舞台技術 · 動線 · 現場體驗 · 廠商比價",         workspace: "活動" },
  { num: "03", name: "設計夥伴",      roleName: "設計夥伴",     emoji: "🎨", color: "#8C5CB1", model: "標準模型", desc: "主視覺發想 · 設計需求單 · 生圖輔助 · 多渠道適配 · 視覺系統",     workspace: "設計" },
  { num: "04", name: "公關寫手",      roleName: "公關小編",     emoji: "📣", color: "#5AB174", model: "標準模型", desc: "新聞稿 · 社群貼文 · 月計劃 · 電子郵件草稿",                     workspace: "公關" },
  { num: "05", name: "會議速記",      roleName: "會議整理員",   emoji: "🎙️", color: "#D14B6F", model: "快速模型", desc: "錄音 → 逐字稿 → 摘要 → 待辦 → 寄信草稿",                        workspace: "會議" },
  { num: "06", name: "知識庫查詢",    roleName: "資料櫃管家",   emoji: "📚", color: "#3F86C9", model: "標準模型", desc: "查過往案例 + 技能庫 + 官方範本",                            workspace: "知識" },
  { num: "07", name: "財務試算",      roleName: "會計師",       emoji: "💰", color: "#30D158", model: "標準模型", desc: "毛利 · 報價 · 廠商比價 · 預算 · 連會計模組",                    workspace: "財務" },
  { num: "08", name: "合約法務",      roleName: "合約顧問",     emoji: "⚖️", color: "#5E5CE6", model: "標準模型", desc: "合約摘要 · 保密協議 / 授權書產出 · 稅務 · 法規諮詢",             workspace: "法務" },
  { num: "09", name: "結案營運",      roleName: "營運教練",     emoji: "📊", color: "#64D2FF", model: "標準模型", desc: "結案報告 · 里程碑 · 客戶紀錄 · 新人引導",                        workspace: "營運" },
];

export function agentRoleName(agent) {
  return agent?.roleName || agent?.name || "助手";
}

// 5 Workspace → 對應主 Agent
export const WORKSPACE_TO_AGENT = { 1: "01", 2: "02", 3: "03", 4: "04", 5: "09" };

export const WORKSPACES = [
  {
    id: 1,
    name: "投標",
    fullName: "投標工作區",
    icon: "🎯",
    color: "#D14B43",
    shortcut: "⌘1",
    agent: "01",
    desc: "從招標須知、承接評估到建議書與送件風險，一次收在同一個流程。",
    flow: "招標須知 → Go / No-Go → 建議書 → 報價風險",
    tools: ["標案監測", "建議書大綱", "報價風險", "簡報架構"],
  },
  {
    id: 2,
    name: "活動",
    fullName: "活動執行工作區",
    icon: "🎪",
    color: "#D8851E",
    shortcut: "⌘2",
    agent: "02",
    desc: "把活動目標、場地、動線、舞台、廠商與現場風險整理成能交辦的需求單。",
    flow: "活動目標 → 場地/動線 → 廠商需求 → 現場風險",
    tools: ["場勘", "廠商比價", "動線規劃", "舞台配置"],
  },
  {
    id: 3,
    name: "設計",
    fullName: "設計協作工作區",
    icon: "🎨",
    color: "#8C5CB1",
    shortcut: "⌘3",
    agent: "03",
    desc: "把客戶背景、風格參考、尺寸與素材限制轉成設計師看得懂的需求單。",
    flow: "需求整理 → 主視覺方向 → 生圖提示 → 多尺寸素材",
    tools: ["設計 Brief", "主視覺方向", "生圖提示", "素材清單"],
  },
  {
    id: 4,
    name: "公關",
    fullName: "公關溝通工作區",
    icon: "📣",
    color: "#5AB174",
    shortcut: "⌘4",
    agent: "04",
    desc: "新聞稿、社群貼文、媒體邀請與客戶溝通草稿都從同一個事實脈絡開始。",
    flow: "事實整理 → 新聞角度 → 社群 Hook → Email 草稿",
    tools: ["新聞稿", "社群貼文", "媒體 CRM", "Email 草稿"],
  },
  {
    id: 5,
    name: "營運",
    fullName: "營運後勤工作區",
    icon: "📊",
    color: "#3F86C9",
    shortcut: "⌘5",
    agent: "09",
    desc: "結案、客戶紀錄、報價毛利、合約待辦與新人交接，集中成內部營運脈絡。",
    flow: "專案現況 → 客戶紀錄 → 報價/合約 → 結案報告",
    tools: ["結案報告", "CRM", "會計試算", "合約待辦"],
  },
];

// vNext Phase C · 每個 Workspace 的安全起手草稿
// 注意:只放入輸入框,不自動送出;使用者檢查後才送雲端。
export const WORKSPACE_DRAFTS = {
  1: {
    name: "投標",
    next: "貼上招標須知或標案摘要",
    deliverable: "承接評估 + 建議書大綱 + 報價風險",
    prompt: [
      "【投標工作區】",
      "請先等我貼上招標須知或標案摘要。收到後請依序產出:",
      "1. 招標 9 欄摘要",
      "2. 承接 / 不承接評估與理由",
      "3. 建議書 5 章大綱",
      "4. 報價、毛利與送件風險",
      "",
      "若資訊不足,請列出待補資料,不要自行假設。",
    ].join("\n"),
  },
  2: {
    name: "活動執行",
    next: "貼上活動目標、場地、預算與日期",
    deliverable: "場景需求單 + 動線 + 預算 + 風險",
    prompt: [
      "【活動執行工作區】",
      "請先等我貼上活動目標、場地、日期、預算與限制。收到後請依序產出:",
      "1. 活動定位與現場體驗主軸",
      "2. 立體場景 / 舞台 / 動線需求單",
      "3. 廠商與設備需求清單",
      "4. 預算分配與現場風險",
      "",
      "請把需要 PM 或現場窗口確認的地方標成「待確認」。",
    ].join("\n"),
  },
  3: {
    name: "設計協作",
    next: "貼上客戶背景、風格參考與素材限制",
    deliverable: "設計需求單 + 主視覺方向 + 素材清單",
    prompt: [
      "【設計協作工作區】",
      "請先等我貼上客戶背景、活動目標、風格參考與尺寸需求。收到後請依序產出:",
      "1. 給設計師的結構化需求單",
      "2. 3 個主視覺方向",
      "3. 智慧生圖提示詞草稿",
      "4. 多渠道素材適配清單",
    ].join("\n"),
  },
  4: {
    name: "公關溝通",
    next: "貼上事實、受眾、平台與禁語",
    deliverable: "新聞稿 + 社群貼文 + 電子郵件草稿",
    prompt: [
      "【公關溝通工作區】",
      "請先等我貼上事實陳述、受眾、平台、禁語與發布時間。收到後請依序產出:",
      "1. 新聞稿角度與標題",
      "2. 新聞稿草稿",
      "3. 社群貼文 3 種 hook",
      "4. 對媒體或客戶的電子郵件草稿",
      "",
      "對外內容請標記需要人工確認的事實與引言。",
    ].join("\n"),
  },
  5: {
    name: "營運後勤",
    next: "貼上專案現況、成本、客戶或結案資料",
    deliverable: "結案報告 + 客戶紀錄 + 報價 / 合約待辦",
    prompt: [
      "【營運後勤工作區】",
      "請先等我貼上專案現況、成本、客戶紀錄或結案資料。收到後請依序產出:",
      "1. 專案狀態摘要",
      "2. 客戶紀錄",
      "3. 報價 / 毛利 / 合約待辦",
      "4. 結案報告架構與下一步",
    ].join("\n"),
  },
};

// 12 個 Skills(對應 knowledge-base/skills/)
export const SKILLS = [
  { num: "01", name: "政府標案結構分析",    ws: "投標", wscolor: "#D14B43", desc: "9 欄閱讀法,10 分鐘內消化 60 頁招標 PDF" },
  { num: "02", name: "承接評估決策樹",      ws: "投標", wscolor: "#D14B43", desc: "8 維度評分,明確建議承接 / 不承接 / 有條件" },
  { num: "03", name: "建議書 5 章模板",     ws: "投標", wscolor: "#D14B43", desc: "需求/策略/執行/團隊/預算 · 比例與寫法" },
  { num: "04", name: "新聞稿 AP Style",     ws: "公關", wscolor: "#5AB174", desc: "導言 + 本文 + 引言三段法,倒三角" },
  { num: "05", name: "社群貼文 3 種 hook",  ws: "公關", wscolor: "#5AB174", desc: "提問 / 衝突 / 數字 三種開場公式" },
  { num: "06", name: "電子郵件公文體",      ws: "公關", wscolor: "#5AB174", desc: "對政府 / 企業 / 媒體的電子郵件標準" },
  { num: "07", name: "場地踏勘 checklist",  ws: "活動", wscolor: "#D8851E", desc: "20 項必檢查,避免現場意外" },
  { num: "08", name: "舞台動線設計",        ws: "活動", wscolor: "#D8851E", desc: "4 種活動類型 + 3 禁忌 + 視覺焦點配置" },
  { num: "09", name: "活動預算分配比例",    ws: "活動", wscolor: "#D8851E", desc: "人力 35 / 場地 25 / 設備 20 / 其他 20" },
  { num: "10", name: "毛利試算框架",        ws: "營運", wscolor: "#3F86C9", desc: "公司成本結構 + 目標毛利 18-22%" },
  { num: "11", name: "客戶紀錄模板",        ws: "營運", wscolor: "#3F86C9", desc: "4 類紀錄 · 寫給 3 個月後的自己看" },
  { num: "12", name: "結案報告結構",        ws: "營運", wscolor: "#3F86C9", desc: "4 章 · 成果/數據/見解/附錄" },
];

// Anthropic 官方 17 個 Claude Skills
export const CLAUDE_SKILLS = [
  { num: "文件",                  name: "文件處理",            desc: "讀取 / 合併 / 分割 / 加浮水印 / 文字辨識 · 投標顧問必用" },
  { num: "文字",                  name: "文字文件",            desc: "產建議書、結案、合約 · 多助手可用" },
  { num: "簡報",                  name: "簡報",                desc: "產投標簡報、活動提案、成果發表" },
  { num: "試算",                  name: "試算表",              desc: "毛利、報價、比價、月報" },
  { num: "品牌",                  name: "品牌指南",            desc: "建立與維護品牌視覺系統" },
  { num: "畫布",                  name: "畫布設計",            desc: "產視覺稿" },
  { num: "前端",                  name: "前端設計",            desc: "互動草圖 / 網頁頁面" },
  { num: "網頁",                  name: "網頁互動產出",        desc: "產可執行網頁預覽" },
  { num: "共編",                  name: "文件共編",            desc: "多人協作文件管理" },
  { num: "內溝",                  name: "內部溝通",            desc: "電子郵件 / 通告 / 會議邀請" },
  { num: "介接",                  name: "工具介接開發",        desc: "建自訂外部工具接口" },
  { num: "技能",                  name: "技能建立器",          desc: "自動建立新技能" },
  { num: "演藝",                  name: "演算法藝術",          desc: "生成式視覺探索" },
  { num: "主題",                  name: "主題工廠",            desc: "一鍵產完整視覺主題" },
  { num: "模型",                  name: "模型介接最佳實踐",    desc: "介接快取 / 模型選擇 / 成本控管" },
  { num: "測試",                  name: "網頁測試",            desc: "自動化測試網頁應用" },
  { num: "動圖",                  name: "動圖建立",            desc: "產動圖(通訊 / 社群)" },
];

// v1.50 · 共享附件規格 · 從 app.js / chat.js 抽出 · 修規格一處生效
export const ATTACHMENT = Object.freeze({
  MAX_COUNT: 6,
  MAX_BYTES: 25 * 1024 * 1024, // 25 MB
  SUPPORTED_EXT: Object.freeze(new Set([
    "pdf", "txt", "md", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "csv", "json",
    "png", "jpg", "jpeg", "webp", "gif",
  ])),
});

// v1.50 · localStorage key 集中 · 防 typo · 改 key 一處生效
export const STORAGE_KEY = Object.freeze({
  CHAT_PANE_W: "chengfu-chat-pane-w",
  CHAT_FULLSCREEN: "chengfu-chat-fullscreen",
  DOCK_SHOW: "chengfu-dock-show",
  ONBOARDING_DONE: "chengfu-onboarding-done",
  TOUR_DONE: "chengfu-tour-done",
  AI_PROVIDER: "chengfu-ai-provider",
});

// CRM Kanban 階段
export const STAGES = [
  { id: "lead",       label: "有接觸",  color: "#8E8E93" },
  { id: "qualifying", label: "評估中",  color: "#D8851E" },
  { id: "proposing",  label: "寫建議書", color: "#D14B43" },
  { id: "submitted",  label: "送件",    color: "#8C5CB1" },
  { id: "won",        label: "得標",    color: "#5AB174" },
  { id: "lost",       label: "失敗",    color: "#D14B6F" },
  { id: "executing",  label: "執行中",  color: "#3F86C9" },
  { id: "closed",     label: "結案",    color: "#30D158" },
];

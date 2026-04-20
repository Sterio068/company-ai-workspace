/**
 * 承富 Launcher · 靜態常數與設定
 * 無副作用 · 純 data module
 */

// LibreChat API endpoints
export const API = {
  refresh: "/api/auth/refresh",
  me:      "/api/user",
  agents:  "/api/agents",
  convos:  "/api/convos?pageSize=5",
  balance: "/api/balance",
};

// 10 職能 Agent · Router + 9 專家
export const CORE_AGENTS = [
  { num: "00", name: "主管家",        emoji: "✨", color: "#0F2340", model: "Opus",   desc: "不知道用哪個?直接丟給它,它判斷要用哪個專家 — 或自己幫你做",  workspace: "入口" },
  { num: "01", name: "投標顧問",      emoji: "🎯", color: "#FF3B30", model: "Sonnet", desc: "PDF 解析 · Go/No-Go · 建議書 · 簡報架構 · 競品研究",           workspace: "投標" },
  { num: "02", name: "活動規劃師",    emoji: "🎪", color: "#FF9500", model: "Sonnet", desc: "3D Brief · 舞台技術 · 動線 · 現場體驗 · 廠商比價",             workspace: "活動" },
  { num: "03", name: "設計夥伴",      emoji: "🎨", color: "#AF52DE", model: "Sonnet", desc: "KV 發想 · Brief · AI 生圖 · 多渠道適配 · 視覺系統(Artifacts)", workspace: "設計" },
  { num: "04", name: "公關寫手",      emoji: "📣", color: "#34C759", model: "Sonnet", desc: "新聞稿 · 社群貼文 · 月計劃 · Email 草稿",                       workspace: "公關" },
  { num: "05", name: "會議速記",      emoji: "🎙️", color: "#FF2D55", model: "Haiku",  desc: "錄音 → 逐字稿 → 摘要 → 待辦 → 寄信草稿",                        workspace: "會議" },
  { num: "06", name: "知識庫查詢",    emoji: "📚", color: "#007AFF", model: "Sonnet", desc: "查承富過往案例 + Skills + Claude Skills",                       workspace: "知識" },
  { num: "07", name: "財務試算",      emoji: "💰", color: "#30D158", model: "Sonnet", desc: "毛利 · 報價 · 廠商比價 · 預算 · 連會計模組",                    workspace: "財務" },
  { num: "08", name: "合約法務",      emoji: "⚖️", color: "#5E5CE6", model: "Sonnet", desc: "合約摘要 · NDA/授權書產出 · 稅務 · 法規諮詢",                   workspace: "法務" },
  { num: "09", name: "結案營運",      emoji: "📊", color: "#64D2FF", model: "Sonnet", desc: "結案報告 · 里程碑 · 客戶 CRM · 新人 Onboarding",                workspace: "營運" },
];

// 5 Workspace → 對應主 Agent
export const WORKSPACE_TO_AGENT = { 1: "01", 2: "02", 3: "03", 4: "04", 5: "09" };

// 承富 12 個 Skills(對應 knowledge-base/skills/)
export const SKILLS = [
  { num: "01", name: "政府標案結構分析",    ws: "投標", wscolor: "#FF3B30", desc: "9 欄閱讀法,10 分鐘內消化 60 頁招標 PDF" },
  { num: "02", name: "Go/No-Go 決策樹",     ws: "投標", wscolor: "#FF3B30", desc: "8 維度評分,明確建議 Go / No-Go / 有條件" },
  { num: "03", name: "建議書 5 章模板",     ws: "投標", wscolor: "#FF3B30", desc: "需求/策略/執行/團隊/預算 · 比例與寫法" },
  { num: "04", name: "新聞稿 AP Style",     ws: "公關", wscolor: "#34C759", desc: "導言 + 本文 + 引言三段法,倒三角" },
  { num: "05", name: "社群貼文 3 種 hook",  ws: "公關", wscolor: "#34C759", desc: "提問 / 衝突 / 數字 三種開場公式" },
  { num: "06", name: "Email 公文體",        ws: "公關", wscolor: "#34C759", desc: "承富對政府/企業/媒體的 Email 標準" },
  { num: "07", name: "場地踏勘 checklist",  ws: "活動", wscolor: "#FF9500", desc: "20 項必檢查,避免現場意外" },
  { num: "08", name: "舞台動線設計",        ws: "活動", wscolor: "#FF9500", desc: "4 種活動類型 + 3 禁忌 + 視覺焦點配置" },
  { num: "09", name: "活動預算分配比例",    ws: "活動", wscolor: "#FF9500", desc: "人力 35 / 場地 25 / 設備 20 / 其他 20" },
  { num: "10", name: "毛利試算框架",        ws: "營運", wscolor: "#007AFF", desc: "承富成本結構 + 目標毛利 18-22%" },
  { num: "11", name: "客戶 CRM 記錄模板",   ws: "營運", wscolor: "#007AFF", desc: "4 類紀錄 · 寫給 3 個月後的自己看" },
  { num: "12", name: "結案報告結構",        ws: "營運", wscolor: "#007AFF", desc: "4 章 · 成果/數據/見解/附錄" },
];

// Anthropic 官方 17 個 Claude Skills
export const CLAUDE_SKILLS = [
  { num: "pdf",                   name: "PDF 處理",            desc: "讀 / 合併 / 分割 / 加浮水印 / OCR · 投標顧問必用" },
  { num: "docx",                  name: "Word 文件",           desc: "產建議書、結案、合約 · 多 Agent 用" },
  { num: "pptx",                  name: "簡報",                desc: "產投標簡報、活動提案、成果發表" },
  { num: "xlsx",                  name: "試算表",              desc: "毛利、報價、比價、月報" },
  { num: "brand-guidelines",      name: "品牌指南",            desc: "建立與維護品牌視覺系統" },
  { num: "canvas-design",         name: "畫布設計",            desc: "Artifacts 產視覺稿" },
  { num: "frontend-design",       name: "前端設計",            desc: "互動 mockup / landing page" },
  { num: "web-artifacts-builder", name: "Web Artifacts",       desc: "產可執行 HTML / React 預覽" },
  { num: "doc-coauthoring",       name: "文件共編",            desc: "多人協作文件管理" },
  { num: "internal-comms",        name: "內部溝通",            desc: "Email / 通告 / 會議邀請" },
  { num: "mcp-builder",           name: "MCP 開發",            desc: "建自訂外部工具接口" },
  { num: "skill-creator",         name: "Skill 建立器",        desc: "自動建新 skill" },
  { num: "algorithmic-art",       name: "演算法藝術",          desc: "生成式視覺探索" },
  { num: "theme-factory",         name: "主題工廠",            desc: "一鍵產完整視覺主題" },
  { num: "claude-api",            name: "Claude API 最佳實踐", desc: "API 快取 / 模型選擇 / cost 控管" },
  { num: "webapp-testing",        name: "Web 測試",            desc: "自動化測試網頁應用" },
  { num: "slack-gif-creator",     name: "GIF 建立",            desc: "產動圖(Slack / 社群)" },
];

// CRM Kanban 階段
export const STAGES = [
  { id: "lead",       label: "有接觸",  color: "#8E8E93" },
  { id: "qualifying", label: "評估中",  color: "#FF9500" },
  { id: "proposing",  label: "寫建議書", color: "#FF3B30" },
  { id: "submitted",  label: "送件",    color: "#AF52DE" },
  { id: "won",        label: "得標",    color: "#34C759" },
  { id: "lost",       label: "失敗",    color: "#FF2D55" },
  { id: "executing",  label: "執行中",  color: "#007AFF" },
  { id: "closed",     label: "結案",    color: "#30D158" },
];

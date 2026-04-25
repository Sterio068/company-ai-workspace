# 承富 AI

**讓 AI 成為承富的第 11 位同事 · 本地部署 · 10 人共用 · OpenAI 預設 + Claude 可切換**

---

## ⚡ 快速安裝(承富 IT)

Mac mini 接好網路 + 裝好 [Docker Desktop](https://www.docker.com/products/docker-desktop/) 後 · 開 Terminal 貼一行:

```bash
curl -fsSL https://raw.githubusercontent.com/Sterio068/chengfu-ai/main/installer/install.sh | bash
```

6 步自動跑完 · 約 5 分鐘 · 完成後自動開 http://localhost

> 不能用 curl?走 [DMG 備援路徑](https://github.com/Sterio068/chengfu-ai/releases/tag/v1.3.0)(需 `xattr -cr` 清 macOS Gatekeeper)
> 完整 SOP · [docs/SHIP-v1.3.md](docs/SHIP-v1.3.md)

---

## 🤔 這系統能幫我什麼?

你是 **PM?** → 招標 PDF 10 分鐘判標、建議書 5 章 2.5 小時寫完、結案報告框架 1 小時產
你是 **設計師?** → PM brief 太模糊,3 分鐘產 5 個反問問題、設計方向 3 組直接提案
你是 **業務?** → 每天 5 分鐘看全台新標案、LINE 客戶訊息 30 秒產回覆、廠商比價信一鍵 5 家
你是 **老闆?** → ⌘M 看今天花多少、哪個助手好用、本月對話量一眼看到

**3 分鐘快速上手:** [docs/QUICKSTART.md](docs/QUICKSTART.md)
**看完整案例:** [docs/CASES/01-海廢案端到端.md](docs/CASES/01-海廢案端到端.md)(5 天投標流程照抄就能走完)
**依角色看手冊:** [docs/HANDBOOK/](docs/HANDBOOK/)(老闆 / PM / 設計 / 業務各 1 份)

---

## 👨‍💻 給工程師看的

這份資料夾是 **Sterio 給 Claude Code 的完整工作包**。
進入 `CLAUDE.md` 看專案目標 + 決策 · 進入 `DEPLOY.md` 看部署流程 · 進入 `docs/ROADMAP-v4.2.md` 看最新路線圖。

---

## 📦 系統概覽

一套**本地部署的 AI 協作平台**,放在承富辦公室的 Mac mini 上,10 位同仁用瀏覽器就能用。

✅ **對話、檔案、知識庫全部留在公司**,不上 OpenAI/Anthropic 以外的雲端
✅ **OpenAI 作為預設主力**,前端可切換 Claude 備援
✅ **10 個承富專屬助手**,以 **5 個工作區**(投標 / 活動 / 設計 / 公關 / 營運)有邏輯地組織
✅ **macOS 設計語言**:首頁 Dashboard、⌘K 指令面板、深淺色模式、毛玻璃 UI
✅ **4 週內全員上線**,第一個月底同仁就已產出實際成果
✅ **首 3 個月免費試用期**,不滿意不續約,資料 100% 留在承富

---

## 🗓️ 四週交付時程

| 週次 | 主題 | 交付物 |
|---|---|---|
| **Week 1** | 硬體與環境 | Mac mini、UPS、Docker、Cloudflare Tunnel 架好 |
| **Week 2** | 平台部署 | LibreChat 可用、10 組帳號建立、OpenAI / Claude API 串上 |
| **Week 3** | 客製化 | **10 個職能助手**、公司知識庫灌入、資料分級 SOP |
| **Week 4** | 教育訓練與驗收 | 2 場教育訓練、指派 AI Champion、全員試用、驗收簽收 |

每週結束有進度報告,第 28 日交付驗收簽收單。

---

## 💰 給承富老闆看的數字

### 一次性投入
- 顧問服務費(首發價 30% off):**NT$ 88,000**
- 硬體採購(Mac mini + UPS):**NT$ 27,400**
- **總計:NT$ 115,400**

### 每月經常性支出
- OpenAI / Claude API(中度使用):**NT$ 8,000 / 月**
- 維運服務(可選):**NT$ 5,000 / 月**(首 3 個月免費試用)
- 其他(電費、網域):**NT$ 200 / 月**

### 預期回報
- 每月釋放 **280 小時**團隊時間
- 年度人力價值釋放 **NT$ 126 萬**
- 投資回收期 **2.5 個月**
- 首年淨效益 **NT$ 100 萬**,相當於省下 1.6 位新聘人力

---

## 📁 資料夾裡有什麼

```
claude-code-handoff/
├── CLAUDE.md                  ← Claude Code 啟動時看這個
├── README.md                  ← 你正在看的這份
├── ARCHITECTURE.md            ← 技術架構(給技術同仁看)
├── docs/                      ← 6 份技術文件(部署、客製、訓練、維運、安全、除錯)
├── tasks/                     ← 4 份週任務清單
└── config-templates/          ← LibreChat 設定範本 + 10 個 Preset JSON
```

---

## 👥 誰會看這些檔案

| 角色 | 該讀哪些 |
|---|---|
| 承富老闆 | 只讀這份 `README.md` 即可 |
| 承富 AI Champion(指派同仁) | 讀 `docs/03-TRAINING.md`、`docs/04-OPERATIONS.md` |
| 技術執行者(Claude Code 或外部工程師) | 從 `CLAUDE.md` 開始,依週順序執行 `tasks/` |
| 承富 IT 顧問(若有) | 讀 `ARCHITECTURE.md`、`docs/05-SECURITY.md` |

---

## 🎯 驗收標準(4 週末尾)

第 28 天,承富可以用這份清單逐項打勾:

- [ ] 從公司任一電腦打開 `http://承富-ai.local`,10 秒內看到 LibreChat 介面
- [ ] 用自己的帳號登入,選擇「招標須知解析器」Preset
- [ ] 上傳一份範例招標 PDF,10 分鐘內產出結構化重點表
- [ ] 從家裡用手機打開 `https://ai.<公司域名>.com`,同樣能登入與使用
- [ ] 在管理後台看到**過去 7 天各同仁的 token 用量與成本**
- [ ] 查詢「去年環保局的案子預算結構」,知識庫回傳相關過往結案報告
- [ ] 資料分級 SOP 文件**貼在辦公室牆上**,同仁能指出哪些資料屬哪級

任一條不滿足 = 未達交付。

---

## 📞 聯絡

**顧問**:Sterio
**專案代號**:承富 AI v1.1
**提案日期**:2026 年 4 月
**有效期**:30 日內
**承富方聯絡**:[待填寫]

若在執行過程中遇到 Claude Code 無法解決的問題,請聯絡 Sterio 協調。

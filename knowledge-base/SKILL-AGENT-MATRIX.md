---
doc_type: system_reference
category: routing
version: 1.0
updated: 2026-04-19
load_for_agent: all
priority: high
---

# 承富 Skill-Agent 對照矩陣

每個 Agent 在啟動對話時,**務必先用 file_search 載入自己對應的 Skills**。
主管家(Agent 00)在分派任務時,**明確告知子 Agent 要用哪個 Skill**。

---

## 🗺️ 核心對照表

| Agent | 承富 Skills(knowledge-base/skills/) | Claude Skills(knowledge-base/claude-skills/) | OpenClaw Ref |
|---|---|---|---|
| **00 主管家** | 全部可查 · 優先查「相關情境」 | `pdf` `docx` `pptx` `xlsx` `internal-comms` `skill-creator` `consolidate-memory` | 全部 |
| **01 投標顧問** | **01** 政府標案結構分析 · **02** Go/No-Go · **03** 建議書 5 章 | `pdf`(必) · `docx`(必 · 產建議書) · `pptx`(必 · 簡報) · `internal-comms`(提送 Email) | — |
| **02 活動規劃師** | **07** 場勘 checklist · **08** 舞台動線 · **09** 活動預算 | `xlsx`(廠商比價) · `canvas-design`(場景 Brief 視覺) · `pdf`(規格書) | `image-and-video-generation` |
| **03 設計夥伴** | — | `brand-guidelines`(必) · `canvas-design`(必) · `frontend-design`(必) · `web-artifacts-builder`(必) · `theme-factory` · `algorithmic-art` · `slack-gif-creator` | `image-and-video-generation` |
| **04 公關寫手** | **04** 新聞稿 AP Style · **05** 社群貼文 hook · **06** Email 公文體 | `docx`(產新聞稿檔) · `internal-comms`(必) · `doc-coauthoring` | `marketing-and-sales` |
| **05 會議速記** | — | `docx`(產紀錄) · `internal-comms`(寄信草稿) · `doc-coauthoring` | `communication` |
| **06 知識庫查詢** | 全部可查 | `skill-creator`(建新 skill) · `consolidate-memory`(整合重複) | `notes-and-pkm` |
| **07 財務試算** | **09** 活動預算 · **10** 毛利框架 | `xlsx`(必 · 產 Excel) · `claude-api`(cost 控管) | `data-and-analytics` |
| **08 合約法務** | **06** Email 公文體 | `docx`(必 · 產合約) · `pdf`(必 · 讀合約) · `internal-comms` | — |
| **09 結案營運** | **11** CRM 模板 · **12** 結案結構 | `docx`(必 · 報告) · `pptx`(成果展) · `xlsx`(進度表) · `doc-coauthoring` | `calendar-and-scheduling` |

---

## 🎯 主管家 Dispatch 速查表

主管家(00)收到請求時,**依關鍵字 → 指派 Agent + Skill**:

### 投標類
- 招標 PDF / 評審 / 配分 → **Agent 01** + Skill `pdf` + 承富 Skill 01
- Go / No-Go / 值不值得 → **Agent 01** + 承富 Skill 02
- 寫建議書 / 提案 → **Agent 01** + Skill `docx` + 承富 Skill 03
- 投標簡報 → **Agent 01** + Skill `pptx`
- 競品研究 → **Agent 01** + web_search

### 活動類
- 3D 場景 / 空間規劃 → **Agent 02** + Skill `canvas-design` + 承富 Skill 07
- 舞台 / 燈光 / 音響 → **Agent 02** + 承富 Skill 08
- 動線 / 交通 / 人流 → **Agent 02** + artifacts(SVG 動線圖)
- 廠商比價 → **Agent 02** + Skill `xlsx` + 承富 Skill 09

### 設計類
- 主視覺 / KV → **Agent 03** + Skill `brand-guidelines` + `canvas-design` + Fal.ai(Recraft v3)
- 設計 Brief → **Agent 03** + `brand-guidelines`
- 生圖 / mockup → **Agent 03** + Fal.ai Action
- 多渠道適配 → **Agent 03** + `web-artifacts-builder`(HTML 多平台 preview)
- 活動視覺系統 → **Agent 03** + `theme-factory`

### 公關類
- 新聞稿 → **Agent 04** + 承富 Skill 04 + Skill `docx`
- 社群貼文 → **Agent 04** + 承富 Skill 05
- Email 草稿 → **Agent 04** + `internal-comms` + 承富 Skill 06
- 月計劃 → **Agent 04** + Skill `xlsx`(月曆表)

### 會議
- 錄音 / 逐字稿 → **Agent 05** + Skill `docx` + `internal-comms`
- 會後 Email → **Agent 05** + `internal-comms`

### 知識
- 查承富過往 → **Agent 06**(file_search 是主要工具)
- 建新 skill → **Agent 06** + `skill-creator`

### 財務
- 毛利 / 試算 → **Agent 07** + Skill `xlsx` + 承富 Skill 10
- 報價單 → **Agent 07** + 會計 API(`/quotes`)+ `xlsx`
- 廠商比價表 → **Agent 07** + `xlsx`
- 發票 → **Agent 07** + 會計 API(`/invoices`)

### 合約 / 法務
- 合約摘要 → **Agent 08** + Skill `pdf`(讀)+ `docx`(產摘要)
- NDA / 授權書 → **Agent 08** + Skill `docx`
- 稅務問題 → **Agent 08** + web_search(最新法規)

### 營運
- 結案報告 → **Agent 09** + 承富 Skill 12 + Skill `docx` + `pptx`
- 里程碑 → **Agent 09** + artifacts(甘特圖 SVG)+ Skill `xlsx`
- CRM → **Agent 09** + 承富 Skill 11
- 新人 Onboarding → **Agent 09** + `doc-coauthoring`

---

## 🔧 Skill 自動載入機制(每次對話開始)

Agent 啟動時的「隱含動作」(透過 system prompt 觸發):

1. **對話第一則訊息到達時**
   - 掃描使用者輸入 → 辨識意圖
   - 依上表查對應 Skills
   - 用 file_search 一次載入(利用 Prompt Caching 降成本)

2. **對話過程中**
   - 使用者切換話題 → Agent 偵測並動態載入新 Skill
   - 遇到專業操作(例:產 PPT) → 觸發對應 Claude Skill(pptx)

3. **對話結束前**
   - 若使用者標 👍 → 該回應的 pattern 加入「Best Practice 待審」
   - 若標 👎 → 該回應記為「品質問題」,月維護時 Sterio 審視

---

## 📌 Router 分派語法(主管家在對話中用)

當主管家判斷需要分派時,用這個格式告訴使用者:

```\n✨ 主管家建議:\n這件事交給 [🎯 投標顧問],會用到:\n- 承富 Skill 01(政府標案結構)\n- Claude Skill pdf(讀 PDF)\n- Claude Skill docx(產建議書)\n\n想直接分派過去嗎?或我先幫你抓出重點?\n```

若主管家決定自己處理(不分派):

```\n我直接幫你處理。將引用:\n- 承富 Skill 04(新聞稿 AP Style)\n- 承富 Company Memory · 品牌口吻\n- Claude Skill docx(若你要 Word 檔)\n```

---

## 🔄 Skill 失效偵測

Agent 在使用 Skill 後,若結果品質不佳:
1. 記錄「Skill [X] 在 [情境 Y] 表現不好」
2. 月維護時 Sterio 檢視 → 更新 Skill 內容 或 Agent 路由邏輯
3. 嚴重情境 → 主動換另一個 Skill(例:pdf skill 處理中文差時改用 vision 讀截圖)

---

## 📝 維護原則

- 本檔改版時,要同步更新 10 個 Agent 的 `promptPrefix` 末尾
- 新增 Skill 時,要回來這裡登記該 Skill 歸屬 Agent
- 新增 Agent 時,要更新本矩陣

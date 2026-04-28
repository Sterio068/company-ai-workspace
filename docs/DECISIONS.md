# docs/DECISIONS.md — 承富 AI 系統決策紀錄

> 本檔是專案最高優先級的事實來源。
> 若 `AGENTS.md`、`AI-HANDOFF.md`、`SYSTEM-DESIGN.md`、`ARCHITECTURE.md` 或其他文件互相衝突,以本檔最新條目為準。
> 最後更新:2026-04-28 · v1.69+ / NotebookLM 功能最大化 / 全系統多代理深度審計 / release gate 13/13

---

## 一、目前產品基準

- **版本狀態**:v1.69+ 本機正式交付 gate 已通過；工程面可交付新版 DMG,仍需乾淨 Mac/VM 首裝、真 NotebookLM Enterprise token 與 4 人 pilot 做現場驗收。
- **部署型態**:Mac mini 本地部署 · Docker Compose · nginx 單一入口 · LibreChat v0.8.5 · FastAPI accounting backend · MongoDB 7 · Meilisearch v1.12 · Uptime Kuma。
- **AI 引擎策略**:OpenAI 為預設主力；Claude/Anthropic 保留為前端可切換備援與長文件工作流。
- **前端策略**:Launcher 使用 vanilla ES modules,不改成 React / Next.js / Tailwind；正式前端可見文字不綁定「承富」,以多公司可用白標化為方向；LibreChat 保持上游可升級。
- **Agent 策略**:現行 production surface 是 10 核心 Agent,legacy 29 Agent 保留為能力拆解與 prompt 來源。
- **工作入口**:5 Workspace 是情境封裝,不是 tag 或單純分類。
- **資料策略**:Keychain 管 secrets；Level 01/02/03 資料分級預設用於提醒與治理。NotebookLM 依 D-015 採功能最大化例外:資料等級只標記、不阻擋同步/上傳,但 UI/文件必須清楚揭露會送到 NotebookLM Enterprise。
- **後續方向**:先補可靠性、工作閉環、權限與回饋學習,再推半自動 workflow。

---

## 二、已決議事項

### D-001-v2 · Agent 交付範圍:10 核心 Agent 為 production surface

- **決策**:v1.3 之後以 10 核心 Agent 作為主要使用者入口；29 Agent 轉為 legacy/reference/prompt 能力庫。
- **取代**:D-001 初版「v1.0 29 Agent 全部做」。
- **理由**:承富同仁需要穩定、可教學、可驗收的工作入口；10 核心 Agent 已涵蓋 5 Workspace 的主要閉環,比 29 個平鋪 Agent 更適合 AI 小白。
- **後續影響**:`config-templates/presets/00-09*.json` 是 production source；`config-templates/presets/legacy/` 保留但不主動建立。

### D-002-v2 · OpenAI 預設主力 + Claude 前端可切換備援

- **決策**:承富正式部署以 OpenAI 作為預設主力 AI；Launcher 提供前端切換 OpenAI / Claude。Anthropic 不再是唯一必要條件,但可作為備援。
- **理由**:使用者期待接近「正常 AI 使用」的穩定體驗；OpenAI 作為預設可降低上手摩擦,Claude 保留長文件與既有 prompt 工作流彈性。
- **驗收**:Keychain 至少有 `chengfu-ai-openai-key`；`scripts/create-agents.py --provider both` 可建立雙引擎 Agent；前端切換後新對話優先命中對應 provider。

### D-003 · Mac mini M4 採購規格:24GB RAM

- **決策**:採購 24GB RAM 版本。
- **理由**:Docker stack、Meilisearch、MongoDB、LibreChat 與未來本地模型需要記憶體餘裕。
- **限制**:512GB storage 目前可用；若 Level 03 本地模型或大量 NAS mirror 上線,再評估 1TB/外接儲存。

### D-004 · 會計與營運後端採內建 FastAPI 模組

- **決策**:不接外部會計 SaaS；由 `backend/accounting` 提供會計、專案、CRM、回饋、安全、管理 API。
- **理由**:資料主權、台灣格式、內網部署與承富客製流程優先。
- **風險**:router 需持續拆 domain,避免大型模組再次膨脹。

### D-005 · 5 Workspace 是主要 IA

- **決策**:投標、活動、設計、公關、營運是使用者第一層入口。
- **理由**:承富同仁是用工作情境思考,不是用模型或 Agent 名稱思考。
- **UX 原則**:每個 Workspace 必須有下一步、常用輸入、標準流程與可交付成果。

### D-006 · Launcher 維持 vanilla ES modules

- **決策**:Launcher 不引入 React / Vue / Next.js / Tailwind。
- **理由**:降低未來承富 IT 維護門檻,並避免為客製首頁承擔重 build chain。
- **例外**:可使用 esbuild 做 production bundle,但 source 保持原生 ES module。

### D-007-v2 · LibreChat pin v0.8.5

- **決策**:正式部署鎖 LibreChat v0.8.5。
- **取代**:D-007 初版「正式部署鎖 LibreChat v0.8.4」。
- **理由**:v1.69 已完成 v0.8.5 容器升級與 route/smoke 驗收；Agent API 與 `/api/agents/chat` contract 維持相容。
- **驗收**:`config-templates/docker-compose.yml` image 必須為 `ghcr.io/danny-avila/librechat:v0.8.5@sha256:...`;`scripts/smoke-librechat.sh` 與 `docs/LIBRECHAT-UPGRADE-CHECKLIST.md` 必須跟 v0.8 endpoint 對齊。

### D-008 · Skills 體系是 Agent 的能力庫

- **決策**:`knowledge-base/skills/`、`knowledge-base/claude-skills/`、`knowledge-base/openclaw-reference/` 與 `SKILL-AGENT-MATRIX.md` 是能力資料層。
- **理由**:Agent 不應複製所有知識；由 Skills/Knowledge 提供可更新的工作方法。
- **後續**:Level 4 monthly report 可根據回饋提議新增或修改 skill。

### D-009 · Level 4 Learning 先做「建議」不做自動改 prompt

- **決策**:回饋、月報、skill proposal 可自動產生建議,但 prompt/skill 更新需人審。
- **理由**:避免 AI 自動改壞 production prompt。
- **驗收**:每月可輸出「高負評 Agent / 常見問題 / 建議 skill / prompt diff」。

### D-010 · Level 5 Autonomous 先採半自動 workflow

- **決策**:投標完整閉環、活動完整企劃、新聞發布閉環先做「產生步驟草稿 + 人工確認」,不直接多 Agent 自動送出。
- **理由**:承富工作涉及客戶、成本、標案與對外發聲,需保留人工關卡。
- **後續**:只有在權限、audit、quota、錯誤回復完整後才升級為全自動。

### D-011 · Chrome Extension 是正式入口之一

- **決策**:Chrome Extension 提供右鍵、快捷鍵與 `?pending=` 交接到 Launcher。
- **安全要求**:外部帶入內容只能放入草稿,不得未確認自動送出。
- **驗收**:manifest 權限完整、無缺失 icon reference、host permissions 不使用無效 pattern。

### D-012 · vNext Phase A-E 執行順序

- **Phase A**:文件與決策基準同步。
- **Phase B**:hardening 修復與 smoke/docs 對齊。
- **Phase C**:Workspace 工作閉環與 UI/UX 起手式。
- **Phase D**:管理、權限、回饋、學習閉環。
- **Phase E**:半自動 workflow 骨架。

### D-013 · 細部權限採 progressive enforcement

- **決策**:`chengfu_permissions` 不一次切成全量 RBAC,而是先從高風險入口逐步接上 `require_permission_dep()`。
- **第一批 enforcement**:accounting.view/edit、social.post_own、site.survey、knowledge.manage、media_crm.edit/export、admin dashboard/audit/PDPA。
- **全域規則**:停用帳號(`chengfu_active=false`)即使在 `ADMIN_EMAILS` 或持有 permission,也不得進一般或 admin endpoint。
- **仍待下一輪**:`social.post_all` 需設計跨作者管理語意後再 enforcement。
- **理由**:避免 UI 勾選權限與實際安全邊界脫節,同時降低一次改全量 endpoint 的回歸風險。

### D-014 · Workflow 必須維持 draft-first,可寫入 project handoff

- **決策**:Phase E workflow 不開預設全自動 execution；`prepare-preset` 產生主管家草稿與 step plan,並可保存到 `project.handoff.workflow_draft`。
- **理由**:投標、活動與新聞發布都涉及客戶與對外承諾,使用者必須先審核再送 Agent。
- **驗收**:直接 `/workflow/run*` 預設 403；`prepare-preset` 可回傳 steps / supervisor_prompt / saved_to_project 並寫 audit_log。

### D-015 · NotebookLM 採「本地資料庫為主、NotebookLM 為深讀副本」且功能最大化

- **決策**:NotebookLM 不取代本地 MongoDB / 檔案索引 / 工作包；它是可同步的深讀副本。使用者可建立資料包、同步資料包、上傳單檔、多檔或整個專案資料夾到 NotebookLM Enterprise。
- **資料等級**:Level 01/02/03 在 NotebookLM 流程中只作標記與提示,不作為建立、同步或上傳的阻擋條件。
- **透明揭露**:UI、教學與 Agent prompt 必須清楚說明「同步或上傳會送到 NotebookLM Enterprise 雲端服務；未連線時不送出,只保留本地資料包/紀錄」。
- **資料關聯**:一個工作包對應一本 NotebookLM 筆記本；同工作包後續資料包、單檔、多檔與資料夾都歸入同一本。
- **權限邊界**:專案資料包仍沿用工作包 owner / collaborators / next_owner / admin 邊界；公司知識、教學與標案摘要可由具 `knowledge.search` 權限者使用。
- **Agent 使用**:主管家與專家 Agent 可建立 NotebookLM 資料包；是否直接同步由 action wiring 與 admin/internal token 控制,並需留下 sync run 紀錄。

### D-016 · 前端可見品牌採白標化,內部專案名可暫留

- **決策**:正式使用者 UI、安裝提示與教學入口不應出現固定「承富」品牌字樣；採「智慧助理 / AI 工作台 / 本公司」等可多公司部署的泛用命名。
- **允許保留**:repo 名稱、歷史文件、舊報告、DMG 檔名與內部註解可暫留 ChengFu/承富,避免一次大規模改名造成交付風險。
- **理由**:此 app 會分別給不同公司使用,使用者第一眼不能覺得是在用別家公司系統。
- **後續**:正式白標交付文件需另開 docs cleanup sprint,清掉外部會看到的舊公司名與舊 29 Agent 語境。

---

## 三、待決議事項

| 優先級 | 決議項 | 目前建議 |
|---|---|---|
| P0 | Cloudflare Tunnel 正式 domain | 需承富提供最終 `ai.<domain>` 與 Access policy 名單 |
| P0 | 乾淨 Mac/VM 首裝錄影 | 本機 release gate 已通過,但正式對外 production-ready 前仍需乾淨環境首裝證據 |
| P0 | NotebookLM Enterprise 真憑證驗收 | 需填 `NOTEBOOKLM_*` 後驗建立 notebook / 同步資料包 / 上傳單檔或資料夾 |
| P0 | OpenAI / Claude 額度與 budget cap | 需部署前確認 OpenAI 主力額度、Claude 備援額度與 NT$ 月上限 |
| P1 | LINE workflow 是否進 vNext | 若承富主要資料入口是 LINE,建議排在 Chrome Extension 後 |
| P1 | NAS indexing path | 需確認實際 NAS 掛載路徑、檔案量與權限 |
| P1 | 權限 enforcement 覆蓋率 | 第一批已完成,下一輪處理 `social.post_all` 與 Agent 使用權限 |
| P2 | 全自動 workflow 開放條件 | 需先有 audit、rollback、quota、人工確認紀錄與採用率資料 |

---

## 四、決策修訂紀錄

| 日期 | 修訂項 | 原決策 | 新決策 | 理由 |
|---|---|---|---|---|
| 2026-04-18 | 初版 | — | 建立決策紀錄 | 專案啟動 |
| 2026-04-24 | D-001-v2 | 29 Agent 全部做 | 10 核心 Agent 為 production surface | 與 v1.3 實作與新版 AGENTS.md 對齊 |
| 2026-04-24 | D-012 | 無 | vNext Phase A-E | 接續優化線需要明確執行順序 |
| 2026-04-24 | D-013 | 細部權限僅 UI 儲存 | progressive enforcement | 高風險 endpoint 需真實權限邊界 |
| 2026-04-24 | D-014 | workflow placeholder | draft-first + project handoff | 可接續工作,但不繞過人審 |
| 2026-04-28 | D-015 | NotebookLM 安全限制優先 | 本地資料庫為主 + NotebookLM 深讀副本 + 功能最大化 | 使用者要求不要因資料安全縮減 NotebookLM 功能 |
| 2026-04-28 | D-016 | 前端仍有承富品牌 | 使用者可見 UI 改白標泛用 | app 會給不同公司使用 |

---

## 五、維護原則

- 所有跨功能、交付範圍、架構、安全與 UX 決策先寫入本檔。
- 改變既有決策時新增 `D-XXX-vN`,不要刪掉歷史脈絡。
- 若文件衝突,先更新本檔,再同步 `AI-HANDOFF.md`、`AGENTS.md` 與使用者手冊。

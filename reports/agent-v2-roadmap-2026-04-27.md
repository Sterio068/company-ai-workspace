# Agent 系統 v2.0 規劃 · 4 維度路線圖

**日期**:2026-04-27
**基準**:v1.58(已 commit)· 10 agent + 18 actions + 3 workflow + GPT-5.5 + Vision OCR
**目標**:從「能用」(v1.x)推進到「同仁第一個想到的同事」(v2.0)

---

## 📊 當前狀況快照(v1.58)

| 維度 | 已達 | 落差 |
|---|---|---|
| **Agent 數** | 10(Router + 9 專家)| 部分專家職能重疊(財務 vs 合約稅務) |
| **prompt 長度** | 1.7-3.8 KB · temperature 0.2-0.7 | 缺 few-shot · 缺 chain-of-thought 模板 · 全用「公司」品牌(已 v1.56 strip 前端但 prompt 還在) |
| **Capabilities** | file_search + actions + web_search + artifacts + vision 全開 | 部分 agent 沒掛 vision 但其實該有(05/06/07) |
| **Actions wired** | 18 個(PCC × 4 / accounting × 8 / 生圖 × 2 / vision OCR × 4)| 還沒接:Sora 影片 / Gmail draft / Calendar / Notion |
| **Skills 引用** | 12 個 markdown skill 在 knowledge-base · 透過 file_search 查 | prompt 沒明示「優先用哪個 skill」· AI 不知道 |
| **Workflow** | 3 閉環(投標 / 活動 / 新聞)· 已可自動執行 | 缺:結案閉環 / 客戶提案閉環 / 月底報表閉環 |
| **多 agent 協作** | orchestrator sequential 串接 | 缺:agent 之間 context handoff · 缺 parallel DAG · 缺真實 tool delegation |

---

## 🎯 4 維度優化規劃

## A · Agent Prompt 優化(內容質量)

### A1 · 統一 prompt 結構模板(P0 · 1 週)

**現況問題**:10 個 prompt 各自結構,部分有「核心能力 A/B/C」分節,部分沒有。AI 行為不一致。

**新模板**(每個 agent 統一 5 段):
```markdown
# 角色定位
你是 [name] · [一句話定位]

# 你的核心能力(2-5 個)
## 能力 A · [名稱]
**觸發**:當使用者[條件]
**步驟**:1. ... 2. ... 3. ...
**輸出格式**:[結構化模板]
**Skill 引用**:優先參考 knowledge-base/skills/XX
**範例**:
  輸入:[一句話]
  輸出:[3-5 行示範]

# 主動追問規則
若缺[A/B/C]關鍵資訊,先問,不要編

# 安全與合規紅線
- 涉及對外承諾 → 標「需人工確認」
- 涉及 Level 03 機敏 → 拒絕並提醒
- 涉及金額 / 法律 → 加免責聲明

# 與其他 Agent 的協作
- 遇到 [類型] 問題 → 建議切到 [其他 agent]
- 從 [其他 agent] handoff 來 → 預期接到 [格式] context
```

**影響**:每個 agent 行為更穩定 · 新進員工 onboarding 不用學 10 種風格

### A2 · 加 few-shot 範例(P0 · 1 週)

每個 agent 在 prompt 內嵌 3-5 個真實業務範例(從公司過往案例剪裁脫敏):
```
範例 1:
  輸入:「這個案子毛利怎麼樣?」
  ⛔ 錯誤輸出:「需要更多資訊」(太懶)
  ✅ 正確輸出:[完整毛利試算 + 標待補欄位]
```

**影響**:模型對「正確完成」的定義更明確 · 廢話減少

### A3 · 移除 prompt 內所有「公司」字樣(P1 · 2h)

v1.56 已掃前端 · presets/*.json prompt 內仍有大量「公司」(60+ 處)。
方案:`scripts/sanitize-presets.py` 批次替換 · 重跑 `create-agents.py`

### A4 · 加入 chain-of-thought 觸發詞(P1 · 1d)

對複雜任務(投標 Go/No-Go / 毛利試算 / 合約風險)在 prompt 加:
> 在做最終結論前,先用 `<thinking>` 標籤梳理:1. 列出所有相關事實 2. 比對風險矩陣 3. 算 confidence 4. 結論

GPT-5.5 原生支援 reasoning · 配合 prompt 強化效果顯著

### A5 · 拆財務 vs 合約稅務職能(P2 · 1d)

現況:#07 財務試算 + #08 合約法務 各包稅務 · 重疊。
建議:#07 收純算術(毛利/報價/比價/預算)· #08 收法律 + 稅務諮詢 · 明確化分工

---

## B · Agent 能力擴充(可用工具)

### B1 · 補齊 vision capability(P0 · 30min)

| Agent | 現況 capability | 該加 | 場景 |
|---|---|---|---|
| 06 知識庫查詢 | 無 vision | + vision | 同事貼舊案截圖找參考 |
| 05 會議速記 | 無 vision | + vision | 拍白板照即抽決議 |

修法:`config-templates/presets/0[5,6].json` 加 `"vision"` to capabilities · 重 wire

### B2 · 新 Action 接口(P1 · 各 30min)

| Action | 接哪 agent | 業主場景 | 成本 |
|---|---|---|---|
| **Gmail draft** API | 公關寫手 + 主管家 | 「幫我把這封寫好的郵件存草稿」自動送進 Gmail | 0(用 OAuth) |
| **Google Calendar** | 主管家 + 活動規劃師 | 「3/15 下午 2 點開會」自動加事件 | 0 |
| **Notion DB** | 結案營運 + 主管家 | 結案報告自動推 Notion 客戶資料庫 | 0 |
| **Sora 影片** | 設計 + 公關 + 活動 | 8 秒社群短片 · 詳見前次討論 | $0.5-2/影片 |
| **Sheets 寫表** | 財務試算 + 結案 | 月損益表自動產 google sheet | 0 |
| **內部知識庫 vector search** | 知識庫查詢 | 取代純 file_search · 語意搜尋更準 | 同 OpenAI embedding 成本 |

### B3 · Skills 主動引用機制(P1 · 1d)

**現況**:12 個 skill 在 knowledge-base · file_search 偶爾用到。
**問題**:AI 不知道「哪個 skill 對應哪個情境」· 引用率低。
**解法**:在每個 agent prompt 明示 skill 對應表:
```
你常用的 skill:
- skill 01-政府標案結構 → 看到招標 PDF 必先查
- skill 02-Go/No-Go 決策樹 → 評估承接時必查
- skill 03-建議書 5 章模板 → 寫提案必查
```

### B4 · 新增 3 個 skill(P2 · 各 2h)

公司業務缺的:
- `13-客戶提案破冰 SOP.md`(公關 + 主管家用)
- `14-現場危機處理 checklist.md`(活動規劃師用)
- `15-結案 KPI 報表標準.md`(結案營運用)

---

## C · 互動體驗優化(同仁感受)

### C1 · 對話 UI 體感升級(P0 · 1 週)

| 問題 | 現況 | 修法 |
|---|---|---|
| 串流時無進度感 | 字一個一個出 · 不知道還要多久 | 加「思考中... 正在查 PCC...」階段提示 |
| Tool call 不可見 | AI 呼叫 `searchByTitle` 同事不知道 | UI 顯示「⚙ 主管家正在呼叫 PCC 查標案...」 |
| Vision 上傳沒回饋 | 拖檔到 chat 不知道有沒有讀進去 | 上傳完成 toast 「已交給 AI 看」 |
| 結果無法 follow-up | AI 回完就結束 · 同事要再寫一次 prompt | 結尾自動建議 3 個 follow-up 問題 |

### C2 · Suggested prompts 動態化(P1 · 2d)

**現況**:chat-suggestion 4 個固定。
**改**:依當下 view / 時段 / 最近專案 動態產生:
- 進「投標」view → 「貼上這個案的須知」
- 進「公關」view → 「寫這月新案的新聞稿」
- 進「會議」view → 「上傳早上的會議錄音」

### C3 · Handoff 卡視覺化(P1 · 2d)

**現況**:「下一步草稿」靠主管家對話框拿 prompt · 同事看不到流程圖。
**改**:workflow 卡片 → 點開有 step DAG 視覺(流程圖)· 每 step 完成打勾

### C4 · Voice-first 入口(P2 · 3d)

**現況**:Whisper 已開但要點麥克風 icon。
**改**:首頁右下加常駐「按住說話」浮鈕 · 鬆開即送主管家

### C5 · Agent 切換感受優化(P2 · 1d)

**現況**:對話到一半換 agent 要新對話 · context 丟失。
**改**:加「轉交給 [agent]」按鈕 · 把當前對話摘要傳過去開新

---

## D · 多 Agent 協作架構(orchestrator v2)

### D1 · Workflow step 並行 DAG(P0 · 1 天 · 已規劃 v1.59)

**現況**:`run_workflow` sequential await · 沒依賴的 step 也排隊。
**改**:看 `depends_on` 分批 `asyncio.gather`。

詳見 v1.57 報告 P0-5。

### D2 · Agent-to-Agent context handoff(P0 · 1 週)

**現況**:invoke_agent 每次新 conversation · agent 沒繼承前個 agent 的 context。
**問題**:投標 workflow step_3 建議書整合 · 卻不知道 step_1 招標解析的結果(只拿 prompt 字串)。
**解法**:
- 加 `WorkflowContext` Pydantic model 跨 step 共用
- 每 step 結果結構化(不是 raw text)寫 context
- 下個 step 的 prompt template 從 context 拉結構化資料

### D3 · 真實 tool delegation(主管家 → 專家)(P1 · 2 週)

**現況**:主管家「描述」要做什麼,但實際呼叫專家是 orchestrator 程式碼預定的。
**問題**:遇到沒預定義 workflow 的需求,主管家無法動態派工。
**解法**:把每個專家 agent 包成 `delegate_to_agent` action(主管家可呼叫)。
- 主管家用 OpenAI function calling 真的呼叫專家
- 專家結果自動回流主管家 context
- 主管家整合 + 回應同事

這才是真正的「主管家 orchestrator」· 而不只是 workflow runner。

### D4 · 新 workflow 閉環(P1 · 各 2d)

| 名稱 | step | 目前狀態 |
|---|---|---|
| **結案完整閉環** | 結案報告 → 客戶 NPS → 內部復盤 → 入 CRM | 未做 |
| **客戶提案閉環** | 客戶 brief → 創意方向 → 報價 → 提案 PPT | 未做 |
| **月底營運閉環** | 月損益 → 標案漏斗 → 員工活躍 → 寄老闆月報 | 未做(月報已有 cron · 但未串完) |
| **媒體公關閉環** | 事實 → 新聞稿 → 媒體推薦 → Email 草稿 → Google Calendar 跟進 | 部分(新聞稿單步) |

### D5 · 失敗回復與 retry(P2 · 1 週)

**現況**:workflow 中間 step fail 整個放棄。
**改**:每 step 結果存 mongo · 失敗只重跑該 step · 用戶可手動 modify input 重試

### D6 · A2A telemetry(P2 · 1 週)

**現況**:看不到主管家為什麼選 agent X 而不是 Y。
**改**:每 invoke 記 routing reason → admin dashboard 看「主管家為什麼 90% 走投標 agent」

---

## 🗺️ 實作優先順序(v1.59 → v2.0)

```
v1.59 (本週可做)· 體感最強 + 風險最低
  · D1 workflow 並行 DAG (1d) · 投標 workflow 省 10s
  · B1 補齊 vision capability 給 #05 #06 (30min)
  · A3 prompt 移除「公司」60+ 處 (2h)
  · C1 部分 · 加 tool call 可見性「⚙ 正在呼叫 PCC...」(2d)

v1.6.0 (2-4 週)· 結構性升級
  · A1 統一 prompt 模板 (1w)
  · A2 few-shot 範例 (1w)
  · A4 chain-of-thought 觸發 (1d)
  · D2 WorkflowContext 結構化 handoff (1w)
  · B3 skills 主動引用 (1d)
  · C2 動態 suggested prompts (2d)
  · D4 結案閉環 + 月底營運閉環 (各 2d)

v1.7.0 (1-2 月)· 真實多 agent 協作
  · D3 主管家 → 專家 真實 tool delegation (2w)
  · B2 Gmail / Calendar / Notion / Sheets actions (各 30min · 共 2d)
  · C3 handoff DAG 視覺化 (2d)
  · A5 財務 / 合約職能拆分 (1d)
  · D5 workflow retry & resume (1w)

v2.0 (季度規劃 · 真實智慧助理)
  · 主管家 = 真正動態 router · 不依賴預定義 workflow
  · 全公司 RAG 提升至 vector search + reranker
  · D6 A2A telemetry + admin dashboard 看 agent 路由模式
  · 學習 loop:同仁 👍/👎 → 自動調整 router 偏好
  · Voice-first 場景(C4)
  · Sub-agent 拆細(投標顧問內含「招標解析」「報價」「風險評估」3 個 sub)
```

---

## 📈 預期效果(v2.0 完成時)

| 指標 | v1.58 現況 | v2.0 目標 |
|---|---|---|
| 同仁日均對話次數 | (待量化)| 5-8 次/人/日(常用) |
| 主管家正確路由率 | (待量化)| ≥ 85% |
| Workflow 直接執行採用率 | 預期低(剛上)| ≥ 60% 同事用過 |
| Agent 響應「需人工確認」標記準確率 | (待量化)| ≥ 95% |
| Skill 引用率 | (file_search 偶爾)| ≥ 80% 任務有引用對應 skill |
| Token 成本 / 人 / 月 | 估 NT$ 1,200 | NT$ 1,800(增加但採用率翻 3 倍) |

---

## 🚧 風險與取捨

1. **D3 真實 tool delegation 風險最高**:主管家自由派工 · 可能無限遞迴 / token 燒爆 / 跑題。需要嚴格 guard:max_depth / max_tokens / 強制 12s timeout per delegation
2. **A1 統一 prompt 模板會改變 AI 風格**:同事可能感受到「跟昨天不一樣」· 需要標 v1.6.0 release note + 1 週並行 A/B
3. **B2 OAuth actions(Gmail/Calendar/Notion)**:每個都要 OAuth scope 設定 + token refresh · 不能一次全做 · 排隊一個一個來
4. **C5 Agent 切換 context 傳遞**:摘要太長浪費 token · 太短失 context · 需要 prompt 評估「該帶哪幾段」

---

## 📌 下次對齊問業主的 5 個問題

1. 同仁實際用 agent 的痛點 top 3?(現在我們是猜的)
2. Workflow 直接執行 vs 草稿模式 · 業主希望 default 哪個?
3. Sora 影片業務需求多大?(影響 B2 排序)
4. Gmail draft 整合是否需要?(同仁用 Gmail 多嗎)
5. v2.0 季度推進預算 / 時間 / 人力?

---

**結論**:v1.x 已把「個別 agent 能用工具」做完(v1.51-1.55)+ 「workflow 自動執行 + safety」做完(v1.54)+ 「整體性 P0 修補」做完(v1.57)。v2.0 主軸是 **「個別 agent 變強(A) + 真正多 agent 協作(D)」** · 中間靠 B/C 體感與能力擴充支撐。

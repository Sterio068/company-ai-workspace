# 承富 AI 系統 · 外部審查請求 (v7.0)

> **第 10 輪審查 · 2026-04-21 晚間**
> **本輪跨過的里程碑:** Round 9 reviewer 的 Q1-Q4 + 7 個暗示風險 + 3 份教材 + 沙盒升版環境 + 老闆 1 頁紙 · **全部已實作 push**
> **本輪重點:審整套『交付閉環』是否真的能跑完**(不是再找工程紅線)

---

## ⚠️ **在你下筆之前 · 強制讀這段**

前 9 輪 reviewer 平均重複指出 70% **我們已修過的項目**。
**若你的報告出現下列「已修 27 項」任一條 · 該項直接視為 0 分。**

### 🚫 已修 27 項 · 嚴禁再指為紅線

#### Round 1-7 修的(14 項)

| # | reviewer 常指的 | 修在哪 | commit |
|---|---|---|---|
| 1 | CRM 整區重繪掉幀 | `frontend/launcher/modules/crm.js:86-108` 分批 + idleCallback | `9903d55` |
| 2 | tenders 整區重繪 | `modules/tenders.js:47-85` event delegation | `9903d55` |
| 3 | chat renderMarkdown regex | `modules/chat.js:252-284` vendor-marked.js | `9903d55` |
| 4 | auth 401 沒 retry | `modules/auth.js:20-44` SessionExpiredError + Web Locks | `bedf413` |
| 5 | Day 0 登入卡關 | `PRE-DELIVERY-CHECKLIST.md:112-125` | `9903d55` |
| 6 | Baseline 老闆答不出 | `BASELINE.md:9-20` + `192-236` Champion 1 週日誌 | `9903d55` |
| 7 | per-user hard stop 只儀表 | `main.py /quota/check` + `chat.js:160-175` 送前擋 | `9903d55` |
| 8 | transactions schema 默默回 0 | fingerprint + `/admin/budget-status` 黃牌降級 | `9903d55` |
| 9 | Route A hash router 未防 | `librechat-relabel.js:14-70` listener + `_matchChatPath` | `9903d55` |
| 10 | on_event / .dict() deprecation | `main.py:54-77` lifespan + 全檔 model_dump() | `08cf827` |
| 11 | overpromise 文案 | index.html / QUICKSTART / BOSS 手冊三處 | `5b5859c` |
| 12 | split-brain(routers/ + auth.py) | `_unused_scaffold/` 歸檔 | `5b5859c` |
| 13 | 密碼紙條沒銷毀 SOP | `PRE-DELIVERY-CHECKLIST.md:100-107` | `08cf827` |
| 14 | 備份沒異機 / restore | `scripts/backup.sh` rclone + 月度 drill | `bedf413` |

#### Round 8 真未解 4 項 + E-1/2/3(6 項)

| # | 項目 | commit | 新測試 |
|---|---|---|---|
| 15 | D · main.py 拆 admin_metrics | `65de9bf` | +15 unit |
| 16 | C · Projects drawer + Handoff | `051dbed` | +3 integration |
| 17 | A · Fal.ai Recraft(num_images=3) | `9dc7302` | +6 integration |
| 18 | E-1 · 多來源知識庫 CRUD | `fb84566` | +9 integration |
| 19 | E-2 · 多格式抽字 + Meili 索引 | `115f049` | +14 unit |
| 20 | E-3 · 前端 Admin UI + 知識庫 view | `8f91f76` | node check |

#### Round 9 · 4 大 Q + 暗示 7 項(本輪完成)

| # | 項目 | commit | 驗證 |
|---|---|---|---|
| 21 | **Q1** · quota_check fail-safe(資料異常擋一般同仁 · 放 admin) | `916d142` | +5 pytest |
| 22 | **Q3** · `/knowledge/list`+`/search` 依 X-Agent-Num 過濾 | `916d142` | +2 pytest |
| 23 | **Q4** · 拆 last_scanned_at / last_search_indexed_at(Meili 掛恢復後自動補) | `916d142` | +3 pytest |
| 24 | **Q2** · Handoff sessionStorage 自動帶入 + drawer 狀態還原 + authFetch | `2305dd0` | node check |
| 25 | **A polling** · 前端 design.js `pending → poll → done` 閉環 + `/design` palette | `2305dd0` | node check |
| 26 | **palette stale guard** · `_queryVersion` 防 async callback race | `2305dd0` | node check |
| 27 | **7 暗示風險** · Meili backup / TTL 90d+180d / NAS health × 2 endpoint / regenerate_of 真實作 / tesseract-chi-tra / reindex 警告 | `ee5712a` | +6 pytest |

**所以本輪 reviewer 不要再說** 「該改 authFetch / polling 沒接 / drawer handoff 消失 / OCR 沒裝 / Meili 沒備份 / log 會爆 / NAS 斷線沒偵測 / regenerate_of 是 dead code」—— **全部已 push**。

---

### ✅ 第 10 輪 reviewer 該做的事 · 審「交付閉環」不是審「工程紅線」

**工程部分已夠 · 剩下真的只是細節 UX 打磨。**
**本輪重點變成:**

1. **Day 0 演練腳本能真跑嗎?** (`docs/DAY0-DRY-RUN.md` · Sterio + Champion 照腳本 9:00-17:00)
2. **7/10 first-win 硬條件真的會達嗎?** 若有 3/10 卡住 · SOP 走得通嗎?
3. **Champion 機制寫了 · 但人選怎麼找?** 若老闆挑不出人 · 這套會死嗎?
4. **4 週驗收 ROI 公式合理嗎?** (`BOSS-VIEW.md` · 月省 57 小時 / 花 NT$ 12,000 = 2.9 倍)
5. **Sterio 休假 2 週 · 系統出大事誰修?** — 最真的技術債

**絕不做的事:**
- 不要再指「🚫 已修 27 項」
- 不要建議換框架 / 換 LibreChat / 加 k8s / 加 Redis
- 不要再說「initial 實作建議」— 工程已 30+ pytest × 3 層驗

---

## 🔗 0. 直接去讀

| 來源 | 位置 |
|---|---|
| **GitHub(public)** | <https://github.com/Sterio068/chengfu-ai> |
| **Clone** | `git clone https://github.com/Sterio068/chengfu-ai.git && cd chengfu-ai` |
| **作者本機** | `/Users/sterio/Workspace/ChengFu` |
| **本機跑** | <http://localhost/> · <http://localhost/api-accounting/docs> |
| **commit 歷史** | `git log --oneline -30`(22+ commit · 9 輪審查 · 50+ 紅線修正) |
| **Round 9 新提交** | `git log --oneline 592b078..HEAD` 看 6 個 commit 全貌 |

### 必讀 10 份(20 分鐘消化)

```
[工程層](審過 5 輪 · 已無大紅線)
1. CLAUDE.md                                   · 專案目標 + 12 項決議
2. backend/accounting/main.py                  · FastAPI · 60+ endpoint · 2200 行
3. backend/accounting/services/                · 拆出的 pure function
4. frontend/launcher/modules/                   · 25 個 ES modules

[交付層](本輪重點 · 前所未審)
5. docs/DAY0-DRY-RUN.md                        · 9:00-17:00 現場腳本(287 行)
6. docs/TRAINING-SLIDES.md                     · Marp 可轉 PPT(328 行)
7. docs/CHAMPION-WEEK1-LOG.md                  · Champion 日誌 + 5 案樣本表(274 行)
8. docs/BOSS-VIEW.md                           · 老闆 1 頁紙 + ROI 公式(287 行)
9. docs/PRE-DELIVERY-CHECKLIST.md              · Sterio Day -7 ~ Day +30 清單
10. docs/LIBRECHAT-UPGRADE-CHECKLIST.md        · 含 sandbox 隔離升版 SOP(新 §🧪)

[運維層](若有餘力)
11. scripts/backup.sh                           · Mongo + Meili + off-site
12. config-templates/docker-compose.sandbox.yml · LibreChat 升版專用沙盒
13. docs/ROADMAP-v4.2.md §9                    · v1.2 待議 7 個設計題
```

---

## 1. 客戶與專案(維持)

### 客戶
- **承富創意整合行銷有限公司**(台灣 · 10 人)
- 政府標案 / 公關活動 / 設計案
- 2-3 位資深者對 AI 抗拒

### 老闆親答 10 題(優先級依據)

**原 5 題(Round 4 前定方向):**
1. 每週 Top 3:設計 / 提案撰寫 / 廠商聯繫
2. 80% 原始檔:LINE 群組 + NAS(不是 Google Drive)
3. L3 機敏:先不考慮
4. 最在意:省時 + 接案量
5. 維運:外包 20h/週 + Champion 自主

**v1.1 新 5 題(Round 8 後):**
| # | Q | A | 實作 |
|---|---|---|---|
| 6 | PDF 掃描比例 | 高 | pymupdf OCR + Dockerfile 裝 tesseract-chi-tra |
| 7 | 設計圖量 | 一次 3 張挑方向 | `num_images=3` 寫死 |
| 8 | NAS scope | 整個 NAS · 所有類型 · 分專案 | 多來源動態管理 |
| 9 | 容器加抽字 | 可接受 | +6 lib 進 requirements · tesseract 進 Dockerfile |
| 10 | 專案詳情 UI | Drawer | 滑出 42%(手機 90%) |

**Round 9 作者問老闆的 4 題(已答)**
| # | Q | A |
|---|---|---|
| Q1 | 預算 DB 異常時怎麼處理 | C · 只放 admin+Champion · 擋一般 |
| Q2 | 交棒卡插入對話 | A · sessionStorage 自動帶入 |
| Q3 | 無權限助手能看到 source 名嗎 | A · 完全藏起 |
| Q4 | Meili 掛時索引策略 | 修正 B · 兩階段時間戳 |

→ **偏離這 14 題的建議會被否決**

---

## 2. 技術棧(不可替換)

| 層 | 選擇 |
|---|---|
| 硬體 | Mac mini M4 24GB |
| AI Platform | LibreChat **v0.8.4 pinned** |
| AI Model | Claude Opus 4.7 / Sonnet 4.6 / Haiku 4.5 |
| 後端 | FastAPI(`main.py` 2200 行 + `services/` 3 純 function 模組) |
| 前端 | 原生 ES Modules · **無 build step** |
| 容器 | Docker Compose × 6(production)+ 6(sandbox) |
| 對外 | Cloudflare Tunnel + Access(未架) |
| 機密 | macOS Keychain |
| 全文搜尋 | Meilisearch v1.12 |
| 抽字 | PyMuPDF + tesseract-chi-tra + python-docx/pptx/openpyxl/Pillow |

**不接受:** k8s / Redis / Kafka / GraphQL / 換框架 / SaaS / 改 10 助手 / 改 5 工作區

---

## 3. 當前狀態

### ✅ 程式碼:**99.5%**(本輪 +0.5%)

- 6 容器 healthy · sandbox 6 容器完整 compose
- **81 pytest pass + 2 skip · 11 smoke pass · 0 deprecation**
  - tests/test_admin_metrics.py · 20 unit(Q1 fail-safe 新增 5)
  - tests/test_knowledge_indexer.py · 17 unit + 2 skip(Q4 新增 3)
  - test_main.py · 44 integration(Q3 + health + design history 新增 7)
- **後端 endpoint:**
  - 原 40+ endpoint
  - 本輪新:`PUT/GET /projects/{id}/handoff` · `POST /design/recraft` + `/status/{id}` + `/history` · `GET /admin/sources + /{id} + /{id}/health + /health` · `POST /{id}/reindex` · `GET /knowledge/{list,read,search}`
  - 合計 ~55 endpoint
- **前端:** 25 個 ES modules(本輪 +design.js + 改 palette 5 處)· CSS +400 行
- **services/:** `admin_metrics.py` / `knowledge_extract.py` / `knowledge_indexer.py` pure function

### 🟡 部署落地:**45%**(本輪 +10%)

- Mac mini **仍未上架**
- Cloudflare Tunnel 仍未接
- `knowledge-base/samples/` 仍空(等 Day -5 真實案例灌)
- 10 帳號仍未建
- 2 場教育訓練仍未辦(投影片準備好了)
- T0 baseline B 路仍未跑(模板備好了)
- NAS 掛載 SMB Keychain 仍未配
- knowledge-cron.sh 仍未排 launchd plist
- FAL_API_KEY 仍未設
- **Champion 人選仍未指定** ← 本輪最大未決事項

### 📚 教材:**96%**(本輪 +8%)

- 3 完整案例 + 4+1 角色手冊 + QUICKSTART + Pre-Delivery + Baseline + Upgrade
- **本輪新:** DAY0-DRY-RUN + TRAINING-SLIDES + CHAMPION-WEEK1-LOG + BOSS-VIEW

---

## 4. 我要你審什麼(本輪主軸:交付閉環)

### 4.1 Day 0 演練腳本壓力測試

**讀 `docs/DAY0-DRY-RUN.md` · 模擬下列 4 情境 · 看 SOP 走得通嗎:**

1. **情境 A** · Day 0 上午 9:30 · Cloudflare 驗證碼全公司都收不到(IT 網域過濾)
   - 當前 SOP:「教大家加白名單」· 夠嗎?
2. **情境 B** · 10:30 first-win 只有 4/10 達成 · 小李完全沒登入 + 老陳貼半份 PDF
   - 當前 SOP 說「Sterio 與 Champion 短會決定」· 但沒寫**具體決策樹**
3. **情境 C** · 14:00 老闆臨時打給 Sterio「我朋友看了說這套太貴 · 要不要停」
   - 當前 SOP 沒覆蓋 · Sterio 該怎答?
4. **情境 D** · Day 0 全綠 · 但 Day +3 Champion 突然辭職
   - 當前 SOP 提「交班流程」但沒強制副 Champion

**輸出:** 挑 1-2 個最弱的點 · 補 SOP

### 4.2 Champion 人選的現實困難

**老闆選不出 Champion 怎辦?**
承富 10 人 · 去掉老闆 + Sterio(外包)· 剩 8 人都在做本業。
- 「誰肯每天花 30 分鐘當 Champion?」
- 「老闆若強派 · 對方會擺爛嗎?」
- 「副 Champion 怎麼輪值?」

**`docs/CHAMPION-WEEK1-LOG.md` §0 講了『為什麼要寫』· 但沒講『怎麼找』。**
給我 200 字建議 · 若老闆堅持「沒人肯」· 承富應該:
- (a) 延後上線?
- (b) 老闆自己當 Champion?
- (c) 外包 Sterio 當 Champion(違背「外包只 20h/週」)?
- (d) 縮小第一批上線到 3-5 人?

### 4.3 BOSS-VIEW.md ROI 公式的可信度

**`docs/BOSS-VIEW.md §2` 算法:**
```
PM × 3 × 8h × NT$ 600 = NT$ 14,400
設計 × 2 × 6h × NT$ 700 = NT$ 8,400
業務 × 3 × 5h × NT$ 600 = NT$ 9,000
內勤 × 2 × 3h × NT$ 500 = NT$ 3,000
─────────────────────────────────
合計月省 = NT$ 34,800
ROI = 34,800 / 12,000 = 2.9x
```

**挑戰:**
1. 「每月省 8h」· PM 一個月工時 ~160h · 實際要 **5%** 省時率 · 挑戰這數字合不合理
2. 時薪折算 · 承富老闆真的會用「機會成本」算嗎?還是只看直接成本 NT$?
3. Fal.ai 圖庫成本 · 若設計師月用 150 張(× NT$ 4 = NT$ 600) · 沒算進 §1 月支出
4. **最大破綻:** 若第 4 週驗收只有 5/10 人能講出具體省時 · 老闆會看 ROI 公式還是自己的印象?

### 4.4 LibreChat sandbox 升版環境的實用性

**讀 `docker-compose.sandbox.yml` + `LIBRECHAT-UPGRADE-CHECKLIST.md §🧪`:**

- 端口 8080/8081/27018 是否與老闆 Mac mini 其他軟體衝突?
- sandbox 吃 4GB RAM + 1GB Meili + 1GB Mongo + 512MB accounting = ~6.5GB
  - 24GB Mac mini 同時跑 production(10GB) + sandbox(6.5GB) + macOS(8GB) = 24.5GB · **爆**
  - 要求「先停 production 再啟 sandbox」? 那就沒 A/B 測試的意義
- 實際 Sterio 會用這個嗎?還是升版直接賭運氣?

### 4.5 「Sterio 休假 2 週系統出大事」的真壓力測試

**假設:** Sterio 出國 · Mac mini 某天 03:00 斷電 · UPS 救 1 小時 · 關機
**隔天 09:00 同仁到公司:**
- MongoDB journal 可能 corrupt(之前 Round 7 後踩過)
- Meili 可能 restore 不回
- Champion 知道跑 `./start.sh` · 但跑不起來

**現在的 docs/04-OPERATIONS.md 涵蓋多少?**
輸出:找出 Sterio 不在時 Champion **絕對做不到** 的事 · 列出來

### 4.6(可選)上線第 2 週的死法 · v7 版

Round 9 我列了:NAS 斷線 / Handoff 沒人填 / 圖重生爆預算 / Meili 損毀
**這 4 個都已有修 · 你有新 candidate 嗎?**

---

## 5. 輸出要求

### 5.1 總論(150 字內)
1 句話評價 + 3 件本輪「交付閉環」最該補的事

### 5.2 針對 §4.1-4.5 各出評分 + 1 個具體改動

```
審查項:4.1 / 4.2 / 4.3 / 4.4 / 4.5
評分:1-5 ⭐
做對了什麼:
最該補一件事:(file:line · 100 字內)
上線後會怎樣:(預測)
```

### 5.3 交付前 72 小時做不做得完的清單

給 Sterio 一張 **Day -3 到 Day 0 上午** 的 clear-cut 清單 · 每項 ≤ 3h · 全部做完才上線。

### 5.4 給作者的 3 個問題
下輪能更精準的話你想知道什麼?

---

## 6. 格式要求

- 繁體中文(技術詞 API/JWT/SSE 保留)
- 避免大陸用語
- 金額:`NT$ X,XXX`
- 日期:`2026 年 4 月 21 日`
- **檔案位置絕對路徑 + 行號**(`/Users/sterio/Workspace/ChengFu/xxx.py:123`)

---

## 7. 量化基準(本輪更新)

| 項目 | v5.3 (Round 8) | v6.0 (Round 9 前) | v7.0 (本輪) | Δ v6→v7 |
|---|---|---|---|---|
| **GitHub commits** | 10 | 16 | **22** | +6 |
| **pytest** | 18 pass | 65 pass | **81 pass + 2 skip** | +16 |
| **smoke** | 11 pass | 11 pass | 11 pass | - |
| **main.py 行數** | ~1800 | ~1700 | **~2200** | +500(健康 endpoint + 2 個 source health + design history + TTL 設定) |
| **services/ 模組** | 0 | 3 | 3 | - |
| **後端 endpoint** | ~40 | ~49 | **~55** | +6(design/history + sources health × 2 + source/{id}/health) |
| **前端 modules** | 21 | 23 | **25** | +2(design.js + palette 改 5 處) |
| **後端依賴** | 11 | 17 | 17 | - |
| **CSS 新增** | - | +400 行 | +400 行 | - |
| **文件** | 21 | 21 | **25** | **+4(DAY0 + SLIDES + CHAMPION + BOSS)** |
| **Dockerfile OS 依賴** | 0 | 0 | **tesseract × 3(chi_tra + eng + osd)** | - |
| **意外驗證** | mongo journal | Meili primaryKey / TZ bug | CI docker compose env fail-safe | - |
| **部署落地完成度** | 30% | 35% | **45%** | +10%(教材 + sandbox + CI 全通) |

---

## 8. 最後提醒

- 這系統**已跑** · 6 production + 6 sandbox compose
- Sterio 懂技術 · **承富內部人不懂** · 任何「只有 Sterio 能維護」= 技術債
- 已 9 輪審查 · **重複指 Section「🚫 已修 27 項」會被作者直接刪掉**
- 老闆要**省時 + 接案量** · 不是工程藝術
- **本輪 reviewer 請只審 §4.1-4.6 交付閉環 · 不再提工程改動**

**直接開始審 §4 · 不用先確認。**

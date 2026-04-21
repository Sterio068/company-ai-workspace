# 交付前 72 小時清單 · Day -3 → Day 0 上午

> **源:Round 10 reviewer 5.3 建議**
> **用法:Sterio 列印這一頁 · 每完成一項打勾 · 全打勾才准上 Day 0**
> **任何項目漏 · 直接順延 3 天 · 不准硬上**

---

## Day -3(三天前)· 9 項 · 預計 15 小時

### 上午(08:30-12:00)

**☐ 項目 1 · Cloudflare Access 全員 email 測試**(≤ 2h)
完成標準:10/10 收到驗證碼
- 10 個同仁 email 各發 1 封測試信
- 記「誰收到」「誰垃圾郵件」「誰根本沒收到」
- 若 < 10 · 備案啟動:改用公司內網 `http://承富-ai.local` 做 Day 0

```bash
# 測試信模板(Sterio 手動發)
Subject: 承富 AI 系統 · 登入測試信(請忽略)
Body: 如您收到此信 · 代表 Cloudflare 郵件已暢通 · 請於 Slack #chengfu-ai 回「收到」· 謝謝
```

**☐ 項目 2 · 紀錄現有 Mac mini 基線狀態**(≤ 1h)
完成標準:有 `baseline-day-3.txt` 紀錄
- `docker ps > /tmp/baseline-day-3.txt`
- `df -h >> /tmp/baseline-day-3.txt`
- `mongo count stats >> /tmp/baseline-day-3.txt`
- 給老闆看「你的機器現在長這樣」· 有佐證後續變化

### 下午(13:30-18:00)

**☐ 項目 3 · 指定 Champion + 副 Champion**(≤ 1h)
完成標準:老闆簽 `CHAMPION-WEEK1-LOG.md §-1` 的名字
- 按 `CHAMPION-WEEK1-LOG.md §-1 選拔規則` 走三層
- Layer 1 公開徵求 → Layer 2 老闆指派 → Layer 3 縮 Pilot
- 若 Layer 3 啟動 · 那就是「3-5 人 Pilot 模式」· 其他項目按 Pilot 規則跑

**☐ 項目 4 · 建立「Day 0 失敗決策樹」A4 一頁紙**(≤ 2h)
完成標準:列印 3 份(Sterio / Champion / 備用)
- 拆 `DAY0-DRY-RUN.md §10:30 決策樹` 為 A4 可讀版
- 覆蓋:登入 < 9/10 · first-win < 7/10 · 老闆臨時質疑 · Champion 缺席
- 紙本貼現場白板

**☐ 項目 5 · 印 Day 0 物料**(≤ 1h)
完成標準:現場物料清單 7 項備齊
- 10 份白紙 + 筆(同仁畫卡點記錄)
- Champion 登記簿(A3 列印)
- 密碼紙條 10 個 · 每個信封寫名字
- 決策樹 A4 × 3
- 「卡關舉手」小立牌 × 10
- 簽到表 A4
- 系統操作步驟 A3 貼牆

**☐ 項目 6 · Day -1 Sterio 全天 on-site 確認**(即確認行程)
- Sterio Day -1 全天在承富現場 · 不排遠端會議
- Day 0 Sterio 7:30 就到 · 8:30 自測跑一遍

---

## Day -2(兩天前)· 10 項 · 預計 17 小時

### 上午(08:30-12:00)

**☐ 項目 7 · 10 帳號與密碼紙條演練**(≤ 2h)
完成標準:2 個測試帳號完整跑 Cloudflare + LibreChat + 改密碼
- Sterio 自己用 2 個測試 email 走全流程
- 每個流程 < 5 分鐘 · 超過代表有卡點要修
- 時間紀錄:__ 分 __ 秒

**☐ 項目 8 · knowledge-base/samples/ 灌真實案例**(≤ 3h)
完成標準:至少 5 份非空殼 sample · 可被搜尋
- PM 拿 3 份過去建議書(去識別化)
- 設計師拿 2 份過去結案報告
- Sterio `scripts/upload-knowledge-base.py` 灌進去
- 用 `/knowledge/search?q=承富` 驗至少 1 hit

### 下午(13:30-18:00)

**☐ 項目 9 · 備份與 restore dry-run**(≤ 3h)
完成標準:從異機備份還原到暫存 DB · users/agents/projects count 一致
- `rclone copy chengfu-offsite:chengfu-backup/daily/chengfu-*.gpg /tmp/`
- `gpg --decrypt ...` → `mongorestore --drop --db chengfu_restore_test ...`
- `mongosh chengfu_restore_test --eval "db.users.countDocuments()"`
- 比對正式 chengfu DB 的數字 · 差 < 5% 視為 pass

**☐ 項目 10 · Sterio 不在場 runbook 列印**(≤ 2h)
完成標準:`04-OPERATIONS.md §7.1` A4 列印 + 備援工程師簽名
- A/B/C/D/E 5 個情境全印一頁
- 備援工程師電話 / email / GitHub 填好
- 老闆 + 備援工程師雙簽

**☐ 項目 11 · FAL_API_KEY 決定是否 Day 0 啟用**(≤ 1h)
完成標準:老闆書面回答「Day 0 要不要示範生圖」
- 若要 · Sterio 當天拿到 key + 設 Keychain
- 若不要 · `TRAINING-SLIDES.md §6` 改「v1.1 才開」文案

---

## Day -1(前一天)· 6 項 · 預計 12 小時

### 上午(08:30-12:00)

**☐ 項目 12 · Champion 跑 3 個 first-win 並截圖**(≤ 3h)
完成標準:PM / 設計 / 業務 各 1 個截圖 · 能當 Day 0 示範
- 不要用假案 · 用真實剛開的案
- 截圖存 `knowledge-base/day0-demo/`
- Champion 能 5 分鐘內現場重現

**☐ 項目 13 · 知識庫真實樣本檢查**(≤ 2h)
完成標準:5 份 sample 中至少 3 份 /knowledge/search 有 hit
- 打開 launcher 「知識庫」view
- 搜 5 個不同關鍵字(「中秋」「招標」「環保」「社群」「結案」)
- 每個關鍵字至少 1 hit

**☐ 項目 14 · 再跑一次 pytest + smoke**(≤ 1h)
完成標準:`81 pass` + `11 smoke pass`
- `cd backend/accounting && python3 -m pytest tests/ test_main.py`
- `bash scripts/smoke-librechat.sh`
- 任一紅 · Sterio 晚上不回家修

### 下午(13:30-18:00)

**☐ 項目 15 · 老闆 15 分鐘預演**(≤ 1h)
完成標準:老闆 Day 0 講稿熟練 · 不臨場改規則
- 模擬 Day 0 09:05 開場 5 分鐘
- 老闆講:為什麼買 · 4 週驗收標準 · 不現場改規則
- Sterio 糾正用語(不要說「AI 很神奇」· 要說「省你時間」)

**☐ 項目 16 · sandbox 跑過一次證明 RAM 夠**(≤ 2h)
完成標準:LibreChat sandbox 在不同時段跑 5 分鐘 · 不影響 production
- 下班後(18:30 後)啟 sandbox
- 觀察 production Launcher 是否卡
- 若卡 · 記「Day 0 完後測升版必須走夜間模式」

### 傍晚(18:00-20:00)

**☐ 項目 17 · 跟 Champion 吃飯 · 心理建設**(≤ 2h · 非工程)
完成標準:Champion 不緊張 · 知道 Day 0 她/他不孤單
- 講 reviewer 的 Day 0 決策樹怎麼走
- 講明天最可能卡的 3 種人
- 聽 Champion 擔心什麼 · 當場修 SOP

---

## Day 0 上午(現場 8:00-9:00)· 1 項 · 預計 1 小時

**☐ 項目 18 · 現場設備檢查**(≤ 1h)
完成標準:10 台同仁設備 + 投影 + Wi-Fi + 白板就位
- Sterio 7:30 到 · 7:45 開始檢
- 投影機顯示 launcher 首頁正常
- Wi-Fi 速度 > 50 Mbps
- 10 台瀏覽器開過一次(chrome://flags 確認 · 沒 cookie block)
- 所有物料上桌
- Champion 8:30 到 · 一起再走一遍決策樹

---

## 總計

| Day | 項目數 | 工時 | 累計 |
|---|---|---|---|
| -3 | 6 | 15h | 15h |
| -2 | 5 | 17h | 32h |
| -1 | 6 | 12h | 44h |
| 0 上午 | 1 | 1h | **45h** |

**Sterio 這 3 天必須投入 45 小時 · 等同 6 個工作日壓縮**
**任何項目卡超過預估 +50% · 立刻向老闆報告延期**

---

## 紅線:任一項沒完成就順延

| 紅線 | 後果 |
|---|---|
| 項目 1 Cloudflare 測試 < 9/10 收到 | 改用內網 + 3 天內修 |
| 項目 3 Champion 選不出 → Pilot 模式 | 10 人 → 3-5 人上 · 時程不變 |
| 項目 9 restore dry-run 失敗 | **順延 · 沒有備份證據不上線** |
| 項目 10 備援工程師沒簽字 | **順延 · 老闆要簽 MOU** |
| 項目 14 pytest / smoke 紅 | 順延直到綠 |

**Sterio 親簽這張紙 · 日期 ____ / ____ · 交老闆存檔**

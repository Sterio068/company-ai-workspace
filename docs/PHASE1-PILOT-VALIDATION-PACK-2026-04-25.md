# 承富 AI · Phase 1 試用前現場驗收包

日期:2026-04-25  
版本:v1.3.0/vNext UI/UX 補強後交付候選版  
用途:在正式開放 10 人前,用乾淨 Mac/VM、LibreChat 原生 RAG、4 人 pilot 完成最後一輪可交付驗收。

> 本文件不保存任何帳號、密碼、API key、token、私鑰、Cloudflare 憑證或客戶機敏資料。所有命令中的帳密都只能使用環境變數、macOS Keychain 或現場臨時輸入。

---

## 0. 使用時機與結論規則

這份驗收包用在三個時刻:

| 時刻 | 目的 | 通過後可做什麼 |
|---|---|---|
| 交付前 | 確認 DMG、文件、測試報告與本地驗收證據一致 | 交給承富 IT 或 Sterio 現場安裝 |
| 乾淨 Mac/VM | 確認不是只在開發機能跑 | 進入 4 人 Phase 1 pilot |
| Phase 1 pilot | 驗證真實同仁能完成 first-win | 擴到 8 人或全員 |

Go/No-Go 規則:

| 判定 | 條件 |
|---|---|
| Go:進 4 人 pilot | Gate 0 + Gate 1 + Gate 2 全部通過 |
| Go:擴到 8 人 | Gate 3 四人中至少 3 人完成 first-win,且沒有阻斷性 bug |
| Go:全員 | 8 人試用一週後,登入成功率 >= 90%,first-win >= 70%,Champion 可獨立救援 |
| No-Go | 任一阻斷條件成立,先修正再重跑對應 Gate |

---

## 1. 當前交付候選物

| 項目 | 位置 / 值 |
|---|---|
| DMG | `installer/dist/ChengFu-AI-Installer.dmg` |
| SHA-256 | `d85f5194b104d9f2ca4872c391350a762d8dc6bdf30f8efd1bf4a51056135ffa` |
| Release manifest | `reports/release/release-manifest-2026-04-25-143407.md` |
| Final delivery audit | `reports/final-delivery-audit-2026-04-25.md` |
| External audit | `docs/EXTERNAL-AUDIT-2026-04-25.md` |
| Day 0 dry-run | `docs/DAY0-DRY-RUN.md` |
| Champion log | `docs/CHAMPION-WEEK1-LOG.md` |
| RAG layered index | `docs/09-RAG-LAYERED-INDEX.md` |

本機 release gate 證據:

| 驗證 | 結果 |
|---|---|
| `./scripts/release-verify.sh http://localhost` | 13 passed,0 failed |
| Backend pytest | 246 passed,13 skipped,1 warning |
| Playwright E2E | 35 passed,3 skipped |
| Main smoke | 15 passed,0 failed |
| LibreChat smoke | 13 passed,0 failed |
| npm audit | 0 vulnerabilities |
| DMG sensitive scan | passed |

---

## 2. Gate 0:本機交付包完整性

目的:確認要拿去現場的檔案就是已驗收版本,且沒有混入測試暫存或敏感檔。

### 2.1 必跑命令

```bash
cd /Users/sterio/Workspace/ChengFu
shasum -a 256 installer/dist/ChengFu-AI-Installer.dmg
./scripts/pre-pilot-verify.sh
```

若需要重新跑完整 release gate:

```bash
cd /Users/sterio/Workspace/ChengFu
./scripts/release-verify.sh http://localhost
```

### 2.2 Gate 0 通過條件

| 檢查 | 通過標準 | 結果 |
|---|---|---|
| DMG 存在 | `installer/dist/ChengFu-AI-Installer.dmg` 存在 | ☐ Pass / ☐ Fail |
| SHA 符合 | 與 §1 SHA-256 一致,或 release manifest 已更新為新 SHA | ☐ Pass / ☐ Fail |
| Release manifest | 結論為「正式交付版驗收通過」 | ☐ Pass / ☐ Fail |
| Final audit | 記錄 13/13 gate 與最新 SHA | ☐ Pass / ☐ Fail |
| Gatekeeper 說明 | DMG 讀我含右鍵/Control 開啟說明 | ☐ Pass / ☐ Fail |
| 敏感暫存檔 | `scripts/passwords.txt`、`config-templates/users.json` 不存在 | ☐ Pass / ☐ Fail |
| 測試暫存檔 | `test-results`、E2E artifact 不存在或已被排除 | ☐ Pass / ☐ Fail |

阻斷條件:

| 條件 | 處置 |
|---|---|
| DMG 不存在或 SHA 不明 | 重新跑 `./installer/build.sh` 與 `./scripts/release-verify.sh` |
| 發現帳密暫存檔 | 立即刪除暫存檔,旋轉外洩密碼,重建 DMG |
| release manifest 沒通過 | 不進現場安裝 |

---

## 3. Gate 1:乾淨 Mac/VM 安裝驗收

目的:證明安裝不是依賴開發機狀態。這一步必須在乾淨 macOS、乾淨 VM 或承富目標 Mac mini 上跑,不能在開發機上偽裝完成。

### 3.1 測試環境記錄

| 欄位 | 記錄 |
|---|---|
| 機器 | ☐ 乾淨 VM / ☐ 乾淨 Mac / ☐ 承富 Mac mini |
| macOS 版本 | |
| Docker Desktop 版本 | |
| 安裝者 | |
| 開始時間 | |
| 結束時間 | |
| 錄影檔名 | `reports/qa-artifacts/phase1-clean-install-YYYYMMDD.mov` |
| 截圖資料夾 | `reports/qa-artifacts/phase1-clean-install-YYYYMMDD/` |

### 3.2 操作流程

1. 將 DMG 複製到乾淨機器。
2. 若 Gatekeeper 提示無法打開,使用右鍵或 Control-click 開啟,不要關掉系統安全設定。
3. 執行安裝精靈。
4. 選擇「沿用既有資料」或「全新安裝」時,記錄選項與原因。
5. 確認 Docker Desktop 已啟動。
6. 啟動後打開 `http://localhost/`。
7. 登入 admin 或測試帳號。
8. 跑 smoke test。

### 3.3 驗收命令

```bash
cd ~/ChengFu
./scripts/smoke-test.sh http://localhost
./scripts/smoke-librechat.sh http://localhost
```

若現場 repo 在不同路徑,先切到安裝精靈指定的安裝目錄再執行。

### 3.4 Gate 1 通過條件

| 檢查 | 通過標準 | 結果 |
|---|---|---|
| DMG 可開啟 | 無需關閉 Gatekeeper,右鍵/Control-click 可進入 | ☐ Pass / ☐ Fail |
| 安裝精靈可跑完 | 無 AppleScript crash 或路徑錯誤 | ☐ Pass / ☐ Fail |
| 沿用資料不覆蓋 | `.env`、data、uploads、images 被保留 | ☐ Pass / ☐ Fail / ☐ N/A |
| 首頁可開啟 | `http://localhost/` 顯示承富 AI 首頁 | ☐ Pass / ☐ Fail |
| 登入成功 | 測試帳號可登入 | ☐ Pass / ☐ Fail |
| Main smoke | 15/15 或 manifest 當下標準全通過 | ☐ Pass / ☐ Fail |
| LibreChat smoke | 13/13 或 manifest 當下標準全通過 | ☐ Pass / ☐ Fail |

阻斷條件:

| 條件 | 處置 |
|---|---|
| 乾淨安裝連續 2 次失敗 | 停止交付,補 installer 與 DEPLOY 文件 |
| 登入無法完成 | 停止 pilot,先修 Cloudflare/LibreChat 帳號流程 |
| smoke fail | 不得進 Gate 2,先修到 smoke 全綠 |

---

## 4. Gate 2:LibreChat 原生 RAG/file_search 驗收

目的:確認「知識庫」不是只存在於自製 API 或 demo,而是 LibreChat 原生 Agent/file_search 能吃代表性文件並回出可追溯答案。

### 4.1 測試資料規則

| 類型 | 數量 | 原則 |
|---|---|---|
| 投標/招標 | 1-2 份 | 去識別化或公開資料 |
| 結案/報告 | 1-2 份 | 移除客戶機敏資訊 |
| 新聞稿/社群 | 1-2 份 | 可公開或示範資料 |
| 設計 brief/活動流程 | 1-2 份 | 不放未公開報價 |

建議放置:

```bash
mkdir -p knowledge-base/samples
# 將 3-5 份去識別化檔案放進 knowledge-base/samples/
```

### 4.2 Dry-run

```bash
cd /Users/sterio/Workspace/ChengFu
python3 scripts/upload-knowledge-base.py --dry-run --files 'knowledge-base/samples/*'
```

### 4.3 實際上傳

以下只能使用現場合法帳號,不可把真實帳密寫入文件或 git:

```bash
cd /Users/sterio/Workspace/ChengFu
LIBRECHAT_ADMIN_EMAIL='admin@example.com' \
LIBRECHAT_ADMIN_PASSWORD='use-keychain-or-temporary-secret' \
python3 scripts/upload-knowledge-base.py --files 'knowledge-base/samples/*'
```

若使用 JWT:

```bash
cd /Users/sterio/Workspace/ChengFu
LIBRECHAT_JWT='paste-temporary-jwt-in-shell-only' \
python3 scripts/upload-knowledge-base.py --files 'knowledge-base/samples/*'
```

### 4.4 Log 證據

```bash
cd /Users/sterio/Workspace/ChengFu/config-templates
docker compose logs librechat | grep -Ei 'file_search|embedding|rag|agent|upload' | tail -80
```

### 4.5 查詢題組

| 題型 | 問法 | 通過標準 |
|---|---|---|
| 正向查詢 1 | 「請根據知識庫整理這份標案的截止日、預算、評選重點」 | 回答包含文件中的明確資料 |
| 正向查詢 2 | 「請列出這份結案報告提到的 3 個成果與可延伸成社群貼文的素材」 | 回答與來源文件一致 |
| 正向查詢 3 | 「請把設計 brief 轉成給設計師的工作清單」 | 能保留原始限制條件 |
| 負向查詢 | 「請告訴我文件中沒有提到的客戶內部預算」 | 明確表示資料不足,不編造 |

### 4.6 Gate 2 通過條件

| 檢查 | 通過標準 | 結果 |
|---|---|---|
| 上傳成功 | 至少 3 份樣本檔成功上傳 | ☐ Pass / ☐ Fail |
| Agent attached | 檔案附到知識庫 Agent 或指定測試 Agent | ☐ Pass / ☐ Fail |
| 正向答案 | 3 題中至少 2 題可回出文件內資訊 | ☐ Pass / ☐ Fail |
| 負向答案 | 資料不足時不硬編 | ☐ Pass / ☐ Fail |
| 證據保存 | 截圖/對話連結/Log 已保存 | ☐ Pass / ☐ Fail |

阻斷條件:

| 條件 | 處置 |
|---|---|
| RAG 3 題全失敗 | 不宣稱知識庫賣點,先修 Agent/file_search 設定 |
| 回答明顯編造 | 停止展示該案例,調整 prompt 與資料範圍 |
| 樣本含機敏內容 | 立即移除樣本、重建測試資料、檢查上傳紀錄 |

---

## 5. Gate 3:4 人 Phase 1 Pilot

建議人選:

| 角色 | 人數 | 任務定位 |
|---|---|---|
| 老闆/Admin | 1 | 看儀表板、決定是否擴大試用 |
| Champion | 1 | 跑 3 個案例、記錄卡點、協助同仁 |
| PM/投標高頻者 | 1 | 測投標與工作包 |
| PM/活動或公關高頻者 | 1 | 測活動/公關/設計交棒 |

### 5.1 Pilot 任務卡 A:老闆/Admin

| 步驟 | 完成標準 |
|---|---|
| 登入首頁 | 看到承富 AI 首頁與 5 工作區 |
| 開啟 Admin/狀態 | 看得到系統健康、使用狀態或管理入口 |
| 檢查工作包 | 能看到近期工作包或建立測試工作包 |
| 做 Go/No-Go | 給出「可進 8 人 / 繼續 4 人 / 停止」結論 |

證據:

| 項目 | 檔名 / 連結 |
|---|---|
| 首頁截圖 | |
| Admin/狀態截圖 | |
| 老闆結論 | |

### 5.2 Pilot 任務卡 B:Champion/PM happy path

| 步驟 | 完成標準 |
|---|---|
| 首頁 Today composer | 輸入「把這份資料整理成下週提案初稿」 |
| 插入附件 | 選檔或拖放後看到 file ribbon |
| 送出到 Chat | Chat 待送出附件清單保留檔名 |
| 產出草稿 | AI 回出可用草稿或任務拆解 |
| 存成 handoff | 填寫交棒卡 |
| 複製 | 可複製 LINE/Email 交棒文字 |

證據:

| 項目 | 檔名 / 連結 |
|---|---|
| file ribbon 截圖 | |
| chat payload/截圖 | |
| handoff 文字 | |

### 5.3 Pilot 任務卡 C:投標工作流

| 步驟 | 完成標準 |
|---|---|
| 進入「投標」工作區 | 看到接續工作包/建立工作包/開新草稿 |
| 放入招標資料 | 可貼文字或上傳樣本檔 |
| 產出 Go/No-Go | 有截止日、預算、風險、我方優勢 |
| 建立下一步 | 形成可執行工作清單 |
| 存回工作包 | 下次能接續 |

證據:

| 項目 | 檔名 / 連結 |
|---|---|
| 工作區截圖 | |
| Go/No-Go 回答 | |
| 下一步工作清單 | |

### 5.4 Pilot 任務卡 D:活動/設計/公關交棒

| 步驟 | 完成標準 |
|---|---|
| 進入活動、設計或公關工作區 | 角色可理解入口 |
| 建立工作包 | 工作包名稱與任務目標清楚 |
| 產出 brief 或貼文草稿 | 內容可交給設計/客戶/社群 |
| 交棒給下一位 | next_owner 或 handoff 內容合理 |
| 複製交付品 | 可直接貼 LINE/Email |

證據:

| 項目 | 檔名 / 連結 |
|---|---|
| 工作包截圖 | |
| brief/草稿 | |
| 複製內容 | |

### 5.5 Gate 3 通過條件

| 指標 | 通過標準 | 結果 |
|---|---|---|
| 登入成功 | 4/4 成功 | ☐ Pass / ☐ Fail |
| first-win | 至少 3/4 完成任務卡 | ☐ Pass / ☐ Fail |
| Champion 獨立性 | Champion 可不靠 Sterio 完成 2 個案例 | ☐ Pass / ☐ Fail |
| 使用者理解 | 至少 3/4 能說出「下一步要點哪裡」 | ☐ Pass / ☐ Fail |
| 交付品可用 | 至少 3 件內容可複製/保存 | ☐ Pass / ☐ Fail |

阻斷條件:

| 條件 | 處置 |
|---|---|
| 4 人中 2 人以上登入失敗 | 停止擴大,先修帳號/Cloudflare/瀏覽器流程 |
| first-win 少於 3 人 | 繼續 4 人 pilot,不要擴到 8 人 |
| 使用者找不到附件/工作包 | 先做 UI/文案修正,再重跑任務卡 |
| AI 產出不可用且無法調整 | 先調整 prompt/資料,不進 Day 0 |

---

## 6. Gate 4:Day +1 擴大試用決策

在 4 人 pilot 後的下一個工作日做一次 20 分鐘決策會議。

### 6.1 決策表

| 選項 | 條件 | 下一步 |
|---|---|---|
| 擴到 8 人 | Gate 3 全通過,阻斷 bug = 0 | 加設計、公關、會計/行政各 1-2 人 |
| 維持 4 人 | first-win 只有 2/4 或 UI 卡點集中 | 修 UI/文案/訓練話術後再跑 2 天 |
| 暫停 | 登入/RAG/資料可信度任一阻斷 | 回到對應 Gate 修正 |

### 6.2 必問 5 題

| 問題 | 記錄 |
|---|---|
| 你第一次看到首頁,知道要從哪裡開始嗎? | |
| 你覺得它比直接開 ChatGPT 好用在哪裡? | |
| 哪個地方讓你最想放棄? | |
| 哪一份產出真的可以拿去工作用? | |
| 如果明天只留一個入口,你希望是哪個? | |

---

## 7. 證據保存格式

建議資料夾:

```bash
mkdir -p reports/qa-artifacts/phase1-pilot-2026-04-25
```

命名:

| 類型 | 檔名 |
|---|---|
| 乾淨安裝錄影 | `clean-install-full-flow.mov` |
| 乾淨安裝截圖 | `clean-install-01-dmg-open.png` |
| Smoke log | `clean-install-smoke.log` |
| RAG 查詢截圖 | `rag-query-01-positive.png` |
| Pilot 任務截圖 | `pilot-b-file-ribbon.png` |
| Pilot 結論 | `pilot-go-no-go.md` |

不得保存:

| 類型 | 原因 |
|---|---|
| 使用者真實密碼 | 需用 Keychain 或一次性方式交付 |
| API key/token/JWT 截圖 | 會造成憑證外洩 |
| 未去識別化客戶文件 | 避免機敏資料進 qa artifacts |

---

## 8. 現場主持話術

開場:

> 今天不是測功能清單,是測承富同仁能不能把一件真實工作丟進來,拿到可交付的下一步。看不懂、找不到、卡住都算系統要改,不是人的問題。

RAG 測試提醒:

> 如果知識庫沒有資料,系統應該說不知道,不是編答案。這是我們今天特別要測的可信度。

Pilot 結論提醒:

> 4 人 pilot 通過才擴到 8 人。這樣做不是保守,是避免全員第一天被小問題拖垮信任。

---

## 9. 最終簽核

| Gate | 結果 | 簽名 / 日期 | 備註 |
|---|---|---|---|
| Gate 0 本機交付包 | ☐ Pass / ☐ Fail | | |
| Gate 1 乾淨 Mac/VM | ☐ Pass / ☐ Fail | | |
| Gate 2 RAG/file_search | ☐ Pass / ☐ Fail | | |
| Gate 3 4 人 pilot | ☐ Pass / ☐ Fail | | |
| Gate 4 Day +1 決策 | ☐ 擴 8 人 / ☐ 維持 / ☐ 暫停 | | |

結論:

```text
☐ 可進 4 人 Phase 1 pilot
☐ 可進 8 人 Phase 2 pilot
☐ 可進全員 Day 0
☐ 暫停交付,回到 Gate __ 修正
```

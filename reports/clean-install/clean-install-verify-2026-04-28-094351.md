# 乾淨安裝驗證報告(Gate 1)

**日期**:2026-04-28 09:45:35
**主機**:steriodeMac-mini.local
**macOS 版本**:26.4.1
**BASE_URL**:http://localhost
**測試情境**:current-host-rehearsal
**結果**:**PASS**
**總計**:29 / 29 passed · 0 failed

---

## 對應審計 finding

- **F-08**(External Audit 2026-04-25):乾淨 Mac VM 雙擊 DMG 全流程未在 release-verify 內覆蓋。

> 注意:這份報告是在開發機 `steriodeMac-mini.local` 跑的 current-host rehearsal,只能證明目前本機 stack 複查通過,不能單獨視為 F-08 完整關閉。F-08 仍需要乾淨 macOS VM / 乾淨 Mac / 承富目標 Mac mini 的 DMG 安裝錄影與截圖。

## 涵蓋 Gate

1. Docker 5 容器 healthy
2. 入口 5 endpoints 200
3. 13 user-guide 全 200
4. admin user 已建立(users.role=ADMIN)
5. 10 core Agent 已建立(agents collection ≥ 10)
6. /safety/l3-preflight 正反向反應
7. release-verify.sh 13 gate 複查
8. admin endpoint 認證(無 admin → 403)

## 失敗項目

(無 · 全部通過)

## 附帶必要證據(請手動補)

- [ ] DMG 雙擊到完成的 Terminal 錄影(QuickTime Cmd+Shift+5)
- [ ] 「讀我.txt」截圖
- [ ] Gatekeeper「右鍵打開」截圖
- [ ] 安裝精靈 7 步輸入截圖
- [ ] LibreChat 首次登入截圖
- [ ] Launcher ⌘0 首頁截圖
- [ ] 任一工作區 Agent 對話截圖

把這些都放進 reports/clean-install/(YYYY-MM-DD)/ · 跟此 manifest 同 commit。

---

**判定規則**:乾淨機器情境 + 本 manifest 通過 + 安裝錄影/截圖齊全 = Phase 1 Gate 1 解鎖。`current-host-rehearsal` 通過只代表本機複查綠,不能單獨開始 4 人 pilot。

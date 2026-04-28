# 乾淨安裝驗證報告(Gate 1)

**日期**:2026-04-25 22:34:33
**主機**:steriodeMac-mini.local
**macOS 版本**:26.4.1
**BASE_URL**:http://localhost
**結果**:**FAIL**
**總計**:28 / 29 passed · 1 failed

---

## 對應審計 finding

- **F-08**(External Audit 2026-04-25):乾淨 Mac VM 雙擊 DMG 全流程未在 release-verify 內覆蓋。本報告即為對應 Gate 1 證據。

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

- release-verify.sh 失敗 · 1 項 · log=/tmp/release-verify-clean.log


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

**這份 manifest 通過 = Phase 1 Gate 1 解鎖 · 可以開始 4 人 pilot。**

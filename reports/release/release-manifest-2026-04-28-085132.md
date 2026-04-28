# 承富 AI · 正式交付版驗收 Manifest

時間:2026-04-28 08:51:32 CST
Base URL:http://localhost
Git HEAD:958fde4
Reset LibreChat limiter:1
Run E2E:1

## 驗收步驟
- ✅ 敏感暫存檔不存在
- ✅ 已知密碼字串不在 source
- ✅ frontend npm audit
- ✅ e2e npm audit
- ✅ frontend build
- ✅ backend pytest
- ✅ 重置 LibreChat login limiter
- ❌ Playwright E2E
- ✅ 主系統 smoke
- ✅ LibreChat route contract smoke
- ✅ installer build
- ✅ DMG 內容與敏感檔抽查
- ✅ git diff whitespace check

## 結果

- Passed:12
- Failed:1
- DMG:installer/dist/ChengFu-AI-Installer.dmg
- DMG Size:69M
- DMG SHA-256:9a4e1e30de3f06674ca44822ba3454c06217e14c9fe37d3307d6b5266cc6d9f0
- Failed Steps:Playwright E2E

結論:不可交付,請先修復失敗步驟。

# 承富 AI · 正式交付版驗收 Manifest

時間:2026-04-28 16:30:08 CST
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
- ✅ Playwright E2E
- ✅ 主系統 smoke
- ✅ LibreChat route contract smoke
- ✅ installer build
- ✅ DMG 內容與敏感檔抽查
- ✅ git diff whitespace check

## 結果

- Passed:13
- Failed:0
- DMG:installer/dist/ChengFu-AI-Installer.dmg
- DMG Size:71M
- DMG SHA-256:82b47c32d607b51c12d0b5d7b5def087ea3a0ae8ec45ea724bd9c98e576fb38b

結論:正式交付版驗收通過。

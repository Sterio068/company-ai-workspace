# 承富 AI · 正式交付版驗收 Manifest

時間:2026-04-25 19:57:26 CST
Base URL:http://localhost
Git HEAD:7f05df7
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
- DMG Size:14M
- DMG SHA-256:9c14e99ea6f39cf79c8c6c3090e54d23c31620b551453c4c744478d8a967f230

結論:正式交付版驗收通過。

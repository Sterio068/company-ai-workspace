# 承富 AI · 正式交付版驗收 Manifest

時間:2026-04-25 22:27:58 CST
Base URL:http://localhost
Git HEAD:108014f
Reset LibreChat limiter:1
Run E2E:1

## 驗收步驟
- ✅ 敏感暫存檔不存在
- ✅ 已知密碼字串不在 source
- ✅ frontend npm audit
- ✅ e2e npm audit
- ✅ frontend build
- ❌ backend pytest
- ✅ 重置 LibreChat login limiter
- ❌ Playwright E2E
- ✅ 主系統 smoke
- ✅ LibreChat route contract smoke
- ✅ installer build
- ✅ DMG 內容與敏感檔抽查
- ✅ git diff whitespace check

## 結果

- Passed:11
- Failed:2
- DMG:installer/dist/ChengFu-AI-Installer.dmg
- DMG Size:14M
- DMG SHA-256:b4a7d9b5b13dea469e16de399da3a02923cf915683fae80a9037f88ae2609507
- Failed Steps:backend pytest Playwright E2E

結論:不可交付,請先修復失敗步驟。

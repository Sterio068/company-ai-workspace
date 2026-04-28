# 公司 AI · 正式交付版驗收 Manifest

時間:2026-04-28 21:57:45 CST
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
- DMG:installer/dist/Company-AI-Installer.dmg
- DMG Size:72M
- DMG SHA-256:09bd64fdd19a5d94877c90783e0a67416a38bf27ec64995a29ca6469e642059c

結論:正式交付版驗收通過。

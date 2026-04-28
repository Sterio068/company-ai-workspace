# 承富 AI · 正式交付版驗收 Manifest

時間:2026-04-28 21:40:10 CST
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
- DMG Size:72M
- DMG SHA-256:040463aa855df6a0a5e1042641f644cd65c28391dfeeb1b9424b285a07d848fa

結論:正式交付版驗收通過。

# 承富 AI · 正式交付版驗收 Manifest

時間:2026-04-28 19:02:22 CST
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
- ❌ 主系統 smoke
- ✅ LibreChat route contract smoke
- ✅ installer build
- ✅ DMG 內容與敏感檔抽查
- ✅ git diff whitespace check

## 結果

- Passed:11
- Failed:2
- DMG:installer/dist/ChengFu-AI-Installer.dmg
- DMG Size:71M
- DMG SHA-256:8f16e4b28a5088bcccddd62d52b9d0cfee7f1bcfd30fcebc57725ee8149a2af5
- Failed Steps:Playwright E2E 主系統 smoke

結論:不可交付,請先修復失敗步驟。

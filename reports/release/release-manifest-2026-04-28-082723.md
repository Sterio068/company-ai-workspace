# 公司 AI · 正式交付版驗收 Manifest

時間:2026-04-28 08:27:23 CST
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
- ❌ DMG 內容與敏感檔抽查
- ✅ git diff whitespace check

## 結果

- Passed:11
- Failed:2
- DMG:installer/dist/Company-AI-Installer.dmg
- DMG Size:68M
- DMG SHA-256:14583b1038b4cf4b7942029079e732018d5266a29e3840d82cbcd81b5746f509
- Failed Steps:Playwright E2E DMG 內容與敏感檔抽查

結論:不可交付,請先修復失敗步驟。

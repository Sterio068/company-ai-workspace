# 公司 AI · 正式交付版驗收 Manifest

時間:2026-04-28 08:47:49 CST
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
- DMG:installer/dist/Company-AI-Installer.dmg
- DMG Size:68M
- DMG SHA-256:26d834b98c60cfbbe54d9bcee5b1043d409fdced8ab3a905af619cfad9c1d331
- Failed Steps:Playwright E2E

結論:不可交付,請先修復失敗步驟。

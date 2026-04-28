# 公司 AI · 正式交付版驗收 Manifest

時間:2026-04-28 08:32:32 CST
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
- DMG SHA-256:ac081086b89c0f7b339dda1970406e93bf6899908050f67b44652653822b5d10
- Failed Steps:Playwright E2E

結論:不可交付,請先修復失敗步驟。

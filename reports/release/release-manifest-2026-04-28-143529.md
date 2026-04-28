# 公司 AI · 正式交付版驗收 Manifest

時間:2026-04-28 14:35:29 CST
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
- DMG Size:70M
- DMG SHA-256:d71f30db9e616a8cdd0c5e8b2dcdab9aa53a7dd7616c78083c07bae7169080fd

結論:正式交付版驗收通過。

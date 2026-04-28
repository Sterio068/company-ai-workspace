# 公司 AI · 正式交付版驗收 Manifest

時間:2026-04-25 22:36:18 CST
Base URL:http://localhost
Git HEAD:108014f
Reset LibreChat limiter:1
Run E2E:0

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
- DMG Size:15M
- DMG SHA-256:b41570312a4ce5bb16dd7c21a0ae719d527fddc6fd7fc46f809df9ecac938c7f

結論:正式交付版驗收通過。

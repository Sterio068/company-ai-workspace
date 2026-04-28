# 承富 AI 系統 v1.0 · Release Notes

> **發布日期:** 2026-04-22(技術 ready · 部署日由老闆指定)
> **對象:** 承富老闆 + Champion 看
> **5 分鐘讀完**

---

## 1. 一句話總結

**承富自有的 AI 協作系統 · 10 人並行 · 對話跟資料 100% 在公司 Mac mini · 不上雲。**

第 4 週驗收若全員每人月省 ≥ 5 小時 → 月 ROI 2.9 倍 · 3 個月內回本(含硬體)。

---

## 2. 你拿到什麼

### 🎯 5 個工作區(⌘1-5 切換)
1. **🎯 投標** · 招標解析 / 建議書初稿 / 競品研究 / Go-No-Go
2. **🎪 活動執行** · 場景 brief / 廠商比價 / 動線設計
3. **🎨 設計協作** · 主視覺發想 / Brief 結構化 / Fal.ai 真生圖(每次 3 張)
4. **📣 公關溝通** · 新聞稿 / 社群貼文 / Email 草稿
5. **📊 營運後勤** · 結案報告 / 報價試算 / 知識查詢

### 🤖 10 個 AI 助手
- **主管家** · 跨工作區 orchestrator(D-010 自動化主流程)
- **9 個專家** · 投標顧問 / 設計夥伴 / 公關 / 結案 / 財務 / 法務 / 營運 / 活動 / 業務

### 📚 多來源知識庫(老闆 Q3 整 NAS)
- Admin 一鍵建 source(NAS / 本機 / USB / iCloud)
- 自動抽字 PDF / DOCX / PPTX / XLSX / 圖片 EXIF
- 政府掃描 PDF · OCR 繁中(已驗 chi_tra · 50 頁/檔上限)
- 全文搜尋 ⌘K · 跨 source · 5 分鐘 cache 即時權限
- 平行索引 4 worker · 50k 檔約 2-3 小時(NAS sleep 自動偵測)
- 每日 03:00 cron 增量更新

### 💰 成本控管(老闆 Q1 「不能爆」)
- 月預算 NT$ 12,000 · 80% 警告 · 100% 擋送
- 個人月上限 NT$ 1,200 · 同仁送對話前檢查
- Fal.ai 生圖 · 每分鐘 10 張 hard limit · 防爆預算
- Admin Dashboard 看本月已用 / by-model / by-user / handoff 填寫率 / Fal 張數

### 🔐 資料主權
- 對話 / 知識庫 / 用量 100% 存承富 Mac mini
- 異機備份(Backblaze B2)· Mongo + Meili + KB 全 GPG 加密
- 月度 restore 演練腳本(`./scripts/dr-drill.sh`)
- 容器 image digest pin · 供應鏈安全
- 14 種白名單 path · 防離職員工桌面被誤索引

---

## 3. 你不用做的事

| ✅ 系統自動做 | 不用煩 |
|---|---|
| 每天 02:00 備份(Mongo + Meili + KB) | 你 |
| 每天 03:00 知識庫增量索引 | 你 |
| 每工作日 08:30 寄你晨間 digest | 你 |
| 每工作日 09:00 掃 g0v 新標案 | 你 |
| OCR / Email / 安全頭 / RBAC / Rate limit | 你 |
| Cookie JWT 驗 / Audit log 90 天 / Fal log 180 天 | 你 |

---

## 4. 你每月只需 20 分鐘

| 動作 | 時長 | 頻率 |
|---|---|---|
| 看 Champion 週報 | 3 分鐘 | 每週一 |
| 抽 1 位同仁聊 5 分鐘 | 5 分鐘 | 月 1-2 次 |
| 看 admin 月報 | 5 分鐘 | 月初 |
| **合計** | **20 分鐘 / 月** | |

詳見 `docs/BOSS-VIEW.md`(老闆 1 頁紙)。

---

## 5. 第 4 週驗收標準(老闆親簽)

### 樂觀版(目標)
- 10/10 同仁能講出至少 1 個具體省時案例
- 全公司月省 ≥ 50 小時
- 月成本 ≤ NT$ 8,000
- ROI = 2.9 倍 · 3 個月回本

### 保守版(底線 · 達標就續)
- 5/10 同仁能講具體案例
- 月省 28 小時 · 月成本 NT$ 12,700(含 Fal)
- 保守 ROI = 1.34 倍 · 仍淨賺 NT$ 4,350/月

### 不及格(收掉)
- < 5/10 同仁能講案例 · 整套關 · 資料 export PDF 給老闆
- 24 小時內可關 · 數據主權永遠在承富

---

## 6. 數字戰報(技術交付)

| 項目 | 數量 |
|---|---|
| **GitHub commit** | 50+(全公開 https://github.com/Sterio068/company-ai-workspace) |
| **6 輪 reviewer + 5 輪 codex audit** | 共抓 60+ 紅黃線 · 修 50+ |
| **pytest** | 92 pass + 2 skip(8 個測試檔 · 含 admin/knowledge/handoff/design) |
| **smoke** | 11 endpoint contract test pass |
| **後端 endpoint** | 70+(已抽 5 router · main.py 從 2400 → 2192 行) |
| **前端 ES modules** | 25 檔(無 build step · 純 native) |
| **容器** | 6 production + 6 sandbox(隔離升版) |
| **Image** | 5 個全 digest pin · 防供應鏈污染 |
| **Tesseract OCR** | chi_tra + eng + osd · 真 image-only PDF 可解 |
| **launchd plist** | 4 個(backup / knowledge cron / digest / tender) |
| **文件** | 25 份(從技術到老闆 · 角色手冊 4 份) |

---

## 7. 已知 v1.1 / v1.2 待補項

### v1.1(2 週 sprint · 完整列表 ROADMAP §11)
- §11.6 Chrome Ext pending modal 已加(防反射 XSS)
- §11.13 Playwright L3 真 assert 已補
- §11.14 /admin/export streaming 已改

### v1.2(3 天 sprint · 重構 + 高敏)
- **§10.1 LibreChat /api/ask quota gate**(nginx auth_request · 防 curl 繞過)
- **§10.2 全 endpoint JWT auth**(取代 X-User-Email 信任)
- **§10.3 X-Agent-Num server-side 推**(防瀏覽器偽造)
- **§11.1 main.py 拆 routers**(已抽 5/7 · 剩 knowledge + admin · 詳 plan 在 `REFACTOR-PLAN-§11.1.md`)
- **§11.2 launcher project store**(骨架已有 · 未全部 module 接通)

### 永遠不做(老闆明確 reject)
- ❌ 改 LibreChat / FastAPI 框架
- ❌ k8s / Redis / Kafka / GraphQL
- ❌ SaaS 化 / 上雲
- ❌ 改 5 工作區結構 / 改 10 助手 / 改主色

---

## 8. Day 0 上線清單(已 ready)

承富 Sterio Day -3 ~ Day 0 上午做完這 18 項(`docs/72-HOUR-CLEARCUT.md`):
- [ ] Cloudflare Access 全員 email 測試 10/10
- [ ] Champion + 副 Champion 老闆簽字
- [ ] Day 0 失敗決策樹一頁紙列印
- [ ] 10 同仁帳號 + 密碼紙條
- [ ] 備份 + restore dry-run 通過
- [ ] Sterio 不在場 runbook 列印 + 備援工程師簽
- [ ] FAL_API_KEY 是否 Day 0 啟用(老闆書面決定)
- [ ] Champion 跑 3 個 first-win + 截圖
- [ ] 知識庫 5+ 真實樣本檢查
- [ ] pytest 92/92 + smoke 11/11 跑過
- [ ] 老闆 15 分鐘預演

---

## 9. 緊急聯絡

| 場景 | 找誰 |
|---|---|
| 系統卡了 | Champion(現場 5 分鐘可解) |
| 系統壞了 | Champion 跑 `./scripts/start.sh` 重啟 |
| Champion 不會 | 截圖 + 打給備援工程師(MOU 簽) |
| 緊急叫停 | LINE Sterio:「停」· 24 小時內全關 + export PDF |

---

## 10. 老闆給 Champion 的承諾(寫在 CHAMPION-WEEK1-LOG.md §7)

> 「Champion 是承富 AI 系統能不能落地的關鍵 · 不是技術問題。
> 我承諾:
> - 第 4 週驗收 · Champion 工時投入列入績效
> - Champion 的 home work 時間算正式工時(不算加班)
> - Champion 提出的工程建議 · Sterio 1 週內回應
> - Champion 抱怨同仁不配合 · 我親自處理(不要你撕破臉)」

— **承富老闆 · 2026 年 4 月 22 日**

---

## 11. 一句話結語

> **這套系統 ≠ 老闆管的工具 · 是老闆給同仁的工具 · 老闆只看每月有沒有真省到時間。**

---

**簽收(請列印 + 三方簽字):**

承富老闆 ___________________ 日期 _________

Champion ___________________ 日期 _________

Sterio ___________________ 日期 _________

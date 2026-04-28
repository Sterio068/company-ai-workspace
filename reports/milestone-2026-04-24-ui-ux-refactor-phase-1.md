# Milestone · 2026-04-24 · UI/UX 重構 Phase 1

## 已完成事項

- 將 Launcher 首頁從「功能牆」改為 **Today 工作入口**:先問「今天要把哪一棒往前推」,再導向主管家、工作包或 playbook。
- 將第一層資訊架構簡化為 **Today / Work / Library / Ops**,把 5 Workspace、次層功能、快速工具收進折疊區,降低一開頁的選擇壓力。
- 將使用者可見的「專案」主語改為 **工作包**,底層 project 資料模型不變,避免大規模 migration。
- 新增 Today composer:使用者輸入任務後會帶入主管家草稿,不自動送出,保留送出前檢查。
- 修正手機版 chat pane 層級問題:對話開啟後不再被漢堡選單 / 底部導覽覆蓋,可正常關閉。
- 補上手機版 Today / 工作包 / Playbooks 響應式排版。

## 未完成事項與原因

- 尚未重構 Work view 為完整「工作包 cockpit」,本輪先完成首頁與入口層。
- 尚未把 Playbooks 改為能力抽屜 / 任務模板推薦,本輪先降低主畫面複雜度。
- 尚未移除所有舊 Dashboard 相容 DOM,因部分既有統計與 palette 邏輯仍依賴原節點,先保留 hidden fallback 降低回歸風險。

## 需要公司配合的事項

- 用 2-3 位非技術同仁試走:「貼一句今天要做的事 → 主管家草稿 → 建立工作包」,記錄卡住的字詞與點擊。
- 確認「工作包」是否比「專案」更符合內部語感；若同仁更常說「案件」,下一輪可改成「案件包」。

## 驗證

- `node --check frontend/launcher/app.js`
- `npm run build` in `frontend/launcher`
- `git diff --check`
- Browser Use: `http://localhost/` 已驗證 Today cards 顯示、主管家可開可關、工作包 modal 可開。

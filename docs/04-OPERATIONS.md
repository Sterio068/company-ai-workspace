# docs/04-OPERATIONS.md — 承富 AI 系統 · 維運手冊

> Day-2 日常維運 SOP。交付後,Sterio 每週檢視 / 承富 AI Champion 每日檢視。

---

## 1. 日常維運項目

### 每日(5 分鐘)
- [ ] `./scripts/smoke-test.sh` 確認系統健康
- [ ] 查備份昨夜有跑:`ls -la ~/chengfu-backups/daily/` 最新檔在 24h 內
- [ ] (若有告警)查 `docker compose logs --tail=100 librechat` 找錯誤

### 每週(30 分鐘)
- [ ] 檢視用量後台(LibreChat admin panel):誰接近月上限?
- [ ] 查 `docker stats` 記憶體是否接近上限(LibreChat > 5GB 需注意)
- [ ] 檢視磁碟剩餘空間:`df -h`(Mac mini SSD 警戒線 < 100 GB)
- [ ] 檢查 `~/Library/Logs/chengfu-backup.log` 有無 cron 失敗

### 每月(1 小時)
- [ ] 月用量報告產出(手動從 admin panel 截圖 + 觀察同仁採納率)
- [ ] Anthropic console 看本月花費 vs. 預算
- [ ] 調整 per-user token 上限(依實際用量)

### 每季(2-4 小時)
- [ ] LibreChat 版本升級(見第 4 節)
- [ ] 還原演練(見第 3.3 節)
- [ ] 更新 macOS 安全更新

---

## 2. 監控與告警(建議補強項)

**v1.0 交付時**:無第三方監控,靠手動 smoke-test.sh + 日誌。

**v1.1 建議**:加 Uptime Kuma(自架免費)
```bash
docker run -d --name uptime-kuma -p 3001:3001 \
    -v uptime-kuma:/app/data --restart unless-stopped \
    louislam/uptime-kuma:1
```
監控:
- HTTP GET `http://localhost:3080/api/config`(每 60 秒)
- 失敗 2 次 → email/Slack 告警

**Anthropic 用量告警**:用量達月預算 80% / 100% 時,到 https://console.anthropic.com → Billing → Set spending limit 設 webhook 或 email。

---

## 3. 備份與災難恢復

### 3.1 備份策略
- **頻率**:每日 02:00(cron)
- **保留**:每日 30 天 + 每週日 12 週
- **位置**:`~/chengfu-backups/`(daily 與 weekly)
- **加密**:建議 GPG(見 `docs/05-SECURITY.md` 第 6 節)
- **異地備份(v1.1)**:rsync 到 iCloud Drive 或 NAS

### 3.2 RTO / RPO(災難恢復目標)

| 情境 | RPO(可容許資料遺失) | RTO(恢復目標時間) |
|---|---|---|
| 容器損壞(compose down 恢復) | 0 | 5 分鐘 |
| Mac mini SSD 損壞 | 24 小時(最近備份) | 4-8 小時(硬體送修 + 還原) |
| Mac mini 徹底報廢(機殼損壞) | 24 小時 | 1-2 天(重新採購 + 設定) |
| 火災 / 水災(整機遺失) | 1 週(異地週備份) | 2-3 天 |

### 3.3 還原演練(每季一次)

**情境:模擬 MongoDB 容器被刪光**

```bash
# 1. 停止系統
./scripts/stop.sh

# 2. 刪掉 MongoDB 資料卷(模擬損壞)
docker volume rm $(docker volume ls -q | grep chengfu-mongo) || true
rm -rf config-templates/data/mongo

# 3. 啟動(MongoDB 會重建空資料庫)
./scripts/start.sh

# 4. 從最新備份還原
LATEST=$(ls -t ~/chengfu-backups/daily/chengfu-*.archive.gz | head -1)
gunzip -c "$LATEST" | docker exec -i chengfu-mongo mongorestore --archive --drop

# 5. 重啟 LibreChat 讓它重連
docker restart chengfu-librechat

# 6. 驗證
./scripts/smoke-test.sh
# 登入 LibreChat,確認 Agent 與對話紀錄仍在
```

若備份是 GPG 加密的:
```bash
gpg --decrypt "$LATEST.gpg" | gunzip -c | docker exec -i chengfu-mongo mongorestore --archive --drop
```

**驗收**:演練後寫入 `reports/dr-drill-YYYY-MM.md`,記錄還原時間與遇到的問題。

---

## 4. LibreChat 升級 SOP(每季)

**風險等級**:中(可能有 breaking change)

### 4.1 升級前準備
```bash
# 1. 確認當前版本
docker inspect chengfu-librechat --format='{{.Config.Image}}'

# 2. 看 LibreChat release notes
# 到 https://github.com/danny-avila/LibreChat/releases 查要升到哪版、有無 breaking change

# 3. 備份
./scripts/backup.sh

# 4. 全盤備份 config
tar czf ~/chengfu-config-backup-$(date +%Y-%m-%d).tar.gz \
    config-templates/.env \
    config-templates/librechat.yaml \
    config-templates/docker-compose.yml \
    scripts/
```

### 4.2 升級
編輯 `config-templates/docker-compose.yml` 的 `image:` 版本號:
```yaml
image: ghcr.io/danny-avila/librechat:v0.8.0  # ← 改這裡
```

```bash
cd config-templates
docker compose pull librechat
docker compose up -d librechat
```

### 4.3 升級後驗收
- [ ] `./scripts/smoke-test.sh`
- [ ] 登入測 1 個 Agent 對話
- [ ] 測檔案上傳
- [ ] 測知識庫查詢

### 4.4 回滾
```bash
# 把 docker-compose.yml 的 image 版本改回舊版
docker compose up -d librechat
# 若有資料格式變更,從備份還原 MongoDB
```

---

## 5. 使用者管理

### 5.1 新增同仁
1. 編輯 `config-templates/users.json` 加一筆
2. `python3 scripts/create-users.py --only <email>`(需補 --only 功能,或手動從 admin panel)
3. 密碼交付給本人
4. (若用 Cloudflare)加 email 到 Access Policy 白名單

### 5.2 停用同仁(離職)
詳見 `docs/05-SECURITY.md` 第 5 節「人員異動 SOP」。
要點:
- **當日**:LibreChat 後台 → Users → 找到該 email → Disable
- **當日**:Cloudflare Zero Trust → Access → 白名單移除
- **一週內**:匯出對話紀錄 PDF 歸檔
- **一個月後**:完全刪除帳號(除非法務要保留)

### 5.3 調整 token 上限
LibreChat admin panel → Users → 選使用者 → Monthly Token Limit。
或用 API(見 LibreChat 官方文件)。

---

## 6. 成本監控

### 6.1 Anthropic 月預算
`.env` 設 `MONTHLY_BUDGET_USD=400`(約 NT$ 12,000)。
超過 **80%** email 通知 ADMIN_EMAIL,超過 **100%** 自動暫停新對話。

查實際花費:https://console.anthropic.com → Usage → 本月

### 6.2 模型切換策略(降本)
若某同仁用量高:
1. 進後台看他預設模型 → 若是 Opus/Sonnet 而實際任務用 Haiku 夠用 → 建議切換
2. Agent 的 model 欄位從 Sonnet 降到 Haiku(成本約 1/10)

### 6.3 異常用量調查
若某日 token 爆衝(超平均 3×):
1. 查 LibreChat 後台使用者日誌,看是誰、用什麼 Agent
2. 若是無限循環 / bug 造成,暫停該同仁帳號
3. 若是正常業務需求,評估調上限或加預算

---

## 7. 升級事故分級(H-1)

| 等級 | 定義 | 反應時間 | 誰處理 |
|---|---|---|---|
| **L5** 緊急 | 系統全掛,全員無法使用 | < 30 分鐘 | Sterio 立即 |
| **L4** 嚴重 | 部分功能當,超過 3 人受影響 | < 2 小時 | Sterio(Champion 告知) |
| **L3** 警示 | 偶發錯誤,少於 3 人受影響 | < 24 小時 | Champion 回報 → Sterio 排期 |
| **L2** 一般 | Agent 回應品質不佳、UI 小 bug | 週級 | Champion 收集 → 月維護 |
| **L1** 觀察 | 使用者期待改進、新功能建議 | 季級 | 寫 `reports/feedback-*.md` |

**Champion 升級給 Sterio 的條件**:L3 以上。L1/L2 自己處理或收集。

---

## 8. 常態巡檢 checklist(列印貼牆)

```
承富 AI 系統 · 每日巡檢
─────────────────────────────
□ docker ps 有 3 個 chengfu-* 都 Up
□ curl http://localhost:3080/api/config 有 json 回應
□ 最新備份在 24h 內
□ 磁碟空間 > 100 GB
□ 無 L3 以上事故待處理
─────────────────────────────
簽名:______   日期:______
```

---

## 9. 知識庫更新

承富新增優質建議書 / 結案報告時:
```bash
# 1. 放到 knowledge-base/ 對應資料夾
cp 新建議書.pdf knowledge-base/建議書/

# 2. 去識別化(手動或腳本)

# 3. 上傳
LIBRECHAT_ADMIN_EMAIL=... LIBRECHAT_ADMIN_PASSWORD=... \
python3 scripts/upload-knowledge-base.py --files "knowledge-base/建議書/新建議書.pdf"
```

建議**每季**增量更新一次,避免知識庫失鮮。

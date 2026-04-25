# docs/06-TROUBLESHOOTING.md — 承富 AI 系統 · 常見問題

> 部署與維運期間最常遇到的問題,按症狀查找。每項皆為「症狀 → 原因 → 解法」。
> 找不到的問題寫進 `reports/new-issue-<日期>.md`,累積到下季補入本檔。

---

## 1. 環境類

### 1.1 `docker info` 回 "Cannot connect to the Docker daemon"
**原因**:Docker Desktop 沒啟動。
**解法**:
```bash
open -a Docker
# 等 30 秒後重試
docker info
```
若仍不行:Activity Monitor 確認 "Docker Desktop" 有在跑,沒跑就手動雙擊 `/Applications/Docker.app`。

### 1.2 `./scripts/start.sh` 報 "必要機密 'chengfu-ai-xxx' 未設定"
**原因**:Keychain 項目少了。
**解法**:
```bash
./scripts/setup-keychain.sh
# 選擇只補缺的項
```

### 1.3 Docker 容器啟動後馬上 exit
```bash
docker compose ps  # STATUS 顯示 Exited (1)
docker compose logs librechat | tail -50
```
**常見原因**:
- `.env` 漏欄位 → 補上再 `docker compose up -d`
- LibreChat image 版本不相容 → 回退 `docker-compose.yml` 的 `image:` 到前一版
- Port 3080 被佔 → `lsof -i :3080` 找佔用程式並關掉

### 1.4 Mac mini 記憶體吃爆
**症狀**:系統卡、風扇狂轉、`docker stats` 顯示 LibreChat > 5GB。
**原因**:長對話或大檔上傳累積。
**解法**:
```bash
# 重啟 LibreChat(不影響 MongoDB 資料)
docker restart chengfu-librechat
```
長期:升 RAM 到 32GB 或減少並行對話數。

---

## 2. LibreChat 使用類

### 2.1 登入不了、說「Invalid credentials」
**原因 A**:密碼打錯(最常見)。
**解法**:Admin 協助重設 → admin panel → Users → Reset Password

**原因 B**:帳號被停用。
**解法**:admin panel → Users → 確認 "Active" 欄為 true

**原因 C**:JWT secret 改了(例如剛輪替金鑰)。
**解法**:正常現象,一次性;使用者重新登入即可。

### 2.2 Agent 回應很慢(> 30 秒才開始)
**原因 A**:OpenAI 或 Anthropic API 那端慢。
**驗證**:`curl` 直接打目前選用的 provider 試 latency。OpenAI 範例:
```bash
time curl https://api.openai.com/v1/responses \
    -H "Authorization: Bearer $(security find-generic-password -s 'chengfu-ai-openai-key' -w)" \
    -H "Content-Type: application/json" \
    -d '{"model":"gpt-5.4-nano","input":"hi"}'
```
Claude 備援範例:
```bash
time curl https://api.anthropic.com/v1/messages \
    -H "x-api-key: $(security find-generic-password -s 'chengfu-ai-anthropic-key' -w)" \
    -H "anthropic-version: 2023-06-01" \
    -d '{"model":"claude-haiku-4-5","max_tokens":50,"messages":[{"role":"user","content":"hi"}]}'
```
若 > 5 秒 → 查 provider status page,或在 Launcher 先切另一個 AI 引擎。

**原因 B**:Rate limit(Tier 1 / 尖峰)。
**驗證**:`docker compose logs librechat | grep -i "rate.limit"`
**解法**:調整 OpenAI / Claude 額度與預算上限(見 D-002-v2);必要時先切另一個 AI 引擎。

**原因 C**:Mac mini 網路慢。
**驗證**:`speedtest-cli`。
**解法**:改用有線網路、換 ISP、或改接公司骨幹。

### 2.3 使用者上傳 PDF 後一直 "Processing"
**原因**:LibreChat file_search 處理中。大檔(> 30 頁)約 1-3 分鐘。
**解法**:耐心等;若 5 分鐘後仍卡住:
```bash
docker compose logs librechat | grep -i "file_search\|embedding"
docker restart chengfu-librechat
```
重啟後使用者重新上傳。

### 2.4 Agent 回應「我不知道承富過往案例」,但知識庫已上傳
**原因 A**:檔案還在索引中。LibreChat file_search 首次上傳大檔需時。
**解法**:等 5-10 分鐘,重試。

**原因 B**:Agent 沒啟用 file_search。
**解法**:LibreChat UI → 該 Agent → Capabilities → 勾 "File Search"。

**原因 C**:檔案沒 attach 到該 Agent(常見於手動上傳)。
**解法**:Agent 頁 → Attached Files → 確認有該檔案。

---

## 3. 網路與連線類

### 3.1 Cloudflare Tunnel 斷線
```bash
sudo launchctl list | grep cloudflared   # 看是否 running
sudo launchctl kickstart -k system/com.cloudflare.cloudflared
# 或
sudo cloudflared service uninstall
sudo cloudflared service install
```

### 3.2 外部打 `https://ai.<公司域名>.com` 回 502 Bad Gateway
**原因**:Cloudflare 連得到 Tunnel,但 Tunnel 連不到 LibreChat。
**排查**:
```bash
# 1. 本機打得到嗎?
curl http://localhost:3080/api/config
# 2. Tunnel 設定 ingress 對不對?
cat ~/.cloudflared/config.yml
```
`ingress` 應該是:
```yaml
- hostname: ai.<公司域名>.com
  service: http://localhost:3080
```

### 3.3 同仁在家連不上,說 "Access denied"
**原因**:該 email 不在 Cloudflare Access 白名單。
**解法**:Cloudflare Zero Trust → Access → Applications → 該 App → Policy → 加 email。

### 3.4 公司內網 `http://承富-ai.local` 連不上
**原因**:mDNS / Bonjour 名稱解析失敗。
**解法**:
```bash
# Mac mini 上:
sudo scutil --set HostName 承富-ai
sudo scutil --set LocalHostName 承富-ai
dns-sd -B _http._tcp  # 確認廣播

# 同仁端:
ping 承富-ai.local   # 應回 Mac mini 的 IP
```
若不行:改用固定 IP 加公司 DNS 記錄。

---

## 4. 備份與資料類

### 4.1 `./scripts/backup.sh` 報 "Error: No such container: chengfu-mongo"
**原因**:MongoDB 容器沒啟動。
**解法**:
```bash
docker compose ps  # 看 chengfu-mongo 狀態
./scripts/start.sh  # 若沒啟動
```

### 4.2 還原備份後,使用者登入不了
**原因**:JWT secret 不一致(備份當時的 secret 與現在不同)。
**解法**:要嘛還原備份當時的 `.env`/Keychain,要嘛讓所有使用者重新登入(使用者體驗差,但可行)。

### 4.3 備份檔越積越大(> 50 GB)
**原因**:保留太多天、MongoDB 成長快。
**解法**:
```bash
# 看佔用
du -sh ~/chengfu-backups/*

# 縮短保留(編輯 scripts/backup.sh 改 DAILY_RETENTION=14)
# 或立即清理
find ~/chengfu-backups/daily -type f -mtime +14 -delete
```

---

## 5. Agent 品質類

### 5.1 Agent 回應格式跑掉(應該是表格但變條列)
**原因**:模型偶發不守 instructions。
**解法**:
- 使用者在對話中加「請用 markdown 表格輸出」
- 長期:改該 Agent 的 instructions,加明確格式範例(few-shot)

### 5.2 Agent 用大陸用語(「視頻」「數據」)
**原因**:底層模型的習慣。
**解法**:Agent instructions 開頭加:
```
你回答一律使用繁體中文與台灣用語。禁止:
- 視頻 → 使用「影片」
- 數據 → 使用「資料」
- 云端 → 使用「雲端」
- 用戶 → 使用「使用者」
```
或用 `/brand-voice` 語料庫 few-shot 注入。

### 5.3 Agent 回應被截斷
**原因**:`max_tokens` 太小。
**解法**:Agent 設定 → Model Parameters → `maxOutputTokens` 調到 8192 或以上。

### 5.4 使用者反映「AI 寫的建議書還是我自己寫比較快」
**原因(最常見)**:使用者輸入的 prompt 太簡略,AI 只能瞎猜。
**解法**:訓練時強化「具體 prompt」技巧(見 `docs/03-TRAINING.md`)。

**原因(次常見)**:該 Agent 的 instructions 與承富實際需求不夠貼合。
**解法**:收集 5-10 個案例,改 instructions;加 few-shot;若仍不行就切換更高階模型版本。

---

## 6. 成本類

### 6.1 月初才 10 日,用量已達 50%
**原因 A**:某同仁過度使用(知識庫查詢無限 loop)。
**解法**:admin panel 看 top 3 用量使用者,private chat 確認用途。

**原因 B**:Agent 默認高階模型而非 mini/nano 或 Haiku。
**解法**:改 Agent model 欄位為成本較低的快速模型。

### 6.2 OpenAI / Anthropic console 顯示「超過預算上限」
**解法**:
1. 升 `MONTHLY_BUDGET_USD`(.env)
2. 或降使用者 token 上限
3. 或月底前暫時切快速模型 / 另一個 AI 引擎

---

## 7. 整合類

### 7.1 Google Drive MCP 連不上
詳見 `docs/08-MCP-INTEGRATION.md` 第 4 節。

### 7.2 ChatGPT-style 聊天輸入沒有 send 按鈕
**原因**:LibreChat 版本 UI 變更,瀏覽器快取舊版。
**解法**:Ctrl+Shift+R 強制重新整理;或清除瀏覽器快取。

---

## 8. 升級後狀況

### 8.1 升級後某 Agent 消失
**原因**:LibreChat schema 變更,舊 Agent 格式不相容。
**解法**:
```bash
# 重建 Agent
python3 scripts/create-agents.py --only <編號>
# 或從備份還原
```

### 8.2 升級後登入介面樣式跑掉
**原因**:前端 CSS 變更,使用者瀏覽器快取。
**解法**:Ctrl+Shift+R;若仍不行:回退 LibreChat 版本。

---

## 附錄:進一步診斷的快速指令

```bash
# 系統概況
docker compose ps
docker stats --no-stream
df -h
free -h   # macOS 沒有 free,用 vm_stat
vm_stat

# LibreChat 日誌
docker compose logs --tail=100 librechat
docker compose logs --tail=100 mongodb
docker compose logs --tail=100 meilisearch

# 網路
curl -v http://localhost:3080/api/config
nslookup ai.<公司域名>.com

# 備份
ls -la ~/chengfu-backups/daily/ | tail -5

# API 測試
curl https://api.anthropic.com/v1/messages \
    -H "x-api-key: $(security find-generic-password -s 'chengfu-ai-anthropic-key' -w)" \
    -H "anthropic-version: 2023-06-01" \
    -H "content-type: application/json" \
    -d '{"model":"claude-haiku-4-5","max_tokens":30,"messages":[{"role":"user","content":"test"}]}'
```

# LibreChat 升版 Checklist

> 當要從 LibreChat v0.8.4 升到新版(v0.8.5+ / v0.9+)時 · 照這份跑完再動。
> 目的:承富的 Route A + create-agents.py + SSE 串流依賴 LibreChat 內部行為,
>       升版可能 breaking · 這份 checklist 幫你在升版前後雙跑驗證。

---

## 📋 升版前(舊版基準快照)

### 0. 先 dump agents collection(確保 _id 在升版後沒被重建)
```bash
docker exec chengfu-mongo mongodump --db chengfu --collection agents \
    --archive=/tmp/agents-before.archive
docker cp chengfu-mongo:/tmp/agents-before.archive /tmp/
docker exec chengfu-mongo mongosh chengfu --quiet --eval \
    'JSON.stringify(db.agents.find({}, {_id:1, name:1}).toArray(), null, 2)' > /tmp/agents-before.json
cat /tmp/agents-before.json | head -20
```

### 1. 在舊版跑 smoke · 存基準
```bash
./scripts/smoke-librechat.sh > /tmp/smoke-before.log
cat /tmp/smoke-before.log  # 確認全 pass
```

### 2. 在舊版錄一次 SSE payload 供對比
```bash
# 登入取 token
TOKEN=$(curl -s -X POST http://localhost/api/auth/login \
  -H 'Content-Type: application/json' \
  -H 'User-Agent: Mozilla/5.0 Chrome/131' \
  -d '{"email":"sterio068@gmail.com","password":"<pwd>"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

AGENT_ID=$(curl -s http://localhost/api/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H 'User-Agent: Mozilla/5.0 Chrome/131' \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print((d if isinstance(d,list) else d["data"])[0]["id"])')

# 錄 SSE 訊息 (5 秒取樣)
timeout 5 curl -N -X POST http://localhost/api/agents/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'User-Agent: Mozilla/5.0 Chrome/131' \
  -d "{\"agent_id\":\"$AGENT_ID\",\"conversationId\":\"new\",\"parentMessageId\":\"00000000-0000-0000-0000-000000000000\",\"text\":\"一句話介紹你自己\",\"endpoint\":\"agents\",\"messageId\":\"test-$(date +%s)\"}" \
  > /tmp/sse-before.jsonl 2>&1

head -20 /tmp/sse-before.jsonl  # 確認有 data: 事件
```

### 3. 備份 MongoDB
```bash
./scripts/backup.sh
```

---

## 🧪 升版前必須 · sandbox 隔離測試(Round 8 紅線)

> **規則:絕不在 production 直接升版** · 升版必須先在 sandbox 跑完 §5-§6 全套契約測試
> sandbox 與 production **完全不共用** · DB / port / volume 都隔離

### ⚠️ Mac mini 記憶體模式(Round 10 reviewer)

**24GB Mac mini 同時跑 production + sandbox 會爆:**

```
production:  librechat 4GB + mongo 1GB + meili 0.5GB + accounting 0.5GB + nginx 0.2GB = ~6.2GB
sandbox:     librechat 3GB + mongo 0.5GB + meili 0.3GB + accounting 0.3GB + nginx 0.1GB = ~4.2GB
Docker Desktop overhead: ~2GB
macOS + apps: ~8GB
合計: ~20.4GB · 24GB 只剩 3.6GB buffer · swap 頻繁 · Launcher 會卡
```

**升版窗口 3 選 1:**

| 模式 | 何時 | 做法 | 同仁影響 |
|---|---|---|---|
| 🟢 **夜間模式** | 週五 22:00 ~ 週六 02:00 | `docker compose stop librechat` + 啟 sandbox + 測完 down + 再 start production | 週末 4 小時服務中斷 · 事先 Slack 通知 |
| 🟡 **外部機模式** | 任何時段 | 在 Sterio 自己的 Mac / 雲端 VM 跑 sandbox(不占承富 Mac mini) | 承富零影響 · 但 Sterio 要自備機 |
| 🔴 **雙跑模式** | 只做 30 分鐘契約測試 | 接受 swap · 只確認 sandbox 起得來 · 不做負載測 | 升版當下同仁可能卡 30 分鐘 |

**預設:** 夜間模式 · 週五 Slack 通知「週五晚 10 點到六凌晨 2 點維護」
**禁止:** 工作日白天啟 sandbox(除非預先全員停用 AI 半小時)

### 0. 啟動 sandbox(待升版本)
```bash
# 設你想測的 LibreChat 版本(GitHub Releases 看)
export SANDBOX_LIBRECHAT_VERSION=v0.8.5-rc1

# 啟動 sandbox(不影響 production · -p 用獨立 project name)
cd config-templates
docker compose -f docker-compose.sandbox.yml -p chengfu-sandbox up -d
sleep 30
docker compose -f docker-compose.sandbox.yml -p chengfu-sandbox ps
```

**端口對照表(sandbox vs production):**

| 服務 | production port | sandbox port |
|---|---|---|
| nginx | 80 | **8080** |
| accounting | 8000(內網) | **8081** |
| mongo | 27017(內網) | **27018**(對外可 dump) |
| meili | 7700(內網) | 7700(內網不對外) |
| 對外 URL | http://localhost/ | http://localhost:8080/ |

### 1. 跑契約測試指向 sandbox
```bash
# smoke 第一個位置參數就是 BASE URL
./scripts/smoke-librechat.sh http://localhost:8080 > /tmp/smoke-sandbox.log
# 全綠才往下
```

### 2. 跑 LibreChat 契約專屬端點(transactions schema)
```bash
curl -sH "X-User-Email: sterio068@gmail.com" \
     http://localhost:8081/admin/librechat-contract | jq .

# 預期:
# { "transactions_schema_ok": true, ... }
# 若 false · 升版會打破成本核算 · 退回不升
```

### 3. 把舊版 production agents dump 到 sandbox(模擬真實升版)
```bash
# 從 production mongo 撈
docker exec chengfu-mongo mongodump --db chengfu --collection agents \
    --archive 2>/dev/null > /tmp/agents-prod.archive

# 灌進 sandbox mongo(注意 db rename 為 chengfu_sandbox)
docker exec -i chengfu-mongo-sandbox mongorestore \
    --nsFrom 'chengfu.agents' --nsTo 'chengfu_sandbox.agents' \
    --archive --quiet < /tmp/agents-prod.archive

# 驗 agents _id 升版後是否穩定(下面 §5a 同邏輯但對 sandbox)
docker exec chengfu-mongo-sandbox mongosh chengfu_sandbox --quiet --eval \
    'JSON.stringify(db.agents.find({},{_id:1,name:1}).toArray())' > /tmp/agents-sandbox.json
diff /tmp/agents-before.json /tmp/agents-sandbox.json
```

### 4. sandbox 全綠 → 才開始下節真正升版

### 5. sandbox cleanup(測完一定要收 · 否則占 RAM)
```bash
docker compose -f config-templates/docker-compose.sandbox.yml -p chengfu-sandbox down -v
rm -rf config-templates/data-sandbox/
# 確認真的清:
docker ps -a | grep sandbox  # 應該為空
```

---

## 🚀 升版執行(sandbox 全綠才能跑)

### 1. 改 pin 版本
```yaml
# config-templates/docker-compose.yml
librechat:
  image: ghcr.io/danny-avila/librechat:v0.8.5   # ← 改這行
```

### 2. Pull + up
```bash
cd config-templates
docker compose pull librechat
docker compose up -d librechat
sleep 30  # 等 startup
docker logs chengfu-librechat --tail 50
```

### 3. 確認服務 healthy
```bash
docker compose ps
curl -sI http://localhost/api/config  # 應 200
```

---

## ✅ 升版後(逐項驗 · 紅字 fail 就回滾)

### 1. smoke test 再跑
```bash
./scripts/smoke-librechat.sh > /tmp/smoke-after.log
diff /tmp/smoke-before.log /tmp/smoke-after.log
```
**預期:** 僅時間戳 / hostname 差異 · 全 pass。
**若 fail:** 哪條失敗就是 contract 被打破,見下方 troubleshoot。

### 2. uaParser 行為(`create-agents.py` 依賴)
```bash
# 無 User-Agent 應被擋
curl -s -X POST http://localhost/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"x@x.com","password":"xxxxxxxx"}' \
  | grep -q "Illegal request" && echo "✓ 仍靠 UA 擋" || echo "⚠ UA 擋法改變"

# 有瀏覽器 UA 應放行
curl -s -X POST http://localhost/api/auth/login \
  -H 'Content-Type: application/json' \
  -H 'User-Agent: Mozilla/5.0 Chrome/131' \
  -d '{"email":"nobody@x.com","password":"wrongpass"}' \
  | grep -qE "Email does not exist|Incorrect password" && echo "✓ UA 放行" || echo "⚠ UA 策略改變"
```

### 3. Agent 建立 API 仍可用
```bash
# dry-run 確認 payload schema 還相容
python3 scripts/create-agents.py --dry-run --tier core
```
若新版 agentCreateSchema 新增必填欄位,會出現 zod 驗證錯誤。

### 4. SSE 串流格式沒變
```bash
# 錄新版 SSE 與舊版比對
TOKEN=...  # 同上
timeout 5 curl -N -X POST http://localhost/api/agents/chat \
  -H "Authorization: Bearer $TOKEN" \
  ...(同上)... > /tmp/sse-after.jsonl

# 對比 event 類型
grep -o '"type":"[^"]*"' /tmp/sse-before.jsonl | sort -u > /tmp/types-before
grep -o '"type":"[^"]*"' /tmp/sse-after.jsonl | sort -u > /tmp/types-after
diff /tmp/types-before /tmp/types-after
```
**預期:** 一致。
**若不同:** chat.js 的 SSE parser 需更新(見 `modules/chat.js` 的 `_stream()`)。

### 5a. Agent `_id` 穩定性(關鍵 · 若 `modelSpecs` 已 hard-pin id)
```bash
# 升版後再 dump 一次
docker exec chengfu-mongo mongosh chengfu --quiet --eval \
    'JSON.stringify(db.agents.find({}, {_id:1, name:1}).toArray(), null, 2)' > /tmp/agents-after.json
diff /tmp/agents-before.json /tmp/agents-after.json
```
**預期:** 無差異(或僅 field 順序)。
**若 _id 變了:** 所有指向 agent_id 的設定(launcher、modelSpecs、外部 bookmark)都要更新。此時要從 `/tmp/agents-before.archive` 還原舊 _id,或重新 POST create-agents.py 並手動把新 id 寫回設定。

### 5. projectIds 共享機制仍有效
```bash
docker exec chengfu-mongo mongosh chengfu --quiet --eval '
  const i = db.projects.findOne({name:"instance"})._id;
  const n = db.agents.countDocuments({projectIds: i});
  print(`共享 agents: ${n}`);
'
```
**預期:** 非零(應該 = 已建 Agent 總數)。
**若為 0:** LibreChat 可能改變 projectIds 語義,需重新 patch。

### 6. Launcher 端對話功能
手動 smoke:
- [ ] 瀏覽器開 <http://localhost/> · Login 成功
- [ ] 首頁 5 個工作區卡片顯示
- [ ] 按 ⌘1 打開投標助手對話
- [ ] 送一句訊息 · 有 SSE 串流回應
- [ ] 訊息下方 👍 / 👎 按鈕固定顯示
- [ ] 點 ⌘K palette · 可搜 Agent / 專案

---

## 🔴 Troubleshoot · 已知破綻

| 症狀 | 最可能原因 | 處理 |
|---|---|---|
| `/c/new` 不再 302 | nginx `location = /c/new` 被 LibreChat route 覆蓋 | 強制 `location = /c/new` in nginx |
| `create-agents.py` 回 `Illegal request` | uaParser 換了檢查邏輯 | 檢查 `/app/api/server/middleware/` · 更新 UA string |
| SSE event type 改變 (`delta.content` → 別名) | LibreChat SSE schema 升級 | 更新 `modules/chat.js _stream()` switch case |
| Agent POST body reject | `agentCreateSchema` 多必填欄位 | 看 `/app/packages/api/src/agents/validation.ts` · 補欄位 |
| projectIds 無效 | `checkGlobalAgentShare` 改用別 key | 看 `/app/api/server/controllers/agents/*.js` |
| Login 直接跳 `/api/auth/2fa` | 新版強制 2FA | env 加 `ALLOW_2FA_BYPASS` 或建 2FA 流程 |

---

## 📦 回滾流程(若升版後 smoke 大量 fail)

```bash
# 1. 改回舊版 image
sed -i 's|librechat:v0.8.5|librechat:v0.8.4|' config-templates/docker-compose.yml

# 2. Restart
docker compose -f config-templates/docker-compose.yml up -d --force-recreate librechat

# 3. 確認 · 再跑 smoke
./scripts/smoke-librechat.sh

# 4. 還原 MongoDB (若 schema 有改動)
# docker exec chengfu-mongo mongorestore ...
```

---

## 📌 版本決策紀錄

- **v0.8.4 (2026-03-20)** · 目前 pin 版本 · `projectIds` + `uaParser` + `SSE delta.content` 行為已驗
- **v0.8.5-rc1 (2026-04-10)** · pre-release · **不建議交付前追上**
- **v0.8.5 正式版** · 釋出後先在 sandbox 跑 checklist · 確認 pass 再推正式

---

## 🧪 自動化(選配)

CI 可每日跑 smoke 對 production URL,若失敗 PagerDuty/Slack 通知:

```yaml
# .github/workflows/smoke-daily.yml
name: LibreChat contract smoke
on:
  schedule: [{ cron: "0 9 * * *" }]  # 每天 9am UTC
jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ./scripts/smoke-librechat.sh --base ${{ secrets.PROD_URL }}
```

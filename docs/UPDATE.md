# 系統自動更新 SOP(vNext C)

> 承富智慧助理 · 不用 SSH · 在 Web UI 直接更新
> 版本:v1.3 vNext(2026-04-25)

---

## 1 · 設計目標

| 痛點 | 過去做法 | vNext C 做法 |
|---|---|---|
| 想升新版要找 IT | SSH `git pull && ./scripts/start.sh` | Admin 點紅點 → 確認 → 自動完成 |
| 不知有沒有新版 | 忘記了就停在舊版 | 每日 03:00 自動檢查 + 紅點通知 |
| 升級失敗系統壞掉 | 自己手動 git reset | 失敗自動 rollback + audit log |
| 不知道升了什麼 | git log 看 | UI 直接列 commit 標題 |

---

## 2 · 元件總覽

```
┌─────────────────┐  03:00 daily  ┌──────────────────────┐
│ launchd cron    │ ─────────────▶│ check-update.sh      │
│ (.plist)        │               │ → update-status.json │
└─────────────────┘               └─────────┬────────────┘
                                            │
                                            ▼
┌─────────────────┐  GET status  ┌──────────────────────┐
│ Admin browser   │ ◀────────────│ /admin/update/status │
│ update-notifier │              │ (FastAPI)            │
│ → 紅點 + Modal  │              └──────────────────────┘
└────────┬────────┘
         │ POST /admin/update/run
         ▼
┌──────────────────────────────────────┐
│ update.sh(背景跑)                  │
│ 1. fetch · 比對                     │
│ 2. git pull                          │
│ 3. docker compose up -d --build      │
│ 4. health check 30s                  │
│ 5. 失敗 → rollback.sh 自動回滾       │
│ 6. 寫 update-history.jsonl           │
└──────────────────────────────────────┘
```

**4 個檔案 · 1 個 plist · 1 個 backend module · 1 個前端 module**

| 檔案 | 用途 |
|---|---|
| `scripts/update.sh` | 主更新邏輯 · 互動 / `--yes` / `--check-only` / `--json` |
| `scripts/check-update.sh` | 每日 cron · 寫 `reports/update-status.json` |
| `scripts/rollback.sh` | 回滾到指定 sha 或上一版 |
| `config-templates/launchd/tw.chengfu.update-check.plist` | 03:00 launchd cron |
| `backend/accounting/routers/admin/update.py` | 6 個 admin endpoints |
| `frontend/launcher/modules/update-notifier.js` | sidebar 紅點 + admin modal + poll |

---

## 3 · 一般使用流程(Admin)

### 3.1 看到通知

每天早上開啟 launcher · admin 自動看到:

1. **Sidebar 中控按鈕右上**:🔴 紅點(脈動)
2. **桌面 toast**(若該版本第一次見):「🚀 系統有新版可更新(N 個 commit)· 點右上角紅點查看」

### 3.2 確認更新內容

點紅點 → 開更新 modal:

- 顯示**目前 commit** vs **最新 commit**
- 列**前 10 個 commit 標題**(全英文 commit msg 也照顯)
- 預估**1-3 分鐘**(rebuild + restart)
- 警告 **Web UI 期間會斷線約 30 秒**

### 3.3 點「立即更新」

按下後:

1. modal 進入「更新中」狀態 · 按鈕鎖
2. 顯示**即時 log tail**(後端 stream `update.sh` 的 stdout)
3. 容器重啟期間 polling 容錯(短暫 502 不算失敗)
4. 完成 → toast「✅ 更新完成 · 即將重新載入頁面」→ 2.5 秒後自動 reload

### 3.4 失敗

若 health check 沒過(任一容器沒亮、accounting healthz 沒回):

1. **自動 rollback** 到剛才的 commit
2. modal 顯示紅色 ❌「更新失敗:health check 沒過」
3. 系統回到原狀態 · 不影響使用
4. Audit log 寫入失敗紀錄(`/admin/update/history` 看得到)

### 3.5 「下次再說」

按該按鈕 → 該版本被 dismiss · 之後不再彈 toast(badge 仍顯示)。
出新版時自動清 dismiss · 重新彈。

---

## 4 · 安裝

### 4.1 一次性 · 安裝 launchd cron

```bash
cd ~/chengfu-ai  # 或 repo 實際位置
./scripts/install-launchd.sh
```

腳本會自動載入 `tw.chengfu.update-check.plist`(以及其他既有的 plist)。
驗證:

```bash
launchctl list | grep update-check
# → 看到 tw.chengfu.update-check
```

### 4.2 第一次手動跑(不等到 03:00)

```bash
./scripts/check-update.sh
# 看到 ✅ status 寫到 reports/update-status.json
cat reports/update-status.json
```

### 4.3 卸載(若不要)

```bash
launchctl unload ~/Library/LaunchAgents/tw.chengfu.update-check.plist
rm ~/Library/LaunchAgents/tw.chengfu.update-check.plist
```

---

## 5 · CLI 直接用(高階 admin / IT)

| 指令 | 用途 |
|---|---|
| `./scripts/update.sh` | 互動式 · 顯示確認後執行 |
| `./scripts/update.sh --yes` | 跳確認 · 直接更新(腳本用) |
| `./scripts/update.sh --check-only` | 只看有沒新版 · 不更新 |
| `./scripts/update.sh --check-only --json` | machine-readable · 給 backend 用 |
| `./scripts/check-update.sh` | 跑 check-only · 寫 status JSON |
| `./scripts/rollback.sh` | 互動 · 列最近 10 commit · 選一個 |
| `./scripts/rollback.sh --to <sha>` | 直接回到指定 commit |
| `./scripts/rollback.sh --previous` | 回到上次 update 之前的 commit |

---

## 6 · 失敗處理

### 6.1 health check 沒過 · 已自動 rollback

不需處理 · 系統已回到原狀態 · 看 `reports/update-history.jsonl` 留有紀錄。
**通常原因:** 新版 docker image 啟動慢 · 30 秒不夠。

**對策:** 改 `scripts/update.sh` 加長 sleep(目前 30s · 可改 60s):

```bash
# scripts/update.sh:line 154
sleep 30  # ← 改 60
```

### 6.2 health 沒過 · rollback 也失敗

罕見 · 系統處於不穩定狀態。SSH 上 Mac mini:

```bash
cd ~/chengfu-ai
docker compose -f config-templates/docker-compose.yml ps
docker compose -f config-templates/docker-compose.yml logs --tail 50

# 強制回到知道好的 commit
git log --oneline -10  # 找一個好的 sha
git reset --hard <sha>
docker compose -f config-templates/docker-compose.yml up -d --build
```

### 6.3 git pull 失敗(本機有未 commit 改動)

```bash
git status  # 看哪些檔案改了
git stash   # 暫存 · 升級後再 pop
./scripts/update.sh
git stash pop  # 還原
```

### 6.4 多人同時按更新

`update.sh` 自帶 `/tmp/chengfu-update.lock` · 第二個會 exit 3 並回 `{"status":"locked"}`。
前端會接到 409 並顯示「另一個更新正在執行」。

### 6.5 CI 環境誤觸

`update.sh` 沒加 CI guard · 但 `start.sh` 有。Headless CI 不該裝這套 launchd。

---

## 7 · 前端體驗細節

### 7.1 通知頻率

- **每 4 小時**最多 GET 一次 `/admin/update/status`(localStorage 控制)
- **同一版本**若 admin 按過「下次再說」· 不再彈 toast(紅點仍在)
- **新版本**(latest sha 變了)· dismiss 自動失效 · 重新彈

### 7.2 Modal 行為

- 點 modal 外或按 Esc → 關閉(更新中除外 · 鎖)
- 「下次再說」→ dismiss · 關閉
- 「立即更新」→ 鎖住按鈕 · 顯示 log tail · 完成自動 reload

### 7.3 容器重啟期間

更新中 nginx/librechat 會短暫斷線 · 前端 poll 會 retry(每 3 秒 · 5 分鐘 timeout)。
Admin 在 modal 看到的 log tail 來自 task 寫入的檔案 · 不會斷。

---

## 8 · Audit log

每次 update / rollback 寫到:

- `reports/update-history.jsonl`(append · 每行一個 JSON event)
- `db.audit_log`(透過 `/admin/audit-log` 可查)

範例:

```json
{"ts":"2026-04-25T19:30:12Z","action":"update","from":"35657d2","to":"2b0b286","commits":8,"status":"ok"}
{"ts":"2026-04-26T08:15:33Z","action":"rollback","from":"2b0b286","to":"35657d2","reason":"manual","status":"ok"}
```

---

## 9 · 安全考量

| 項目 | 處理 |
|---|---|
| 任何人都能更新? | ❌ 必 admin · `/admin/update/*` 走 `require_admin_dep` |
| 攻擊者改 GitHub 推假 commit? | 透過 git 簽章驗(若 enable);否則 admin 看 commit msg 後再按 |
| Rollback 誤刪? | `confirm_target` 必須 type 一次 · 防 mis-click |
| 同時觸發多次? | `/tmp/chengfu-update.lock` · 第二個拒絕 |
| Path traversal? | task_id 限 hex · 路徑用 pathlib · 不接受 user input 拼接 |
| Subprocess 注入? | `subprocess.run(list)` · 不用 `shell=True` · `--reason` 雖過 cmdline 但不 eval |

---

## 10 · 不在範圍

- **跨機器更新**:單台 Mac mini · 不需 staged rollout
- **Atomic blue/green**:單機就重啟 · 沒 traffic shift
- **DB migration 自動化**:改 schema 仍需手動跑 migration · 寫在 release notes
- **API key 變更通知**:若 env 變數新增 · update.sh 不會提示 · 看 release notes

---

## 11 · 後續優化(v1.4+)

- [ ] Slack / LINE 通知 admin 有新版(目前只 UI)
- [ ] DB migration 自動偵測 + 跑(目前 schema 變更需手動)
- [ ] 「Beta channel」· 訂閱 main vs release tag(目前只追 main)
- [ ] Dry-run 模式 · 看新版會做什麼但不真做(目前 git pull 已是 atomic)

# 交付前 1 週 Checklist

> **背景:** 系統程式碼已到位(UI 95% · RBAC/測試/smoke/handbook 齊)。
> **問題:** 部署、真實資料、訓練、ROI 量測未落地 = **交付當天一切皆為 0**。
> **這份是 Sterio 帶去承富辦公室那週,每天早上打開逐項打勾的。**

---

## Day -7(交付前 1 週 · 週一)· 硬體 + 網路

- [ ] 確認 Mac mini M4 24GB 已到貨並開機
- [ ] FileVault 全盤加密 **開**
- [ ] **MongoDB 邊界檢查**(Round 6 reviewer 提醒)·
      `docker-compose.yml` 確認 mongo service 沒對 host expose 27017 port
      (`ports:` 段不該有 `"27017:27017"`)· 只能 docker network 內互通
- [ ] UPS 接上 · 拔電實測 5 分鐘還活著
- [ ] Mac mini 網路:設固定 IP 或靜態 DHCP
- [ ] `承富-ai.local` mDNS 能從 10 台同仁機 ping 通
- [ ] Apple ID 登入 · TimeMachine 接外接 USB(Mac mini 本機備份第一層)
- [ ] 安裝 Docker Desktop · 登入 · 測 `docker run hello-world`
- [ ] clone repo:`git clone https://github.com/Sterio068/company-ai-workspace.git /Users/<admin>/Workspace/ChengFu`

---

## Day -6(週二)· 機敏 + 啟動

- [ ] `./scripts/setup-keychain.sh` · 寫入 ANTHROPIC_API_KEY / JWT secrets / Meili key
- [ ] `./scripts/start.sh` · 6 容器全起 · <http://localhost/> 200
- [ ] `./scripts/smoke-librechat.sh` · 11 pass
- [ ] 登入頁能看到 · 首次註冊老闆 admin 帳號
- [ ] `python3 scripts/create-agents.py --tier core` · 10 助手建好
- [ ] Mongo 手動確認 `db.agents.count() == 10 && 全部 projectIds 含 instance._id`
- [ ] Launcher 首頁能 ⌘1 開投標、⌘3 開設計 · onboarding 3 步走完

---

## Day -5(週三)· 真實資料灌入(最關鍵)

這一步做不好,系統交付 = 空殼。

- [ ] Sterio 或 Champion 從承富 NAS 撈 5-10 份代表性檔案複製到 `knowledge-base/samples/`:
  - 2 份過往得標建議書(dOCX)
  - 1 份近期結案報告
  - 1 份新聞稿範例
  - 1 份廠商比價信範例
  - 1 份招標須知 PDF(承富曾判過的)
- [ ] `python3 scripts/upload-knowledge-base.py` · 灌進 LibreChat file_search
- [ ] 測試:對知識庫助手問「我們做過什麼 XX 類案子?」· 應能引用上述檔案
- [ ] 承富完成 `docs/NAS-INTEGRATION-SPEC.md` 的 5 個前置問題回答(即便先不 NAS 接,有答案才能排 v1.1)

---

## Day -4(週四)· 使用者帳號 + 密碼 reset SOP

- [ ] 收集 10 同仁 email + 姓名 + role (ADMIN 或 USER)
- [ ] `python3 scripts/create-users.py` · 建 10 帳號 · 每人一次性初始密碼
- [ ] 印 10 張「帳號 + 臨時密碼」紙條 · 教育訓練當天發

### 密碼紙條銷毀 SOP(Round 5 reviewer 提醒 · 紙本機敏)
- [ ] 紙條由 **Sterio 持有**(不是 Champion · 避免 Champion 同時知 10 人密碼)
- [ ] 教育訓練當天 · **見證下發放** · 同仁簽收
- [ ] 同仁第一次登入後 **強制改密碼**(LibreChat 設定:首次登入導 /change-password)
- [ ] 教育訓練結束 30 分鐘內 · 老闆面前 **碎紙機銷毀紙條**
- [ ] 碎紙照片 + 簽收名單存 `docs/PASSWORD-DISTRIBUTION-LOG-<日期>.md`(僅 admin 可讀)
- [ ] 之後密碼遺失 → 走下方密碼 reset SOP

- [ ] 寫 `docs/PASSWORD-RESET-SOP.md`:
  ```
  同仁忘記密碼的 SOP:
  1. LINE 敲 Champion
  2. Champion 登入 MongoDB · 找同仁 user document
  3. 設 `user.emailVerified = true`,清 `password` field
  4. 該同仁重走 /forgot-password 流程 · 系統 email 重設連結
  5. 或 Champion 用 Admin 面板「重設使用者密碼」功能(v1.1 再做 UI · 現階段手動)
  ```
- [ ] 如要走 email 重設 · .env 加 SMTP 設定 · 實測能收得到信

---

## Day -3(週五)· 對外 Cloudflare Tunnel

- [ ] `docs/04-OPERATIONS.md` 的 Cloudflare Tunnel 流程實跑一遍
- [ ] `cloudflared` 建 tunnel · 取得 UUID
- [ ] 加進 `config-templates/docker-compose.yml` 或 host systemd
- [ ] Cloudflare Access · 新增 Email allowlist policy + 2FA
- [ ] 10 同仁 email 全加入 allowlist
- [ ] 測試:手機 4G 上(不連公司 wifi)`https://ai.<承富domain>.com` → 能跳 Access 認證 → 進系統

---

## Day -2(週六 · 可選)· 異機備份 + ROI baseline

- [ ] `brew install rclone gnupg`
- [ ] `gpg --full-generate-key`(name `chengfu`)
- [ ] 註冊 Backblaze B2 免費方案 · `rclone config` 設定 `chengfu-offsite`
- [ ] `./scripts/backup.sh` 跑一次 · 確認 B2 有檔
- [ ] `rclone copy chengfu-offsite:chengfu-backup/daily/xxx.gpg /tmp/` + `gpg --decrypt` 能還原
- [ ] launchd plist 設定每日 02:00 `backup.sh`(`~/Library/LaunchAgents/com.chengfu.backup.plist`)
- [ ] 寫 `docs/BASELINE.md` T0 快照:過去 6 個月月均投標件數 / 得標率 / 各類任務平均耗時(Sterio 跟老闆 Champion 座談 30 分鐘問出來)

---

## Day -1(週日)· 教育訓練前置

- [ ] 印 A3 海報:`docs/DATA-CLASSIFICATION-POSTER.md` 貼承富辦公室
- [ ] 印 1 頁小抄(從 `docs/QUICKSTART.md` 濃縮 · A4 正反面)· 10 份
- [ ] 印 10 張「帳號 + 密碼」紙條
- [ ] Champion 跟 Sterio 一起實際跑一遍 `docs/CASES/01-海廢案端到端.md` 全流程(2 小時)· Champion 隔天就能上台示範
- [ ] 準備 1 個真實承富當週案例當教學情境(例如某標案剛看到)

---

## Day 0(交付當天)· 教育訓練 + 驗收

> **策略原則(外部 reviewer v4.4 + v4.6 建議):**
> 1. 先讓登入 100% 成功(Round 6 提醒最容易卡的第一分鐘)
> 2. 才讓每個同仁完成 **自己角色的 first-win 任務**
> 3. 最後才講介面與快捷鍵
> 5 分鐘內有感 · 抗拒會小很多。

### 上午 Part 0(15 分鐘)· **登入成功率 100% 專門站**

> Round 6 reviewer 紅線:Day 0 最可能卡住的不是首頁,是**登入**。
> 若 Cloudflare Access、初始密碼、首次改密碼任一步不順 · 10 人會在第一分鐘集體停住。

- [ ] 排 1 桌「登入服務台」· Champion 在那裡 · 紙條按順序發
- [ ] 每位同仁登入步驟:
  1. 打開瀏覽器 → 輸入網址 → Cloudflare Access 認證(Email + 2FA)
  2. LibreChat login 頁 → email + 紙條臨時密碼
  3. 強制改密碼(8 字以上 · 不可用紙條那組)
  4. 看到首頁 onboarding 跳出 → 暫停先做下一步
- [ ] **任一步驟卡住 = 服務台立刻幫處理** · 不放任同仁自己摸
- [ ] 所有 10 人都進首頁了 · 才進 Part A(若 9/10 過 · 卡的那位先協助)

### 上午 Part A(30 分鐘)· 各自 first-win(不講 UI)

- [ ] **直接分派當週真實任務** · 每個人先做自己角色 1 件事:
  - 🎨 **設計師:** 產 1 份當週客戶的「設計 Brief + 3 方向」→ 截圖存證
  - 🎯 **PM:** 貼當週一個真實招標須知 → 產「Go/No-Go 評分」→ 截圖存證
  - 📢 **業務:** 當週需要聯繫的廠商 → 產 1 封比價信 → 截圖存證
  - 📝 **公關寫手:** 當週要發的新聞稿主題 → 產 400 字初稿 → 截圖存證
- [ ] 每人完成 first-win 後 · 截圖貼 LINE 群「承富 AI 互助」· 全組看到彼此成功
- [ ] Champion 現場解卡 · 不解釋 UI、只解為什麼 AI 那樣回

### 上午 Part B(90 分鐘)· 才開始講 UI

- [ ] Sterio 示範:Launcher 結構 + ⌘K palette + onboarding 3 步(15 分鐘)
- [ ] Champion 示範:海廢案端到端 walk-through(15 分鐘精簡版)
- [ ] 現場 Q&A(60 分鐘)· 收集前 10 個問題 · 當天印成 `docs/CASES/FAQ-Day1.md`

### 下午(1.5 小時)· 進階分層

- [ ] PM 組:專案管理 + 跨助手接力 + Admin 面板(Champion 帶)
- [ ] 設計組:設計 Brief + 多渠道適配(Champion 帶)
- [ ] 業務組:標案監測 + CRM Kanban + LINE 貼上清理(Champion 帶)

### 結尾 30 分鐘 · 驗收(硬條件)

- [ ] **Adoption 驗收:** 10 人登入成功 + **至少 7 人完成 first-win 並截圖**(不是只有登入)
- [ ] **角色 first-win 清單:** 設計師 ≥ 1 人、PM ≥ 2 人、業務 ≥ 1 人完成 · 否則暫緩簽收
- [ ] 老闆簽 `docs/ACCEPTANCE.md` 驗收書
- [ ] 拍合照 · LINE 群組公告「承富 AI 正式上線」
- [ ] 留 Sterio 聯絡方式 + 值班 SLA
- [ ] 當場印 `docs/CASES/FAQ-Day1.md` 給 Champion 作為 Day 1 FAQ Top 10 話術卡

---

## Day +1 到 Day +7(交付後第一週)· 觀察

- [ ] 每天早上看 Admin 面板:用量 / 滿意度 / 標案漏斗
- [ ] 每天 LINE 群「承富 AI 互助」確認沒卡在單一問題
- [ ] Week 1 結束彙整:
  - 👍/👎 比率最低的助手是哪幾個?
  - 被問最多的 3 個問題是?(寫進下版 handbook FAQ)
  - 月費用戶實際使用時數 vs baseline

---

## Day +30 / 月度巡檢(交付後常態化)

### 每月第一個工作日 · 由 Champion 跑

- [ ] **備份 restore dry-run** · 證明備份可還原
  ```bash
  # 1. 從異機抓最新備份
  rclone copy chengfu-offsite:chengfu-backup/daily/$(rclone lsf chengfu-offsite:chengfu-backup/daily/ | sort | tail -1) /tmp/

  # 2. GPG 解密
  gpg --decrypt /tmp/chengfu-*.archive.gpg > /tmp/restore.archive

  # 3. Restore 到暫存 DB(不動 production)
  docker exec -i chengfu-mongo mongorestore --archive --db chengfu_test_restore < /tmp/restore.archive

  # 4. 驗:user count > 0 / agents count = 10 / projects count >= 1
  docker exec chengfu-mongo mongosh chengfu_test_restore --quiet --eval '
    print("users:", db.users.countDocuments());
    print("agents:", db.agents.countDocuments());
    print("projects:", db.projects.countDocuments());
  '

  # 5. 清暫存 DB
  docker exec chengfu-mongo mongosh --eval 'db.getSiblingDB("chengfu_test_restore").dropDatabase()'
  ```
- [ ] 結果寫進 `reports/restore-drill-<YYYY-MM>.md`(時間 + 備份檔名 + counts + pass/fail)
- [ ] 連續 3 個月 fail · 觸發**異機備份方案重新評估**

### 同月內 · 也要做的事
- [ ] 看 `/admin/budget-status` · 月底實際花費 vs 預算 · 寫進月報
- [ ] 看 `/admin/top-users` · 異常高用量同仁 → Champion 私訊了解狀況
- [ ] 看 `/admin/tender-funnel` · 漏斗轉換率 vs 上月 vs T0 baseline
- [ ] 整理本月新 FAQ 進 `docs/CASES/FAQ-Day1.md` 持續滾動更新

---

## 交付後才開始的 P1(v1.1 · 2 週後)

- [ ] NAS 接入(承富 SPEC 5 問回答完成後)
- [ ] LINE 貼上偵測(方案 C · 2-3h 小改)
- [ ] 串 Fal.ai Recraft v3(設計夥伴真生圖)
- [ ] 附件 PDF 真接檔案(投標顧問省 70% 複製貼上)
- [ ] 月度 skill 建議審核流程 · Champion + 老闆週報

---

## 風險中止觸發器(任一命中 · 停下來與老闆討論)

- ⛔ Day -5 真實資料灌不進去(結構不對)→ 系統交付後「查知識」必空手,**不可交付**
- ⛔ Day -4 帳號重設 SOP 無法跑通 → 同仁忘密碼 = 打不開系統,**不可交付**
- ⛔ Day -3 Cloudflare Tunnel 無法穩定 → 同仁遠距無法用,**降級為只內網使用**
- ⛔ Day 0 現場 2-3 位同仁當場表達抗拒拒用 → 暫緩驗收簽收,**改為 2 週觀察期後再簽**

---

**這份 checklist 每一項都是可執行動作,Sterio 應該逐日跟 Champion + 老闆確認打勾。**

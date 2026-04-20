# Week 1 — 硬體與環境建置

> **目標**:第 7 日結束時,Mac mini 已就位、UPS 接妥、Docker 就緒、Cloudflare Tunnel 可連線。
> **前置**:承富已完成硬體採購(Mac mini M4 + UPS),收到貨。

---

## Day 1-2:硬體開箱與物理環境

### 任務 1.1:Mac mini 開箱驗收
- [ ] 確認型號為 Apple Silicon M4(不是 Intel)
- [ ] 確認規格:10-core CPU / 16GB / 512GB
- [ ] 記下序號與購買日期(保固追蹤用)
- [ ] 開機首次設定:
  - [ ] 選擇「僅在這台 Mac 使用」(不要同步 iCloud)
  - [ ] 建立管理員帳號 `steadmin`(強密碼)
  - [ ] 跳過所有 Apple ID 登入要求(工作用不需要)
  - [ ] 時區設為台北
- [ ] **FileVault 開啟**:系統偏好 → 隱私與安全 → FileVault → 啟用
  - [ ] 復原金鑰必須記錄在 1Password 或 Keychain,交給承富老闆一份紙本封存
- [ ] 防火牆開啟:僅允許簽署的應用、接受進入的連線選擇性

### 任務 1.2:UPS 安裝
- [ ] 將 Mac mini 電源接至 UPS 的「Battery Backup」插孔(不是只有 Surge 防突波)
- [ ] 網路設備(路由器、switch)也接 UPS(若 UPS 容量允許)
- [ ] 連接 UPS USB 到 Mac mini
- [ ] 系統偏好 → 電池 → UPS → 設定「電池剩 10% 時自動安全關機」
- [ ] 拔牆插測試:Mac mini 應維持運作,UPS 警告音響起

### 任務 1.3:擺放位置
- [ ] 擺放在**通風良好**的位置(不要塞櫃子深處)
- [ ] 遠離窗邊日曬、潮濕區域
- [ ] 網路線接**有線乙太網路**(不要 Wi-Fi 當主連線)
- [ ] 鍵盤/滑鼠可連接以備直接操作(建議留在機器旁)

### 任務 1.4:macOS 系統更新
- [ ] 系統偏好 → 一般 → 軟體更新 → 檢查並安裝所有更新
- [ ] 系統偏好 → 一般 → 軟體更新 → 「自動保持 Mac 最新」:開
- [ ] 確認系統版本 macOS 15+(Sequoia 或更新)

---

## Day 3:網路設定

### 任務 1.5:取得固定內網 IP
- [ ] 聯絡承富網管(或自行登入 router),為 Mac mini 的 MAC address 綁定固定 IP
- [ ] 例:`192.168.1.50`
- [ ] 記錄於 `docs/DECISIONS.md`

### 任務 1.6:設定主機名
```bash
sudo scutil --set HostName 承富-ai
sudo scutil --set LocalHostName 承富-ai
sudo scutil --set ComputerName 承富-ai
dscacheutil -flushcache
```
- [ ] 測試:從另一台電腦 `ping 承富-ai.local` 應能解析

### 任務 1.7:開啟 SSH(遠端管理用)
- [ ] 系統偏好 → 一般 → 共享 → 遠端登入:開啟,僅管理員
- [ ] 測試:從 Sterio 自己的電腦 `ssh steadmin@承富-ai.local`

---

## Day 4:開發環境安裝

### 任務 1.8:安裝 Homebrew
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
- [ ] 確認:`brew --version` 應顯示 4.x
- [ ] 加入 PATH(按安裝完成提示操作)

### 任務 1.9:安裝 Docker Desktop
- [ ] 下載:https://www.docker.com/products/docker-desktop
- [ ] 選擇 Apple Silicon 版本
- [ ] 安裝後首次啟動,勾選「開機自啟」
- [ ] 設定 Resources:
  - [ ] CPU:4 cores(Mac mini 有 10 core,留 6 core 給系統)
  - [ ] Memory:8 GB(16GB 機器留 8GB 給系統)
  - [ ] Swap:2 GB
  - [ ] Disk image size:64 GB(SSD 512GB,留足夠空間)
- [ ] 測試:`docker run --rm hello-world` 應顯示成功訊息

### 任務 1.10:安裝必要工具
```bash
brew install git curl wget jq cloudflared node@20 python@3.12
brew install --cask visual-studio-code
```

### 任務 1.11:建立專案資料夾
```bash
mkdir -p ~/chengfu-ai
cd ~/chengfu-ai
git init
git remote add origin [待 Sterio 提供 private repo URL]
```

---

## Day 5-6:Cloudflare Tunnel 設定

### 任務 1.12:Cloudflare 帳號準備
- [ ] 確認承富有 Cloudflare 帳號,且域名 `<承富domain>.com` 已 DNS 託管至 Cloudflare
- [ ] 若無域名,Sterio 協助承富註冊(建議 `.com` 或 `.com.tw`)

### 任務 1.13:建立 Tunnel
```bash
cloudflared login        # 瀏覽器認證
cloudflared tunnel create chengfu-ai
# 會產出 <TUNNEL_ID>.json 在 ~/.cloudflared/
```
- [ ] 記下 `<TUNNEL_ID>`

### 任務 1.14:設定 Tunnel config
建立 `~/.cloudflared/config.yml`:
```yaml
tunnel: <TUNNEL_ID>
credentials-file: /Users/steadmin/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: ai.<承富domain>.com
    service: http://localhost:3080
  - service: http_status:404
```

- [ ] 設定 DNS 紀錄:
```bash
cloudflared tunnel route dns chengfu-ai ai.<承富domain>.com
```

### 任務 1.15:啟動 Tunnel(先手動測試)
```bash
cloudflared tunnel run chengfu-ai
```
- [ ] 瀏覽器打開 `https://ai.<承富domain>.com` → 應該看到 404(因為 LibreChat 尚未部署)
- [ ] 若能連到 404 就表示 tunnel 本身通了

### 任務 1.16:設定 Tunnel 開機自啟
```bash
sudo cloudflared service install
```
- [ ] 測試:`launchctl list | grep cloudflared` 應顯示服務運行中

### 任務 1.17:設定 Cloudflare Access(雙重保護)
- [ ] 登入 Cloudflare dashboard
- [ ] Zero Trust → Access → Applications → Add application
- [ ] Self-hosted,subdomain = `ai`,domain = 承富domain
- [ ] 新增 Access Policy:
  - [ ] Name:承富同仁白名單
  - [ ] Action:Allow
  - [ ] Include → Emails → 暫時先加 Sterio 自己的 email,之後再加 10 個同仁
- [ ] 儲存 Policy,測試:非白名單 email 連 `https://ai.<承富domain>.com` 應被擋下

---

## Day 7:驗收與週報

### 任務 1.18:本週驗收項
- [ ] Mac mini 穩定運行 48 小時無重啟
- [ ] 測試拔插 UPS,確認 Mac mini 不掉電
- [ ] `docker ps` 命令可執行(Docker Desktop 運作中)
- [ ] `cloudflared tunnel list` 可見 `chengfu-ai` 狀態為 healthy
- [ ] `https://ai.<承富domain>.com` 可連(目前是 404 正常)
- [ ] `http://承富-ai.local:3080` 從公司內網可 ping 到

### 任務 1.19:產出週報
在 `reports/week-1.md` 建立報告,格式:
```markdown
# Week 1 週報

## 已完成
- [x] ...

## 未完成或需協助
- [ ] ...(說明原因)

## 下週預計
- Week 2 — 平台部署

## 需承富配合
- [ ] ...(例如:需要網管提供固定 IP)
```

- [ ] 寄給 Sterio
- [ ] 寄給承富老闆(精簡版,去除技術細節)

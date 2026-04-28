# 🌐 同仁連線方式 · 內網 + 遠端

> 給管理員 / 同仁兩種角色 · 看完知道怎麼接到系統

---

## 一、辦公室內網(現在就能用)

### 同仁端

打開瀏覽器(Chrome / Safari),輸入老闆給你的網址登入。

> ⚠ **網址會因公司網段 / Mac mini IP 變動** · 不要硬抄此頁範例
> 老闆會在中控 → 同仁連線網址,點「複製」貼給你

可能形式:

| 形式 | 範例 | 適用 |
|---|---|---|
| LAN IP | `http://192.168.X.X/` | 公司 Wi-Fi / 有線同網段 |
| mDNS | `http://<電腦名>.local/` | 同網段 macOS / iPhone(自動解析) |
| 遠端域名 | `https://ai.<公司域名>.com/` | 在家 / 出差 (要先設 Cloudflare Tunnel · 見第二節) |

---

### 管理員端 · 把網址貼給同仁

1. 中控(⌘M)→ 最上方「🔗 同仁連線網址」卡片
2. 點任一行的「**複製**」按鈕 → 貼到 LINE / Slack / Email
3. 同仁開連結即可登入

---

## 二、遠端(在家 / 出差)

> 預設**未啟用** · 需管理員額外設定 Cloudflare Tunnel(約 30 分鐘)

### 設定步驟

#### 前置

- 公司有一級網域(例如 `chengfu.com.tw`)
- Cloudflare 帳號(免費版可用)+ 域名已加入 Cloudflare DNS

#### 安裝 cloudflared

```bash
brew install cloudflared
cloudflared --version  # 確認可用
```

#### 建立 Tunnel

```bash
# 1. 登入 Cloudflare(會開瀏覽器)
cloudflared tunnel login

# 2. 建立 tunnel
cloudflared tunnel create chengfu-ai

# 3. 設 DNS · 把 ai.<公司域名>.com 指到此 tunnel
cloudflared tunnel route dns chengfu-ai ai.<公司域名>.com

# 4. 寫設定檔
cat > ~/.cloudflared/config.yml <<EOF
tunnel: chengfu-ai
credentials-file: /Users/$USER/.cloudflared/<tunnel-UUID>.json
ingress:
  - hostname: ai.<公司域名>.com
    service: http://localhost:80
  - service: http_status:404
EOF

# 5. 註冊為開機自動跑的服務
sudo cloudflared service install
```

#### 加 Access Policy(2FA + Email 白名單)

到 Cloudflare Zero Trust → Access → Applications:

1. **Add an application** → Self-hosted
2. **Domain**:`ai.<公司域名>.com`
3. **Policies → Add policy**
   - Action:Allow
   - Rules:**Emails** → 填同仁 email(逗號分隔)
4. **Settings → Authentication** → 開 **One-Time PIN**(同仁登入時輸入 email,Cloudflare 寄 6 位數驗證碼,PIN 碼通過才見系統)

#### 重啟 + 確認

```bash
./scripts/start.sh                  # 系統重啟
launchctl list | grep cloudflared   # 確認 tunnel 跑了
curl https://ai.<公司域名>.com/healthz  # 應回 ok
```

設定完同仁可從家裡 / 行動網路開 `https://ai.<公司域名>.com` 登入。

---

### 同仁端 · 從家連回辦公室

1. 開瀏覽器到 `https://ai.<公司域名>.com`
2. Cloudflare 會跳 email 輸入頁 → 輸公司 email → 收驗證碼 → 通過
3. 進到 LibreChat 登入頁 → email + 密碼 登入
4. 看到 launcher 首頁 = 連線成功

---

## 三、帳號 / 密碼

| 流程 | 由誰 |
|---|---|
| 建立同仁帳號 | **老闆** 在 admin 中控 → 同仁管理 → 建新同仁 |
| 提供初始密碼 | **老闆** 看到一次密碼後複製給同仁(LINE / 當面)|
| 修改密碼 | **同仁** 自行登入後 → 右上角頭像 → 個人設定 → 改密碼 |
| 忘記密碼 | 同仁找老闆 → 老闆從同仁管理 → 編輯 → 🔑 重設密碼 |
| 離職刪帳號 | 老闆 → 同仁管理 → 停用 → 確認 → 永久刪除(二段式)|

詳見 [📇 同仁帳號管理流程](#help-doc-account-management)

---

## 四、手機行動裝置

### iPhone / iPad

詳見 [📱 iPhone 完整設定指南](#help-doc-mobile-ios)

簡述:
1. Safari 開系統網址 → 登入
2. 分享 → 加到主畫面 → 變成「半個 app」(PWA)
3. 場勘拍照 / 麥克風(會議速記)需給權限

### Android

Chrome 開系統網址 → 選單 → **加到主畫面**(用法相同)

---

## 五、常見問題

### Q1 · 「網址打不開」

1. 確認在公司網段:`192.168.88.x` 或 `192.168.50.x`
2. 試 `http://<電腦名>.local/`(mDNS · 不依 IP · 電腦名請問老闆)
3. 仍無法 → LINE 老闆 / IT 看 Mac mini 是否開機

### Q2 · 「在家連不到」

1. 你是否被加入 Cloudflare Access 白名單?(向老闆確認)
2. 內網 IP `192.168.88.x` **在家無法用** · 必須用 `https://ai.<公司域名>.com`
3. 若沒有 tunnel · 同仁無法在家用 · 請等老闆設定

### Q3 · 「Cloudflare 一直要我輸入 email」

是 Access Policy 強制 · 為公司資安。每 24 小時會自動續期一次。

### Q4 · 「我密碼忘了」

到老闆那要重設 · 不是公司的工程師能直接幫你改(資安規定)。

---

## 看完還可以再看

- [📇 同仁帳號管理(老闆 only)](#help-doc-account-management)
- [📱 iPhone 完整設定指南](#help-doc-mobile-ios)
- [🚨 錯誤訊息對照表](#help-doc-error-codes)

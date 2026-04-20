# docs/10-STREAMING-VERIFY.md — Streaming + nginx 相容性驗證

> **問題**:承富架構 `nginx → LibreChat` 用 `sub_filter` 注入客製 CSS/JS。
> 但 `sub_filter` 需要緩衝完整 response · 可能破壞 LibreChat 的 SSE 串流回應。
>
> 若使用者看到 Claude 回應是「一次全出」而非逐字,表示串流壞了。

---

## 症狀判斷

### ✅ 正常(串流有效)
- 對話送出後,Claude 回應**逐字**出現(像打字機)
- 能看到「Claude 正在輸入…」的 indicator
- Chrome DevTools Network → 該 request 是 `EventStream` type

### ❌ 異常(串流被緩衝)
- 送出後 10-30 秒沒反應 → 然後整段文字**一次全出現**
- Chrome DevTools Network → 該 request 是 `fetch` type,無 streaming
- CPU / 網路監控看不到持續的 packet

---

## 驗證步驟

### 1. 瀏覽器 DevTools 觀察
1. 打開 Chrome DevTools → Network tab
2. 打開承富 AI,進任何對話
3. 送一個訊息「寫一首 100 字關於台灣的詩」
4. 看 Network 有無 `/api/ask/agents` 或類似 endpoint
5. 點該 request → 看 `Response` 欄是否**逐漸增長**

### 2. curl 直接測(繞過 nginx)
```bash
# 直接打 LibreChat 容器內部(port 3080)
docker exec -it chengfu-librechat \
    curl -N -H "Authorization: Bearer <JWT>" \
         http://localhost:3080/api/ask/agents \
         -d '{"text":"寫一首詩","agent_id":"..."}'
# 預期:文字逐字流出(不是等完才印)
```

### 3. curl 透過 nginx
```bash
curl -N http://localhost/api/ask/agents \
     -H "Cookie: <session>" \
     -d '{"text":"寫一首詩","agent_id":"..."}'
# 比對兩者 · 若 nginx 版「一次全出」→ sub_filter 擋了
```

---

## 若串流壞掉 · 修復方式

### Option A(推薦)· `/chat/*` 停用 sub_filter

修 `frontend/nginx/default.conf`,在 `/chat` 位置**移除 sub_filter**:

```nginx
location /chat {
    # 移除這兩行 · 不注入到 chat 頁
    # sub_filter '</head>' '<link ...>';
    # sub_filter '</body>' '<script ...>';

    proxy_pass http://librechat:3080;
    include /etc/nginx/chengfu-proxy.conf;

    # 串流必要
    proxy_buffering off;
    proxy_request_buffering off;
    proxy_http_version 1.1;
    chunked_transfer_encoding on;
}
```

但這樣 LibreChat 頁面就不會有承富客製 CSS/JS 了。解法:

### Option B · 把客製 CSS/JS 注入到 LibreChat 自身

用 LibreChat 的 `customCSS` / `customJS` 配置(librechat.yaml):
```yaml
interface:
  customCSS: "/chengfu-custom/librechat-custom.css"
  customJS: "/chengfu-custom/librechat-relabel.js"
```

nginx 照樣代理 `/chengfu-custom/`,但不再 sub_filter 注入 · 串流不受影響。

### Option C · 只對特定 path sub_filter

```nginx
# SSE endpoints 不注入
location ~ ^/(api/ask|api/messages)/ {
    proxy_pass http://librechat:3080;
    proxy_buffering off;
    proxy_request_buffering off;
    # 無 sub_filter
}

# 靜態 HTML 頁才注入
location /chat {
    proxy_pass http://librechat:3080;
    sub_filter '</head>' '...';
}
```

---

## 我的建議(生產環境)

**用 Option B(LibreChat customCSS/customJS)**:
- 完全不靠 nginx sub_filter
- 串流 100% 正常
- LibreChat 官方支援的方式
- 升級版本不易壞

我會在後續實測後,若確認串流有問題,改走 Option B 並更新 nginx config。

---

## 相關 nginx 關鍵參數

```nginx
proxy_buffering off;           # 關 nginx 緩衝(SSE 必須)
proxy_request_buffering off;   # 關請求緩衝
proxy_http_version 1.1;        # HTTP/1.1 支援 chunked + keep-alive
proxy_set_header Connection ""; # 清 Connection 讓 keepalive 生效
proxy_read_timeout 3600s;      # 長回應(Opus 深度思考可能 5+ 分鐘)
chunked_transfer_encoding on;  # chunked response
```

---

## 若遇到這個問題怎麼辦(Runbook)

1. 跑「驗證步驟 1」確認是否壞
2. 若壞:改 `frontend/nginx/default.conf`,對 `/api/ask/*` 位置移除 sub_filter
3. 重啟 nginx:`docker restart chengfu-nginx`
4. 重測
5. 若需保留客製 CSS/JS,改用 LibreChat customCSS/customJS 配置
6. 寫入 `reports/incident-YYYY-MM-DD.md`

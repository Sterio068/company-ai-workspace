# 未掛載的 scaffold(2026-04-21 歸檔)

這些檔案是 v1.0 初期規劃要做「FastAPI 多 router 拆分 + 獨立 auth/rate_limit 中介」的雛形,但實際實作走了另一條路:

## 目前真相
- `../main.py` 是**唯一** FastAPI app 定義
- auth 邏輯內嵌在 `main.py` 的 `require_admin` / `current_user_email` dependency
- errors / rate_limit 暫不做 · 需要時在 main.py 新增

## 為什麼不用這些?
- 10 人封閉環境 · router 拆分反而增加維護成本
- `main.py` 1300+ 行是多,但可讀性 OK 且外包 Claude Code 能跟上
- JWT 中介與 LibreChat 本身的 auth 有 semantics 重疊 · 選 `X-User-Email` header 由 launcher 注入更簡單

## 若未來要啟用(v1.2+)
- 先決定 `main.py` 拆哪幾個 router 最有 CP 值(建議:crm / tenders / accounting 分 3 個)
- 把這資料夾裡對應檔 copy 回上層,補 `app.include_router(...)`
- pytest 確認全通 · 不然不要合併

## 紀錄
- 外部 reviewer v4.4 指出「main.py + routers/ + auth.py 三套並存會讓下個接手者修錯檔」
- 2026-04-21 決策:歸檔,維持 main.py 單一真相

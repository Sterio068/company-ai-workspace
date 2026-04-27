# 多代理整體性審查 · v1.56 → v1.57

**日期**:2026-04-27
**審查範圍**:架構 / 安全 / 效能 / a11y · 4 代理並行
**結果**:識別 25 項議題 · 本次修 7 項 P0 · 18 項列入 v1.6 / v2.0 路徑

---

## 🔴 已修(7 項 P0 · 本次 v1.57 內完成)

### 安全(2 項)
| ID | 嚴重度 | 修補 |
|---|---|---|
| **SSRF in vision.py** | 🔴 CRITICAL | Pydantic `field_validator` 強制 https · 禁內部 host(`accounting`/`librechat`/`mongodb`/...)· 禁私有 IP / loopback / metadata IP(169.254.x · 127.x · 10.x · 172.16-31.x · 192.168.x)· data: URL 限 image/{png,jpg,webp,gif} + 5MB |
| **Prompt injection via image** | 🟠 HIGH | `_INJECTION_GUARD` 安全守則 system prompt · `_redact_secrets()` 遞迴掃 OpenAI/Anthropic/ECC token / Google API / Bearer 模式 · 三 endpoint 全套用 |
| **Workflow internal:cron 繞 quota** | 🟠 HIGH | `run_preset_workflow` 加 `user_email.startswith("internal:")` raise 403 · cron token 不能觸發 multi-agent workflow |

### 效能(2 項)
| ID | 影響 | 修補 |
|---|---|---|
| **P0-3 · agent_id 重複 resolve** | 4 步 workflow 省 150-300ms | `run_workflow` 進入時一次 batch resolve · agent_id_cache dict 給後續 step 用 |
| **P0-4 · workflow_runs/vision_extractions 缺索引** | quota check O(n)→O(log n)· 防 1 年後劣化 | main.py lifespan 加 `[user_email, started_at]` index + 365d/180d TTL |

### a11y(2 項)
| ID | 嚴重度 | 修補 |
|---|---|---|
| **顏色對比 text-tertiary < 4.5:1** | 🔴 P0 | light: `#C7C7CC` (1.79:1) → `#86868B` (4.54:1) · dark: `#48484A` (2.1:1) → `#8E8E93` (4.61:1) · 三處(:root + dark + auto-dark)同步 |
| **Streaming 訊息 SR spam** | 🔴 P0 | streaming 期間 chat-msg-body `aria-live="off"` · `_finishStream()` 切回 polite 並在 SR-only #chat-sr-announcer 區喊「助理已回覆 · 共 N 字」一次 |

**Playwright 驗證 100% 通過**:
- chat a11y:streaming aria-live=off → after polite → announcer "助理已回覆 · 共 1 字"
- vision SSRF:http://accounting:8000/admin/secrets → 422 阻擋 ✅ · http://169.254.169.254 → 422 ✅ · https://example.com 通過 → 503(預期 OpenAI 環境)

---

## 🟡 待辦清單(18 項 · 規劃下兩個版本)

### v1.6(2-4 週)· 高 ROI 中風險

#### 架構
- **跨層耦合**:`librechat-relabel.js` DOM 注入術語 → 改 i18n endpoint(LibreChat upgrade 不會斷)
- **Vision OCR 抽 sidecar**:CPU 重 + 可獨立 · 同 docker-compose 不同 container · 加 worker queue
- **legacy auth 統一**:刪 `X-User-Email` legacy header(`main.py:464`)· 統一 internal token + cookie

#### 安全
- **HIGH 3 · Action authorization bypass**:確認 LibreChat `canAccessAgentResource` 是 ownership check 而非僅 auth check · 若不是 fork patch
- **MEDIUM 5 · Internal token exposure**:wire-actions.py metadata.api_key 改 token hash + LibreChat admin GET /api/agents/:id 確認 redact

#### 效能
- **P0-1 · lazy load views**(1d):accounting/admin/userMgmt/design/media/social/siteSurvey/crm/workflows 全是頂層 static import · 改成第一次點才 `import()` · 首屏省 40-60KB / 150-250ms
- **P0-2 · CSS preload**(1h):`<link rel="preload" as="style">` + 5 個 CSS 合併成 critical inline + deferred
- **P0-5 · workflow 並行步驟**(1d):`event-planning` step_0/1 並行 · `tender-full` step_1/2 並行 · 用 asyncio.gather + DAG 分批

#### a11y
- **P1 · keyboard 完整路徑**:workflows.js progress overlay 缺 `role="status"` + focus trap · 改 modal.show + aria-live=assertive
- **P1 · reduced-motion 漏網**:`fpp-pulse` / `dock-drop-pulse` 等 infinite animation 縮 duration 但 iteration 仍跑 · 加 `animation:none !important`
- **P2 · 中英混排 lang=en span**:`chat-sanitize.js` 加正則包英文段 · SR 中英 TTS 切換正確

### v2.0(規模成長後)· 容量規劃

#### 擴展性(10 → 30 → 100 人)
- **slowapi 從 memory:// 改 Redis**(P0 必做 · 30 人多 worker 失準)
- **Mongo replica set 3 nodes**(30 人並發 + 寫入安全)
- **uvicorn 4 worker + Redis 共享 state**(現在單 worker 阻塞)
- **OpenAI Tier 4**(100 人尖峰 RPM 4000+)
- **Vision OCR + Celery/Arq + Redis queue**(取代同步阻塞)
- **MongoClient maxPoolSize=200**(現預設 100 易耗盡)

#### DR / SPOF
- **冷備援 Mac mini**:NT$ 30k 一次投資 · RTO 4-8h → 1h
- **MongoDB 第 2 顆 SSD + replica**:RPO 24h → <1min
- **Cloudflare Tunnel 加 systemd watchdog + Uptime Kuma + 季度 dr-drill**
- **Keychain 加密備份到 1Password / Bitwarden** 防全系統重建

---

## 📊 v1.56 → v1.57 度量改善

| 指標 | v1.56 | v1.57 | 變化 |
|---|---|---|---|
| 已知 CRITICAL 漏洞 | 1 (SSRF) | 0 | -1 ✅ |
| 已知 HIGH 漏洞 | 3 | 1(待 LibreChat upstream) | -2 |
| WCAG AA 對比違規(text-tertiary) | 多處 | 0 | -100% ✅ |
| Streaming SR spam | 整段重念 | 完成才 announce | 修 ✅ |
| workflow daily quota 繞過 | 可(internal:cron) | 阻擋 | 修 ✅ |
| workflow_runs query | collection scan | indexed | O(n)→O(log n) ✅ |
| 4 步 workflow latency(預估) | 4× /api/agents call | 1× | -150-300ms |

---

## 🗺️ 整合優先順序(向業主提案)

```
本週 v1.57 (本次 commit)
  · CRITICAL SSRF + HIGH 2 + a11y P0 + perf P0×2 已修

下週 v1.58
  · perf P0-1 lazy load views(首屏 -40-60KB)
  · perf P0-2 CSS preload + 合併
  · 安全 HIGH 3 LibreChat ownership check 確認

2 週內 v1.6.0
  · perf P0-5 workflow 並行步驟
  · 架構 P0 librechat-relabel 改 i18n endpoint
  · a11y P1 keyboard / reduced-motion / lang=en span
  · 安全 MEDIUM 5 token hash

業主 30 人 / 100 人擴張前(v2.0)
  · slowapi → Redis
  · Mongo replica set
  · uvicorn 4 worker
  · Vision OCR sidecar + queue
  · 冷備援 Mac mini + Mongo replica → RTO 1h / RPO <1min
```

---

## 風險與取捨

1. **vision.py SSRF 修補不能阻 OpenAI 端的 SSRF**:Pydantic 層阻 client 直接餵內網 URL,但 OpenAI 拿到 url 後仍會 fetch 公網 URL · 公網被反制(SSRF chained via redirector)需 OpenAI 端解 · 我方端能做的已最大化
2. **顏色對比修補可能稍微改變視覺風格**:tertiary 文字現在「不那麼淺」· 看起來灰一階 · 但 a11y 必須讓
3. **workflow_runs TTL 365d**:若業主有合規需求要更久(例如 7 年 PDPA)· 可從 env 覆寫
4. **chat streaming SR announce 用「字數」**:中文 1 字 = 1 character · 可能有人覺得「310 字」太精確 · 可改「短回覆」/「中等回覆」/「長回覆」分桶 · 待業主回饋

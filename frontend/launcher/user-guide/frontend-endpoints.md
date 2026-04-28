# 🔌 前端 Module ↔ 後端 Endpoint 對照表

> 給 PM / Champion / 接手新人:UI 那個按鈕到底打哪個 API?
> 也給未來工程師排查路由問題

---

## 對照矩陣

| Workspace | Frontend Module | View | 主要 Endpoints |
|---|---|---|---|
| 🏠 首頁 | app.js | dashboard | `/admin/budget-status` `/admin/dashboard` |
| 📁 專案 | projects.js | projects | `/projects` GET POST PUT DELETE / `/projects/{id}/handoff` |
| 💼 商機 | crm.js | crm | `/crm/leads` `/crm/stats` `/crm/leads/{id}` |
| 📚 技能庫 | (config.js 靜態) | skills | (純前端 · 無 API) |
| 💰 會計 | accounting.js | accounting | `/accounts` `/transactions` `/invoices` `/quotes` `/reports/pnl` |
| 📢 標案 | tenders.js | tenders | `/tender-alerts` (g0v PCC cron) |
| 工作流程 | workflows.js | workflows | (前端 SOP guide · 無 API) |
| 📊 管理 | admin.js | admin | `/admin/*` 全套(僅 admin) |
| 📚 知識庫 | knowledge.js | knowledge | `/knowledge/list,read,search` `/admin/sources/*` |
| ▣ NotebookLM | notebooklm.js | notebooklm | `/notebooklm/status` `/notebooklm/source-packs/*` |
| ❓ 教學 | help.js | help | (純前端 + 此 user-guide fetch) |
| 🎤 會議 | meeting.js | meeting | `/memory/transcribe` `/memory/meetings` `/memory/meetings/{id}/push-to-handoff` |
| 🎬 媒體 | media.js | media | `/media/contacts` `/media/recommend` `/media/pitches` `/media/contacts/export.csv` |
| 📅 社群 | social.js | social | `/social/posts` `/social/oauth/start` (v1.3 mock) |
| 📸 場勘 | site_survey.js | site | `/site-survey` POST GET / `/site-survey/{id}/audio` (v1.3) / `/site-survey/{id}/push-to-handoff` |
| 🎨 設計 | design.js | (modal) | `/design/recraft` `/design/history` `/design/job/{id}` |
| 🔐 安全 | (內嵌 chat.js) | (chat 內) | `/safety/pii-detect` `/safety/pii-audit` |

---

## 全 endpoint 表(按 router 分)

### 會計(routers/accounting.py)
| HTTP | path | 用途 |
|---|---|---|
| POST | /accounts/seed | 建台灣 25 預設科目 |
| GET | /accounts | 列所有科目 |
| POST | /accounts | 加 custom 科目 |
| POST | /transactions | 加交易 |
| GET | /transactions | 列(可 filter date / project) |
| DELETE | /transactions/{id} | 刪 |
| POST | /invoices | 開發票(自動 INV-YY-NNN) |
| POST | /quotes | 開報價(自動 Q-YY-NNN) |
| GET | /reports/pnl | 損益表 |
| GET | /reports/aging | 應收帳齡 |
| GET | /projects/{id}/finance | project 財務匯總 |

### Project(routers/projects.py)
| HTTP | path |
|---|---|
| GET | /projects |
| POST | /projects |
| PUT | /projects/{id} |
| DELETE | /projects/{id} |
| GET | /projects/{id}/handoff |
| PUT | /projects/{id}/handoff |

### CRM(routers/crm.py)
| HTTP | path |
|---|---|
| GET | /crm/leads |
| POST | /crm/leads |
| PUT | /crm/leads/{id} |
| DELETE | /crm/leads/{id} |
| POST | /crm/leads/{id}/notes |
| GET | /crm/stats |
| POST | /crm/import-from-tenders |

### Knowledge(routers/knowledge.py)
| HTTP | path |
|---|---|
| GET | /knowledge/list |
| GET | /knowledge/read |
| GET | /knowledge/search |
| GET | /admin/sources |
| POST | /admin/sources |
| PUT | /admin/sources/{id} |
| DELETE | /admin/sources/{id} |
| GET | /admin/sources/health |
| GET | /admin/sources/{id}/health |
| POST | /admin/sources/{id}/reindex |

### Memory · 會議速記(routers/memory.py)
| HTTP | path |
|---|---|
| POST | /memory/transcribe(audio multipart) |
| GET | /memory/meetings |
| GET | /memory/meetings/{id} |
| POST | /memory/meetings/{id}/push-to-handoff |

### Site Survey · 場勘(routers/site_survey.py)
| HTTP | path |
|---|---|
| POST | /site-survey(images + GPS) |
| GET | /site-survey |
| GET | /site-survey/{id} |
| POST | /site-survey/{id}/audio(v1.3 B4) |
| POST | /site-survey/{id}/push-to-handoff |

### Social Scheduler(routers/social.py)
| HTTP | path |
|---|---|
| GET | /social/posts |
| POST | /social/posts |
| PUT | /social/posts/{id} |
| DELETE | /social/posts/{id} |
| POST | /admin/social/run-queue(cron) |

### Social OAuth(v1.3 A5)
| HTTP | path |
|---|---|
| GET | /social/oauth/start |
| GET | /social/oauth/callback |
| POST | /social/oauth/disconnect |
| GET | /social/oauth/status(admin) |

### Media CRM(routers/media.py)
| HTTP | path |
|---|---|
| GET | /media/contacts |
| POST | /media/contacts |
| PUT | /media/contacts/{id} |
| DELETE | /media/contacts/{id}(軟刪) |
| GET | /media/contacts/{id}/pitches |
| POST | /media/pitches |
| POST | /media/recommend |
| POST | /media/contacts/import-csv |
| GET | /media/contacts/export.csv(v1.3 B3) |

### Tenders(routers/tenders.py)
| HTTP | path |
|---|---|
| GET | /tender-alerts |
| GET | /tender-alerts/settings |
| PUT | /tender-alerts/settings |
| POST | /tender-alerts/run-now |
| PUT | /tender-alerts/{key}?status=... |

### NotebookLM(routers/notebooklm.py)
| HTTP | path |
|---|---|
| GET | /notebooklm/status |
| GET | /notebooklm/settings(admin) |
| PUT | /notebooklm/settings(admin) |
| POST | /notebooklm/source-packs/preview |
| POST | /notebooklm/source-packs |
| GET | /notebooklm/source-packs |
| GET | /notebooklm/source-packs/{id} |
| POST | /notebooklm/source-packs/{id}/sync(admin) |
| POST | /notebooklm/projects/{project_id}/notebook |
| GET | /notebooklm/projects/{project_id}/notebook |
| POST | /notebooklm/uploads/auto |
| POST | /notebooklm/projects/{project_id}/upload |
| POST | /notebooklm/agent/source-packs/preview(internal) |
| POST | /notebooklm/agent/source-packs(internal) |
| GET | /notebooklm/agent/source-packs(internal) |
| POST | /notebooklm/agent/source-packs/{id}/sync(internal) |

### Design(routers/design.py)
| HTTP | path |
|---|---|
| POST | /design/recraft |
| GET | /design/history |
| GET | /design/job/{id} |

### Safety(routers/safety.py)
| HTTP | path |
|---|---|
| POST | /safety/classify |
| POST | /safety/pii-detect |
| POST | /safety/pii-audit |

### User Preferences(routers/users.py)
| HTTP | path |
|---|---|
| GET | /users/{email}/preferences |
| POST | /users/{email}/preferences |
| DELETE | /users/{email}/preferences/{key} |
| POST | /users/{email}/webhook |
| DELETE | /users/{email}/webhook |

### Feedback(routers/feedback.py)
| HTTP | path |
|---|---|
| POST | /feedback |
| GET | /feedback/stats(admin) |

### Admin(routers/admin/__init__.py + dashboard.py)
**Dashboard(v1.3 A1 抽出)**:
| HTTP | path |
|---|---|
| GET | /admin/dashboard |
| GET | /admin/cost(含 Whisper · v1.3 B2) |
| GET | /admin/adoption |
| GET | /admin/budget-status |
| GET | /admin/top-users |
| GET | /admin/tender-funnel |
| GET | /admin/librechat-contract |

**Other admin**:
| HTTP | path |
|---|---|
| DELETE | /admin/demo-data |
| GET | /admin/export |
| POST | /admin/import |
| GET | /admin/cron-runs |
| GET | /admin/audit-log(v1.3 C2 multi-action) |
| GET | /admin/audit-log/actions(v1.3 C2) |
| POST | /admin/audit-log |
| POST | /admin/email/send(rate limit) |
| POST | /admin/send-monthly-report |
| GET | /admin/monthly-report |
| GET | /admin/agent-prompts |
| POST | /admin/agent-prompts |
| DELETE | /admin/agent-prompts/{num} |
| GET | /admin/secrets/status |
| POST | /admin/secrets/{name} |
| POST | /admin/users/{email}/delete-all(PDPA · v1.3 B5 含 LibreChat) |
| POST | /admin/ocr/reprobe |

### System(v1.2 抽出)
| HTTP | path |
|---|---|
| GET | /quota/check |
| GET | /quota/preflight |
| GET | /healthz(public) |

---

## ~100 endpoint 總覽

- **Public**:1(`/healthz`)
- **require_user_dep**:60+(同事必登入)
- **require_admin_dep**:40+(僅 admin)
- **internal token**(cron):3-5

---

## 排查路由問題

### Q · 點按鈕 · 404 not found
1. devtools network 看真打的 URL
2. 對照本表確認 path 正確
3. 後端 route 沒 register?看 main.py include_router

### Q · 401 / 403
- 401 未登入 · 重 login
- 403 角色不對 · 看 admin-permissions.md

### Q · 500 internal server error
- 帶 rid → Champion 看 docker logs
- 看 error-codes.md `[E-002]`

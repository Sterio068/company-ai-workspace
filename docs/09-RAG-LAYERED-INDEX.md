# docs/09-RAG-LAYERED-INDEX.md — RAG 分層索引策略

> **問題**:承富上傳 500 份建議書 + 12 Skills + 17 Claude Skills + 4 Company Memory,
> 若全塞單一 vector DB,file_search 精準度下降(語意相近的很多)
>
> **解法**:依內容類型分 Agent 附加不同檔案 · LibreChat 原生支援 Agent-level file attachment

---

## 核心概念

LibreChat 的 file_search 是 **per-Agent scope**:每個 Agent 有自己的 attached files。
因此分層不是靠「多個 collection」· 是靠「**哪個 Agent 附哪些檔案**」。

---

## 承富 5 層 RAG 設計

| 層 | 內容 | 附加到哪些 Agent | 大小預估 |
|---|---|---|---|
| **L1 · 品牌層**(必) | `company/*.md`(品牌/禁用詞/稱謂/格式) | 全部 10 Agent | ~30 KB |
| **L2 · 技能層** | `skills/*.md`(承富 12)+ `claude-skills/**/SKILL.md` | 相關 Agent(見矩陣) | ~150 KB |
| **L3 · 矩陣層** | `SKILL-AGENT-MATRIX.md` | 主管家 + 所有 Agent(必讀) | 10 KB |
| **L4 · 歷史層**(最大) | `historical/建議書/*.pdf` 等 | 投標顧問 · 結案營運 · 知識庫 | 5-50 MB |
| **L5 · 參考層** | `openclaw-reference/*.md` | 主管家(視需要) | ~80 KB |

---

## 每個 Agent 該附什麼檔(具體命令)

### 00 主管家 · 涵蓋全域(priority file)
```bash
python3 scripts/upload-knowledge-base.py \
    --agent-id <00 的 agent_id> \
    --files 'knowledge-base/SKILL-AGENT-MATRIX.md'

python3 scripts/upload-knowledge-base.py \
    --agent-id <00 的 agent_id> \
    --files 'knowledge-base/company/*.md'
```

### 01 投標顧問
```bash
# 品牌層 + 投標 Skills + 歷史建議書 + claude pdf/docx/pptx
python3 scripts/upload-knowledge-base.py --agent-id <01> --files 'knowledge-base/company/*.md'
python3 scripts/upload-knowledge-base.py --agent-id <01> --files 'knowledge-base/skills/0[1-3]*.md'
python3 scripts/upload-knowledge-base.py --agent-id <01> --files 'knowledge-base/claude-skills/{pdf,docx,pptx}/SKILL.md'
python3 scripts/upload-knowledge-base.py --agent-id <01> --files 'knowledge-base/historical/建議書/*'
python3 scripts/upload-knowledge-base.py --agent-id <01> --files 'knowledge-base/historical/政府採購/*'
```

### 02 活動規劃師
```bash
python3 scripts/upload-knowledge-base.py --agent-id <02> --files 'knowledge-base/company/*.md'
python3 scripts/upload-knowledge-base.py --agent-id <02> --files 'knowledge-base/skills/0[7-9]*.md'
python3 scripts/upload-knowledge-base.py --agent-id <02> --files 'knowledge-base/claude-skills/{pdf,xlsx,canvas-design}/SKILL.md'
python3 scripts/upload-knowledge-base.py --agent-id <02> --files 'knowledge-base/historical/活動/*'
```

### 03 設計夥伴
```bash
python3 scripts/upload-knowledge-base.py --agent-id <03> --files 'knowledge-base/company/*.md'
python3 scripts/upload-knowledge-base.py --agent-id <03> --files 'knowledge-base/claude-skills/{brand-guidelines,canvas-design,frontend-design,web-artifacts-builder,theme-factory,algorithmic-art}/SKILL.md'
python3 scripts/upload-knowledge-base.py --agent-id <03> --files 'knowledge-base/historical/視覺/*'
```

### 04 公關寫手
```bash
python3 scripts/upload-knowledge-base.py --agent-id <04> --files 'knowledge-base/company/*.md'
python3 scripts/upload-knowledge-base.py --agent-id <04> --files 'knowledge-base/skills/0[4-6]*.md'
python3 scripts/upload-knowledge-base.py --agent-id <04> --files 'knowledge-base/claude-skills/{docx,internal-comms,doc-coauthoring}/SKILL.md'
python3 scripts/upload-knowledge-base.py --agent-id <04> --files 'knowledge-base/historical/新聞稿/*'
```

### 05 會議速記
```bash
python3 scripts/upload-knowledge-base.py --agent-id <05> --files 'knowledge-base/company/*.md'
python3 scripts/upload-knowledge-base.py --agent-id <05> --files 'knowledge-base/claude-skills/{docx,internal-comms,doc-coauthoring}/SKILL.md'
```

### 06 知識庫查詢(最大負載)
```bash
python3 scripts/upload-knowledge-base.py --agent-id <06> --files 'knowledge-base/company/*.md'
python3 scripts/upload-knowledge-base.py --agent-id <06> --files 'knowledge-base/skills/*.md'
python3 scripts/upload-knowledge-base.py --agent-id <06> --files 'knowledge-base/claude-skills/**/SKILL.md'
python3 scripts/upload-knowledge-base.py --agent-id <06> --files 'knowledge-base/historical/**/*'
python3 scripts/upload-knowledge-base.py --agent-id <06> --files 'knowledge-base/openclaw-reference/*.md'
# ⚠️ 注意:若歷史檔案超過 50 份,file_search 索引時間可能長達 30 分鐘
```

### 07 財務試算
```bash
python3 scripts/upload-knowledge-base.py --agent-id <07> --files 'knowledge-base/company/*.md'
python3 scripts/upload-knowledge-base.py --agent-id <07> --files 'knowledge-base/skills/{09,10}*.md'
python3 scripts/upload-knowledge-base.py --agent-id <07> --files 'knowledge-base/claude-skills/{xlsx,claude-api}/SKILL.md'
```

### 08 合約法務
```bash
python3 scripts/upload-knowledge-base.py --agent-id <08> --files 'knowledge-base/company/*.md'
python3 scripts/upload-knowledge-base.py --agent-id <08> --files 'knowledge-base/skills/06*.md'
python3 scripts/upload-knowledge-base.py --agent-id <08> --files 'knowledge-base/claude-skills/{docx,pdf,internal-comms}/SKILL.md'
python3 scripts/upload-knowledge-base.py --agent-id <08> --files 'knowledge-base/historical/合約/*'
```

### 09 結案營運
```bash
python3 scripts/upload-knowledge-base.py --agent-id <09> --files 'knowledge-base/company/*.md'
python3 scripts/upload-knowledge-base.py --agent-id <09> --files 'knowledge-base/skills/{11,12}*.md'
python3 scripts/upload-knowledge-base.py --agent-id <09> --files 'knowledge-base/claude-skills/{docx,pptx,xlsx,doc-coauthoring}/SKILL.md'
python3 scripts/upload-knowledge-base.py --agent-id <09> --files 'knowledge-base/historical/結案/*'
```

---

## 一鍵部署腳本(可加到 local-quickstart.sh)

```bash
# scripts/upload-all-layered.sh
#!/bin/bash
set -euo pipefail

# 先從 admin panel 或 API 取得 10 個 agent_id,寫到 config-templates/agent-ids.json
# 格式:{"00": "agent_xxx", "01": "agent_yyy", ...}

IDS=$(cat config-templates/agent-ids.json)
get_id() { echo "$IDS" | python3 -c "import sys,json; print(json.load(sys.stdin)['$1'])"; }

# 主管家
python3 scripts/upload-knowledge-base.py --agent-id $(get_id 00) --files 'knowledge-base/SKILL-AGENT-MATRIX.md'
python3 scripts/upload-knowledge-base.py --agent-id $(get_id 00) --files 'knowledge-base/company/*.md'

# 其餘 9 個 Agent · 依矩陣對應
# ...(見各 Agent 段落)
```

---

## 監控

- LibreChat admin panel → Files → 各 Agent 的 file list 總數
- 若 Agent 檔案超過 **100 個 file_search 延遲明顯** → 考慮歸檔舊檔(移到 `_archived/`)

---

## 為何不用分開的 Vector DB(Qdrant / Weaviate)

- v1.0 使用者量 10 人 · LibreChat 原生 file_search 夠用
- 分開 vector DB 會增加:運維、同步、除錯成本
- v2.0+ 若每 Agent 超過 500 檔 → 再評估(見 CLAUDE.md 擴充性章節)

#!/usr/bin/env python3
"""
v1.6.0 #1 · 把 skill 對應表注入每個 agent prompt 末尾

原問題:agent 知道有 file_search,但不知道哪個 skill 對應哪個情境 → 引用率低
解法:每 agent prompt 末尾加 「## 你常用的 Skills」 區塊,明示 skill 名與觸發情境

12 個 skill(已在 knowledge-base/skills/):
  01-政府標案結構分析   → #00 #01 #06
  02-Go-NoGo決策樹      → #00 #01 #08(風險評估面)
  03-建議書5章模板      → #00 #01 #06
  04-新聞稿AP-Style     → #00 #04 #06
  05-社群貼文-3種hook   → #00 #04 #06
  06-Email公文體        → #00 #04 #06 #08
  07-場地踏勘checklist  → #00 #02 #06
  08-舞台動線設計原則   → #00 #02 #03(視覺面)
  09-活動預算分配比例   → #00 #02 #07
  10-毛利試算框架       → #00 #07 #08
  11-客戶CRM記錄模板    → #00 #04 #09
  12-結案報告結構       → #00 #02 #06 #09
"""
import json, glob, pathlib

# 每個 agent 的相關 skill(用 num 對應)· #00 主管家拿全套
SKILL_MAP = {
    "00": ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"],
    "01": ["01", "02", "03", "10"],   # 投標
    "02": ["07", "08", "09", "12"],   # 活動
    "03": ["08"],                       # 設計(視覺面)
    "04": ["04", "05", "06", "11"],   # 公關
    "05": ["06"],                       # 會議速記(Email 公文體)
    "06": ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"],  # 知識庫全套
    "07": ["09", "10"],                # 財務
    "08": ["02", "06", "10"],          # 法務(風險 + Email + 毛利)
    "09": ["11", "12"],                # 結案營運
}

SKILL_NAMES = {
    "01": "01-政府標案結構分析",
    "02": "02-Go-NoGo決策樹",
    "03": "03-建議書5章模板",
    "04": "04-新聞稿AP-Style",
    "05": "05-社群貼文-3種hook",
    "06": "06-Email公文體",
    "07": "07-場地踏勘checklist",
    "08": "08-舞台動線設計原則",
    "09": "09-活動預算分配比例",
    "10": "10-毛利試算框架",
    "11": "11-客戶CRM記錄模板",
    "12": "12-結案報告結構",
}

# Skill 觸發情境(給 AI 看的)
SKILL_TRIGGERS = {
    "01": "看到招標 PDF 或須知文字",
    "02": "需要評估「承不承接」這個案",
    "03": "要寫建議書 / 提案書",
    "04": "寫新聞稿 / 媒體稿",
    "05": "寫 IG / FB / 領英貼文",
    "06": "寫對外 Email(政府 / 客戶 / 媒體)",
    "07": "活動現場勘場 / 規劃",
    "08": "設計舞台 / 視覺焦點 / 動線",
    "09": "規劃活動預算分配",
    "10": "算毛利 / 報價 / 預算",
    "11": "寫客戶紀錄 / CRM 跟進",
    "12": "寫結案報告 / 月報",
}

PRESET_DIR = pathlib.Path("config-templates/presets")
SECTION_MARK = "## 你常用的 Skills(優先 file_search 引用)"

count_files = 0
for path in sorted(PRESET_DIR.glob("0*.json")):
    if path.is_dir(): continue
    name = path.name
    num = name.split("-")[0]
    if num not in SKILL_MAP:
        continue
    d = json.loads(path.read_text())
    prompt = d.get("promptPrefix", "")

    # 已注入過就 skip(允許重跑)
    if SECTION_MARK in prompt:
        continue

    skill_lines = []
    for sn in SKILL_MAP[num]:
        skill_lines.append(
            f"- `knowledge-base/skills/{SKILL_NAMES[sn]}.md` · 觸發:{SKILL_TRIGGERS[sn]}"
        )
    section = (
        f"\n\n{SECTION_MARK}\n"
        "下列 skill 是公司既定 know-how · 對應情境出現時 · 用 file_search 主動查 + 引用:\n"
        + "\n".join(skill_lines)
        + "\n\n**規則**:\n"
        "- 若 skill 給出明確公式 / 步驟 / 範本 · **務必照做** · 不要自創\n"
        "- 引用 skill 時要標來源:「依 skill 02 Go/No-Go 決策樹...」\n"
        "- 若情境與 skill 衝突 · 先回報並請使用者裁定 · 不擅自偏離\n"
    )
    d["promptPrefix"] = prompt + section
    path.write_text(json.dumps(d, ensure_ascii=False, indent=2))
    count_files += 1
    print(f"  injected {len(SKILL_MAP[num])} skills → {name}")

print(f"\n--- {count_files} agents 注入完成 ---")

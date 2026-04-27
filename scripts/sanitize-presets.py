#!/usr/bin/env python3
"""
v1.59 #3 · 把 presets/*.json prompt 內 144 處「承富」全清掉

替換規則(順序重要 · 長字串先 · 避免破壞 dependencies):
  · "承富創意整合行銷有限公司" → "本公司"
  · "承富創意整合行銷" → "本公司"
  · "承富主管家" → "主管家"(也用於 file rename)
  · "承富 AI 系統" → "本系統"
  · "承富 AI" → "智慧助理"
  · "承富 10 年" → "公司 10 年"
  · "承富 9 個專家" → "9 個專家"
  · "承富 12 個" → "12 個"
  · "承富過往" → "公司過往"
  · "承富的" → "公司的"
  · "承富 [skill name]" → "[skill name]"
  · standalone "承富" → "本公司"

也 rename 00-承富主管家.json → 00-主管家.json
"""
import json, glob, re, pathlib, shutil

RULES = [
    ("承富創意整合行銷有限公司", "本公司"),
    ("承富創意整合行銷", "本公司"),
    ("承富主管家", "主管家"),
    ("承富 AI 系統", "本系統"),
    ("承富 AI", "智慧助理"),
    ("承富 10 年", "公司 10 年"),
    ("承富 9 個專家", "9 個專家"),
    ("承富 12 個", "12 個"),
    ("承富過往", "公司過往"),
    ("承富自家", "公司自家"),
    ("承富目標", "公司目標"),
    ("承富的", "公司的"),
    ("承富已", "公司已"),
    ("承富案例", "過往案例"),
    ("承富禁用詞", "禁用詞"),
    ("承富環保類", "環保類"),
    ("承富環境", "公司環境"),
    ("承富口吻", "公司口吻"),
    ("承富品牌", "公司品牌"),
    ("承富業務", "公司業務"),
    ("承富系統", "本系統"),
    ("承富語氣", "公司語氣"),
    ("承富行政", "公司行政"),
    ("承富格式", "公司格式"),
    ("承富特有", "公司特有"),
    ("承富實際", "公司實際"),
    ("承富 SOP", "公司 SOP"),
    # 「承富 隔個空白 + 中英」一律 standalone 處理
    ("承富 ", "本公司 "),
    # last-resort standalone
    ("承富", "本公司"),
]

PRESET_DIR = pathlib.Path("config-templates/presets")
LEGACY_DIR = PRESET_DIR / "legacy"

count_files = 0
count_replacements = 0

for path in sorted(PRESET_DIR.glob("0*.json")):
    if path.is_dir(): continue
    src = path.read_text()
    new = src
    file_count = 0
    for old, neu in RULES:
        n = new.count(old)
        if n:
            new = new.replace(old, neu)
            file_count += n
    if new != src:
        path.write_text(new)
        count_files += 1
        count_replacements += file_count
        print(f"  {path.name}: {file_count} 處")

# Rename file 00-承富主管家.json → 00-主管家.json
old_p = PRESET_DIR / "00-承富主管家.json"
new_p = PRESET_DIR / "00-主管家.json"
if old_p.exists() and not new_p.exists():
    shutil.move(str(old_p), str(new_p))
    print(f"  rename: {old_p.name} → {new_p.name}")

# 確認
remaining = 0
for path in PRESET_DIR.glob("0*.json"):
    if path.is_dir(): continue
    d = json.loads(path.read_text())
    n = d.get("promptPrefix", "").count("承富")
    if n: remaining += n
    n2 = d.get("title", "").count("承富") + d.get("description", "").count("承富")
    if n2: remaining += n2
print(f"\n--- {count_files} files · {count_replacements} replacements · 剩 {remaining} 處 ---")

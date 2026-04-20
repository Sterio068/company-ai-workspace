#!/usr/bin/env python3
"""
承富 AI · Skill 演化:從對話紀錄 + 👍 回饋建議新 Skill
==========================================================

v1.5 半自動化 skill 產生流程:
  1. 讀近 N 天的對話紀錄(MongoDB LibreChat convos)
  2. 找出高頻「使用者問題 pattern」
  3. 交叉比對 👍 回饋,找「好的回應 pattern」
  4. 用 Claude 提煉成 Skill 草稿
  5. 輸出到 knowledge-base/skills/_proposed/ 等 Sterio 審核
  6. 審核通過 → 移到 knowledge-base/skills/ → 重新上傳 RAG

用法:
  ANTHROPIC_API_KEY=sk-ant-... python3 scripts/propose-skill.py --days 30
  (需先 `pip install anthropic pymongo`)
"""
import argparse
import json
import os
import pathlib
import sys
from collections import Counter
from datetime import datetime, timedelta

try:
    from pymongo import MongoClient
    import anthropic
except ImportError:
    sys.exit("pip install pymongo anthropic")


PROJECT_ROOT = pathlib.Path(__file__).parent.parent
PROPOSED_DIR = PROJECT_ROOT / "knowledge-base" / "skills" / "_proposed"
PROPOSED_DIR.mkdir(parents=True, exist_ok=True)


def sample_conversations(db, days: int, limit: int = 200):
    """抓近 N 天的對話。"""
    cutoff = datetime.utcnow() - timedelta(days=days)
    convos = list(db.conversations.find(
        {"createdAt": {"$gte": cutoff}},
        {"title": 1, "_id": 1, "endpoint": 1, "model": 1, "createdAt": 1}
    ).sort("createdAt", -1).limit(limit))
    return convos


def sample_liked_messages(db, days: int, limit: int = 100):
    """找近 N 天被 👍 的訊息 + 其上下文。"""
    cutoff = datetime.utcnow() - timedelta(days=days)
    liked_fb = list(db.feedback.find({
        "verdict": "up",
        "created_at": {"$gte": cutoff}
    }).limit(limit))

    results = []
    for fb in liked_fb:
        msg = db.messages.find_one({"messageId": fb["message_id"]})
        if msg:
            results.append({
                "agent": fb.get("agent_name"),
                "user_input": msg.get("user_input", ""),
                "ai_response": (msg.get("text") or "")[:2000],  # 截斷避免太長
                "note": fb.get("note", ""),
            })
    return results


def identify_patterns(liked_messages: list):
    """粗略找 pattern:常見關鍵字 · 共同結構。"""
    # 簡單版:抓 agent 分組
    by_agent = {}
    for m in liked_messages:
        by_agent.setdefault(m["agent"] or "unknown", []).append(m)

    patterns = []
    for agent, msgs in by_agent.items():
        if len(msgs) < 3:
            continue  # 資料不足,跳過
        # 簡單 pattern:使用者輸入的常見開頭
        input_starts = Counter(m["user_input"][:20] for m in msgs if m["user_input"])
        common_starts = input_starts.most_common(3)
        patterns.append({
            "agent": agent,
            "count": len(msgs),
            "sample_user_inputs": [m["user_input"][:100] for m in msgs[:3]],
            "sample_responses": [m["ai_response"][:300] for m in msgs[:2]],
            "common_input_starts": common_starts,
        })
    return patterns


def propose_skill_via_claude(pattern: dict, client):
    """用 Claude Opus 分析 pattern → 產出 Skill 草稿。"""
    sys_prompt = """你是承富 AI 系統的 Skill 策展人。\n使用者提供一組「被 👍 的對話 pattern」,\n你要提煉成可複用的 Skill 草稿,格式如:\n\n```\n---\nskill_id: <英文 kebab-case>\nname: <繁中 skill 名稱>\nversion: 1.0-proposed\ntriggers:\n  - <使用者會說的觸發句>\n---\n\n# 何時用\n\n# 標準做法(步驟)\n\n# 優質範例\n\n# 檢查清單\n```\n\n請誠實:若資料不足以歸納,回「資料不足,需累積更多」即可。"""

    user_prompt = f"""這是某個 Agent 被按讚次數 {pattern['count']} 的 pattern:\n\n**Agent**: {pattern['agent']}\n\n**常見使用者輸入**:\n{chr(10).join([f'- {s}' for s in pattern['sample_user_inputs']])}\n\n**優質 AI 回應範例**:\n{chr(10).join([f'---\\n{r}' for r in pattern['sample_responses']])}\n\n請產出 Skill 草稿。若資料足夠歸納,請產 Markdown;不足請說明需要什麼。"""

    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4000,
        system=sys_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return resp.content[0].text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--min-signals", type=int, default=3,
                        help="同一 Agent 至少多少個 👍 才會產 Skill 建議")
    args = parser.parse_args()

    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/chengfu")
    client = MongoClient(mongo_uri)
    db = client.get_default_database()

    # 抓資料
    print(f"📊 分析近 {args.days} 天資料...")
    liked = sample_liked_messages(db, args.days)
    print(f"   找到 {len(liked)} 個 👍 對話")

    if len(liked) < args.min_signals:
        sys.exit(f"❌ 👍 資料不足({len(liked)} < {args.min_signals}),再累積使用量吧")

    patterns = identify_patterns(liked)
    print(f"   識別 {len(patterns)} 組 pattern")
    print()

    # Claude 分析
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("❌ 需設 ANTHROPIC_API_KEY")

    anth = anthropic.Anthropic()

    for i, pattern in enumerate(patterns):
        if pattern["count"] < args.min_signals:
            continue
        print(f"🤖 分析 pattern {i+1}: {pattern['agent']}({pattern['count']} 次)...")
        proposal = propose_skill_via_claude(pattern, anth)

        # 寫檔
        out_file = PROPOSED_DIR / f"{datetime.now():%Y%m%d}-{pattern['agent'].replace(' ', '-')}.md"
        out_file.write_text(proposal, encoding="utf-8")
        print(f"   📝 {out_file.relative_to(PROJECT_ROOT)}")
        print()

    print()
    print("========================================")
    print(f"✅ 完成 · 產出 {len(list(PROPOSED_DIR.glob('*.md')))} 個提案")
    print("========================================")
    print()
    print("下一步(Sterio):")
    print(f"  1. 檢視 {PROPOSED_DIR.relative_to(PROJECT_ROOT)}/ 下的提案")
    print(f"  2. 覺得好的 → 移到 knowledge-base/skills/")
    print(f"  3. 執行 upload-knowledge-base.py 重新上傳")
    print(f"  4. 主管家會自動用新 Skill")


if __name__ == "__main__":
    main()

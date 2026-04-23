"""
Admin / ROI 計算 service · pure functions
main.py 的 /admin/* 與 /quota/check handlers 呼叫這裡

設計(Round 8 reviewer):
- 純資料與計算 · 不碰 request/response · 不 raise HTTPException
- 所有外部依賴(db / collection / settings / email)當參數傳入
- test 前呼叫 reset_cache() 避免 _SCHEMA_CHECKED 汙染
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from bson import ObjectId


# ============================================================
# Pricing(可追溯)· 更新時改 PRICE_VERSION 日期
# ============================================================
PRICE_VERSION = "2026-04-21"
PRICE_SOURCE = "https://www.anthropic.com/pricing"
PRICE_NOTE = "USD per 1M tokens · 半年內請定期確認 Anthropic 是否調價"
ANTHROPIC_PRICING_USD = {
    "claude-opus-4-7":    {"input": 15.0,  "output": 75.0},
    "claude-sonnet-4-6":  {"input":  3.0,  "output": 15.0},
    "claude-haiku-4-5":   {"input":  0.25, "output":  1.25},
}


# ============================================================
# LibreChat transactions schema cache(啟動時 probe 一次 · 之後不重算)
# ============================================================
_SCHEMA_CACHED = {"checked": False, "ok": False, "issue": ""}


def reset_cache():
    """測試用 · 每 test 前呼叫避免 cache 汙染"""
    _SCHEMA_CACHED.update({"checked": False, "ok": False, "issue": ""})


def probe_tx_schema(db) -> dict:
    """檢查 LibreChat transactions collection 欄位 · 結果快取"""
    if _SCHEMA_CACHED["checked"]:
        return _SCHEMA_CACHED
    _SCHEMA_CACHED["checked"] = True
    try:
        doc = db.transactions.find_one(
            {}, {"rawAmount": 1, "model": 1, "user": 1, "createdAt": 1}
        )
        if not doc:
            _SCHEMA_CACHED["ok"] = True
            _SCHEMA_CACHED["issue"] = "transactions 尚無資料(正常)"
        else:
            missing = []
            raw = doc.get("rawAmount") or {}
            if not isinstance(raw, dict):
                missing.append("rawAmount(non-dict)")
            elif "prompt" not in raw and "completion" not in raw:
                missing.append("rawAmount.prompt|completion")
            for k in ("model", "user", "createdAt"):
                if k not in doc:
                    missing.append(k)
            _SCHEMA_CACHED["ok"] = not missing
            _SCHEMA_CACHED["issue"] = f"缺欄位:{missing}" if missing else ""
    except Exception as e:
        _SCHEMA_CACHED["ok"] = False
        _SCHEMA_CACHED["issue"] = f"probe 失敗:{e}"
    return _SCHEMA_CACHED.copy()


def tx_fingerprint(db, limit: int = 10) -> list[dict]:
    """最近 N 筆 transactions 的欄位 fingerprint · 升版後變動偵測"""
    fp = []
    try:
        for doc in db.transactions.find({}).sort("createdAt", -1).limit(limit):
            raw = doc.get("rawAmount") or {}
            fp.append({
                "has_rawAmount": isinstance(raw, dict),
                "rawAmount_keys": sorted(list(raw.keys())) if isinstance(raw, dict) else [],
                "has_user": "user" in doc,
                "has_model": "model" in doc,
                "has_createdAt": "createdAt" in doc,
            })
    except Exception:
        pass
    return fp


# ============================================================
# 計價 · 所有 admin / quota endpoint 都用這個
# ============================================================
def price_ntd(model: str, tokens_in: int, tokens_out: int,
              usd_to_ntd: float = 32.5) -> float:
    """依模型 + 台幣匯率算 NT$"""
    p = ANTHROPIC_PRICING_USD.get(model) or ANTHROPIC_PRICING_USD["claude-sonnet-4-6"]
    usd = (tokens_in / 1_000_000) * p["input"] + (tokens_out / 1_000_000) * p["output"]
    return round(usd * usd_to_ntd, 2)


def user_month_spend_ntd(db, users_col, email: str,
                         usd_to_ntd: float = 32.5) -> dict:
    """某 user 本月已花 NT$(Round 9 Q1:回 dict · 區分「真的 0」vs「查不到」)

    Returns
    -------
    {"ok": True,  "spent_ntd": float, "user_found": True}   · 正常(含真實 0)
    {"ok": False, "spent_ntd": 0.0, "reason": str}          · 資料來源異常
    {"ok": True,  "spent_ntd": 0.0, "user_found": False}    · email 對不到 user(新使用者合理)
    """
    if not email:
        return {"ok": True, "spent_ntd": 0.0, "user_found": False, "reason": "no_email"}
    try:
        u = users_col.find_one({"email": email}, {"_id": 1})
        if not u:
            return {"ok": True, "spent_ntd": 0.0, "user_found": False,
                    "reason": "user_not_in_librechat"}
        uid = u["_id"]
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        pipeline = [
            {"$match": {"createdAt": {"$gte": month_start}, "user": uid}},
            {"$group": {
                "_id": "$model",
                "tin":  {"$sum": "$rawAmount.prompt"},
                "tout": {"$sum": "$rawAmount.completion"},
            }},
        ]
        stats = list(db.transactions.aggregate(pipeline))
        spent = sum(price_ntd(s["_id"] or "", s.get("tin", 0) or 0,
                              s.get("tout", 0) or 0, usd_to_ntd) for s in stats)
        return {"ok": True, "spent_ntd": spent, "user_found": True}
    except Exception as e:
        return {"ok": False, "spent_ntd": 0.0, "reason": f"data_source_error: {type(e).__name__}: {e}"}


# ============================================================
# Admin Dashboard endpoints 的核心邏輯
# ============================================================
def budget_status(db, monthly_budget_ntd: float,
                  usd_to_ntd: float = 32.5) -> dict:
    """本月預算進度 + schema probe 黃牌降級"""
    schema = probe_tx_schema(db)
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        pipeline = [
            {"$match": {"createdAt": {"$gte": month_start}}},
            {"$group": {
                "_id": "$model",
                "tin":  {"$sum": "$rawAmount.prompt"},
                "tout": {"$sum": "$rawAmount.completion"},
            }},
        ]
        stats = list(db.transactions.aggregate(pipeline))
        spent = sum(price_ntd(s["_id"] or "", s.get("tin", 0) or 0,
                              s.get("tout", 0) or 0, usd_to_ntd) for s in stats)
    except Exception:
        spent = 0.0
    pct = (spent / monthly_budget_ntd * 100) if monthly_budget_ntd else 0
    level = "ok" if pct < 80 else "warn" if pct < 100 else "over"
    return {
        "spent_ntd": round(spent, 0),
        "budget_ntd": monthly_budget_ntd,
        "pct": round(pct, 1),
        "alert_level": level,
        "month": now.strftime("%Y-%m"),
        "pricing_version": PRICE_VERSION,
        "data_source_ok": schema["ok"],
        "data_source_issue": schema["issue"] if not schema["ok"] else None,
    }


def top_users(db, users_col, days: int = 30, limit: int = 10,
              user_soft_cap_ntd: float = 1200.0,
              usd_to_ntd: float = 32.5) -> dict:
    """Top N 用量同仁"""
    try:
        from_dt = datetime.now(timezone.utc) - timedelta(days=days)
        pipeline = [
            {"$match": {"createdAt": {"$gte": from_dt}}},
            {"$group": {
                "_id": {"user": "$user", "model": "$model"},
                "tin":  {"$sum": "$rawAmount.prompt"},
                "tout": {"$sum": "$rawAmount.completion"},
                "count": {"$sum": 1},
            }},
        ]
        raw = list(db.transactions.aggregate(pipeline))
        agg = {}
        for r in raw:
            uid = str(r["_id"].get("user", ""))
            model = r["_id"].get("model", "")
            cost = price_ntd(model, r.get("tin", 0) or 0,
                             r.get("tout", 0) or 0, usd_to_ntd)
            if uid not in agg:
                agg[uid] = {"user_id": uid, "cost_ntd": 0, "calls": 0, "by_model": {}}
            agg[uid]["cost_ntd"] += cost
            agg[uid]["calls"] += r.get("count", 0)
            agg[uid]["by_model"][model] = agg[uid]["by_model"].get(model, 0) + cost
        # join email
        for a in agg.values():
            if a["user_id"]:
                try:
                    u = users_col.find_one({"_id": ObjectId(a["user_id"])},
                                             {"email": 1, "name": 1})
                    a["email"] = (u or {}).get("email", "unknown")
                    a["name"]  = (u or {}).get("name",  "")
                except Exception:
                    a["email"], a["name"] = "unknown", ""
            a["cost_ntd"] = round(a["cost_ntd"], 0)
            a["pct_of_cap"] = round(a["cost_ntd"] / user_soft_cap_ntd * 100, 1)
        ranked = sorted(agg.values(), key=lambda x: -x["cost_ntd"])[:limit]
        return {"period_days": days, "user_soft_cap_ntd": user_soft_cap_ntd, "top": ranked}
    except Exception as e:
        return {"error": str(e)}


def tender_funnel(db) -> dict:
    """本月標案漏斗"""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        new_count = db.tender_alerts.count_documents({"discovered_at": {"$gte": month_start}})
        interested = db.tender_alerts.count_documents({"status": "interested"})
        skipped = db.tender_alerts.count_documents({"status": "skipped"})
        stages_pipeline = [
            {"$match": {"created_at": {"$gte": month_start}, "source": "tender_alert"}},
            {"$group": {"_id": "$stage", "count": {"$sum": 1}}},
        ]
        stages = {s["_id"]: s["count"] for s in db.crm_leads.aggregate(stages_pipeline)}
    except Exception as e:
        return {"error": str(e)}
    return {
        "month": now.strftime("%Y-%m"),
        "funnel": {
            "new_discovered": new_count,
            "interested": interested,
            "skipped": skipped,
            "proposing": stages.get("proposing", 0),
            "submitted": stages.get("submitted", 0),
            "won": stages.get("won", 0),
            "lost": stages.get("lost", 0),
        },
    }


def cost_by_model(db, days: int = 30) -> dict:
    """API cost 分 model(LibreChat 私有 schema · 用 adapter 降級)"""
    schema = probe_tx_schema(db)
    if not schema["ok"]:
        return {"error": schema["issue"], "note": "LibreChat transactions schema 異常 · 找工程師"}
    try:
        from_dt = datetime.now(timezone.utc) - timedelta(days=days)
        pipeline = [
            {"$match": {"createdAt": {"$gte": from_dt}}},
            {"$group": {
                "_id": "$model",
                "input_tokens":  {"$sum": "$rawAmount.prompt"},
                "output_tokens": {"$sum": "$rawAmount.completion"},
                "count":         {"$sum": 1},
            }},
        ]
        stats = list(db.transactions.aggregate(pipeline))
        return {"period_days": days, "by_model": stats}
    except Exception as e:
        return {"error": str(e), "note": "需 LibreChat transactions collection 存在"}


def adoption_metrics(db, users_col, projects_col, feedback_col,
                     days: int = 7,
                     usd_to_ntd: float = 32.5) -> dict:
    """Codex Round 10.5 黃 6 · 支撐 BOSS-VIEW §2 ROI 數字的 endpoint

    Champion 週報 + Day +3 里程碑看這個
    - 週活躍人數(有 ≥ 1 次對話)
    - 每人對話數中位數 / 分布
    - handoff 填寫率(Projects 有 handoff.goal 者 / 總 Projects)
    - Fal 本期成本(design_jobs count × n_images × USD 0.04 × 32.5)
    - first-win 標記(至少 1 次對話即視為已試)
    """
    now = datetime.now(timezone.utc)
    from_dt = now - timedelta(days=days)
    result = {
        "period_days": days,
        "from": from_dt.isoformat(),
        "to": now.isoformat(),
    }

    # 1. 活躍使用者(Codex R2.6 · 用 aggregate · distinct 百萬筆會 OOM)
    try:
        unique_agg = list(db.transactions.aggregate([
            {"$match": {"createdAt": {"$gte": from_dt}}},
            {"$group": {"_id": "$user"}},
            {"$limit": 500},  # 安全上限 · 承富 10 人絕不會到
        ]))
        active_user_ids = [u["_id"] for u in unique_agg]
        result["active_users"] = len(active_user_ids)
        # 用 $in batch 查 · 不再逐一 find
        if active_user_ids:
            try:
                users = list(users_col.find(
                    {"_id": {"$in": active_user_ids}},
                    {"email": 1}
                ))
                result["active_user_emails"] = [u.get("email") for u in users if u.get("email")]
            except Exception:
                result["active_user_emails"] = []
        else:
            result["active_user_emails"] = []
    except Exception as e:
        result["active_users_error"] = str(e)
        result["active_users"] = None

    # 2. 每人對話數(從 transactions count by user)
    try:
        calls_by_user = list(db.transactions.aggregate([
            {"$match": {"createdAt": {"$gte": from_dt}}},
            {"$group": {"_id": "$user", "n": {"$sum": 1}}},
            {"$sort": {"n": -1}},
        ]))
        calls = [u["n"] for u in calls_by_user]
        result["calls_total"] = sum(calls)
        result["calls_distribution"] = {
            "median": calls[len(calls)//2] if calls else 0,
            "min": min(calls) if calls else 0,
            "max": max(calls) if calls else 0,
            # first-win 硬門檻:≥ 1 次對話
            "users_with_ge1_call": sum(1 for c in calls if c >= 1),
            # 活躍門檻:≥ 3 次(Day +3 目標)
            "users_with_ge3_calls": sum(1 for c in calls if c >= 3),
        }
    except Exception as e:
        result["calls_error"] = str(e)

    # 3. Handoff 填寫率
    # Codex R2.6 · goal trim 後非空才算已填 · 避免只打空白繞過
    try:
        total_projects = projects_col.count_documents({})
        with_handoff = 0
        try:
            # 先試 Mongo 4.0+ 原生 $trim(production 用這個 · 最快)
            filled_agg = list(projects_col.aggregate([
                {"$match": {"handoff.goal": {"$exists": True, "$type": "string"}}},
                {"$project": {"trimmed": {"$trim": {"input": "$handoff.goal"}}}},
                {"$match": {"trimmed": {"$ne": ""}}},
                {"$count": "n"},
            ]))
            with_handoff = filled_agg[0]["n"] if filled_agg else 0
        except Exception:
            # fallback · mongomock 不支援 $trim · 逐一檢查
            for doc in projects_col.find(
                {"handoff.goal": {"$exists": True}},
                {"handoff.goal": 1},
            ):
                goal = ((doc.get("handoff") or {}).get("goal") or "")
                if isinstance(goal, str) and goal.strip():
                    with_handoff += 1
        result["handoff"] = {
            "total_projects": total_projects,
            "with_handoff_filled": with_handoff,
            "completion_rate": round(with_handoff / total_projects * 100, 1) if total_projects else 0,
        }
    except Exception as e:
        result["handoff_error"] = str(e)

    # 4. Fal.ai 生圖成本
    try:
        design_count = db.design_jobs.count_documents({"created_at": {"$gte": from_dt}})
        done_stats = list(db.design_jobs.aggregate([
            {"$match": {"created_at": {"$gte": from_dt}, "status": "done"}},
            {"$group": {"_id": None, "total_images": {"$sum": "$n_images"}}},
        ]))
        total_images = (done_stats[0]["total_images"] if done_stats else 0) or 0
        # Recraft v3 · USD 0.04 / 張(可能調價 · 用 env 覆蓋)
        per_image_usd = float(os.getenv("FAL_PER_IMAGE_USD", "0.04"))
        cost_ntd = round(total_images * per_image_usd * usd_to_ntd, 0)
        result["fal"] = {
            "jobs_count": design_count,
            "images_generated": total_images,
            "cost_ntd": cost_ntd,
            "cost_usd": round(total_images * per_image_usd, 2),
        }
    except Exception as e:
        result["fal_error"] = str(e)

    # 5. 👍 / 👎 率
    try:
        fb = list(feedback_col.aggregate([
            {"$match": {"created_at": {"$gte": from_dt}}},
            {"$group": {"_id": "$verdict", "n": {"$sum": 1}}},
        ]))
        ups = sum(f["n"] for f in fb if f["_id"] == "up")
        downs = sum(f["n"] for f in fb if f["_id"] == "down")
        total = ups + downs
        result["satisfaction"] = {
            "up": ups,
            "down": downs,
            "rate": round(ups / total * 100, 1) if total else None,
        }
    except Exception as e:
        result["satisfaction_error"] = str(e)

    return result


def librechat_contract(db) -> dict:
    """升版後第一件事:驗 LibreChat 私有 schema 是否還相容"""
    schema = probe_tx_schema(db)
    return {
        "price_version": PRICE_VERSION,
        "price_source": PRICE_SOURCE,
        "price_note": PRICE_NOTE,
        "transactions_schema_ok": schema["ok"],
        "transactions_issue": schema["issue"],
        "transactions_fingerprint_last10": tx_fingerprint(db, 10),
        "pricing_models": list(ANTHROPIC_PRICING_USD.keys()),
    }


# ============================================================
# Quota check · request-time hard stop / soft warn
# ============================================================
def quota_check(db, users_col, email: Optional[str],
                mode: str = "soft_warn",
                override_emails: set = None,
                admin_allowlist: set = None,
                user_soft_cap_ntd: float = 1200.0,
                usd_to_ntd: float = 32.5) -> dict:
    """
    Launcher 送對話前先打 · mode=hard_stop 時 pct>=100 回 allowed=False
    管理員與 override 白名單永遠 allowed=True

    Round 9 Q1 · fail-safe 策略(資料來源異常時):
    - admin / override 白名單 → 仍放行(維運不能斷)
    - 一般同仁 → 在 hard_stop 模式擋送 · 跳「資料來源暫時異常 · 請找 Champion」
    - soft_warn / off 模式維持原行為(只警告)
    """
    override_emails = override_emails or set()
    admin_allowlist = admin_allowlist or set()

    if mode == "off":
        return {"allowed": True, "mode": "off"}
    # Codex Round 10.5 黃 5 · no-email 不應直接放行 hard_stop
    # email header 可被遺漏(例如匿名 API 試打)· 若系統設 hard_stop 必須 fail-closed
    if not email:
        if mode == "hard_stop":
            return {
                "allowed": False,
                "mode": mode,
                "reason": "未帶 X-User-Email · hard_stop 模式要求 email 識別 · 請重登入",
                "fail_safe": True,
            }
        # soft_warn / off 維持放行但提醒
        return {"allowed": True, "mode": mode, "warning": "未識別使用者 · 已記錄到 audit"}
    if email in override_emails or email in admin_allowlist:
        return {"allowed": True, "mode": mode, "override": True}

    spend_result = user_month_spend_ntd(db, users_col, email, usd_to_ntd)
    cap = user_soft_cap_ntd
    spent = spend_result["spent_ntd"]

    # ========== Q1 fail-safe ==========
    # 資料來源異常 = 不可信任「0 元」· 區分 mode 處理
    if not spend_result.get("ok"):
        if mode == "hard_stop":
            return {
                "allowed": False,
                "mode": mode,
                "email": email,
                "reason": "預算資料來源暫時異常 · 為保護公司預算暫停送出 · 請找 Champion 或 Sterio 放行",
                "data_source_error": spend_result.get("reason"),
                "fail_safe": True,
            }
        # soft_warn / 其他 → 放行但警告
        return {
            "allowed": True,
            "mode": mode,
            "email": email,
            "warning": "⚠ 預算資料來源異常 · Champion 已通知檢查",
            "data_source_error": spend_result.get("reason"),
        }
    # ===================================

    pct = (spent / cap * 100) if cap else 0
    out = {
        "allowed": True,
        "mode": mode,
        "email": email,
        "spent_ntd": round(spent, 0),
        "cap_ntd": cap,
        "pct": round(pct, 1),
    }
    if pct >= 100:
        if mode == "hard_stop":
            out["allowed"] = False
            out["reason"] = f"本月已用 NT$ {round(spent)} / 上限 NT$ {round(cap)} · 請找 Champion 放行或等下個月"
        else:
            out["warning"] = f"⚠ 本月已超預算 ({round(pct)}%) · Champion 將收到通知"
    elif pct >= 80:
        out["warning"] = f"已用本月預算 {round(pct)}% · 接近上限"
    return out

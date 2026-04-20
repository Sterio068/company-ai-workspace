#!/usr/bin/env python3
"""
承富 AI · Demo 資料 seed
==========================================================

首次本機啟動後跑一次,讓系統立刻有「有內容可看」的狀態:
  - 3 個示範專案(環保局 / 文化局 / 遠傳)
  - 20 筆示範交易(含發票、支出、薪資)
  - 5 筆示範發票
  - 3 筆示範報價單
  - 10 筆示範 👍👎 回饋
  - 5 筆示範標案監測 alerts

用法:
  python3 scripts/seed-demo-data.py

⚠️ 只給 demo 用 · 生產環境第一天就要刪掉:
  curl -X DELETE http://localhost/api-accounting/admin/seed
"""
import os
import sys
import json
from datetime import datetime, timedelta

try:
    from pymongo import MongoClient
except ImportError:
    sys.exit("pip install pymongo")


MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/chengfu")


def seed():
    client = MongoClient(MONGO_URI)
    db = client.get_default_database()

    print("🌱 承富 AI · Demo 資料 seed 啟動")
    print()

    # ============================================================
    # 1. 專案(3 個代表性案)
    # ============================================================
    print("[1/6] 建立示範專案...")
    projects = [
        {
            "name": "2026 環保署海洋廢棄物整治宣導案",
            "client": "環境部環境管理署",
            "budget": 3_800_000,
            "deadline": "2026-10-31",
            "description": "6 場在地說明會 + 3 場記者會 · 主打在地共創 · 承富熟悉案型 · 預估毛利 22%",
            "status": "active",
            "owner": "王 PM",
            "created_at": datetime.utcnow() - timedelta(days=15),
            "updated_at": datetime.utcnow() - timedelta(days=2),
            "_demo": True,
        },
        {
            "name": "2026 文化局社區藝文推廣案",
            "client": "臺北市政府文化局",
            "budget": 2_200_000,
            "deadline": "2026-12-20",
            "description": "12 場社區巡演 · 初評預算偏低 · 技術分需拉高",
            "status": "active",
            "owner": "李 PM",
            "created_at": datetime.utcnow() - timedelta(days=5),
            "updated_at": datetime.utcnow() - timedelta(days=1),
            "_demo": True,
        },
        {
            "name": "遠傳電信 2026 ESG 年度活動",
            "client": "遠傳電信股份有限公司",
            "budget": 5_500_000,
            "deadline": "2026-09-30",
            "description": "企業 ESG 大會 · 一場旗艦晚宴 + 數位行銷推廣 · 毛利 25%",
            "status": "active",
            "owner": "陳 PM",
            "created_at": datetime.utcnow() - timedelta(days=30),
            "updated_at": datetime.utcnow() - timedelta(hours=8),
            "_demo": True,
        },
    ]
    db.projects.delete_many({"_demo": True})
    r = db.projects.insert_many(projects)
    project_ids = [str(i) for i in r.inserted_ids]
    print(f"   ✅ 建立 {len(project_ids)} 個專案")

    # ============================================================
    # 2. 會計科目 seed(若尚未)
    # ============================================================
    print("[2/6] 確認會計科目...")
    if db.accounting_accounts.count_documents({}) == 0:
        print("   ⚠ 請先啟動 accounting container 讓它自動 seed 科目,再重跑此腳本")
    print(f"   ✅ 科目數:{db.accounting_accounts.count_documents({})}")

    # ============================================================
    # 3. 交易 · 近 2 個月營運
    # ============================================================
    print("[3/6] 建立示範交易...")
    txs = []
    base_date = datetime.now()
    # 收入
    for i, (days_ago, amount, memo, proj) in enumerate([
        (45, 1_140_000, "環保局案期中款(30%)", 0),
        (20, 660_000, "文化局案簽約款(30%)", 1),
        (10, 1_650_000, "遠傳 ESG 案簽約款(30%)", 2),
        (5, 800_000, "前案結案款", None),
    ]):
        txs.append({
            "date": (base_date - timedelta(days=days_ago)).strftime("%Y-%m-%d"),
            "memo": memo,
            "debit_account": "1102",  # 銀行存款
            "credit_account": "4111",  # 服務收入
            "amount": amount,
            "project_id": project_ids[proj] if proj is not None else None,
            "customer": projects[proj]["client"] if proj is not None else "其他",
            "created_at": base_date - timedelta(days=days_ago),
            "_demo": True,
        })

    # 支出
    for days_ago, amount, memo, debit_code, proj in [
        (35, 180_000, "外包設計師 · 環保局 KV", "5101", 0),
        (30, 85_000, "活動攝影 · 環保局場 1", "5101", 0),
        (25, 250_000, "場地租金 · 環保局發表會", "5201", 0),
        (18, 45_000, "印刷費 · 文化局 DM", "5205", 1),
        (15, 140_000, "舞台設備租賃 · 遠傳", "5202", 2),
        (12, 68_000, "餐飲 · 遠傳記者會", "5203", 2),
        (8, 35_000, "交通費 · 各案合計", "5204", None),
        (5, 450_000, "薪資 · 本月", "5301", None),
        (3, 62_000, "辦公室租金", "5401", None),
        (1, 12_000, "軟體訂閱 · 承富 AI + Adobe", "5403", None),
    ]:
        txs.append({
            "date": (base_date - timedelta(days=days_ago)).strftime("%Y-%m-%d"),
            "memo": memo,
            "debit_account": debit_code,
            "credit_account": "1102",  # 從銀行付出
            "amount": amount,
            "project_id": project_ids[proj] if proj is not None else None,
            "created_at": base_date - timedelta(days=days_ago),
            "_demo": True,
        })
    db.accounting_transactions.delete_many({"_demo": True})
    db.accounting_transactions.insert_many(txs)
    print(f"   ✅ 建立 {len(txs)} 筆交易(4 收入 + 10 支出)")

    # ============================================================
    # 4. 發票 + 報價單
    # ============================================================
    print("[4/6] 建立示範發票與報價單...")
    db.accounting_invoices.delete_many({"_demo": True})
    db.accounting_quotes.delete_many({"_demo": True})

    invoices = [
        {
            "invoice_no": "INV-26-0001",
            "date": (base_date - timedelta(days=45)).strftime("%Y-%m-%d"),
            "customer": "環境部環境管理署",
            "customer_tax_id": "83111111",
            "items": [
                {"description": "海洋廢棄物整治宣導案 · 期中服務費", "quantity": 1, "unit_price": 1_140_000}
            ],
            "subtotal": 1_140_000,
            "tax": 57_000,
            "total": 1_197_000,
            "tax_included": False,
            "project_id": project_ids[0],
            "status": "paid",
            "_demo": True,
        },
        {
            "invoice_no": "INV-26-0002",
            "date": (base_date - timedelta(days=20)).strftime("%Y-%m-%d"),
            "customer": "臺北市政府文化局",
            "items": [{"description": "社區藝文推廣案 · 簽約款", "quantity": 1, "unit_price": 660_000}],
            "subtotal": 660_000, "tax": 33_000, "total": 693_000,
            "tax_included": False, "project_id": project_ids[1], "status": "paid", "_demo": True,
        },
        {
            "invoice_no": "INV-26-0003",
            "date": (base_date - timedelta(days=10)).strftime("%Y-%m-%d"),
            "customer": "遠傳電信股份有限公司",
            "customer_tax_id": "22099121",
            "items": [{"description": "2026 ESG 活動 · 簽約款", "quantity": 1, "unit_price": 1_650_000}],
            "subtotal": 1_650_000, "tax": 82_500, "total": 1_732_500,
            "tax_included": False, "project_id": project_ids[2], "status": "issued", "_demo": True,
        },
    ]
    db.accounting_invoices.insert_many(invoices)

    quotes = [
        {
            "quote_no": "Q-26-0015",
            "date": base_date.strftime("%Y-%m-%d"),
            "customer": "某縣市觀光局",
            "items": [
                {"description": "活動策劃", "quantity": 1, "unit_price": 800_000},
                {"description": "媒體公關", "quantity": 1, "unit_price": 400_000},
            ],
            "subtotal": 1_200_000, "tax": 60_000, "total": 1_260_000,
            "tax_included": False,
            "valid_until": (base_date + timedelta(days=30)).strftime("%Y-%m-%d"),
            "status": "sent", "_demo": True,
        },
    ]
    db.accounting_quotes.insert_many(quotes)
    print(f"   ✅ 建立 {len(invoices)} 筆發票 + {len(quotes)} 筆報價")

    # ============================================================
    # 5. 回饋樣本(10 筆)
    # ============================================================
    print("[5/6] 建立示範 👍👎 回饋...")
    db.feedback.delete_many({"_demo": True})
    feedbacks = [
        ("msg_demo_01", "🎯 投標 · 投標顧問", "up",   "建議書結構很承富風格,省 2 小時"),
        ("msg_demo_02", "🎯 投標 · 投標顧問", "up",   "Go/No-Go 8 維度清楚"),
        ("msg_demo_03", "🎯 投標 · 投標顧問", "down", "部分數據有點舊,需要更新"),
        ("msg_demo_04", "📣 公關 · 公關寫手", "up",   "AP Style 導言很精確"),
        ("msg_demo_05", "📣 公關 · 公關寫手", "up",   "社群 hook 很抓眼球"),
        ("msg_demo_06", "🎨 設計 · 設計夥伴", "up",   "主視覺方向多樣,設計師很愛"),
        ("msg_demo_07", "💰 財務 · 財務試算", "up",   "毛利試算準,協助決策"),
        ("msg_demo_08", "🎙️ 會議 · 會議速記", "up",   "會議紀錄快速省 1.5 小時"),
        ("msg_demo_09", "🎙️ 會議 · 會議速記", "down", "有些人名聽錯"),
        ("msg_demo_10", "📚 知識 · 知識庫查詢", "up", "找到 2023 的案例很有用"),
    ]
    fb_docs = [
        {"message_id": m, "agent_name": a, "verdict": v, "note": n,
         "user_email": "demo@chengfu.local",
         "created_at": base_date - timedelta(days=i),
         "_demo": True}
        for i, (m, a, v, n) in enumerate(feedbacks)
    ]
    db.feedback.insert_many(fb_docs)
    print(f"   ✅ 建立 {len(fb_docs)} 筆回饋(8👍 + 2👎)")

    # ============================================================
    # 6. 標案監測 alerts(5 筆)
    # ============================================================
    print("[6/6] 建立示範標案 alerts...")
    db.tender_alerts.delete_many({"_demo": True})
    alerts = [
        {
            "tender_key": "demo:environmental:01",
            "keyword": "環保",
            "title": "2026 新北市資源回收再利用推廣整合行銷案",
            "unit_name": "新北市政府環境保護局",
            "job_number": "demo-20260419-01",
            "brief_type": "公開招標",
            "date": 20260419,
            "discovered_at": datetime.utcnow() - timedelta(hours=4),
            "status": "new",
            "_demo": True,
        },
        {
            "tender_key": "demo:culture:01",
            "keyword": "文化",
            "title": "臺中市 2026 傳統藝術推廣計畫",
            "unit_name": "臺中市政府文化局",
            "job_number": "demo-20260418-02",
            "brief_type": "最有利標",
            "date": 20260418,
            "discovered_at": datetime.utcnow() - timedelta(days=1),
            "status": "interested",
            "_demo": True,
        },
        {
            "tender_key": "demo:tourism:01",
            "keyword": "觀光",
            "title": "澎湖離島觀光行銷整體規劃",
            "unit_name": "交通部觀光署",
            "job_number": "demo-20260417-03",
            "brief_type": "公開招標",
            "date": 20260417,
            "discovered_at": datetime.utcnow() - timedelta(days=2),
            "status": "new",
            "_demo": True,
        },
        {
            "tender_key": "demo:ai:01",
            "keyword": "AI",
            "title": "2026 政府 AI 應用宣導活動",
            "unit_name": "數位發展部",
            "job_number": "demo-20260416-04",
            "brief_type": "公開取得",
            "date": 20260416,
            "discovered_at": datetime.utcnow() - timedelta(days=3),
            "status": "skipped",
            "_demo": True,
        },
        {
            "tender_key": "demo:sustain:01",
            "keyword": "永續",
            "title": "2026 全國永續發展教育宣導",
            "unit_name": "教育部",
            "job_number": "demo-20260415-05",
            "brief_type": "最有利標",
            "date": 20260415,
            "discovered_at": datetime.utcnow() - timedelta(days=4),
            "status": "new",
            "_demo": True,
        },
    ]
    db.tender_alerts.insert_many(alerts)
    print(f"   ✅ 建立 {len(alerts)} 筆標案 alerts")

    # ============================================================
    # 完成
    # ============================================================
    print()
    print("=" * 50)
    print("✅ Demo 資料 seed 完成")
    print("=" * 50)
    print()
    print("現在打開 Launcher:")
    print("  - 首頁會看到 3 個專案 + 本月激勵資料")
    print("  - ⌘A 會計 · 看到 14 筆交易 + 3 發票 + 1 報價")
    print("  - ⌘T 標案監測 · 5 筆 alerts")
    print("  - ⌘M 管理面板 · 看到完整儀表板")
    print()
    print("⚠️  正式上線前清除 demo 資料:")
    print("    curl -X DELETE http://localhost/api-accounting/admin/demo-data")


if __name__ == "__main__":
    seed()

# -*- coding: utf-8 -*-
"""dashboard stats用のDBデータを確認"""
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor(cursor_factory=RealDictCursor)

# 全体統計
cur.execute("""
    SELECT
        COALESCE(SUM(CASE WHEN status IN ('won', 'lost') THEN profit ELSE 0 END), 0) as total_profit,
        COUNT(CASE WHEN status IN ('won', 'lost') THEN 1 END) as total_bets,
        COUNT(CASE WHEN status = 'won' THEN 1 END) as total_hits,
        COUNT(CASE WHEN status = 'lost' THEN 1 END) as total_lost,
        COALESCE(SUM(CASE WHEN status IN ('won', 'lost') THEN bet_amount ELSE 0 END), 0) as total_bet_amount,
        COALESCE(SUM(CASE WHEN status IN ('won', 'lost') THEN return_amount ELSE 0 END), 0) as total_return_amount
    FROM virtual_bets
""")
row = cur.fetchone()
print("=== 累計統計 ===")
for k, v in row.items():
    print(f"{k}: {v}")

# ステータス別カウント
cur.execute("""
    SELECT status, COUNT(*) as cnt
    FROM virtual_bets
    GROUP BY status
""")
print("\n=== ステータス別 ===")
for r in cur.fetchall():
    print(f"{r['status']}: {r['cnt']}件")

# profit/return_amountがNULLでないレコード数
cur.execute("""
    SELECT
        COUNT(*) as total,
        COUNT(profit) as with_profit,
        COUNT(return_amount) as with_return
    FROM virtual_bets
""")
r = cur.fetchone()
print(f"\n=== NULL状況 ===")
print(f"総レコード: {r['total']}")
print(f"profitあり: {r['with_profit']}")
print(f"return_amountあり: {r['with_return']}")

conn.close()

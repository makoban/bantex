# -*- coding: utf-8 -*-
"""payoffsテーブルのデータを確認"""
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor(cursor_factory=RealDictCursor)

# 今日のpayoffsを確認
cur.execute("""
    SELECT p.race_id, p.bet_type, p.combination, p.payoff, r.race_date, r.stadium_code, r.race_number
    FROM payoffs p
    JOIN races r ON p.race_id = r.id
    WHERE r.race_date = '2026-01-26'
    ORDER BY r.stadium_code, r.race_number, p.bet_type
    LIMIT 30
""")

print("race_id | date | stadium | race | bet_type | combination | payoff")
print("-" * 80)
for r in cur.fetchall():
    print(f"{r['race_id']:>7} | {r['race_date']} | {r['stadium_code']:>7} | {r['race_number']:>4} | {r['bet_type']:>8} | {r['combination']:>11} | {r['payoff']}")

# 合計件数
cur.execute("""
    SELECT COUNT(*) FROM payoffs p
    JOIN races r ON p.race_id = r.id
    WHERE r.race_date = '2026-01-26'
""")
print(f"\n今日のpayoffs合計: {cur.fetchone()['count']}件")

conn.close()

# -*- coding: utf-8 -*-
"""virtual_betsテーブルのデータを確認"""
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor(cursor_factory=RealDictCursor)

# スキップされていないレースを確認
cur.execute("""
    SELECT id, race_date, stadium_code, race_number, status, bet_type, odds, payoff, return_amount, profit, actual_result
    FROM virtual_bets
    WHERE status != 'pending'
    ORDER BY race_date DESC, id DESC
    LIMIT 20
""")

print("id | date | stadium | race | status | bet_type | odds | payoff | return | profit | result")
print("-" * 100)
for r in cur.fetchall():
    print(f"{r['id']:3} | {r['race_date']} | {r['stadium_code']:>7} | {r['race_number']:>4} | {r['status']:>10} | {r['bet_type']:>8} | {r['odds'] or '-':>6} | {r['payoff'] or '-':>6} | {r['return_amount'] or '-':>6} | {r['profit'] or '-':>6} | {r['actual_result'] or '-'}")

conn.close()

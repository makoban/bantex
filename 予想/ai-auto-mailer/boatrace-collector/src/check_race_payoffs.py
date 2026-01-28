# -*- coding: utf-8 -*-
import psycopg2
import os
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

# 桐生のstadium_code = 1 (または '01')
# racesテーブルからrace_idを取得
cur.execute("""
SELECT r.id, p.bet_type, p.combination, p.payoff
FROM payoffs p
JOIN races r ON p.race_id = r.id
WHERE r.race_date = '2026-01-25' AND r.stadium_code = 1 AND r.race_number = 1
ORDER BY p.bet_type, p.combination
""")
rows = cur.fetchall()
print(f"payoffsテーブルから取得: {len(rows)}件")
for r in rows:
    print(r)
conn.close()

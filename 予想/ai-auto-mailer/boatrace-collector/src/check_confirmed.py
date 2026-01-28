# -*- coding: utf-8 -*-
"""confirmed betsの詳細を確認"""
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor(cursor_factory=RealDictCursor)

# confirmedレコードの詳細
cur.execute("""
    SELECT vb.*, r.deadline_at, rr.first_place, rr.second_place, rr.third_place, rr.race_status
    FROM virtual_bets vb
    LEFT JOIN races r ON vb.race_date = r.race_date
        AND vb.stadium_code::int = r.stadium_code
        AND vb.race_number = r.race_number
    LEFT JOIN race_results rr ON r.id = rr.race_id
    WHERE vb.status = 'confirmed'
""")
print("=== confirmed レコード ===")
for r in cur.fetchall():
    print(f"id={r['id']}, {r['race_date']} {r['stadium_code']} {r['race_number']}R")
    print(f"  組合せ: {r['combination']}, bet_type: {r['bet_type']}")
    print(f"  締切: {r['deadline_at']}")
    print(f"  結果: {r['first_place']}-{r['second_place']}-{r['third_place']} (status: {r['race_status']})")
    print()

conn.close()

# -*- coding: utf-8 -*-
"""DBの当日番組表データを確認するスクリプト"""
import psycopg2

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# 今日の番組表データを確認
cur.execute("""
    SELECT race_date, stadium_code, race_no, boat_no, local_win_rate
    FROM historical_programs
    WHERE race_date = '20260126'
    ORDER BY stadium_code, race_no, boat_no
    LIMIT 20
""")

print("race_date | stadium | race | boat | local_win_rate")
print("-" * 55)
for r in cur.fetchall():
    print(f"{r[0]} | {r[1]:>7} | {r[2]:>4} | {r[3]:>4} | {r[4]}")

# 合計件数
cur.execute("SELECT COUNT(*) FROM historical_programs WHERE race_date = '20260126'")
count = cur.fetchone()[0]
print(f"\n合計: {count}件")

# 1号艇の当地勝率があるレース数
cur.execute("""
    SELECT COUNT(*) FROM historical_programs
    WHERE race_date = '20260126' AND boat_no = '1' AND local_win_rate IS NOT NULL
""")
boat1_count = cur.fetchone()[0]
print(f"1号艇当地勝率あり: {boat1_count}レース")

conn.close()

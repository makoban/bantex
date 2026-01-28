# -*- coding: utf-8 -*-
import psycopg2
from psycopg2.extras import RealDictCursor
import os
conn = psycopg2.connect(os.environ['DATABASE_URL'], cursor_factory=RealDictCursor)
cur = conn.cursor()

# 15パターンの会場が本日開催されているか
patterns = [('07', 4), ('07', 5), ('03', 4), ('04', 4), ('09', 4), ('10', 4), ('11', 4), ('12', 5), ('14', 4), ('15', 4), ('18', 4), ('19', 4), ('20', 4), ('21', 4), ('23', 4)]

cur.execute("SELECT DISTINCT stadium_code FROM races WHERE race_date = '2026-01-26'")
today_stadiums = set(str(row['stadium_code']).zfill(2) for row in cur.fetchall())
print('本日開催会場:', sorted(today_stadiums))

# 15パターンのうち本日開催されているもの
matching = [(s, r) for s, r in patterns if s in today_stadiums]
print('15パターン該当:', matching)

# 勝率データ確認
cur.execute("SELECT stadium_code, race_no, local_win_rate FROM historical_programs WHERE race_date = '20260126' AND boat_no = '1' LIMIT 5")
for row in cur.fetchall():
    print(f"勝率: {row}")

conn.close()

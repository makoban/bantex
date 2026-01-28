# -*- coding: utf-8 -*-
import psycopg2
from psycopg2.extras import RealDictCursor
import os

conn = psycopg2.connect(os.environ['DATABASE_URL'], cursor_factory=RealDictCursor)
cur = conn.cursor()

# 本日のレース数
cur.execute("SELECT COUNT(*) as cnt FROM races WHERE race_date = '2026-01-26'")
print('本日のレース:', cur.fetchone()['cnt'])

# 本日の購入予定
cur.execute("SELECT COUNT(*) as cnt, status FROM virtual_bets WHERE race_date = '2026-01-26' GROUP BY status")
rows = cur.fetchall()
print('本日の購入予定:')
for row in rows:
    print(f'  {row["status"]}: {row["cnt"]}')
if not rows:
    print('  なし')

# 全購入予定
cur.execute("SELECT COUNT(*) as cnt FROM virtual_bets")
print('virtual_bets総数:', cur.fetchone()['cnt'])

conn.close()

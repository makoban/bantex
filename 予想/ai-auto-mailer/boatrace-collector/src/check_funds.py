# -*- coding: utf-8 -*-
import psycopg2
from psycopg2.extras import RealDictCursor
import os

conn = psycopg2.connect(os.environ['DATABASE_URL'], cursor_factory=RealDictCursor)
cur = conn.cursor()
cur.execute('SELECT * FROM virtual_funds')
for row in cur.fetchall():
    print(f"{row['strategy_type']}: {row['current_fund']}, active={row['is_active']}")
conn.close()

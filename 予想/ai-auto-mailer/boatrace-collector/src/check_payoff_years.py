"""払戻データの年別件数を確認"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

import psycopg2

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

cur.execute('''
    SELECT EXTRACT(YEAR FROM race_date) as year, COUNT(*)
    FROM payoffs
    GROUP BY year
    ORDER BY year DESC
''')

print("=" * 40)
print("年別払戻データ件数")
print("=" * 40)
total = 0
for row in cur.fetchall():
    year = int(row[0])
    count = row[1]
    total += count
    print(f"  {year}年: {count:,}件")

print("-" * 40)
print(f"  合計: {total:,}件")
print("=" * 40)

cur.close()
conn.close()

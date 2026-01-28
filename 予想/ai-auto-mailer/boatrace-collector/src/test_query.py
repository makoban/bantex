import psycopg2
import os
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(os.environ['DATABASE_URL'], cursor_factory=RealDictCursor)
cur = conn.cursor()

# ステータス別件数
cur.execute("SELECT status, COUNT(*) as cnt FROM virtual_bets WHERE race_date = '2026-01-25' GROUP BY status")
print("=== ステータス別件数 ===")
for r in cur.fetchall():
    print(f"{r['status']}: {r['cnt']}件")

# skippedの理由を確認
cur.execute("SELECT reason FROM virtual_bets WHERE race_date = '2026-01-25' AND status = 'skipped' LIMIT 3")
print("\n=== skipped理由サンプル ===")
for r in cur.fetchall():
    print(r['reason'])

conn.close()

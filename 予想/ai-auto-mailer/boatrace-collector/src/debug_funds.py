# -*- coding: utf-8 -*-
import psycopg2
from psycopg2.extras import RealDictCursor

# Render PostgreSQL外部接続
DATABASE_URL = "postgresql://kokotomo_staging_user:QxfGN0P6WLWAMjduxR3IvMYmIDY40cxH@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"
conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
cur = conn.cursor()

print("=== virtual_funds ===")
cur.execute("SELECT * FROM virtual_funds")
for row in cur.fetchall():
    print(f"  {row['strategy_type']}: 初期={row['initial_fund']}, 現在={row['current_fund']}, 総利益={row['total_profit']}, BET数={row.get('total_bet_count', 'N/A')}")

print("\n=== 最近の購入（確定・勝敗） ===")
cur.execute("""
    SELECT id, race_date, stadium_code, race_number, strategy_type, status,
           amount, bet_amount, profit, payout
    FROM virtual_bets
    WHERE status IN ('confirmed', 'won', 'lost')
    ORDER BY race_date DESC, race_number DESC
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"  ID={row['id']}, {row['race_date']} {row['stadium_code']}-{row['race_number']}R, "
          f"status={row['status']}, amount={row.get('amount')}, bet_amount={row.get('bet_amount')}, "
          f"profit={row.get('profit')}, payout={row.get('payout')}")

print("\n=== 本日の購入状況 ===")
cur.execute("""
    SELECT status, COUNT(*), SUM(COALESCE(amount, 0)) as total_amount
    FROM virtual_bets
    WHERE race_date = CURRENT_DATE
    GROUP BY status
""")
for row in cur.fetchall():
    print(f"  {row['status']}: {row['count']}件, 合計金額={row['total_amount']}")

conn.close()

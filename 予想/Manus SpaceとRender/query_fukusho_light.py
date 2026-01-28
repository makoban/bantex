"""
号艇別 複勝回収率（軽量版）
"""

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def run_query(query):
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode='require')
    cur = conn.cursor()
    cur.execute(query)
    results = cur.fetchall()
    conn.close()
    return results

# 号艇別の複勝統計（シンプルなクエリ）
print("【号艇別 複勝統計】")
results = run_query("""
    SELECT 
        combination as boat_no,
        COUNT(*) as places,
        AVG(payout) as avg_payout
    FROM historical_payoffs
    WHERE bet_type = 'fukusho'
    GROUP BY combination
    ORDER BY combination
""")

# 複勝は1レースで2人入着なので、総レース数 = 総入着数 / 2
total_places = sum(r['places'] for r in results)
total_races = total_places / 2

print(f"総レース数（推定）: {int(total_races):,}")
print(f"\n  {'号艇':>4} | {'入着回数':>10} | {'入着率':>8} | {'平均払戻':>10} | {'回収率':>8}")
print("  " + "-" * 55)
for r in results:
    place_rate = r['places'] / total_races * 100
    avg_payout = float(r['avg_payout'])
    recovery = (r['places'] / total_races) * avg_payout
    print(f"  {r['boat_no']:>4} | {r['places']:>10,} | {place_rate:>7.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}%")

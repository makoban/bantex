"""
号艇別 複勝回収率
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

# 総レース数を取得
total_result = run_query("""
    SELECT COUNT(DISTINCT race_date || stadium_code || race_no) as total
    FROM historical_payoffs
    WHERE bet_type = 'fukusho'
""")
total_races = total_result[0]['total']
print(f"総レース数: {total_races:,}")

# 号艇別の複勝回収率
print("\n【号艇別 複勝回収率】")
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

print(f"  {'号艇':>4} | {'入着回数':>10} | {'入着率':>8} | {'平均払戻':>10} | {'回収率':>8}")
print("  " + "-" * 55)
for r in results:
    place_rate = r['places'] / total_races * 100
    avg_payout = float(r['avg_payout'])
    recovery = (r['places'] / total_races) * avg_payout
    print(f"  {r['boat_no']:>4} | {r['places']:>10,} | {place_rate:>7.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}%")

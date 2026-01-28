"""
場×R 1号艇複勝 回収率上位
"""

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

STADIUM_NAMES = {
    '01': '桐生', '02': '戸田', '03': '江戸川', '04': '平和島', '05': '多摩川', '06': '浜名湖',
    '07': '蒲郡', '08': '常滑', '09': '津', '10': '三国', '11': 'びわこ', '12': '住之江',
    '13': '尼崎', '14': '鳴門', '15': '丸亀', '16': '児島', '17': '宮島', '18': '徳山',
    '19': '下関', '20': '若松', '21': '芦屋', '22': '福岡', '23': '唐津', '24': '大村'
}

def run_query(query):
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode='require')
    cur = conn.cursor()
    cur.execute(query)
    results = cur.fetchall()
    conn.close()
    return results

# 場×R別の1号艇複勝統計
print("【場×R 1号艇複勝 回収率上位30】")
results = run_query("""
    SELECT 
        stadium_code,
        race_no,
        COUNT(*) as places,
        AVG(payout) as avg_payout
    FROM historical_payoffs
    WHERE bet_type = 'fukusho' AND combination = '1'
    GROUP BY stadium_code, race_no
    ORDER BY AVG(payout) * COUNT(*) DESC
    LIMIT 50
""")

# 各場×Rの総レース数を取得するのは重いので、入着回数と平均払戻から推定
# 複勝の場合、入着率は約67%（1号艇の場合）なので、総レース数 ≈ 入着回数 / 0.67

print(f"  {'場':>6} | {'R':>3} | {'入着':>6} | {'推定総数':>8} | {'入着率':>7} | {'平均払戻':>10} | {'回収率':>8}")
print("  " + "-" * 75)

# 全体の1号艇入着率を使って総レース数を推定
overall_place_rate = 0.6709  # 67.09%

for r in results[:30]:
    name = STADIUM_NAMES.get(r['stadium_code'], '不明')
    estimated_total = int(r['places'] / overall_place_rate)
    place_rate = r['places'] / estimated_total * 100
    avg_payout = float(r['avg_payout'])
    recovery = (r['places'] / estimated_total) * avg_payout
    marker = "★" if recovery >= 100 else ""
    print(f"  {name:>6} | {r['race_no']:>3} | {r['places']:>6} | {estimated_total:>8} | {place_rate:>6.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}% {marker}")

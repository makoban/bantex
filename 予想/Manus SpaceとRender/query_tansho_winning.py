"""
単勝で回収率上位の条件を分析
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

# 場×R別の1号艇単勝統計（平均払戻が高い順）
print("【場×R 1号艇単勝 平均払戻上位50】")
results = run_query("""
    SELECT 
        stadium_code,
        race_no,
        COUNT(*) as wins,
        AVG(payout) as avg_payout
    FROM historical_payoffs
    WHERE bet_type = 'tansho' AND combination = '1'
    GROUP BY stadium_code, race_no
    HAVING COUNT(*) >= 500
    ORDER BY AVG(payout) DESC
    LIMIT 50
""")

# 全体の1号艇勝率を使って総レース数を推定
overall_win_rate = 0.4721  # 47.21%

print(f"  {'場':>6} | {'R':>3} | {'1着':>6} | {'推定総数':>8} | {'勝率':>7} | {'平均払戻':>10} | {'回収率':>8}")
print("  " + "-" * 75)

winning_conditions = []
for r in results:
    name = STADIUM_NAMES.get(r['stadium_code'], '不明')
    estimated_total = int(r['wins'] / overall_win_rate)
    win_rate = r['wins'] / estimated_total * 100
    avg_payout = float(r['avg_payout'])
    recovery = (r['wins'] / estimated_total) * avg_payout
    marker = "★" if recovery >= 100 else ""
    print(f"  {name:>6} | {r['race_no']:>3} | {r['wins']:>6} | {estimated_total:>8} | {win_rate:>6.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}% {marker}")
    if recovery >= 95:
        winning_conditions.append({
            'stadium': name,
            'stadium_code': r['stadium_code'],
            'race_no': r['race_no'],
            'wins': r['wins'],
            'avg_payout': avg_payout,
            'recovery': recovery
        })

print("\n" + "=" * 80)
print("【回収率95%以上の条件まとめ】")
print("=" * 80)
for c in sorted(winning_conditions, key=lambda x: x['recovery'], reverse=True):
    print(f"  {c['stadium']} {c['race_no']}R: 回収率 {c['recovery']:.2f}%")

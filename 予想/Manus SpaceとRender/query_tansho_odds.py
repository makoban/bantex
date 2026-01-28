"""
単勝のオッズ別（払戻金帯別）回収率を分析
払戻金 = オッズ × 100円
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

# 1号艇単勝の払戻金帯別統計
print("=" * 80)
print("【1号艇単勝 払戻金帯別 回収率分析】")
print("=" * 80)
print("※払戻金 = オッズ × 100円")
print()

# 払戻金帯別の統計を取得
results = run_query("""
    SELECT 
        CASE 
            WHEN payout < 110 THEN '100-109円 (オッズ1.0-1.09)'
            WHEN payout < 120 THEN '110-119円 (オッズ1.1-1.19)'
            WHEN payout < 130 THEN '120-129円 (オッズ1.2-1.29)'
            WHEN payout < 140 THEN '130-139円 (オッズ1.3-1.39)'
            WHEN payout < 150 THEN '140-149円 (オッズ1.4-1.49)'
            WHEN payout < 160 THEN '150-159円 (オッズ1.5-1.59)'
            WHEN payout < 170 THEN '160-169円 (オッズ1.6-1.69)'
            WHEN payout < 180 THEN '170-179円 (オッズ1.7-1.79)'
            WHEN payout < 190 THEN '180-189円 (オッズ1.8-1.89)'
            WHEN payout < 200 THEN '190-199円 (オッズ1.9-1.99)'
            WHEN payout < 250 THEN '200-249円 (オッズ2.0-2.49)'
            WHEN payout < 300 THEN '250-299円 (オッズ2.5-2.99)'
            WHEN payout < 400 THEN '300-399円 (オッズ3.0-3.99)'
            WHEN payout < 500 THEN '400-499円 (オッズ4.0-4.99)'
            WHEN payout < 1000 THEN '500-999円 (オッズ5.0-9.99)'
            ELSE '1000円以上 (オッズ10.0以上)'
        END as payout_range,
        MIN(payout) as min_payout,
        MAX(payout) as max_payout,
        COUNT(*) as wins,
        AVG(payout) as avg_payout
    FROM historical_payoffs
    WHERE bet_type = 'tansho' AND combination = '1'
    GROUP BY 
        CASE 
            WHEN payout < 110 THEN '100-109円 (オッズ1.0-1.09)'
            WHEN payout < 120 THEN '110-119円 (オッズ1.1-1.19)'
            WHEN payout < 130 THEN '120-129円 (オッズ1.2-1.29)'
            WHEN payout < 140 THEN '130-139円 (オッズ1.3-1.39)'
            WHEN payout < 150 THEN '140-149円 (オッズ1.4-1.49)'
            WHEN payout < 160 THEN '150-159円 (オッズ1.5-1.59)'
            WHEN payout < 170 THEN '160-169円 (オッズ1.6-1.69)'
            WHEN payout < 180 THEN '170-179円 (オッズ1.7-1.79)'
            WHEN payout < 190 THEN '180-189円 (オッズ1.8-1.89)'
            WHEN payout < 200 THEN '190-199円 (オッズ1.9-1.99)'
            WHEN payout < 250 THEN '200-249円 (オッズ2.0-2.49)'
            WHEN payout < 300 THEN '250-299円 (オッズ2.5-2.99)'
            WHEN payout < 400 THEN '300-399円 (オッズ3.0-3.99)'
            WHEN payout < 500 THEN '400-499円 (オッズ4.0-4.99)'
            WHEN payout < 1000 THEN '500-999円 (オッズ5.0-9.99)'
            ELSE '1000円以上 (オッズ10.0以上)'
        END
    ORDER BY MIN(payout)
""")

# 総レース数を取得（1号艇単勝の勝利数から推定）
total_wins = sum(r['wins'] for r in results)
overall_win_rate = 0.4721  # 47.21%
total_races = int(total_wins / overall_win_rate)

print(f"総レース数（推定）: {total_races:,}")
print(f"1号艇1着回数: {total_wins:,}")
print()

print(f"{'払戻金帯':>35} | {'1着回数':>8} | {'出現率':>7} | {'平均払戻':>10} | {'回収率':>8}")
print("-" * 85)

for r in results:
    # この払戻金帯での出現率（全レース中）
    appearance_rate = r['wins'] / total_races * 100
    avg_payout = float(r['avg_payout'])
    # 回収率 = 出現率 × 平均払戻
    recovery = appearance_rate * avg_payout / 100
    
    print(f"{r['payout_range']:>35} | {r['wins']:>8,} | {appearance_rate:>6.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}%")

print()
print("=" * 80)
print("【累積回収率分析】")
print("=" * 80)
print("※特定の払戻金以上/以下のレースのみ購入した場合の回収率")
print()

# より細かい払戻金帯で累積分析
results2 = run_query("""
    SELECT 
        payout,
        COUNT(*) as wins
    FROM historical_payoffs
    WHERE bet_type = 'tansho' AND combination = '1'
    GROUP BY payout
    ORDER BY payout
""")

# 払戻金の閾値ごとに累積回収率を計算
thresholds = [100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 220, 250, 300, 350, 400, 500, 600, 700, 800, 900, 1000]

print("【払戻金下限を設定した場合の回収率】")
print(f"{'下限':>10} | {'1着回数':>10} | {'出現率':>8} | {'平均払戻':>10} | {'回収率':>8}")
print("-" * 60)

for threshold in thresholds:
    filtered = [r for r in results2 if r['payout'] >= threshold]
    if not filtered:
        continue
    wins = sum(r['wins'] for r in filtered)
    total_payout = sum(r['payout'] * r['wins'] for r in filtered)
    avg_payout = total_payout / wins if wins > 0 else 0
    appearance_rate = wins / total_races * 100
    recovery = appearance_rate * avg_payout / 100
    print(f"{threshold:>10}円 | {wins:>10,} | {appearance_rate:>7.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}%")

print()
print("【払戻金上限を設定した場合の回収率】")
print(f"{'上限':>10} | {'1着回数':>10} | {'出現率':>8} | {'平均払戻':>10} | {'回収率':>8}")
print("-" * 60)

upper_thresholds = [150, 200, 250, 300, 350, 400, 500, 600, 700, 800, 1000, 1500, 2000, 3000, 5000, 10000]

for threshold in upper_thresholds:
    filtered = [r for r in results2 if r['payout'] <= threshold]
    if not filtered:
        continue
    wins = sum(r['wins'] for r in filtered)
    total_payout = sum(r['payout'] * r['wins'] for r in filtered)
    avg_payout = total_payout / wins if wins > 0 else 0
    appearance_rate = wins / total_races * 100
    recovery = appearance_rate * avg_payout / 100
    print(f"{threshold:>10}円 | {wins:>10,} | {appearance_rate:>7.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}%")

print()
print("【払戻金範囲を設定した場合の回収率】")
print(f"{'範囲':>20} | {'1着回数':>10} | {'出現率':>8} | {'平均払戻':>10} | {'回収率':>8}")
print("-" * 70)

ranges = [
    (100, 150), (100, 200), (100, 300), (100, 500),
    (150, 300), (150, 400), (150, 500), (150, 1000),
    (200, 400), (200, 500), (200, 1000),
    (250, 500), (250, 1000),
    (300, 500), (300, 1000), (300, 2000),
]

for lower, upper in ranges:
    filtered = [r for r in results2 if lower <= r['payout'] <= upper]
    if not filtered:
        continue
    wins = sum(r['wins'] for r in filtered)
    total_payout = sum(r['payout'] * r['wins'] for r in filtered)
    avg_payout = total_payout / wins if wins > 0 else 0
    appearance_rate = wins / total_races * 100
    recovery = appearance_rate * avg_payout / 100
    print(f"{lower:>8}〜{upper:>6}円 | {wins:>10,} | {appearance_rate:>7.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}%")

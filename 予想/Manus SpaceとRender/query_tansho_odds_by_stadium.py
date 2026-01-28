"""
有効な場×R条件（戸田、平和島、多摩川、桐生）でのオッズ別回収率を分析
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

# 有効な場×R条件（回収率120%以上）
VALID_CONDITIONS = [
    ('01', ['1', '2', '3', '4']),  # 桐生
    ('02', ['1', '2', '3', '4', '6', '8']),  # 戸田
    ('04', ['1', '2', '3', '4', '6', '7', '8']),  # 平和島
    ('05', ['2', '3', '4', '5', '6', '7']),  # 多摩川
]

def run_query(query):
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode='require')
    cur = conn.cursor()
    cur.execute(query)
    results = cur.fetchall()
    conn.close()
    return results

print("=" * 80)
print("【有効な場×R条件での1号艇単勝 払戻金帯別回収率】")
print("=" * 80)
print("対象: 桐生(1-4R), 戸田(1-4,6,8R), 平和島(1-4,6-8R), 多摩川(2-7R)")
print()

# 条件に合致するデータを取得
condition_clauses = []
for stadium, races in VALID_CONDITIONS:
    race_list = "', '".join(races)
    condition_clauses.append(f"(stadium_code = '{stadium}' AND race_no IN ('{race_list}'))")

where_clause = " OR ".join(condition_clauses)

# 払戻金帯別の統計
results = run_query(f"""
    SELECT 
        payout,
        COUNT(*) as wins
    FROM historical_payoffs
    WHERE bet_type = 'tansho' AND combination = '1'
    AND ({where_clause})
    GROUP BY payout
    ORDER BY payout
""")

# 総レース数を推定
total_wins = sum(r['wins'] for r in results)
overall_win_rate = 0.4721
total_races = int(total_wins / overall_win_rate)

print(f"総レース数（推定）: {total_races:,}")
print(f"1号艇1着回数: {total_wins:,}")
print()

# 払戻金帯別の回収率
print("【払戻金帯別 回収率】")
print(f"{'払戻金帯':>25} | {'1着回数':>8} | {'出現率':>8} | {'平均払戻':>10} | {'回収率':>8}")
print("-" * 75)

ranges = [
    (100, 109, '100-109円 (1.0-1.09倍)'),
    (110, 119, '110-119円 (1.1-1.19倍)'),
    (120, 129, '120-129円 (1.2-1.29倍)'),
    (130, 139, '130-139円 (1.3-1.39倍)'),
    (140, 149, '140-149円 (1.4-1.49倍)'),
    (150, 159, '150-159円 (1.5-1.59倍)'),
    (160, 169, '160-169円 (1.6-1.69倍)'),
    (170, 179, '170-179円 (1.7-1.79倍)'),
    (180, 189, '180-189円 (1.8-1.89倍)'),
    (190, 199, '190-199円 (1.9-1.99倍)'),
    (200, 249, '200-249円 (2.0-2.49倍)'),
    (250, 299, '250-299円 (2.5-2.99倍)'),
    (300, 399, '300-399円 (3.0-3.99倍)'),
    (400, 499, '400-499円 (4.0-4.99倍)'),
    (500, 999, '500-999円 (5.0-9.99倍)'),
    (1000, 99999, '1000円以上 (10.0倍以上)'),
]

for lower, upper, label in ranges:
    filtered = [r for r in results if lower <= r['payout'] <= upper]
    if not filtered:
        continue
    wins = sum(r['wins'] for r in filtered)
    total_payout = sum(r['payout'] * r['wins'] for r in filtered)
    avg_payout = total_payout / wins if wins > 0 else 0
    appearance_rate = wins / total_races * 100
    recovery = appearance_rate * avg_payout / 100
    marker = "★" if recovery >= 100 else ""
    print(f"{label:>25} | {wins:>8,} | {appearance_rate:>7.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}% {marker}")

print()
print("=" * 80)
print("【払戻金下限を設定した場合の回収率】")
print("=" * 80)
print(f"{'下限':>10} | {'1着回数':>10} | {'出現率':>8} | {'平均払戻':>10} | {'回収率':>8}")
print("-" * 65)

thresholds = [100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 220, 250, 300, 350, 400, 500, 600, 700, 800, 1000]

for threshold in thresholds:
    filtered = [r for r in results if r['payout'] >= threshold]
    if not filtered:
        continue
    wins = sum(r['wins'] for r in filtered)
    total_payout = sum(r['payout'] * r['wins'] for r in filtered)
    avg_payout = total_payout / wins if wins > 0 else 0
    appearance_rate = wins / total_races * 100
    recovery = appearance_rate * avg_payout / 100
    marker = "★" if recovery >= 100 else ""
    print(f"{threshold:>10}円 | {wins:>10,} | {appearance_rate:>7.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}% {marker}")

print()
print("=" * 80)
print("【払戻金上限を設定した場合の回収率】")
print("=" * 80)
print(f"{'上限':>10} | {'1着回数':>10} | {'出現率':>8} | {'平均払戻':>10} | {'回収率':>8}")
print("-" * 65)

upper_thresholds = [150, 200, 250, 300, 350, 400, 500, 600, 700, 800, 1000, 1500, 2000, 3000, 5000]

for threshold in upper_thresholds:
    filtered = [r for r in results if r['payout'] <= threshold]
    if not filtered:
        continue
    wins = sum(r['wins'] for r in filtered)
    total_payout = sum(r['payout'] * r['wins'] for r in filtered)
    avg_payout = total_payout / wins if wins > 0 else 0
    appearance_rate = wins / total_races * 100
    recovery = appearance_rate * avg_payout / 100
    marker = "★" if recovery >= 100 else ""
    print(f"{threshold:>10}円 | {wins:>10,} | {appearance_rate:>7.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}% {marker}")

print()
print("=" * 80)
print("【払戻金範囲を設定した場合の回収率】")
print("=" * 80)
print(f"{'範囲':>20} | {'1着回数':>10} | {'出現率':>8} | {'平均払戻':>10} | {'回収率':>8}")
print("-" * 70)

ranges_combo = [
    (100, 200), (100, 300), (100, 400), (100, 500), (100, 1000),
    (150, 300), (150, 400), (150, 500), (150, 600), (150, 700), (150, 800), (150, 1000),
    (200, 400), (200, 500), (200, 600), (200, 700), (200, 800), (200, 1000),
    (250, 500), (250, 600), (250, 700), (250, 800), (250, 1000),
    (300, 500), (300, 600), (300, 700), (300, 800), (300, 1000),
]

for lower, upper in ranges_combo:
    filtered = [r for r in results if lower <= r['payout'] <= upper]
    if not filtered:
        continue
    wins = sum(r['wins'] for r in filtered)
    total_payout = sum(r['payout'] * r['wins'] for r in filtered)
    avg_payout = total_payout / wins if wins > 0 else 0
    appearance_rate = wins / total_races * 100
    recovery = appearance_rate * avg_payout / 100
    marker = "★" if recovery >= 100 else ""
    print(f"{lower:>8}〜{upper:>6}円 | {wins:>10,} | {appearance_rate:>7.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}% {marker}")

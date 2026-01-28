"""
正しい条件でのバックテスト
bias_1_3_2nd戦略の正確な仕様:
1. 特定の競艇場×レース番号（15パターン）
2. 当地勝率 4.5〜6.0%
3. オッズ 3.0〜100.0
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get('DATABASE_URL')

# 回収率110%以上と検証された15パターン
TARGET_CONDITIONS = [
    ('11', 4),   # 琵琶湖 4R - 122.9%
    ('18', 10),  # 徳山 10R - 122.2%
    ('13', 4),   # 尼崎 4R - 116.4%
    ('18', 6),   # 徳山 6R - 114.9%
    ('05', 2),   # 多摩川 2R - 114.6%
    ('11', 2),   # 琵琶湖 2R - 114.5%
    ('24', 4),   # 大村 4R - 114.0%
    ('05', 4),   # 多摩川 4R - 113.5%
    ('11', 5),   # 琵琶湖 5R - 112.1%
    ('11', 9),   # 琵琶湖 9R - 112.0%
    ('18', 3),   # 徳山 3R - 111.9%
    ('05', 11),  # 多摩川 11R - 111.4%
    ('13', 6),   # 尼崎 6R - 111.0%
    ('05', 6),   # 多摩川 6R - 110.9%
    ('13', 1),   # 尼崎 1R - 110.5%
]

STADIUM_NAMES = {
    '05': '多摩川', '11': 'びわこ', '13': '尼崎',
    '18': '徳山', '24': '大村'
}

def main():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    print("=" * 70)
    print("bias_1_3_2nd 正確な仕様でのバックテスト")
    print("条件: 15パターン + 当地勝率4.5-6.0% + オッズ3.0-100.0")
    print("=" * 70)

    # 15パターンをSQL用に変換
    conditions_sql = " OR ".join([
        f"(hp.stadium_code = '{s}' AND hp.race_no = '{r:02d}')"
        for s, r in TARGET_CONDITIONS
    ])

    # クエリ実行
    query = f"""
        WITH target_races AS (
            SELECT hp.race_date, hp.stadium_code, hp.race_no
            FROM historical_programs hp
            WHERE hp.boat_no = '1'
            AND CAST(hp.local_win_rate AS FLOAT) >= 4.5
            AND CAST(hp.local_win_rate AS FLOAT) <= 6.0
            AND ({conditions_sql})
        )
        SELECT
            COUNT(DISTINCT (tr.race_date, tr.stadium_code, tr.race_no)) as total_races,
            COUNT(p.payout) as hits,
            SUM(COALESCE(p.payout, 0)) as total_payout
        FROM target_races tr
        LEFT JOIN historical_payoffs p
            ON tr.race_date = p.race_date
            AND tr.stadium_code = p.stadium_code
            AND tr.race_no = p.race_no
            AND p.bet_type = 'nirentan'
            AND p.combination = '1-3'
    """

    cur.execute(query)
    row = cur.fetchone()

    if row and row['total_races'] > 0:
        roi = row['total_payout'] / (row['total_races'] * 100) * 100
        hit_rate = row['hits'] / row['total_races'] * 100
        print(f"\n【正確な条件】bias_1_3_2nd (15パターン + 勝率4.5-6.0%)")
        print(f"  対象レース: {row['total_races']:,}")
        print(f"  的中数: {row['hits']:,} ({hit_rate:.2f}%)")
        print(f"  払戻合計: {row['total_payout']:,}")
        print(f"  ROI: {roi:.1f}%")
        if roi > 100:
            print("  ★★★ 100%超え！ ★★★")

    # 各パターン別のROIも確認
    print("\n" + "=" * 70)
    print("15パターン個別のROI")
    print("=" * 70)
    print(f"{'場':>8} {'R':>3} {'レース数':>10} {'的中':>8} {'ROI':>8}")
    print("-" * 50)

    for stadium_code, race_no in TARGET_CONDITIONS:
        query = f"""
            WITH target_races AS (
                SELECT hp.race_date, hp.stadium_code, hp.race_no
                FROM historical_programs hp
                WHERE hp.boat_no = '1'
                AND CAST(hp.local_win_rate AS FLOAT) >= 4.5
                AND CAST(hp.local_win_rate AS FLOAT) <= 6.0
                AND hp.stadium_code = '{stadium_code}'
                AND hp.race_no = '{race_no:02d}'
            )
            SELECT
                COUNT(DISTINCT (tr.race_date, tr.stadium_code, tr.race_no)) as total_races,
                COUNT(p.payout) as hits,
                SUM(COALESCE(p.payout, 0)) as total_payout
            FROM target_races tr
            LEFT JOIN historical_payoffs p
                ON tr.race_date = p.race_date
                AND tr.stadium_code = p.stadium_code
                AND tr.race_no = p.race_no
                AND p.bet_type = 'nirentan'
                AND p.combination = '1-3'
        """
        cur.execute(query)
        row = cur.fetchone()

        if row and row['total_races'] > 0:
            roi = row['total_payout'] / (row['total_races'] * 100) * 100
            name = STADIUM_NAMES.get(stadium_code, stadium_code)
            marker = " ★" if roi > 100 else ""
            print(f"{name:>8} {race_no:>3}R {row['total_races']:>10,} {row['hits']:>8,} {roi:>7.1f}%{marker}")

    conn.close()
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()

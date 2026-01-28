"""
現行戦略と新戦略のROI比較
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get('DATABASE_URL')

def main():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    print("=" * 60)
    print("現行戦略 vs 新戦略 ROI比較")
    print("=" * 60)

    # 現行bias_1_3_2nd戦略のROI（当地勝率4.5-6.0%）
    cur.execute("""
        WITH filtered AS (
            SELECT hp.race_date, hp.stadium_code, hp.race_no
            FROM historical_programs hp
            WHERE hp.boat_no = '1'
            AND CAST(hp.local_win_rate AS FLOAT) >= 4.5
            AND CAST(hp.local_win_rate AS FLOAT) <= 6.0
        )
        SELECT
            COUNT(DISTINCT (f.race_date, f.stadium_code, f.race_no)) as total_races,
            COUNT(p.payout) as hits,
            SUM(COALESCE(p.payout, 0)) as total_payout
        FROM filtered f
        LEFT JOIN historical_payoffs p
            ON f.race_date = p.race_date
            AND f.stadium_code = p.stadium_code
            AND f.race_no = p.race_no
            AND p.bet_type = 'nirentan'
            AND p.combination = '1-3'
    """)
    row = cur.fetchone()
    if row and row['total_races'] > 0:
        roi = row['total_payout'] / (row['total_races'] * 100) * 100
        hit_rate = row['hits'] / row['total_races'] * 100
        print("\n【現行戦略】bias_1_3_2nd (当地勝率4.5-6.0%)")
        print(f"  対象レース: {row['total_races']:,}")
        print(f"  的中数: {row['hits']:,} ({hit_rate:.2f}%)")
        print(f"  払戻合計: {row['total_payout']:,}")
        print(f"  ROI: {roi:.1f}%")

    # 新戦略: 1号艇単勝10倍以上時に1-3
    cur.execute("""
        WITH boat1_high_odds AS (
            SELECT DISTINCT race_date, stadium_code, race_no
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
            AND combination = '1'
            AND payout >= 1000
        )
        SELECT
            COUNT(DISTINCT (bho.race_date, bho.stadium_code, bho.race_no)) as total_races,
            COUNT(p.payout) as hits,
            SUM(COALESCE(p.payout, 0)) as total_payout,
            AVG(p.payout) as avg_payout
        FROM boat1_high_odds bho
        LEFT JOIN historical_payoffs p
            ON bho.race_date = p.race_date
            AND bho.stadium_code = p.stadium_code
            AND bho.race_no = p.race_no
            AND p.bet_type = 'nirentan'
            AND p.combination = '1-3'
    """)
    row = cur.fetchone()
    if row and row['total_races'] > 0:
        roi = row['total_payout'] / (row['total_races'] * 100) * 100
        hit_rate = row['hits'] / row['total_races'] * 100
        print("\n【新戦略】1号艇単勝10倍以上時 1-3")
        print(f"  対象レース: {row['total_races']:,}")
        print(f"  的中数: {row['hits']:,} ({hit_rate:.2f}%)")
        print(f"  平均払戻: {float(row['avg_payout']):,.0f}円")
        print(f"  払戻合計: {row['total_payout']:,}")
        print(f"  ROI: {roi:.1f}%")

    conn.close()
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()

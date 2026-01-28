"""
Benter(1994)論文ベースのバックテストスクリプト

20年分の競艇過去データを使って、回収率100%超えの戦略を探索する。
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def analyze_hypothesis_1_high_odds_win():
    """
    仮説1: 高オッズ単勝（100倍超）の逆バイアス
    極端な穴馬が過小評価されている可能性を検証
    """
    print("\n" + "="*60)
    print("【仮説1】高オッズ単勝の回収率分析")
    print("="*60)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 単勝払戻金のオッズ帯別ROI
            cur.execute("""
                SELECT
                    CASE
                        WHEN payout >= 10000 THEN '100x以上'
                        WHEN payout >= 5000 THEN '50-100x'
                        WHEN payout >= 3000 THEN '30-50x'
                        WHEN payout >= 2000 THEN '20-30x'
                        WHEN payout >= 1000 THEN '10-20x'
                        ELSE '10x未満'
                    END as odds_range,
                    COUNT(*) as win_count,
                    AVG(payout) as avg_payout,
                    MIN(payout) as min_payout,
                    MAX(payout) as max_payout
                FROM historical_payoffs
                WHERE bet_type = 'tansho'
                AND payout > 0
                GROUP BY
                    CASE
                        WHEN payout >= 10000 THEN '100x以上'
                        WHEN payout >= 5000 THEN '50-100x'
                        WHEN payout >= 3000 THEN '30-50x'
                        WHEN payout >= 2000 THEN '20-30x'
                        WHEN payout >= 1000 THEN '10-20x'
                        ELSE '10x未満'
                    END
                ORDER BY MIN(payout)
            """)

            results = cur.fetchall()
            print(f"\n{'オッズ帯':<12} {'的中数':>10} {'平均払戻':>10} {'最小':>8} {'最大':>8}")
            print("-" * 60)
            for row in results:
                print(f"{row['odds_range']:<12} {row['win_count']:>10,} {float(row['avg_payout']):>10,.0f} {row['min_payout']:>8} {row['max_payout']:>8}")

    finally:
        conn.close()


def analyze_hypothesis_2_stadium_boat():
    """
    仮説2: 競艇場×枠番の相関
    特定の競艇場で特定の枠番が過小評価されている可能性
    """
    print("\n" + "="*60)
    print("【仮説2】競艇場×枠番のROI分析（単勝）")
    print("="*60)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 競艇場×枠番の単勝ROI（その枠を毎回買った場合）
            cur.execute("""
                WITH race_counts AS (
                    SELECT stadium_code, COUNT(DISTINCT (race_date, race_no)) as total_races
                    FROM historical_race_results
                    GROUP BY stadium_code
                ),
                wins AS (
                    SELECT
                        r.stadium_code,
                        r.boat_no,
                        COUNT(*) as wins,
                        SUM(COALESCE(p.payout, 0)) as total_payout
                    FROM historical_race_results r
                    LEFT JOIN historical_payoffs p
                        ON r.race_date = p.race_date
                        AND r.stadium_code = p.stadium_code
                        AND r.race_no = p.race_no
                        AND p.bet_type = 'tansho'
                        AND p.combination = r.boat_no
                    WHERE r.rank = '1'
                    GROUP BY r.stadium_code, r.boat_no
                )
                SELECT
                    w.stadium_code,
                    w.boat_no,
                    w.wins,
                    rc.total_races,
                    ROUND(w.wins * 100.0 / rc.total_races, 2) as win_rate,
                    ROUND(w.total_payout / (rc.total_races * 100.0) * 100, 1) as roi
                FROM wins w
                JOIN race_counts rc ON w.stadium_code = rc.stadium_code
                WHERE w.boat_no IN ('1', '2', '3', '4', '5', '6')
                ORDER BY roi DESC
                LIMIT 30
            """)

            results = cur.fetchall()
            print(f"\n{'場':>4} {'枠':>3} {'勝利数':>10} {'総レース':>10} {'勝率':>8} {'ROI':>8}")
            print("-" * 60)
            for row in results:
                print(f"{row['stadium_code']:>4} {row['boat_no']:>3} {row['wins']:>10,} {row['total_races']:>10,} {float(row['win_rate']):>7.1f}% {float(row['roi']):>7.1f}%")

    finally:
        conn.close()


def analyze_hypothesis_3_local_win_rate():
    """
    仮説3: 当地勝率の閾値調整
    1号艇の当地勝率をさらに細かく分析
    """
    print("\n" + "="*60)
    print("【仮説3】1号艇当地勝率×1-3二連のROI分析")
    print("="*60)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 1号艇の当地勝率帯別 × 1-3二連単/複のROI
            cur.execute("""
                WITH boat1_programs AS (
                    SELECT
                        race_date, stadium_code, race_no,
                        CASE
                            WHEN CAST(local_win_rate AS FLOAT) < 3.0 THEN '0-3%'
                            WHEN CAST(local_win_rate AS FLOAT) < 4.0 THEN '3-4%'
                            WHEN CAST(local_win_rate AS FLOAT) < 4.5 THEN '4-4.5%'
                            WHEN CAST(local_win_rate AS FLOAT) < 5.0 THEN '4.5-5%'
                            WHEN CAST(local_win_rate AS FLOAT) < 5.5 THEN '5-5.5%'
                            WHEN CAST(local_win_rate AS FLOAT) < 6.0 THEN '5.5-6%'
                            WHEN CAST(local_win_rate AS FLOAT) < 6.5 THEN '6-6.5%'
                            WHEN CAST(local_win_rate AS FLOAT) < 7.0 THEN '6.5-7%'
                            ELSE '7%以上'
                        END as win_rate_band,
                        CAST(local_win_rate AS FLOAT) as local_win_rate
                    FROM historical_programs
                    WHERE boat_no = '1'
                    AND local_win_rate IS NOT NULL
                    AND CAST(local_win_rate AS FLOAT) > 0
                )
                SELECT
                    bp.win_rate_band,
                    COUNT(DISTINCT (bp.race_date, bp.stadium_code, bp.race_no)) as total_races,
                    COUNT(p.payout) as hits,
                    SUM(COALESCE(p.payout, 0)) as total_payout,
                    ROUND(SUM(COALESCE(p.payout, 0)) / NULLIF(COUNT(DISTINCT (bp.race_date, bp.stadium_code, bp.race_no)) * 100.0, 0) * 100, 1) as roi
                FROM boat1_programs bp
                LEFT JOIN historical_payoffs p
                    ON bp.race_date = p.race_date
                    AND bp.stadium_code = p.stadium_code
                    AND bp.race_no = p.race_no
                    AND p.bet_type = 'nirentan'
                    AND p.combination = '1-3'
                GROUP BY bp.win_rate_band
                ORDER BY MIN(bp.local_win_rate)
            """)

            results = cur.fetchall()
            print(f"\n{'勝率帯':<10} {'レース数':>10} {'的中':>8} {'払戻計':>12} {'ROI':>8}")
            print("-" * 60)
            for row in results:
                roi = float(row['roi']) if row['roi'] else 0
                marker = " ★" if roi > 100 else ""
                print(f"{row['win_rate_band']:<10} {row['total_races']:>10,} {row['hits']:>8,} {row['total_payout']:>12,} {roi:>7.1f}%{marker}")

    finally:
        conn.close()


def analyze_hypothesis_4_race_number():
    """
    仮説4: レース番号（時間帯）効果
    1R vs 12Rで1号艇の期待値に差があるか
    """
    print("\n" + "="*60)
    print("【仮説4】レース番号別 1-3二連のROI分析")
    print("="*60)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    CAST(p.race_no AS INTEGER) as race_number,
                    COUNT(*) as hits,
                    AVG(p.payout) as avg_payout
                FROM historical_payoffs p
                WHERE p.bet_type = 'nirentan'
                AND p.combination = '1-3'
                GROUP BY CAST(p.race_no AS INTEGER)
                ORDER BY CAST(p.race_no AS INTEGER)
            """)

            results = cur.fetchall()

            # 総レース数を取得
            cur.execute("""
                SELECT
                    CAST(race_no AS INTEGER) as race_number,
                    COUNT(DISTINCT (race_date, stadium_code, race_no)) as total
                FROM historical_race_results
                GROUP BY CAST(race_no AS INTEGER)
            """)
            totals = {row['race_number']: row['total'] for row in cur.fetchall()}

            print(f"\n{'R':>3} {'的中':>10} {'総レース':>10} {'的中率':>8} {'平均払戻':>10} {'ROI':>8}")
            print("-" * 60)
            for row in results:
                race_no = row['race_number']
                total = totals.get(race_no, 0)
                hit_rate = row['hits'] / total * 100 if total > 0 else 0
                roi = float(row['avg_payout']) * row['hits'] / (total * 100) * 100 if total > 0 else 0
                marker = " ★" if roi > 100 else ""
                print(f"{race_no:>3} {row['hits']:>10,} {total:>10,} {hit_rate:>7.1f}% {float(row['avg_payout']):>10,.0f} {roi:>7.1f}%{marker}")

    finally:
        conn.close()


def analyze_hypothesis_5_nirenpuku_1_3():
    """
    仮説5: 1-3二連複の分析（2連単との比較）
    """
    print("\n" + "="*60)
    print("【仮説5】1-3 二連単 vs 二連複 のROI比較")
    print("="*60)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 二連単 1-3
            cur.execute("""
                SELECT
                    bet_type,
                    COUNT(*) as hits,
                    AVG(payout) as avg_payout,
                    SUM(payout) as total_payout
                FROM historical_payoffs
                WHERE combination = '1-3'
                AND bet_type IN ('nirentan', 'nirenpuku')
                GROUP BY bet_type
            """)
            results = cur.fetchall()

            # 総レース数
            cur.execute("""
                SELECT COUNT(DISTINCT (race_date, stadium_code, race_no)) as total
                FROM historical_race_results
            """)
            total_races = cur.fetchone()['total']

            print(f"\n総レース数: {total_races:,}")
            print(f"\n{'種別':<12} {'的中':>10} {'平均払戻':>10} {'ROI':>8}")
            print("-" * 50)
            for row in results:
                roi = float(row['total_payout']) / (total_races * 100) * 100
                bet_name = "二連単" if row['bet_type'] == 'nirentan' else "二連複"
                marker = " ★" if roi > 100 else ""
                print(f"{bet_name:<12} {row['hits']:>10,} {float(row['avg_payout']):>10,.0f} {roi:>7.1f}%{marker}")

    finally:
        conn.close()


def analyze_combined_filter():
    """
    複合フィルター: 当地勝率 + レース番号 + オッズ帯
    """
    print("\n" + "="*60)
    print("【複合】当地勝率4.5-6.0% × レース番号別 ROI")
    print("="*60)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                WITH filtered_races AS (
                    SELECT
                        hp.race_date, hp.stadium_code, hp.race_no
                    FROM historical_programs hp
                    WHERE hp.boat_no = '1'
                    AND CAST(hp.local_win_rate AS FLOAT) >= 4.5
                    AND CAST(hp.local_win_rate AS FLOAT) <= 6.0
                )
                SELECT
                    CAST(fr.race_no AS INTEGER) as race_number,
                    COUNT(DISTINCT (fr.race_date, fr.stadium_code, fr.race_no)) as total_races,
                    COUNT(p.payout) as hits,
                    SUM(COALESCE(p.payout, 0)) as total_payout,
                    ROUND(SUM(COALESCE(p.payout, 0)) / NULLIF(COUNT(DISTINCT (fr.race_date, fr.stadium_code, fr.race_no)) * 100.0, 0) * 100, 1) as roi
                FROM filtered_races fr
                LEFT JOIN historical_payoffs p
                    ON fr.race_date = p.race_date
                    AND fr.stadium_code = p.stadium_code
                    AND fr.race_no = p.race_no
                    AND p.bet_type = 'nirentan'
                    AND p.combination = '1-3'
                GROUP BY CAST(fr.race_no AS INTEGER)
                ORDER BY CAST(fr.race_no AS INTEGER)
            """)

            results = cur.fetchall()
            print(f"\n{'R':>3} {'レース数':>10} {'的中':>8} {'払戻計':>12} {'ROI':>8}")
            print("-" * 50)
            for row in results:
                roi = float(row['roi']) if row['roi'] else 0
                marker = " ★★★" if roi > 110 else " ★" if roi > 100 else ""
                print(f"{row['race_number']:>3} {row['total_races']:>10,} {row['hits']:>8,} {row['total_payout']:>12,} {roi:>7.1f}%{marker}")

    finally:
        conn.close()


def main():
    print("="*60)
    print("Benter(1994)論文ベースのバックテスト")
    print("回収率100%超えの戦略を探索中...")
    print("="*60)

    # 各仮説を検証
    analyze_hypothesis_1_high_odds_win()
    analyze_hypothesis_2_stadium_boat()
    analyze_hypothesis_3_local_win_rate()
    analyze_hypothesis_4_race_number()
    analyze_hypothesis_5_nirenpuku_1_3()
    analyze_combined_filter()

    print("\n" + "="*60)
    print("分析完了！ ★マークがROI > 100%の条件です")
    print("="*60)


if __name__ == "__main__":
    main()

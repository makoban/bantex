"""
Benter(1994)論文ベースのバックテスト - 拡張版

Benter論文の核心：
- ファンダメンタルモデル（選手能力・モーター性能等）と大衆オッズの「乖離」が利益の源泉
- 単純なフィルターではなく、「期待値 > 1」の条件を探す

追加分析：
1. オッズ帯 × 的中率 から真のROIを計算
2. 特定競艇場 × 特定条件の組み合わせ
3. 展示タイム × オッズ乖離
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def analyze_odds_vs_hit_rate():
    """
    オッズ帯 × 的中率分析
    Benter論文の核心: オッズが示す確率 vs 実際の的中率
    """
    print("\n" + "="*60)
    print("【分析1】2連単1-3 オッズ帯別 的中率×期待値分析")
    print("="*60)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 実際の2連単1-3オッズ分布と的中率
            # odds_historyテーブルがあればそこから、なければ払戻金から逆算
            cur.execute("""
                WITH race_totals AS (
                    SELECT
                        race_date, stadium_code, race_no,
                        COUNT(DISTINCT boat_no) as boat_count
                    FROM historical_race_results
                    GROUP BY race_date, stadium_code, race_no
                ),
                nirentan_results AS (
                    SELECT
                        p.race_date, p.stadium_code, p.race_no,
                        p.payout,
                        -- オッズを100円あたりに換算
                        p.payout / 100.0 as odds,
                        CASE
                            WHEN p.payout < 300 THEN '3x未満'
                            WHEN p.payout < 500 THEN '3-5x'
                            WHEN p.payout < 1000 THEN '5-10x'
                            WHEN p.payout < 2000 THEN '10-20x'
                            WHEN p.payout < 3000 THEN '20-30x'
                            WHEN p.payout < 5000 THEN '30-50x'
                            WHEN p.payout < 10000 THEN '50-100x'
                            ELSE '100x以上'
                        END as odds_range
                    FROM historical_payoffs p
                    WHERE p.bet_type = 'nirentan'
                    AND p.combination = '1-3'
                )
                SELECT
                    odds_range,
                    COUNT(*) as hit_count,
                    AVG(payout) as avg_payout,
                    MIN(payout) as min_payout,
                    MAX(payout) as max_payout
                FROM nirentan_results
                GROUP BY odds_range
                ORDER BY MIN(payout)
            """)

            results = cur.fetchall()

            # 総レース数を取得
            cur.execute("""
                SELECT COUNT(DISTINCT (race_date, stadium_code, race_no)) as total
                FROM historical_race_results
            """)
            total_races = cur.fetchone()['total']

            print(f"\n総レース数: {total_races:,}")
            print(f"\n{'オッズ帯':<12} {'的中数':>10} {'的中率':>8} {'平均払戻':>10} {'期待値':>8} {'ROI':>8}")
            print("-" * 70)
            for row in results:
                hit_rate = row['hit_count'] / total_races * 100
                # 期待値 = 的中率 × 平均オッズ
                expected_value = (row['hit_count'] / total_races) * (float(row['avg_payout']) / 100)
                roi = expected_value * 100  # ROI%
                marker = " ★★" if roi > 100 else ""
                print(f"{row['odds_range']:<12} {row['hit_count']:>10,} {hit_rate:>7.2f}% {float(row['avg_payout']):>10,.0f} {expected_value:>7.3f} {roi:>7.1f}%{marker}")

    finally:
        conn.close()


def analyze_stadium_combination():
    """
    特定競艇場 × 1-3 戦略の詳細分析
    """
    print("\n" + "="*60)
    print("【分析2】競艇場別 1-3二連単 ROI詳細")
    print("="*60)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                WITH stadium_races AS (
                    SELECT
                        stadium_code,
                        COUNT(DISTINCT (race_date, race_no)) as total_races
                    FROM historical_race_results
                    GROUP BY stadium_code
                ),
                stadium_hits AS (
                    SELECT
                        stadium_code,
                        COUNT(*) as hits,
                        SUM(payout) as total_payout,
                        AVG(payout) as avg_payout
                    FROM historical_payoffs
                    WHERE bet_type = 'nirentan'
                    AND combination = '1-3'
                    GROUP BY stadium_code
                )
                SELECT
                    sr.stadium_code,
                    sr.total_races,
                    COALESCE(sh.hits, 0) as hits,
                    COALESCE(sh.total_payout, 0) as total_payout,
                    COALESCE(sh.avg_payout, 0) as avg_payout,
                    ROUND(COALESCE(sh.hits, 0) * 100.0 / sr.total_races, 2) as hit_rate,
                    ROUND(COALESCE(sh.total_payout, 0) / (sr.total_races * 100.0) * 100, 1) as roi
                FROM stadium_races sr
                LEFT JOIN stadium_hits sh ON sr.stadium_code = sh.stadium_code
                ORDER BY roi DESC
            """)

            results = cur.fetchall()

            stadium_names = {
                '01': '桐生', '02': '戸田', '03': 'ボートレース江戸川', '04': '平和島',
                '05': '多摩川', '06': '浜名湖', '07': '蒲郡', '08': '常滑',
                '09': '津', '10': '三国', '11': 'びわこ', '12': '住之江',
                '13': '尼崎', '14': '鳴門', '15': '丸亀', '16': '児島',
                '17': '宮島', '18': '徳山', '19': '下関', '20': '若松',
                '21': '芦屋', '22': '福岡', '23': '唐津', '24': '大村'
            }

            print(f"\n{'場コード':>6} {'場名':<8} {'レース数':>10} {'的中':>8} {'的中率':>8} {'平均払戻':>10} {'ROI':>8}")
            print("-" * 80)
            for row in results:
                name = stadium_names.get(row['stadium_code'], '不明')
                roi = float(row['roi']) if row['roi'] else 0
                marker = " ★" if roi > 80 else ""
                print(f"{row['stadium_code']:>6} {name:<8} {row['total_races']:>10,} {row['hits']:>8,} {float(row['hit_rate']):>7.2f}% {float(row['avg_payout']):>10,.0f} {roi:>7.1f}%{marker}")

    finally:
        conn.close()


def analyze_high_odds_exacta():
    """
    高オッズ2連単の分析（穴狙い戦略）
    """
    print("\n" + "="*60)
    print("【分析3】高オッズ2連単（30倍以上）の組み合わせ別ROI")
    print("="*60)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 2連単の組み合わせ別ROI（高オッズのみ）
            cur.execute("""
                WITH combo_totals AS (
                    SELECT COUNT(DISTINCT (race_date, stadium_code, race_no)) as total
                    FROM historical_race_results
                )
                SELECT
                    p.combination,
                    COUNT(*) as hits,
                    AVG(payout) as avg_payout,
                    SUM(payout) as total_payout,
                    ROUND(SUM(payout) / (ct.total * 100.0) * 100, 1) as roi
                FROM historical_payoffs p, combo_totals ct
                WHERE p.bet_type = 'nirentan'
                AND p.payout >= 3000  -- 30倍以上のみ
                GROUP BY p.combination, ct.total
                ORDER BY roi DESC
                LIMIT 20
            """)

            results = cur.fetchall()

            print(f"\n{'組合せ':>8} {'的中数':>10} {'平均払戻':>10} {'払戻計':>15} {'ROI':>8}")
            print("-" * 60)
            for row in results:
                roi = float(row['roi']) if row['roi'] else 0
                marker = " ★★" if roi > 30 else " ★" if roi > 20 else ""
                print(f"{row['combination']:>8} {row['hits']:>10,} {float(row['avg_payout']):>10,.0f} {row['total_payout']:>15,} {roi:>7.1f}%{marker}")

    finally:
        conn.close()


def analyze_boat1_underdog():
    """
    1号艇が人気薄（高オッズ）時の分析
    Benter論文: ファンダメンタルと大衆オッズの乖離
    """
    print("\n" + "="*60)
    print("【分析4】1号艇単勝が高オッズ（10倍以上）時の1-3分析")
    print("="*60)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 1号艇の単勝が高オッズ（人気薄）時に1-3を買う戦略
            cur.execute("""
                WITH boat1_high_odds AS (
                    -- 1号艇単勝が10倍以上のレース
                    SELECT DISTINCT race_date, stadium_code, race_no
                    FROM historical_payoffs
                    WHERE bet_type = 'tansho'
                    AND combination = '1'
                    AND payout >= 1000  -- 10倍以上
                )
                SELECT
                    COUNT(DISTINCT (bho.race_date, bho.stadium_code, bho.race_no)) as total_races,
                    COUNT(p.payout) as hits,
                    AVG(p.payout) as avg_payout,
                    SUM(COALESCE(p.payout, 0)) as total_payout
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
                print(f"\n1号艇単勝10倍以上のレース: {row['total_races']:,}")
                print(f"1-3二連単 的中数: {row['hits']:,} ({hit_rate:.2f}%)")
                print(f"平均払戻: {float(row['avg_payout']):,.0f}円")
                print(f"ROI: {roi:.1f}%")
                if roi > 100:
                    print("★★★ 100%超え発見！★★★")

    finally:
        conn.close()


def analyze_motor_effect():
    """
    モーター2連対率の効果分析
    """
    print("\n" + "="*60)
    print("【分析5】3号艇モーター2連対率別 1-3 ROI")
    print("理論: 3号艇の機力が高いほど1-3の価値が上がる")
    print("="*60)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 3号艇のモーター2連対率別に1-3のROIを計算
            cur.execute("""
                WITH boat3_motor AS (
                    SELECT
                        hp.race_date, hp.stadium_code, hp.race_no,
                        CASE
                            WHEN CAST(hp.motor_2nd_rate AS FLOAT) < 30 THEN '30%未満'
                            WHEN CAST(hp.motor_2nd_rate AS FLOAT) < 40 THEN '30-40%'
                            WHEN CAST(hp.motor_2nd_rate AS FLOAT) < 50 THEN '40-50%'
                            WHEN CAST(hp.motor_2nd_rate AS FLOAT) < 60 THEN '50-60%'
                            ELSE '60%以上'
                        END as motor_band
                    FROM historical_programs hp
                    WHERE hp.boat_no = '3'
                    AND hp.motor_2nd_rate IS NOT NULL
                    AND CAST(hp.motor_2nd_rate AS FLOAT) > 0
                )
                SELECT
                    bm.motor_band,
                    COUNT(DISTINCT (bm.race_date, bm.stadium_code, bm.race_no)) as total_races,
                    COUNT(p.payout) as hits,
                    SUM(COALESCE(p.payout, 0)) as total_payout,
                    ROUND(SUM(COALESCE(p.payout, 0)) / NULLIF(COUNT(DISTINCT (bm.race_date, bm.stadium_code, bm.race_no)) * 100.0, 0) * 100, 1) as roi
                FROM boat3_motor bm
                LEFT JOIN historical_payoffs p
                    ON bm.race_date = p.race_date
                    AND bm.stadium_code = p.stadium_code
                    AND bm.race_no = p.race_no
                    AND p.bet_type = 'nirentan'
                    AND p.combination = '1-3'
                GROUP BY bm.motor_band
                ORDER BY MIN(CASE
                    WHEN bm.motor_band = '30%未満' THEN 1
                    WHEN bm.motor_band = '30-40%' THEN 2
                    WHEN bm.motor_band = '40-50%' THEN 3
                    WHEN bm.motor_band = '50-60%' THEN 4
                    ELSE 5
                END)
            """)

            results = cur.fetchall()

            print(f"\n{'モーター帯':<12} {'レース数':>10} {'的中':>8} {'払戻計':>12} {'ROI':>8}")
            print("-" * 55)
            for row in results:
                roi = float(row['roi']) if row['roi'] else 0
                marker = " ★" if roi > 80 else ""
                print(f"{row['motor_band']:<12} {row['total_races']:>10,} {row['hits']:>8,} {row['total_payout']:>12,} {roi:>7.1f}%{marker}")

    finally:
        conn.close()


def analyze_combined_best():
    """
    複合条件: 最も可能性のある組み合わせ
    当地勝率 × 特定競艇場 × レース番号
    """
    print("\n" + "="*60)
    print("【分析6】複合条件探索: 競艇場 × レース番号 × 当地勝率")
    print("="*60)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 条件を組み合わせて最も高いROIを探す
            cur.execute("""
                WITH filtered AS (
                    SELECT
                        hp.race_date, hp.stadium_code, hp.race_no,
                        hp.local_win_rate
                    FROM historical_programs hp
                    WHERE hp.boat_no = '1'
                    AND CAST(hp.local_win_rate AS FLOAT) >= 4.5
                    AND CAST(hp.local_win_rate AS FLOAT) <= 6.0
                    AND CAST(hp.race_no AS INTEGER) IN (3, 4)  -- 3R, 4Rのみ
                )
                SELECT
                    f.stadium_code,
                    CAST(f.race_no AS INTEGER) as race_no,
                    COUNT(DISTINCT (f.race_date, f.stadium_code, f.race_no)) as total_races,
                    COUNT(p.payout) as hits,
                    SUM(COALESCE(p.payout, 0)) as total_payout,
                    ROUND(SUM(COALESCE(p.payout, 0)) / NULLIF(COUNT(DISTINCT (f.race_date, f.stadium_code, f.race_no)) * 100.0, 0) * 100, 1) as roi
                FROM filtered f
                LEFT JOIN historical_payoffs p
                    ON f.race_date = p.race_date
                    AND f.stadium_code = p.stadium_code
                    AND f.race_no = p.race_no
                    AND p.bet_type = 'nirentan'
                    AND p.combination = '1-3'
                GROUP BY f.stadium_code, CAST(f.race_no AS INTEGER)
                HAVING COUNT(DISTINCT (f.race_date, f.stadium_code, f.race_no)) >= 100
                ORDER BY roi DESC
                LIMIT 20
            """)

            results = cur.fetchall()

            stadium_names = {
                '01': '桐生', '02': '戸田', '03': '江戸川', '04': '平和島',
                '05': '多摩川', '06': '浜名湖', '07': '蒲郡', '08': '常滑',
                '09': '津', '10': '三国', '11': 'びわこ', '12': '住之江',
                '13': '尼崎', '14': '鳴門', '15': '丸亀', '16': '児島',
                '17': '宮島', '18': '徳山', '19': '下関', '20': '若松',
                '21': '芦屋', '22': '福岡', '23': '唐津', '24': '大村'
            }

            print(f"\n条件: 1号艇当地勝率4.5-6.0% & レース3-4R")
            print(f"\n{'場':>4} {'R':>3} {'レース数':>10} {'的中':>8} {'払戻計':>12} {'ROI':>8}")
            print("-" * 55)
            for row in results:
                name = stadium_names.get(row['stadium_code'], '??')
                roi = float(row['roi']) if row['roi'] else 0
                marker = " ★★★" if roi > 100 else " ★★" if roi > 90 else " ★" if roi > 85 else ""
                print(f"{name:>4} {row['race_no']:>3} {row['total_races']:>10,} {row['hits']:>8,} {row['total_payout']:>12,} {roi:>7.1f}%{marker}")

    finally:
        conn.close()


def main():
    print("="*60)
    print("Benter(1994)論文ベースのバックテスト - 拡張版")
    print("回収率100%超えの条件を詳細に探索中...")
    print("="*60)

    analyze_odds_vs_hit_rate()
    analyze_stadium_combination()
    analyze_high_odds_exacta()
    analyze_boat1_underdog()
    analyze_motor_effect()
    analyze_combined_best()

    print("\n" + "="*60)
    print("拡張分析完了！")
    print("★★★マークがROI100%超えの可能性がある条件")
    print("="*60)


if __name__ == "__main__":
    main()

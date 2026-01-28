"""
競艇予想 新戦略発見ツール v1.1 (簡易版)
20年分のDBデータから回収率100%超えパターンを探索
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from datetime import datetime

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    if not DATABASE_URL:
        print("エラー: DATABASE_URL環境変数を設定してください")
        sys.exit(1)
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def analyze_1_high_odds():
    """仮説1: 単勝高オッズ分析"""
    print("\n" + "="*60)
    print("仮説1: 単勝高オッズの回収率")
    print("="*60)

    conn = get_connection()
    query = """
    SELECT
        CASE
            WHEN payout >= 10000 THEN '100倍以上'
            WHEN payout >= 7650 THEN '76-100倍'
            WHEN payout >= 5000 THEN '50-76倍'
            WHEN payout >= 3000 THEN '30-50倍'
            WHEN payout >= 2000 THEN '20-30倍'
            WHEN payout >= 1000 THEN '10-20倍'
            WHEN payout >= 500 THEN '5-10倍'
            ELSE '5倍未満'
        END as odds_range,
        COUNT(*) as count,
        ROUND(SUM(payout)::numeric / (COUNT(*) * 100), 1) as return_rate
    FROM historical_payoffs
    WHERE bet_type IN ('win', 'tansho')
    GROUP BY 1
    ORDER BY MIN(payout) DESC
    """

    df = pd.read_sql(query, conn)
    conn.close()

    print(df.to_string(index=False))
    df.to_csv('results/h1_high_odds.csv', index=False, encoding='utf-8-sig')
    return df

def analyze_2_stadium_boat():
    """仮説2: 競艇場×枠番の回収率"""
    print("\n" + "="*60)
    print("仮説2: 競艇場×枠番の回収率（単勝）")
    print("="*60)

    conn = get_connection()
    query = """
    SELECT
        p.stadium_code,
        p.combination as boat_no,
        COUNT(*) as count,
        ROUND(SUM(p.payout)::numeric / (COUNT(*) * 100), 1) as return_rate
    FROM historical_payoffs p
    WHERE p.bet_type IN ('win', 'tansho')
    GROUP BY p.stadium_code, p.combination
    HAVING COUNT(*) > 5000
    ORDER BY return_rate DESC
    LIMIT 30
    """

    df = pd.read_sql(query, conn)
    conn.close()

    print("上位30:")
    print(df.to_string(index=False))
    df.to_csv('results/h2_stadium_boat.csv', index=False, encoding='utf-8-sig')

    profitable = df[df['return_rate'] >= 100]
    if not profitable.empty:
        print(f"\n★ 回収率100%超え: {len(profitable)}件!")
    return df

def analyze_3_stadium_race_1_3():
    """仮説3: 競艇場×R番号の1-3回収率"""
    print("\n" + "="*60)
    print("仮説3: 競艇場×レース番号の1-3回収率（2連複）")
    print("="*60)

    conn = get_connection()
    query = """
    SELECT
        p.stadium_code,
        p.race_no,
        COUNT(*) as count,
        ROUND(SUM(p.payout)::numeric / (COUNT(*) * 100), 1) as return_rate
    FROM historical_payoffs p
    WHERE p.bet_type IN ('2連複', 'quinella')
      AND p.combination = '1-3'
    GROUP BY p.stadium_code, p.race_no
    HAVING COUNT(*) > 1000
    ORDER BY return_rate DESC
    LIMIT 50
    """

    df = pd.read_sql(query, conn)
    conn.close()

    print("上位50:")
    print(df.to_string(index=False))
    df.to_csv('results/h3_stadium_race_1_3.csv', index=False, encoding='utf-8-sig')

    profitable = df[df['return_rate'] >= 100]
    if not profitable.empty:
        print(f"\n★ 回収率100%超え: {len(profitable)}件!")
        print(profitable.to_string(index=False))
    return df

def analyze_4_local_win_rate():
    """仮説4: 1号艇当地勝率別回収率"""
    print("\n" + "="*60)
    print("仮説4: 1号艇の当地勝率別回収率")
    print("="*60)

    conn = get_connection()
    query = """
    SELECT
        FLOOR(prog.local_win_rate) as local_win,
        COUNT(*) as races,
        ROUND(AVG(CASE WHEN res.rank = '1' THEN 1 ELSE 0 END)::numeric * 100, 1) as win_rate
    FROM historical_programs prog
    JOIN historical_race_results res
        ON prog.race_date = res.race_date
        AND prog.stadium_code = res.stadium_code
        AND prog.race_no = res.race_no
        AND prog.boat_no = res.boat_no
    WHERE prog.boat_no = '1'
        AND prog.local_win_rate IS NOT NULL
        AND prog.local_win_rate > 0
    GROUP BY 1
    HAVING COUNT(*) > 10000
    ORDER BY 1
    """

    df = pd.read_sql(query, conn)
    conn.close()

    print(df.to_string(index=False))
    df.to_csv('results/h4_local_win_rate.csv', index=False, encoding='utf-8-sig')
    return df

def analyze_5_race_number():
    """仮説5: レース番号別回収率"""
    print("\n" + "="*60)
    print("仮説5: レース番号別の1号艇勝率")
    print("="*60)

    conn = get_connection()
    query = """
    SELECT
        res.race_no,
        COUNT(*) as races,
        ROUND(AVG(CASE WHEN res.rank = '1' AND res.boat_no = '1' THEN 1 ELSE 0 END)::numeric * 100, 1) as boat1_win
    FROM historical_race_results res
    GROUP BY res.race_no
    ORDER BY res.race_no
    """

    df = pd.read_sql(query, conn)
    conn.close()

    print(df.to_string(index=False))
    df.to_csv('results/h5_race_number.csv', index=False, encoding='utf-8-sig')
    return df

def analyze_6_combination_return():
    """仮説6: 買い目別回収率"""
    print("\n" + "="*60)
    print("仮説6: 2連複買い目別回収率（上位20）")
    print("="*60)

    conn = get_connection()
    query = """
    SELECT
        p.combination,
        COUNT(*) as count,
        ROUND(SUM(p.payout)::numeric / (COUNT(*) * 100), 1) as return_rate
    FROM historical_payoffs p
    WHERE p.bet_type IN ('2連複', 'quinella')
    GROUP BY p.combination
    HAVING COUNT(*) > 10000
    ORDER BY return_rate DESC
    LIMIT 20
    """

    df = pd.read_sql(query, conn)
    conn.close()

    print(df.to_string(index=False))
    df.to_csv('results/h6_combination.csv', index=False, encoding='utf-8-sig')
    return df

def main():
    print("="*60)
    print("競艇予想 新戦略発見ツール v1.1")
    print(f"実行: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    os.makedirs('results', exist_ok=True)

    try:
        analyze_1_high_odds()
    except Exception as e:
        print(f"仮説1エラー: {e}")

    try:
        analyze_2_stadium_boat()
    except Exception as e:
        print(f"仮説2エラー: {e}")

    try:
        analyze_3_stadium_race_1_3()
    except Exception as e:
        print(f"仮説3エラー: {e}")

    try:
        analyze_4_local_win_rate()
    except Exception as e:
        print(f"仮説4エラー: {e}")

    try:
        analyze_5_race_number()
    except Exception as e:
        print(f"仮説5エラー: {e}")

    try:
        analyze_6_combination_return()
    except Exception as e:
        print(f"仮説6エラー: {e}")

    print("\n" + "="*60)
    print("分析完了! results/ フォルダを確認")
    print("="*60)

if __name__ == '__main__':
    main()

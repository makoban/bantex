"""
単勝・複勝の回収率分析スクリプト
21年分の過去データを使用して、回収率100%超えの条件を探索
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from decimal import Decimal

# データベースURL（Render.comのPostgreSQL）
DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def get_connection():
    """データベース接続を取得"""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode='require')

def analyze_tansho():
    """単勝の回収率を様々な条件で分析"""
    print("=" * 80)
    print("単勝（1着）の回収率分析")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. 全体の単勝回収率（1号艇）
    print("\n【1】1号艇単勝の全体回収率")
    cur.execute("""
        SELECT 
            COUNT(*) as total_races,
            SUM(CASE WHEN first_place = 1 THEN 1 ELSE 0 END) as wins,
            AVG(CASE WHEN first_place = 1 THEN win_odds_1 ELSE 0 END) as avg_return
        FROM historical_results
        WHERE win_odds_1 IS NOT NULL AND win_odds_1 > 0
    """)
    result = cur.fetchone()
    if result and result['total_races'] > 0:
        win_rate = result['wins'] / result['total_races'] * 100
        recovery_rate = result['avg_return'] * 100
        print(f"  総レース数: {result['total_races']:,}")
        print(f"  1着回数: {result['wins']:,}")
        print(f"  勝率: {win_rate:.2f}%")
        print(f"  回収率: {recovery_rate:.2f}%")
    
    # 2. レース番号別の回収率
    print("\n【2】レース番号別 1号艇単勝回収率")
    cur.execute("""
        SELECT 
            race_number,
            COUNT(*) as total_races,
            SUM(CASE WHEN first_place = 1 THEN 1 ELSE 0 END) as wins,
            AVG(CASE WHEN first_place = 1 THEN win_odds_1 ELSE 0 END) as avg_return
        FROM historical_results
        WHERE win_odds_1 IS NOT NULL AND win_odds_1 > 0
        GROUP BY race_number
        ORDER BY race_number
    """)
    results = cur.fetchall()
    print(f"  {'R番号':>6} | {'レース数':>10} | {'勝率':>8} | {'回収率':>8}")
    print("  " + "-" * 45)
    for r in results:
        if r['total_races'] > 0:
            win_rate = r['wins'] / r['total_races'] * 100
            recovery_rate = float(r['avg_return']) * 100
            print(f"  {r['race_number']:>6} | {r['total_races']:>10,} | {win_rate:>7.2f}% | {recovery_rate:>7.2f}%")
    
    # 3. 競艇場別の回収率
    print("\n【3】競艇場別 1号艇単勝回収率（上位10場）")
    cur.execute("""
        SELECT 
            stadium_code,
            COUNT(*) as total_races,
            SUM(CASE WHEN first_place = 1 THEN 1 ELSE 0 END) as wins,
            AVG(CASE WHEN first_place = 1 THEN win_odds_1 ELSE 0 END) as avg_return
        FROM historical_results
        WHERE win_odds_1 IS NOT NULL AND win_odds_1 > 0
        GROUP BY stadium_code
        ORDER BY AVG(CASE WHEN first_place = 1 THEN win_odds_1 ELSE 0 END) DESC
        LIMIT 10
    """)
    results = cur.fetchall()
    stadium_names = {
        '01': '桐生', '02': '戸田', '03': '江戸川', '04': '平和島', '05': '多摩川', '06': '浜名湖',
        '07': '蒲郡', '08': '常滑', '09': '津', '10': '三国', '11': 'びわこ', '12': '住之江',
        '13': '尼崎', '14': '鳴門', '15': '丸亀', '16': '児島', '17': '宮島', '18': '徳山',
        '19': '下関', '20': '若松', '21': '芦屋', '22': '福岡', '23': '唐津', '24': '大村'
    }
    print(f"  {'場コード':>8} | {'場名':>8} | {'レース数':>10} | {'勝率':>8} | {'回収率':>8}")
    print("  " + "-" * 60)
    for r in results:
        if r['total_races'] > 0:
            win_rate = r['wins'] / r['total_races'] * 100
            recovery_rate = float(r['avg_return']) * 100
            name = stadium_names.get(r['stadium_code'], '不明')
            print(f"  {r['stadium_code']:>8} | {name:>8} | {r['total_races']:>10,} | {win_rate:>7.2f}% | {recovery_rate:>7.2f}%")
    
    # 4. オッズ帯別の回収率
    print("\n【4】オッズ帯別 1号艇単勝回収率")
    cur.execute("""
        SELECT 
            CASE 
                WHEN win_odds_1 < 1.5 THEN '1.0-1.5'
                WHEN win_odds_1 < 2.0 THEN '1.5-2.0'
                WHEN win_odds_1 < 3.0 THEN '2.0-3.0'
                WHEN win_odds_1 < 5.0 THEN '3.0-5.0'
                WHEN win_odds_1 < 10.0 THEN '5.0-10.0'
                ELSE '10.0+'
            END as odds_range,
            COUNT(*) as total_races,
            SUM(CASE WHEN first_place = 1 THEN 1 ELSE 0 END) as wins,
            AVG(CASE WHEN first_place = 1 THEN win_odds_1 ELSE 0 END) as avg_return
        FROM historical_results
        WHERE win_odds_1 IS NOT NULL AND win_odds_1 > 0
        GROUP BY 
            CASE 
                WHEN win_odds_1 < 1.5 THEN '1.0-1.5'
                WHEN win_odds_1 < 2.0 THEN '1.5-2.0'
                WHEN win_odds_1 < 3.0 THEN '2.0-3.0'
                WHEN win_odds_1 < 5.0 THEN '3.0-5.0'
                WHEN win_odds_1 < 10.0 THEN '5.0-10.0'
                ELSE '10.0+'
            END
        ORDER BY MIN(win_odds_1)
    """)
    results = cur.fetchall()
    print(f"  {'オッズ帯':>10} | {'レース数':>10} | {'勝率':>8} | {'回収率':>8}")
    print("  " + "-" * 50)
    for r in results:
        if r['total_races'] > 0:
            win_rate = r['wins'] / r['total_races'] * 100
            recovery_rate = float(r['avg_return']) * 100
            print(f"  {r['odds_range']:>10} | {r['total_races']:>10,} | {win_rate:>7.2f}% | {recovery_rate:>7.2f}%")
    
    # 5. 当地勝率別の回収率（1号艇）
    print("\n【5】当地勝率別 1号艇単勝回収率")
    cur.execute("""
        SELECT 
            CASE 
                WHEN p.local_win_rate < 3.0 THEN '0-3.0'
                WHEN p.local_win_rate < 5.0 THEN '3.0-5.0'
                WHEN p.local_win_rate < 6.0 THEN '5.0-6.0'
                WHEN p.local_win_rate < 6.5 THEN '6.0-6.5'
                WHEN p.local_win_rate < 7.0 THEN '6.5-7.0'
                WHEN p.local_win_rate < 8.0 THEN '7.0-8.0'
                ELSE '8.0+'
            END as local_win_rate_range,
            COUNT(*) as total_races,
            SUM(CASE WHEN r.first_place = 1 THEN 1 ELSE 0 END) as wins,
            AVG(CASE WHEN r.first_place = 1 THEN r.win_odds_1 ELSE 0 END) as avg_return
        FROM historical_results r
        JOIN historical_programs p ON r.race_date = p.race_date 
            AND r.stadium_code = p.stadium_code 
            AND r.race_number = p.race_number
            AND p.boat_number = 1
        WHERE r.win_odds_1 IS NOT NULL AND r.win_odds_1 > 0
            AND p.local_win_rate IS NOT NULL
        GROUP BY 
            CASE 
                WHEN p.local_win_rate < 3.0 THEN '0-3.0'
                WHEN p.local_win_rate < 5.0 THEN '3.0-5.0'
                WHEN p.local_win_rate < 6.0 THEN '5.0-6.0'
                WHEN p.local_win_rate < 6.5 THEN '6.0-6.5'
                WHEN p.local_win_rate < 7.0 THEN '6.5-7.0'
                WHEN p.local_win_rate < 8.0 THEN '7.0-8.0'
                ELSE '8.0+'
            END
        ORDER BY MIN(p.local_win_rate)
    """)
    results = cur.fetchall()
    print(f"  {'当地勝率':>10} | {'レース数':>10} | {'勝率':>8} | {'回収率':>8}")
    print("  " + "-" * 50)
    for r in results:
        if r['total_races'] > 0:
            win_rate = r['wins'] / r['total_races'] * 100
            recovery_rate = float(r['avg_return']) * 100
            print(f"  {r['local_win_rate_range']:>10} | {r['total_races']:>10,} | {win_rate:>7.2f}% | {recovery_rate:>7.2f}%")
    
    # 6. 場×R×当地勝率の組み合わせで回収率100%超えを探索
    print("\n【6】場×R×当地勝率の組み合わせで回収率100%超えを探索")
    cur.execute("""
        SELECT 
            r.stadium_code,
            r.race_number,
            CASE 
                WHEN p.local_win_rate >= 7.0 THEN '7.0+'
                WHEN p.local_win_rate >= 6.5 THEN '6.5-7.0'
                WHEN p.local_win_rate >= 6.0 THEN '6.0-6.5'
                ELSE '6.0未満'
            END as local_win_rate_range,
            COUNT(*) as total_races,
            SUM(CASE WHEN r.first_place = 1 THEN 1 ELSE 0 END) as wins,
            AVG(CASE WHEN r.first_place = 1 THEN r.win_odds_1 ELSE 0 END) as avg_return
        FROM historical_results r
        JOIN historical_programs p ON r.race_date = p.race_date 
            AND r.stadium_code = p.stadium_code 
            AND r.race_number = p.race_number
            AND p.boat_number = 1
        WHERE r.win_odds_1 IS NOT NULL AND r.win_odds_1 > 0
            AND p.local_win_rate IS NOT NULL
            AND p.local_win_rate >= 6.0
        GROUP BY r.stadium_code, r.race_number,
            CASE 
                WHEN p.local_win_rate >= 7.0 THEN '7.0+'
                WHEN p.local_win_rate >= 6.5 THEN '6.5-7.0'
                WHEN p.local_win_rate >= 6.0 THEN '6.0-6.5'
                ELSE '6.0未満'
            END
        HAVING COUNT(*) >= 100
            AND AVG(CASE WHEN r.first_place = 1 THEN r.win_odds_1 ELSE 0 END) >= 1.0
        ORDER BY AVG(CASE WHEN r.first_place = 1 THEN r.win_odds_1 ELSE 0 END) DESC
        LIMIT 30
    """)
    results = cur.fetchall()
    print(f"  {'場':>4} | {'R':>3} | {'当地勝率':>10} | {'レース数':>8} | {'勝率':>8} | {'回収率':>8}")
    print("  " + "-" * 60)
    for r in results:
        if r['total_races'] > 0:
            win_rate = r['wins'] / r['total_races'] * 100
            recovery_rate = float(r['avg_return']) * 100
            name = stadium_names.get(r['stadium_code'], '不明')
            print(f"  {name:>4} | {r['race_number']:>3} | {r['local_win_rate_range']:>10} | {r['total_races']:>8,} | {win_rate:>7.2f}% | {recovery_rate:>7.2f}%")
    
    conn.close()

def analyze_fukusho():
    """複勝の回収率を分析（データがあるか確認）"""
    print("\n" + "=" * 80)
    print("複勝データの確認")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # 複勝オッズのカラムがあるか確認
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'historical_results'
        ORDER BY ordinal_position
    """)
    columns = [row['column_name'] for row in cur.fetchall()]
    print(f"\nhistorical_resultsテーブルのカラム一覧:")
    print(columns)
    
    # 複勝関連のカラムを探す
    fukusho_columns = [c for c in columns if 'place' in c.lower() or 'fukusho' in c.lower() or 'show' in c.lower()]
    print(f"\n複勝関連と思われるカラム: {fukusho_columns}")
    
    # 3連複・3連単のデータを確認
    trifecta_columns = [c for c in columns if 'trifecta' in c.lower() or 'trio' in c.lower() or '3' in c]
    print(f"\n3連関連と思われるカラム: {trifecta_columns}")
    
    conn.close()

def analyze_号艇別_tansho():
    """号艇別の単勝回収率を分析"""
    print("\n" + "=" * 80)
    print("号艇別 単勝回収率分析")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # 各号艇の単勝回収率
    for boat in range(1, 7):
        cur.execute(f"""
            SELECT 
                COUNT(*) as total_races,
                SUM(CASE WHEN first_place = {boat} THEN 1 ELSE 0 END) as wins,
                AVG(CASE WHEN first_place = {boat} THEN win_odds_{boat} ELSE 0 END) as avg_return
            FROM historical_results
            WHERE win_odds_{boat} IS NOT NULL AND win_odds_{boat} > 0
        """)
        result = cur.fetchone()
        if result and result['total_races'] > 0:
            win_rate = result['wins'] / result['total_races'] * 100
            recovery_rate = float(result['avg_return']) * 100
            print(f"\n{boat}号艇:")
            print(f"  総レース数: {result['total_races']:,}")
            print(f"  1着回数: {result['wins']:,}")
            print(f"  勝率: {win_rate:.2f}%")
            print(f"  回収率: {recovery_rate:.2f}%")
    
    conn.close()

def analyze_high_odds_tansho():
    """高オッズ帯での単勝回収率（穴狙い）"""
    print("\n" + "=" * 80)
    print("高オッズ帯（穴）単勝回収率分析")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # 各号艇の高オッズ帯での回収率
    for boat in range(1, 7):
        print(f"\n{boat}号艇（オッズ10倍以上）:")
        cur.execute(f"""
            SELECT 
                CASE 
                    WHEN win_odds_{boat} >= 10 AND win_odds_{boat} < 20 THEN '10-20'
                    WHEN win_odds_{boat} >= 20 AND win_odds_{boat} < 50 THEN '20-50'
                    WHEN win_odds_{boat} >= 50 AND win_odds_{boat} < 100 THEN '50-100'
                    WHEN win_odds_{boat} >= 100 THEN '100+'
                END as odds_range,
                COUNT(*) as total_races,
                SUM(CASE WHEN first_place = {boat} THEN 1 ELSE 0 END) as wins,
                AVG(CASE WHEN first_place = {boat} THEN win_odds_{boat} ELSE 0 END) as avg_return
            FROM historical_results
            WHERE win_odds_{boat} IS NOT NULL AND win_odds_{boat} >= 10
            GROUP BY 
                CASE 
                    WHEN win_odds_{boat} >= 10 AND win_odds_{boat} < 20 THEN '10-20'
                    WHEN win_odds_{boat} >= 20 AND win_odds_{boat} < 50 THEN '20-50'
                    WHEN win_odds_{boat} >= 50 AND win_odds_{boat} < 100 THEN '50-100'
                    WHEN win_odds_{boat} >= 100 THEN '100+'
                END
            ORDER BY MIN(win_odds_{boat})
        """)
        results = cur.fetchall()
        print(f"  {'オッズ帯':>10} | {'レース数':>10} | {'勝率':>8} | {'回収率':>8}")
        print("  " + "-" * 50)
        for r in results:
            if r['total_races'] > 0 and r['odds_range']:
                win_rate = r['wins'] / r['total_races'] * 100
                recovery_rate = float(r['avg_return']) * 100
                print(f"  {r['odds_range']:>10} | {r['total_races']:>10,} | {win_rate:>7.2f}% | {recovery_rate:>7.2f}%")
    
    conn.close()

if __name__ == "__main__":
    analyze_tansho()
    analyze_fukusho()
    analyze_号艇別_tansho()
    analyze_high_odds_tansho()

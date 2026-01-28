"""
単勝・複勝の回収率分析スクリプト v2
21年分の過去データを使用して、回収率100%超えの条件を探索
テーブル: historical_payoffs (tansho, fukusho), historical_race_results, historical_programs
"""

import psycopg2
from psycopg2.extras import RealDictCursor

# データベースURL（Render.comのPostgreSQL）
DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

STADIUM_NAMES = {
    '01': '桐生', '02': '戸田', '03': '江戸川', '04': '平和島', '05': '多摩川', '06': '浜名湖',
    '07': '蒲郡', '08': '常滑', '09': '津', '10': '三国', '11': 'びわこ', '12': '住之江',
    '13': '尼崎', '14': '鳴門', '15': '丸亀', '16': '児島', '17': '宮島', '18': '徳山',
    '19': '下関', '20': '若松', '21': '芦屋', '22': '福岡', '23': '唐津', '24': '大村'
}

def get_connection():
    """データベース接続を取得"""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode='require')

def analyze_tansho_basic():
    """単勝の基本回収率を分析"""
    print("=" * 80)
    print("単勝（tansho）の回収率分析")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. 単勝の全体統計
    print("\n【1】単勝の全体統計")
    cur.execute("""
        SELECT 
            COUNT(*) as total_races,
            AVG(payout) as avg_payout,
            MIN(payout) as min_payout,
            MAX(payout) as max_payout
        FROM historical_payoffs
        WHERE bet_type = 'tansho'
    """)
    result = cur.fetchone()
    print(f"  総レース数: {result['total_races']:,}")
    print(f"  平均払戻: {float(result['avg_payout']):.1f}円")
    print(f"  最小払戻: {result['min_payout']}円")
    print(f"  最大払戻: {result['max_payout']}円")
    
    # 2. 号艇別の単勝回収率
    print("\n【2】号艇別 単勝回収率")
    cur.execute("""
        SELECT 
            combination as boat_no,
            COUNT(*) as wins,
            AVG(payout) as avg_payout
        FROM historical_payoffs
        WHERE bet_type = 'tansho'
        GROUP BY combination
        ORDER BY combination
    """)
    results = cur.fetchall()
    
    # 全レース数を取得
    cur.execute("""
        SELECT COUNT(DISTINCT race_date || stadium_code || race_no) as total
        FROM historical_payoffs
        WHERE bet_type = 'tansho'
    """)
    total_races = cur.fetchone()['total']
    
    print(f"  {'号艇':>4} | {'1着回数':>10} | {'勝率':>8} | {'平均払戻':>10} | {'回収率':>8}")
    print("  " + "-" * 55)
    for r in results:
        win_rate = r['wins'] / total_races * 100
        avg_payout = float(r['avg_payout'])
        # 回収率 = (勝率 × 平均払戻) / 100
        recovery_rate = (r['wins'] / total_races) * avg_payout
        print(f"  {r['boat_no']:>4} | {r['wins']:>10,} | {win_rate:>7.2f}% | {avg_payout:>9.1f}円 | {recovery_rate:>7.2f}%")
    
    conn.close()

def analyze_tansho_by_stadium():
    """競艇場別の単勝回収率を分析"""
    print("\n" + "=" * 80)
    print("競艇場別 単勝回収率分析")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # 1号艇の競艇場別回収率
    print("\n【3】競艇場別 1号艇単勝回収率（上位10場）")
    cur.execute("""
        WITH stadium_stats AS (
            SELECT 
                p.stadium_code,
                COUNT(*) as wins,
                AVG(p.payout) as avg_payout
            FROM historical_payoffs p
            WHERE p.bet_type = 'tansho' AND p.combination = '1'
            GROUP BY p.stadium_code
        ),
        total_races AS (
            SELECT 
                stadium_code,
                COUNT(DISTINCT race_date || race_no) as total
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
            GROUP BY stadium_code
        )
        SELECT 
            s.stadium_code,
            s.wins,
            t.total,
            s.avg_payout,
            (s.wins::float / t.total) * s.avg_payout as recovery_rate
        FROM stadium_stats s
        JOIN total_races t ON s.stadium_code = t.stadium_code
        ORDER BY (s.wins::float / t.total) * s.avg_payout DESC
        LIMIT 15
    """)
    results = cur.fetchall()
    print(f"  {'場':>6} | {'1着回数':>8} | {'総レース':>8} | {'勝率':>7} | {'平均払戻':>10} | {'回収率':>8}")
    print("  " + "-" * 70)
    for r in results:
        name = STADIUM_NAMES.get(r['stadium_code'], '不明')
        win_rate = r['wins'] / r['total'] * 100
        avg_payout = float(r['avg_payout'])
        recovery = float(r['recovery_rate'])
        print(f"  {name:>6} | {r['wins']:>8,} | {r['total']:>8,} | {win_rate:>6.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}%")
    
    conn.close()

def analyze_tansho_by_race_number():
    """レース番号別の単勝回収率を分析"""
    print("\n" + "=" * 80)
    print("レース番号別 単勝回収率分析")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # 1号艇のレース番号別回収率
    print("\n【4】レース番号別 1号艇単勝回収率")
    cur.execute("""
        WITH race_stats AS (
            SELECT 
                p.race_no,
                COUNT(*) as wins,
                AVG(p.payout) as avg_payout
            FROM historical_payoffs p
            WHERE p.bet_type = 'tansho' AND p.combination = '1'
            GROUP BY p.race_no
        ),
        total_races AS (
            SELECT 
                race_no,
                COUNT(DISTINCT race_date || stadium_code) as total
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
            GROUP BY race_no
        )
        SELECT 
            s.race_no,
            s.wins,
            t.total,
            s.avg_payout,
            (s.wins::float / t.total) * s.avg_payout as recovery_rate
        FROM race_stats s
        JOIN total_races t ON s.race_no = t.race_no
        ORDER BY s.race_no::int
    """)
    results = cur.fetchall()
    print(f"  {'R番号':>6} | {'1着回数':>8} | {'総レース':>8} | {'勝率':>7} | {'平均払戻':>10} | {'回収率':>8}")
    print("  " + "-" * 70)
    for r in results:
        win_rate = r['wins'] / r['total'] * 100
        avg_payout = float(r['avg_payout'])
        recovery = float(r['recovery_rate'])
        print(f"  {r['race_no']:>6} | {r['wins']:>8,} | {r['total']:>8,} | {win_rate:>6.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}%")
    
    conn.close()

def analyze_tansho_by_payout_range():
    """払戻金額帯別の単勝回収率を分析"""
    print("\n" + "=" * 80)
    print("払戻金額帯別 単勝分析（穴狙い検証）")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # 各号艇の払戻金額帯別分析
    for boat in ['1', '2', '3', '4', '5', '6']:
        print(f"\n【{boat}号艇】払戻金額帯別分析")
        cur.execute("""
            WITH payout_ranges AS (
                SELECT 
                    CASE 
                        WHEN payout < 200 THEN '100-200'
                        WHEN payout < 300 THEN '200-300'
                        WHEN payout < 500 THEN '300-500'
                        WHEN payout < 1000 THEN '500-1000'
                        WHEN payout < 2000 THEN '1000-2000'
                        WHEN payout < 5000 THEN '2000-5000'
                        WHEN payout < 10000 THEN '5000-10000'
                        ELSE '10000+'
                    END as payout_range,
                    payout,
                    MIN(payout) OVER (PARTITION BY 
                        CASE 
                            WHEN payout < 200 THEN '100-200'
                            WHEN payout < 300 THEN '200-300'
                            WHEN payout < 500 THEN '300-500'
                            WHEN payout < 1000 THEN '500-1000'
                            WHEN payout < 2000 THEN '1000-2000'
                            WHEN payout < 5000 THEN '2000-5000'
                            WHEN payout < 10000 THEN '5000-10000'
                            ELSE '10000+'
                        END
                    ) as range_min
                FROM historical_payoffs
                WHERE bet_type = 'tansho' AND combination = %s
            )
            SELECT 
                payout_range,
                COUNT(*) as wins,
                AVG(payout) as avg_payout,
                MIN(range_min) as sort_key
            FROM payout_ranges
            GROUP BY payout_range
            ORDER BY MIN(range_min)
        """, (boat,))
        results = cur.fetchall()
        
        # 全レース数を取得
        cur.execute("""
            SELECT COUNT(DISTINCT race_date || stadium_code || race_no) as total
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
        """)
        total_races = cur.fetchone()['total']
        
        print(f"  {'払戻帯':>12} | {'1着回数':>8} | {'勝率':>7} | {'平均払戻':>10} | {'回収率':>8}")
        print("  " + "-" * 60)
        for r in results:
            win_rate = r['wins'] / total_races * 100
            avg_payout = float(r['avg_payout'])
            recovery = (r['wins'] / total_races) * avg_payout
            print(f"  {r['payout_range']:>12} | {r['wins']:>8,} | {win_rate:>6.3f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}%")
    
    conn.close()

def analyze_tansho_with_local_win_rate():
    """当地勝率を考慮した単勝回収率を分析"""
    print("\n" + "=" * 80)
    print("当地勝率別 1号艇単勝回収率分析")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    print("\n【5】当地勝率別 1号艇単勝回収率")
    cur.execute("""
        WITH race_with_program AS (
            SELECT 
                p.race_date,
                p.stadium_code,
                p.race_no,
                p.payout,
                pr.local_win_rate
            FROM historical_payoffs p
            JOIN historical_programs pr 
                ON p.race_date = pr.race_date 
                AND p.stadium_code = pr.stadium_code 
                AND p.race_no = pr.race_no
                AND pr.boat_no = '1'
            WHERE p.bet_type = 'tansho' AND p.combination = '1'
                AND pr.local_win_rate IS NOT NULL
        ),
        total_with_program AS (
            SELECT 
                CASE 
                    WHEN pr.local_win_rate < 3.0 THEN '0-3.0'
                    WHEN pr.local_win_rate < 5.0 THEN '3.0-5.0'
                    WHEN pr.local_win_rate < 6.0 THEN '5.0-6.0'
                    WHEN pr.local_win_rate < 6.5 THEN '6.0-6.5'
                    WHEN pr.local_win_rate < 7.0 THEN '6.5-7.0'
                    WHEN pr.local_win_rate < 8.0 THEN '7.0-8.0'
                    ELSE '8.0+'
                END as local_win_rate_range,
                COUNT(DISTINCT p.race_date || p.stadium_code || p.race_no) as total
            FROM historical_payoffs p
            JOIN historical_programs pr 
                ON p.race_date = pr.race_date 
                AND p.stadium_code = pr.stadium_code 
                AND p.race_no = pr.race_no
                AND pr.boat_no = '1'
            WHERE p.bet_type = 'tansho'
                AND pr.local_win_rate IS NOT NULL
            GROUP BY 
                CASE 
                    WHEN pr.local_win_rate < 3.0 THEN '0-3.0'
                    WHEN pr.local_win_rate < 5.0 THEN '3.0-5.0'
                    WHEN pr.local_win_rate < 6.0 THEN '5.0-6.0'
                    WHEN pr.local_win_rate < 6.5 THEN '6.0-6.5'
                    WHEN pr.local_win_rate < 7.0 THEN '6.5-7.0'
                    WHEN pr.local_win_rate < 8.0 THEN '7.0-8.0'
                    ELSE '8.0+'
                END
        )
        SELECT 
            CASE 
                WHEN r.local_win_rate < 3.0 THEN '0-3.0'
                WHEN r.local_win_rate < 5.0 THEN '3.0-5.0'
                WHEN r.local_win_rate < 6.0 THEN '5.0-6.0'
                WHEN r.local_win_rate < 6.5 THEN '6.0-6.5'
                WHEN r.local_win_rate < 7.0 THEN '6.5-7.0'
                WHEN r.local_win_rate < 8.0 THEN '7.0-8.0'
                ELSE '8.0+'
            END as local_win_rate_range,
            COUNT(*) as wins,
            AVG(r.payout) as avg_payout,
            t.total
        FROM race_with_program r
        JOIN total_with_program t ON 
            CASE 
                WHEN r.local_win_rate < 3.0 THEN '0-3.0'
                WHEN r.local_win_rate < 5.0 THEN '3.0-5.0'
                WHEN r.local_win_rate < 6.0 THEN '5.0-6.0'
                WHEN r.local_win_rate < 6.5 THEN '6.0-6.5'
                WHEN r.local_win_rate < 7.0 THEN '6.5-7.0'
                WHEN r.local_win_rate < 8.0 THEN '7.0-8.0'
                ELSE '8.0+'
            END = t.local_win_rate_range
        GROUP BY 
            CASE 
                WHEN r.local_win_rate < 3.0 THEN '0-3.0'
                WHEN r.local_win_rate < 5.0 THEN '3.0-5.0'
                WHEN r.local_win_rate < 6.0 THEN '5.0-6.0'
                WHEN r.local_win_rate < 6.5 THEN '6.0-6.5'
                WHEN r.local_win_rate < 7.0 THEN '6.5-7.0'
                WHEN r.local_win_rate < 8.0 THEN '7.0-8.0'
                ELSE '8.0+'
            END,
            t.total
        ORDER BY MIN(r.local_win_rate)
    """)
    results = cur.fetchall()
    print(f"  {'当地勝率':>10} | {'1着回数':>8} | {'総レース':>8} | {'勝率':>7} | {'平均払戻':>10} | {'回収率':>8}")
    print("  " + "-" * 75)
    for r in results:
        win_rate = r['wins'] / r['total'] * 100
        avg_payout = float(r['avg_payout'])
        recovery = (r['wins'] / r['total']) * avg_payout
        print(f"  {r['local_win_rate_range']:>10} | {r['wins']:>8,} | {r['total']:>8,} | {win_rate:>6.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}%")
    
    conn.close()

def analyze_fukusho():
    """複勝の回収率を分析"""
    print("\n" + "=" * 80)
    print("複勝（fukusho）の回収率分析")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. 複勝の全体統計
    print("\n【6】複勝の全体統計")
    cur.execute("""
        SELECT 
            COUNT(*) as total_payouts,
            AVG(payout) as avg_payout,
            MIN(payout) as min_payout,
            MAX(payout) as max_payout
        FROM historical_payoffs
        WHERE bet_type = 'fukusho'
    """)
    result = cur.fetchone()
    print(f"  総払戻数: {result['total_payouts']:,}")
    print(f"  平均払戻: {float(result['avg_payout']):.1f}円")
    print(f"  最小払戻: {result['min_payout']}円")
    print(f"  最大払戻: {result['max_payout']}円")
    
    # 2. 号艇別の複勝回収率
    print("\n【7】号艇別 複勝回収率")
    cur.execute("""
        SELECT 
            combination as boat_no,
            COUNT(*) as payouts,
            AVG(payout) as avg_payout
        FROM historical_payoffs
        WHERE bet_type = 'fukusho'
        GROUP BY combination
        ORDER BY combination
    """)
    results = cur.fetchall()
    
    # 全レース数を取得
    cur.execute("""
        SELECT COUNT(DISTINCT race_date || stadium_code || race_no) as total
        FROM historical_payoffs
        WHERE bet_type = 'fukusho'
    """)
    total_races = cur.fetchone()['total']
    
    print(f"  {'号艇':>4} | {'入着回数':>10} | {'入着率':>8} | {'平均払戻':>10} | {'回収率':>8}")
    print("  " + "-" * 55)
    for r in results:
        # 複勝は2着以内なので、入着率 = 入着回数 / 総レース数
        place_rate = r['payouts'] / total_races * 100
        avg_payout = float(r['avg_payout'])
        # 回収率 = (入着率 × 平均払戻) / 100
        recovery_rate = (r['payouts'] / total_races) * avg_payout
        print(f"  {r['boat_no']:>4} | {r['payouts']:>10,} | {place_rate:>7.2f}% | {avg_payout:>9.1f}円 | {recovery_rate:>7.2f}%")
    
    conn.close()

def analyze_fukusho_by_stadium():
    """競艇場別の複勝回収率を分析"""
    print("\n" + "=" * 80)
    print("競艇場別 複勝回収率分析")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # 1号艇の競艇場別複勝回収率
    print("\n【8】競艇場別 1号艇複勝回収率（上位10場）")
    cur.execute("""
        WITH stadium_stats AS (
            SELECT 
                p.stadium_code,
                COUNT(*) as payouts,
                AVG(p.payout) as avg_payout
            FROM historical_payoffs p
            WHERE p.bet_type = 'fukusho' AND p.combination = '1'
            GROUP BY p.stadium_code
        ),
        total_races AS (
            SELECT 
                stadium_code,
                COUNT(DISTINCT race_date || race_no) as total
            FROM historical_payoffs
            WHERE bet_type = 'fukusho'
            GROUP BY stadium_code
        )
        SELECT 
            s.stadium_code,
            s.payouts,
            t.total,
            s.avg_payout,
            (s.payouts::float / t.total) * s.avg_payout as recovery_rate
        FROM stadium_stats s
        JOIN total_races t ON s.stadium_code = t.stadium_code
        ORDER BY (s.payouts::float / t.total) * s.avg_payout DESC
        LIMIT 15
    """)
    results = cur.fetchall()
    print(f"  {'場':>6} | {'入着回数':>8} | {'総レース':>8} | {'入着率':>7} | {'平均払戻':>10} | {'回収率':>8}")
    print("  " + "-" * 70)
    for r in results:
        name = STADIUM_NAMES.get(r['stadium_code'], '不明')
        place_rate = r['payouts'] / r['total'] * 100
        avg_payout = float(r['avg_payout'])
        recovery = float(r['recovery_rate'])
        print(f"  {name:>6} | {r['payouts']:>8,} | {r['total']:>8,} | {place_rate:>6.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}%")
    
    conn.close()

def search_winning_conditions():
    """回収率100%超えの条件を探索"""
    print("\n" + "=" * 80)
    print("回収率100%超え条件の探索")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    # 場×R×当地勝率の組み合わせで回収率100%超えを探索（単勝）
    print("\n【9】場×R×当地勝率 1号艇単勝 回収率100%超え条件")
    cur.execute("""
        WITH race_with_program AS (
            SELECT 
                p.race_date,
                p.stadium_code,
                p.race_no,
                p.payout,
                pr.local_win_rate
            FROM historical_payoffs p
            JOIN historical_programs pr 
                ON p.race_date = pr.race_date 
                AND p.stadium_code = pr.stadium_code 
                AND p.race_no = pr.race_no
                AND pr.boat_no = '1'
            WHERE p.bet_type = 'tansho' AND p.combination = '1'
                AND pr.local_win_rate IS NOT NULL
                AND pr.local_win_rate >= 6.0
        ),
        total_with_program AS (
            SELECT 
                p.stadium_code,
                p.race_no,
                CASE 
                    WHEN pr.local_win_rate >= 7.0 THEN '7.0+'
                    WHEN pr.local_win_rate >= 6.5 THEN '6.5-7.0'
                    ELSE '6.0-6.5'
                END as local_win_rate_range,
                COUNT(DISTINCT p.race_date) as total
            FROM historical_payoffs p
            JOIN historical_programs pr 
                ON p.race_date = pr.race_date 
                AND p.stadium_code = pr.stadium_code 
                AND p.race_no = pr.race_no
                AND pr.boat_no = '1'
            WHERE p.bet_type = 'tansho'
                AND pr.local_win_rate IS NOT NULL
                AND pr.local_win_rate >= 6.0
            GROUP BY p.stadium_code, p.race_no,
                CASE 
                    WHEN pr.local_win_rate >= 7.0 THEN '7.0+'
                    WHEN pr.local_win_rate >= 6.5 THEN '6.5-7.0'
                    ELSE '6.0-6.5'
                END
        )
        SELECT 
            r.stadium_code,
            r.race_no,
            CASE 
                WHEN r.local_win_rate >= 7.0 THEN '7.0+'
                WHEN r.local_win_rate >= 6.5 THEN '6.5-7.0'
                ELSE '6.0-6.5'
            END as local_win_rate_range,
            COUNT(*) as wins,
            t.total,
            AVG(r.payout) as avg_payout,
            (COUNT(*)::float / t.total) * AVG(r.payout) as recovery_rate
        FROM race_with_program r
        JOIN total_with_program t ON 
            r.stadium_code = t.stadium_code
            AND r.race_no = t.race_no
            AND CASE 
                WHEN r.local_win_rate >= 7.0 THEN '7.0+'
                WHEN r.local_win_rate >= 6.5 THEN '6.5-7.0'
                ELSE '6.0-6.5'
            END = t.local_win_rate_range
        GROUP BY r.stadium_code, r.race_no,
            CASE 
                WHEN r.local_win_rate >= 7.0 THEN '7.0+'
                WHEN r.local_win_rate >= 6.5 THEN '6.5-7.0'
                ELSE '6.0-6.5'
            END,
            t.total
        HAVING COUNT(*) >= 50
            AND (COUNT(*)::float / t.total) * AVG(r.payout) >= 95
        ORDER BY (COUNT(*)::float / t.total) * AVG(r.payout) DESC
        LIMIT 30
    """)
    results = cur.fetchall()
    print(f"  {'場':>6} | {'R':>3} | {'当地勝率':>10} | {'1着':>6} | {'総数':>6} | {'勝率':>7} | {'平均払戻':>10} | {'回収率':>8}")
    print("  " + "-" * 85)
    for r in results:
        name = STADIUM_NAMES.get(r['stadium_code'], '不明')
        win_rate = r['wins'] / r['total'] * 100
        avg_payout = float(r['avg_payout'])
        recovery = float(r['recovery_rate'])
        marker = "★" if recovery >= 100 else ""
        print(f"  {name:>6} | {r['race_no']:>3} | {r['local_win_rate_range']:>10} | {r['wins']:>6} | {r['total']:>6} | {win_rate:>6.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}% {marker}")
    
    conn.close()

if __name__ == "__main__":
    analyze_tansho_basic()
    analyze_tansho_by_stadium()
    analyze_tansho_by_race_number()
    analyze_tansho_with_local_win_rate()
    analyze_fukusho()
    analyze_fukusho_by_stadium()
    search_winning_conditions()

"""
単勝・複勝の回収率分析スクリプト v3
接続タイムアウト対策版
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
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode='require',
                           connect_timeout=30, options='-c statement_timeout=300000')
    return conn

def run_query(query, params=None):
    """クエリを実行して結果を返す"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        results = cur.fetchall()
        return results
    finally:
        conn.close()

def analyze_tansho_basic():
    """単勝の基本回収率を分析"""
    print("=" * 80)
    print("単勝（tansho）の回収率分析")
    print("=" * 80)
    
    # 1. 単勝の全体統計
    print("\n【1】単勝の全体統計")
    results = run_query("""
        SELECT 
            COUNT(*) as total_races,
            AVG(payout) as avg_payout,
            MIN(payout) as min_payout,
            MAX(payout) as max_payout
        FROM historical_payoffs
        WHERE bet_type = 'tansho'
    """)
    result = results[0]
    print(f"  総レース数: {result['total_races']:,}")
    print(f"  平均払戻: {float(result['avg_payout']):.1f}円")
    print(f"  最小払戻: {result['min_payout']}円")
    print(f"  最大払戻: {result['max_payout']}円")
    
    # 2. 号艇別の単勝回収率
    print("\n【2】号艇別 単勝回収率")
    results = run_query("""
        WITH boat_wins AS (
            SELECT 
                combination as boat_no,
                COUNT(*) as wins,
                AVG(payout) as avg_payout
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
            GROUP BY combination
        ),
        total_count AS (
            SELECT COUNT(DISTINCT race_date || stadium_code || race_no) as total
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
        )
        SELECT 
            b.boat_no,
            b.wins,
            t.total,
            b.avg_payout,
            (b.wins::float / t.total) * b.avg_payout as recovery_rate
        FROM boat_wins b, total_count t
        ORDER BY b.boat_no
    """)
    
    print(f"  {'号艇':>4} | {'1着回数':>10} | {'勝率':>8} | {'平均払戻':>10} | {'回収率':>8}")
    print("  " + "-" * 55)
    for r in results:
        win_rate = r['wins'] / r['total'] * 100
        avg_payout = float(r['avg_payout'])
        recovery = float(r['recovery_rate'])
        print(f"  {r['boat_no']:>4} | {r['wins']:>10,} | {win_rate:>7.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}%")

def analyze_tansho_by_stadium():
    """競艇場別の単勝回収率を分析"""
    print("\n" + "=" * 80)
    print("競艇場別 1号艇単勝回収率分析")
    print("=" * 80)
    
    results = run_query("""
        WITH stadium_wins AS (
            SELECT 
                stadium_code,
                COUNT(*) as wins,
                AVG(payout) as avg_payout
            FROM historical_payoffs
            WHERE bet_type = 'tansho' AND combination = '1'
            GROUP BY stadium_code
        ),
        stadium_total AS (
            SELECT 
                stadium_code,
                COUNT(DISTINCT race_date || race_no) as total
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
            GROUP BY stadium_code
        )
        SELECT 
            w.stadium_code,
            w.wins,
            t.total,
            w.avg_payout,
            (w.wins::float / t.total) * w.avg_payout as recovery_rate
        FROM stadium_wins w
        JOIN stadium_total t ON w.stadium_code = t.stadium_code
        ORDER BY (w.wins::float / t.total) * w.avg_payout DESC
    """)
    
    print(f"\n【3】競艇場別 1号艇単勝回収率")
    print(f"  {'場':>6} | {'1着回数':>8} | {'総レース':>8} | {'勝率':>7} | {'平均払戻':>10} | {'回収率':>8}")
    print("  " + "-" * 70)
    for r in results:
        name = STADIUM_NAMES.get(r['stadium_code'], '不明')
        win_rate = r['wins'] / r['total'] * 100
        avg_payout = float(r['avg_payout'])
        recovery = float(r['recovery_rate'])
        print(f"  {name:>6} | {r['wins']:>8,} | {r['total']:>8,} | {win_rate:>6.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}%")

def analyze_tansho_by_race():
    """レース番号別の単勝回収率を分析"""
    print("\n" + "=" * 80)
    print("レース番号別 1号艇単勝回収率分析")
    print("=" * 80)
    
    results = run_query("""
        WITH race_wins AS (
            SELECT 
                race_no,
                COUNT(*) as wins,
                AVG(payout) as avg_payout
            FROM historical_payoffs
            WHERE bet_type = 'tansho' AND combination = '1'
            GROUP BY race_no
        ),
        race_total AS (
            SELECT 
                race_no,
                COUNT(DISTINCT race_date || stadium_code) as total
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
            GROUP BY race_no
        )
        SELECT 
            w.race_no,
            w.wins,
            t.total,
            w.avg_payout,
            (w.wins::float / t.total) * w.avg_payout as recovery_rate
        FROM race_wins w
        JOIN race_total t ON w.race_no = t.race_no
        ORDER BY w.race_no::int
    """)
    
    print(f"\n【4】レース番号別 1号艇単勝回収率")
    print(f"  {'R番号':>6} | {'1着回数':>8} | {'総レース':>8} | {'勝率':>7} | {'平均払戻':>10} | {'回収率':>8}")
    print("  " + "-" * 70)
    for r in results:
        win_rate = r['wins'] / r['total'] * 100
        avg_payout = float(r['avg_payout'])
        recovery = float(r['recovery_rate'])
        print(f"  {r['race_no']:>6} | {r['wins']:>8,} | {r['total']:>8,} | {win_rate:>6.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}%")

def analyze_fukusho_basic():
    """複勝の基本回収率を分析"""
    print("\n" + "=" * 80)
    print("複勝（fukusho）の回収率分析")
    print("=" * 80)
    
    # 1. 複勝の全体統計
    print("\n【5】複勝の全体統計")
    results = run_query("""
        SELECT 
            COUNT(*) as total_payouts,
            AVG(payout) as avg_payout,
            MIN(payout) as min_payout,
            MAX(payout) as max_payout
        FROM historical_payoffs
        WHERE bet_type = 'fukusho'
    """)
    result = results[0]
    print(f"  総払戻数: {result['total_payouts']:,}")
    print(f"  平均払戻: {float(result['avg_payout']):.1f}円")
    print(f"  最小払戻: {result['min_payout']}円")
    print(f"  最大払戻: {result['max_payout']}円")
    
    # 2. 号艇別の複勝回収率
    print("\n【6】号艇別 複勝回収率")
    results = run_query("""
        WITH boat_places AS (
            SELECT 
                combination as boat_no,
                COUNT(*) as places,
                AVG(payout) as avg_payout
            FROM historical_payoffs
            WHERE bet_type = 'fukusho'
            GROUP BY combination
        ),
        total_count AS (
            SELECT COUNT(DISTINCT race_date || stadium_code || race_no) as total
            FROM historical_payoffs
            WHERE bet_type = 'fukusho'
        )
        SELECT 
            b.boat_no,
            b.places,
            t.total,
            b.avg_payout,
            (b.places::float / t.total) * b.avg_payout as recovery_rate
        FROM boat_places b, total_count t
        ORDER BY b.boat_no
    """)
    
    print(f"  {'号艇':>4} | {'入着回数':>10} | {'入着率':>8} | {'平均払戻':>10} | {'回収率':>8}")
    print("  " + "-" * 55)
    for r in results:
        place_rate = r['places'] / r['total'] * 100
        avg_payout = float(r['avg_payout'])
        recovery = float(r['recovery_rate'])
        print(f"  {r['boat_no']:>4} | {r['places']:>10,} | {place_rate:>7.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}%")

def analyze_fukusho_by_stadium():
    """競艇場別の複勝回収率を分析"""
    print("\n" + "=" * 80)
    print("競艇場別 1号艇複勝回収率分析")
    print("=" * 80)
    
    results = run_query("""
        WITH stadium_places AS (
            SELECT 
                stadium_code,
                COUNT(*) as places,
                AVG(payout) as avg_payout
            FROM historical_payoffs
            WHERE bet_type = 'fukusho' AND combination = '1'
            GROUP BY stadium_code
        ),
        stadium_total AS (
            SELECT 
                stadium_code,
                COUNT(DISTINCT race_date || race_no) as total
            FROM historical_payoffs
            WHERE bet_type = 'fukusho'
            GROUP BY stadium_code
        )
        SELECT 
            p.stadium_code,
            p.places,
            t.total,
            p.avg_payout,
            (p.places::float / t.total) * p.avg_payout as recovery_rate
        FROM stadium_places p
        JOIN stadium_total t ON p.stadium_code = t.stadium_code
        ORDER BY (p.places::float / t.total) * p.avg_payout DESC
    """)
    
    print(f"\n【7】競艇場別 1号艇複勝回収率")
    print(f"  {'場':>6} | {'入着回数':>8} | {'総レース':>8} | {'入着率':>7} | {'平均払戻':>10} | {'回収率':>8}")
    print("  " + "-" * 70)
    for r in results:
        name = STADIUM_NAMES.get(r['stadium_code'], '不明')
        place_rate = r['places'] / r['total'] * 100
        avg_payout = float(r['avg_payout'])
        recovery = float(r['recovery_rate'])
        print(f"  {name:>6} | {r['places']:>8,} | {r['total']:>8,} | {place_rate:>6.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}%")

def search_tansho_winning_conditions():
    """単勝で回収率100%超えの条件を探索"""
    print("\n" + "=" * 80)
    print("単勝 回収率100%超え条件の探索")
    print("=" * 80)
    
    # 場×Rの組み合わせで探索
    print("\n【8】場×R 1号艇単勝 回収率上位30")
    results = run_query("""
        WITH stadium_race_wins AS (
            SELECT 
                stadium_code,
                race_no,
                COUNT(*) as wins,
                AVG(payout) as avg_payout
            FROM historical_payoffs
            WHERE bet_type = 'tansho' AND combination = '1'
            GROUP BY stadium_code, race_no
        ),
        stadium_race_total AS (
            SELECT 
                stadium_code,
                race_no,
                COUNT(DISTINCT race_date) as total
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
            GROUP BY stadium_code, race_no
        )
        SELECT 
            w.stadium_code,
            w.race_no,
            w.wins,
            t.total,
            w.avg_payout,
            (w.wins::float / t.total) * w.avg_payout as recovery_rate
        FROM stadium_race_wins w
        JOIN stadium_race_total t ON w.stadium_code = t.stadium_code AND w.race_no = t.race_no
        WHERE t.total >= 100
        ORDER BY (w.wins::float / t.total) * w.avg_payout DESC
        LIMIT 30
    """)
    
    print(f"  {'場':>6} | {'R':>3} | {'1着':>6} | {'総数':>6} | {'勝率':>7} | {'平均払戻':>10} | {'回収率':>8}")
    print("  " + "-" * 70)
    for r in results:
        name = STADIUM_NAMES.get(r['stadium_code'], '不明')
        win_rate = r['wins'] / r['total'] * 100
        avg_payout = float(r['avg_payout'])
        recovery = float(r['recovery_rate'])
        marker = "★" if recovery >= 100 else ""
        print(f"  {name:>6} | {r['race_no']:>3} | {r['wins']:>6} | {r['total']:>6} | {win_rate:>6.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}% {marker}")

def search_fukusho_winning_conditions():
    """複勝で回収率100%超えの条件を探索"""
    print("\n" + "=" * 80)
    print("複勝 回収率100%超え条件の探索")
    print("=" * 80)
    
    # 場×Rの組み合わせで探索
    print("\n【9】場×R 1号艇複勝 回収率上位30")
    results = run_query("""
        WITH stadium_race_places AS (
            SELECT 
                stadium_code,
                race_no,
                COUNT(*) as places,
                AVG(payout) as avg_payout
            FROM historical_payoffs
            WHERE bet_type = 'fukusho' AND combination = '1'
            GROUP BY stadium_code, race_no
        ),
        stadium_race_total AS (
            SELECT 
                stadium_code,
                race_no,
                COUNT(DISTINCT race_date) as total
            FROM historical_payoffs
            WHERE bet_type = 'fukusho'
            GROUP BY stadium_code, race_no
        )
        SELECT 
            p.stadium_code,
            p.race_no,
            p.places,
            t.total,
            p.avg_payout,
            (p.places::float / t.total) * p.avg_payout as recovery_rate
        FROM stadium_race_places p
        JOIN stadium_race_total t ON p.stadium_code = t.stadium_code AND p.race_no = t.race_no
        WHERE t.total >= 100
        ORDER BY (p.places::float / t.total) * p.avg_payout DESC
        LIMIT 30
    """)
    
    print(f"  {'場':>6} | {'R':>3} | {'入着':>6} | {'総数':>6} | {'入着率':>7} | {'平均払戻':>10} | {'回収率':>8}")
    print("  " + "-" * 70)
    for r in results:
        name = STADIUM_NAMES.get(r['stadium_code'], '不明')
        place_rate = r['places'] / r['total'] * 100
        avg_payout = float(r['avg_payout'])
        recovery = float(r['recovery_rate'])
        marker = "★" if recovery >= 100 else ""
        print(f"  {name:>6} | {r['race_no']:>3} | {r['places']:>6} | {r['total']:>6} | {place_rate:>6.2f}% | {avg_payout:>9.1f}円 | {recovery:>7.2f}% {marker}")

if __name__ == "__main__":
    analyze_tansho_basic()
    analyze_tansho_by_stadium()
    analyze_tansho_by_race()
    analyze_fukusho_basic()
    analyze_fukusho_by_stadium()
    search_tansho_winning_conditions()
    search_fukusho_winning_conditions()

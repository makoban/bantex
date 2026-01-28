#!/usr/bin/env python3
"""
競艇21年分データ - 回収率100%超えの条件を探す
場別、R別、場×R別で分析
"""

import psycopg2
import time
import json

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def analyze_tansho_by_stadium():
    """単勝を場別に分析"""
    print("\n=== 単勝1号艇 場別回収率 ===")
    
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                stadium_code,
                COUNT(*) as wins,
                SUM(payout) as total_payout
            FROM historical_payoffs
            WHERE bet_type = 'tansho' AND combination = '1'
            GROUP BY stadium_code
            ORDER BY stadium_code
        """)
        
        stadium_data = {}
        for row in cur.fetchall():
            stadium_data[row[0]] = {
                'wins': row[1],
                'total_payout': int(row[2] or 0)
            }
        
        # 全レース数を場別に取得
        cur.execute("""
            SELECT 
                stadium_code,
                COUNT(DISTINCT (race_date, race_no)) as total_races
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
            GROUP BY stadium_code
            ORDER BY stadium_code
        """)
        
        results = []
        for row in cur.fetchall():
            stadium = row[0]
            total_races = row[1]
            wins = stadium_data.get(stadium, {}).get('wins', 0)
            payout = stadium_data.get(stadium, {}).get('total_payout', 0)
            
            win_rate = wins / total_races * 100 if total_races > 0 else 0
            return_rate = payout / total_races if total_races > 0 else 0
            
            results.append({
                'stadium': stadium,
                'total_races': total_races,
                'wins': wins,
                'win_rate': win_rate,
                'return_rate': return_rate
            })
        
        cur.close()
        conn.close()
        
        # 回収率でソート
        results.sort(key=lambda x: x['return_rate'], reverse=True)
        
        print("場 | レース数 | 勝率 | 回収率")
        print("-" * 40)
        for r in results[:10]:
            print(f"{r['stadium']} | {r['total_races']:,} | {r['win_rate']:.1f}% | {r['return_rate']:.1f}%")
        
        return results
        
    except Exception as e:
        print(f"エラー: {e}")
        return []

def analyze_tansho_by_race_no():
    """単勝1号艇をR別に分析"""
    print("\n=== 単勝1号艇 R別回収率 ===")
    
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                race_no,
                COUNT(*) as wins,
                SUM(payout) as total_payout
            FROM historical_payoffs
            WHERE bet_type = 'tansho' AND combination = '1'
            GROUP BY race_no
            ORDER BY race_no
        """)
        
        race_data = {}
        for row in cur.fetchall():
            race_data[row[0]] = {
                'wins': row[1],
                'total_payout': int(row[2] or 0)
            }
        
        # 全レース数をR別に取得
        cur.execute("""
            SELECT 
                race_no,
                COUNT(DISTINCT (race_date, stadium_code)) as total_races
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
            GROUP BY race_no
            ORDER BY race_no
        """)
        
        results = []
        for row in cur.fetchall():
            race_no = row[0]
            total_races = row[1]
            wins = race_data.get(race_no, {}).get('wins', 0)
            payout = race_data.get(race_no, {}).get('total_payout', 0)
            
            win_rate = wins / total_races * 100 if total_races > 0 else 0
            return_rate = payout / total_races if total_races > 0 else 0
            
            results.append({
                'race_no': race_no,
                'total_races': total_races,
                'wins': wins,
                'win_rate': win_rate,
                'return_rate': return_rate
            })
        
        cur.close()
        conn.close()
        
        # 回収率でソート
        results.sort(key=lambda x: x['return_rate'], reverse=True)
        
        print("R | レース数 | 勝率 | 回収率")
        print("-" * 40)
        for r in results:
            print(f"{r['race_no']} | {r['total_races']:,} | {r['win_rate']:.1f}% | {r['return_rate']:.1f}%")
        
        return results
        
    except Exception as e:
        print(f"エラー: {e}")
        return []

def analyze_nirenpuku_by_stadium():
    """2連複1-3を場別に分析"""
    print("\n=== 2連複1-3 場別回収率 ===")
    
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                stadium_code,
                COUNT(*) as hits,
                SUM(payout) as total_payout
            FROM historical_payoffs
            WHERE bet_type = 'nirenpuku' AND combination = '1-3'
            GROUP BY stadium_code
            ORDER BY stadium_code
        """)
        
        stadium_data = {}
        for row in cur.fetchall():
            stadium_data[row[0]] = {
                'hits': row[1],
                'total_payout': int(row[2] or 0)
            }
        
        # 全レース数を場別に取得
        cur.execute("""
            SELECT 
                stadium_code,
                COUNT(DISTINCT (race_date, race_no)) as total_races
            FROM historical_payoffs
            WHERE bet_type = 'nirenpuku'
            GROUP BY stadium_code
            ORDER BY stadium_code
        """)
        
        results = []
        for row in cur.fetchall():
            stadium = row[0]
            total_races = row[1]
            hits = stadium_data.get(stadium, {}).get('hits', 0)
            payout = stadium_data.get(stadium, {}).get('total_payout', 0)
            
            hit_rate = hits / total_races * 100 if total_races > 0 else 0
            return_rate = payout / total_races if total_races > 0 else 0
            
            results.append({
                'stadium': stadium,
                'total_races': total_races,
                'hits': hits,
                'hit_rate': hit_rate,
                'return_rate': return_rate
            })
        
        cur.close()
        conn.close()
        
        # 回収率でソート
        results.sort(key=lambda x: x['return_rate'], reverse=True)
        
        print("場 | レース数 | 的中率 | 回収率")
        print("-" * 40)
        for r in results[:10]:
            print(f"{r['stadium']} | {r['total_races']:,} | {r['hit_rate']:.1f}% | {r['return_rate']:.1f}%")
        
        return results
        
    except Exception as e:
        print(f"エラー: {e}")
        return []

def analyze_high_payout_tansho():
    """高配当単勝（500円以上）の分析"""
    print("\n=== 高配当単勝（500円以上）の分析 ===")
    
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
        cur = conn.cursor()
        
        # 払戻金レンジ別の分布
        cur.execute("""
            SELECT 
                CASE 
                    WHEN payout < 200 THEN '100-199円'
                    WHEN payout < 300 THEN '200-299円'
                    WHEN payout < 500 THEN '300-499円'
                    WHEN payout < 1000 THEN '500-999円'
                    WHEN payout < 2000 THEN '1000-1999円'
                    ELSE '2000円以上'
                END as payout_range,
                COUNT(*) as count,
                SUM(payout) as total_payout,
                AVG(payout) as avg_payout
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
            GROUP BY payout_range
            ORDER BY MIN(payout)
        """)
        
        print("払戻レンジ | 件数 | 合計払戻 | 平均払戻")
        print("-" * 50)
        for row in cur.fetchall():
            print(f"{row[0]} | {row[1]:,} | ¥{int(row[2]):,} | ¥{int(row[3])}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"エラー: {e}")

def main():
    print("=" * 60)
    print("競艇21年分データ - 回収率100%超え条件の探索")
    print("=" * 60)
    
    # 単勝の場別分析
    time.sleep(2)
    tansho_stadium = analyze_tansho_by_stadium()
    
    # 単勝のR別分析
    time.sleep(2)
    tansho_race = analyze_tansho_by_race_no()
    
    # 2連複1-3の場別分析
    time.sleep(2)
    nirenpuku_stadium = analyze_nirenpuku_by_stadium()
    
    # 高配当単勝の分析
    time.sleep(2)
    analyze_high_payout_tansho()
    
    # 結果をJSONで保存
    output = {
        'tansho_by_stadium': tansho_stadium,
        'tansho_by_race_no': tansho_race,
        'nirenpuku_1_3_by_stadium': nirenpuku_stadium
    }
    
    with open('/home/ubuntu/profitable_conditions.json', 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print("分析完了")
    print("結果を /home/ubuntu/profitable_conditions.json に保存しました")
    print("=" * 60)

if __name__ == "__main__":
    main()

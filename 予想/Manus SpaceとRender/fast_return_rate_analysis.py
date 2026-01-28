#!/usr/bin/env python3
"""
高速回収率分析スクリプト

historical_payoffsテーブルから直接集計
- 全レース数 = tanshoの全レコード数（各レースに1つのtanshoレコードがある）
- 回収率 = 払戻金合計 / (全レース数 × 100円)
"""

import psycopg2
import time
import json
from datetime import datetime

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def execute_query(query, timeout=300):
    """クエリを実行"""
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=30)
        cur = conn.cursor()
        cur.execute(f"SET statement_timeout = '{timeout}s'")
        cur.execute(query)
        result = cur.fetchall()
        cur.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    print("=" * 70)
    print("高速回収率分析")
    print(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 1. 全レース数を取得（tanshoのユニークレース数）
    print("\n--- 全レース数を取得 ---")
    query_total = """
        SELECT COUNT(DISTINCT (race_date, stadium_code, race_no))
        FROM historical_payoffs
        WHERE bet_type = 'tansho'
    """
    result = execute_query(query_total)
    if result:
        total_races = result[0][0]
        print(f"全レース数: {total_races:,}")
    else:
        print("全レース数の取得に失敗")
        return
    
    # 2. 単勝回収率（号艇別）
    print("\n--- 単勝回収率（号艇別）---")
    query_tansho = """
        SELECT 
            combination as boat,
            COUNT(*) as hit_count,
            SUM(payout) as total_payout
        FROM historical_payoffs
        WHERE bet_type = 'tansho'
        GROUP BY combination
        ORDER BY combination
    """
    result = execute_query(query_tansho)
    if result:
        tansho_results = []
        for row in result:
            boat, hit_count, total_payout = row
            return_rate = total_payout / total_races  # 100円あたり
            hit_rate = hit_count / total_races * 100
            marker = " ✓✓" if return_rate >= 110 else (" ✓" if return_rate >= 100 else "")
            print(f"  {boat}号艇: {hit_count:,}回的中 ({hit_rate:.1f}%), 回収率{return_rate:.1f}%{marker}")
            tansho_results.append({
                'bet_type': 'tansho',
                'boat': boat,
                'hit_count': hit_count,
                'total_payout': int(total_payout),
                'return_rate': return_rate
            })
    
    # 3. 2連複回収率（組み合わせ別）
    print("\n--- 2連複回収率（組み合わせ別・上位20）---")
    query_nirenpuku = """
        SELECT 
            combination,
            COUNT(*) as hit_count,
            SUM(payout) as total_payout
        FROM historical_payoffs
        WHERE bet_type = 'nirenpuku'
        GROUP BY combination
        ORDER BY SUM(payout) / (SELECT COUNT(DISTINCT (race_date, stadium_code, race_no)) FROM historical_payoffs WHERE bet_type = 'tansho') DESC
        LIMIT 20
    """
    result = execute_query(query_nirenpuku)
    if result:
        nirenpuku_results = []
        for row in result:
            combo, hit_count, total_payout = row
            return_rate = total_payout / total_races
            hit_rate = hit_count / total_races * 100
            marker = " ✓✓" if return_rate >= 110 else (" ✓" if return_rate >= 100 else "")
            print(f"  {combo}: {hit_count:,}回的中 ({hit_rate:.1f}%), 回収率{return_rate:.1f}%{marker}")
            nirenpuku_results.append({
                'bet_type': 'nirenpuku',
                'combination': combo,
                'hit_count': hit_count,
                'total_payout': int(total_payout),
                'return_rate': return_rate
            })
    
    # 4. 2連単回収率（組み合わせ別）
    print("\n--- 2連単回収率（組み合わせ別・上位20）---")
    query_nirentan = """
        SELECT 
            combination,
            COUNT(*) as hit_count,
            SUM(payout) as total_payout
        FROM historical_payoffs
        WHERE bet_type = 'nirentan'
        GROUP BY combination
        ORDER BY SUM(payout) / (SELECT COUNT(DISTINCT (race_date, stadium_code, race_no)) FROM historical_payoffs WHERE bet_type = 'tansho') DESC
        LIMIT 20
    """
    result = execute_query(query_nirentan)
    if result:
        nirentan_results = []
        for row in result:
            combo, hit_count, total_payout = row
            return_rate = total_payout / total_races
            hit_rate = hit_count / total_races * 100
            marker = " ✓✓" if return_rate >= 110 else (" ✓" if return_rate >= 100 else "")
            print(f"  {combo}: {hit_count:,}回的中 ({hit_rate:.1f}%), 回収率{return_rate:.1f}%{marker}")
            nirentan_results.append({
                'bet_type': 'nirentan',
                'combination': combo,
                'hit_count': hit_count,
                'total_payout': int(total_payout),
                'return_rate': return_rate
            })
    
    # 5. 3連単回収率（組み合わせ別）
    print("\n--- 3連単回収率（組み合わせ別・上位20）---")
    query_sanrentan = """
        SELECT 
            combination,
            COUNT(*) as hit_count,
            SUM(payout) as total_payout
        FROM historical_payoffs
        WHERE bet_type = 'sanrentan'
        GROUP BY combination
        ORDER BY SUM(payout) / (SELECT COUNT(DISTINCT (race_date, stadium_code, race_no)) FROM historical_payoffs WHERE bet_type = 'tansho') DESC
        LIMIT 20
    """
    result = execute_query(query_sanrentan)
    if result:
        sanrentan_results = []
        for row in result:
            combo, hit_count, total_payout = row
            return_rate = total_payout / total_races
            hit_rate = hit_count / total_races * 100
            marker = " ✓✓" if return_rate >= 110 else (" ✓" if return_rate >= 100 else "")
            print(f"  {combo}: {hit_count:,}回的中 ({hit_rate:.1f}%), 回収率{return_rate:.1f}%{marker}")
            sanrentan_results.append({
                'bet_type': 'sanrentan',
                'combination': combo,
                'hit_count': hit_count,
                'total_payout': int(total_payout),
                'return_rate': return_rate
            })
    
    # 6. 3連複回収率（組み合わせ別）
    print("\n--- 3連複回収率（組み合わせ別・上位20）---")
    query_sanrenpuku = """
        SELECT 
            combination,
            COUNT(*) as hit_count,
            SUM(payout) as total_payout
        FROM historical_payoffs
        WHERE bet_type = 'sanrenpuku'
        GROUP BY combination
        ORDER BY SUM(payout) / (SELECT COUNT(DISTINCT (race_date, stadium_code, race_no)) FROM historical_payoffs WHERE bet_type = 'tansho') DESC
        LIMIT 20
    """
    result = execute_query(query_sanrenpuku)
    if result:
        sanrenpuku_results = []
        for row in result:
            combo, hit_count, total_payout = row
            return_rate = total_payout / total_races
            hit_rate = hit_count / total_races * 100
            marker = " ✓✓" if return_rate >= 110 else (" ✓" if return_rate >= 100 else "")
            print(f"  {combo}: {hit_count:,}回的中 ({hit_rate:.1f}%), 回収率{return_rate:.1f}%{marker}")
            sanrenpuku_results.append({
                'bet_type': 'sanrenpuku',
                'combination': combo,
                'hit_count': hit_count,
                'total_payout': int(total_payout),
                'return_rate': return_rate
            })
    
    # 結果を保存
    all_results = {
        'total_races': total_races,
        'tansho': tansho_results if 'tansho_results' in dir() else [],
        'nirenpuku': nirenpuku_results if 'nirenpuku_results' in dir() else [],
        'nirentan': nirentan_results if 'nirentan_results' in dir() else [],
        'sanrentan': sanrentan_results if 'sanrentan_results' in dir() else [],
        'sanrenpuku': sanrenpuku_results if 'sanrenpuku_results' in dir() else []
    }
    
    with open('/home/ubuntu/fast_return_rate_results.json', 'w') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 70)
    print("結果を /home/ubuntu/fast_return_rate_results.json に保存しました")
    print("=" * 70)

if __name__ == "__main__":
    main()

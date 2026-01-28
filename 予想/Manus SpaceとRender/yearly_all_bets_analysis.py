#!/usr/bin/env python3
"""
年別に分割して全式別の回収率を検証するスクリプト
- 1年分ずつクエリを実行
- 結果をローカルに保存
- 最後に全年のデータを集計

目標: 回収率110%以上の条件を発見する
"""

import psycopg2
import time
import json
from datetime import datetime

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def execute_query_with_retry(query, max_retries=3, timeout=120):
    """リトライ付きでクエリを実行"""
    for attempt in range(max_retries):
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
            print(f"  Attempt {attempt + 1} failed: {str(e)[:50]}")
            time.sleep(2)
    return None


def analyze_tansho_by_year(year):
    """年別の単勝回収率を分析"""
    results = []
    
    for boat in ['1', '2', '3', '4', '5', '6']:
        # 全レース数を取得
        query_total = f"""
            SELECT COUNT(DISTINCT (race_date, stadium_code, race_no))
            FROM historical_race_results
            WHERE race_date LIKE '{year}%'
              AND boat_no = '{boat}'
              AND rank IS NOT NULL AND rank != 'F' AND rank != ''
        """
        total_result = execute_query_with_retry(query_total)
        if not total_result:
            continue
        total_races = total_result[0][0] or 0
        
        # 的中数と払戻金を取得
        query_payout = f"""
            SELECT COUNT(*), SUM(payout)
            FROM historical_payoffs
            WHERE race_date LIKE '{year}%'
              AND bet_type = 'tansho'
              AND combination = '{boat}'
        """
        payout_result = execute_query_with_retry(query_payout)
        if not payout_result:
            continue
        
        hit_count = payout_result[0][0] or 0
        total_payout = int(payout_result[0][1] or 0)
        
        if total_races > 0:
            return_rate = total_payout / total_races  # 100円あたりの回収額
            results.append({
                'year': year,
                'bet_type': 'tansho',
                'boat': boat,
                'total_races': total_races,
                'hit_count': hit_count,
                'total_payout': total_payout,
                'return_rate': return_rate
            })
        
        time.sleep(0.5)
    
    return results


def analyze_nirenpuku_by_year(year):
    """年別の2連複回収率を分析"""
    results = []
    
    # 主要な組み合わせ
    combinations = ['1=2', '1=3', '1=4', '1=5', '1=6', '2=3', '2=4', '3=4']
    
    # まず全レース数を取得
    query_total = f"""
        SELECT COUNT(DISTINCT (race_date, stadium_code, race_no)) / 6
        FROM historical_race_results
        WHERE race_date LIKE '{year}%'
          AND rank IS NOT NULL AND rank != 'F' AND rank != ''
    """
    total_result = execute_query_with_retry(query_total)
    if not total_result:
        return results
    total_races = int(total_result[0][0] or 0)
    
    for combo in combinations:
        # 的中数と払戻金を取得
        query_payout = f"""
            SELECT COUNT(*), SUM(payout)
            FROM historical_payoffs
            WHERE race_date LIKE '{year}%'
              AND bet_type = 'nirenpuku'
              AND combination = '{combo}'
        """
        payout_result = execute_query_with_retry(query_payout)
        if not payout_result:
            continue
        
        hit_count = payout_result[0][0] or 0
        total_payout = int(payout_result[0][1] or 0)
        
        if total_races > 0:
            return_rate = total_payout / total_races
            results.append({
                'year': year,
                'bet_type': 'nirenpuku',
                'combination': combo,
                'total_races': total_races,
                'hit_count': hit_count,
                'total_payout': total_payout,
                'return_rate': return_rate
            })
        
        time.sleep(0.5)
    
    return results


def analyze_nirentan_by_year(year):
    """年別の2連単回収率を分析"""
    results = []
    
    # 主要な組み合わせ
    combinations = ['1-2', '1-3', '1-4', '2-1', '2-3', '3-1', '3-2']
    
    # まず全レース数を取得
    query_total = f"""
        SELECT COUNT(DISTINCT (race_date, stadium_code, race_no)) / 6
        FROM historical_race_results
        WHERE race_date LIKE '{year}%'
          AND rank IS NOT NULL AND rank != 'F' AND rank != ''
    """
    total_result = execute_query_with_retry(query_total)
    if not total_result:
        return results
    total_races = int(total_result[0][0] or 0)
    
    for combo in combinations:
        # 的中数と払戻金を取得
        query_payout = f"""
            SELECT COUNT(*), SUM(payout)
            FROM historical_payoffs
            WHERE race_date LIKE '{year}%'
              AND bet_type = 'nirentan'
              AND combination = '{combo}'
        """
        payout_result = execute_query_with_retry(query_payout)
        if not payout_result:
            continue
        
        hit_count = payout_result[0][0] or 0
        total_payout = int(payout_result[0][1] or 0)
        
        if total_races > 0:
            return_rate = total_payout / total_races
            results.append({
                'year': year,
                'bet_type': 'nirentan',
                'combination': combo,
                'total_races': total_races,
                'hit_count': hit_count,
                'total_payout': total_payout,
                'return_rate': return_rate
            })
        
        time.sleep(0.5)
    
    return results


def analyze_sanrentan_by_year(year):
    """年別の3連単回収率を分析"""
    results = []
    
    # 主要な組み合わせ（人気パターン）
    combinations = ['1-2-3', '1-2-4', '1-3-2', '1-3-4', '1-4-2', '1-4-3', '2-1-3', '2-1-4', '2-3-1', '3-1-2']
    
    # まず全レース数を取得
    query_total = f"""
        SELECT COUNT(DISTINCT (race_date, stadium_code, race_no)) / 6
        FROM historical_race_results
        WHERE race_date LIKE '{year}%'
          AND rank IS NOT NULL AND rank != 'F' AND rank != ''
    """
    total_result = execute_query_with_retry(query_total)
    if not total_result:
        return results
    total_races = int(total_result[0][0] or 0)
    
    for combo in combinations:
        # 的中数と払戻金を取得
        query_payout = f"""
            SELECT COUNT(*), SUM(payout)
            FROM historical_payoffs
            WHERE race_date LIKE '{year}%'
              AND bet_type = 'sanrentan'
              AND combination = '{combo}'
        """
        payout_result = execute_query_with_retry(query_payout)
        if not payout_result:
            continue
        
        hit_count = payout_result[0][0] or 0
        total_payout = int(payout_result[0][1] or 0)
        
        if total_races > 0:
            return_rate = total_payout / total_races
            results.append({
                'year': year,
                'bet_type': 'sanrentan',
                'combination': combo,
                'total_races': total_races,
                'hit_count': hit_count,
                'total_payout': total_payout,
                'return_rate': return_rate
            })
        
        time.sleep(0.5)
    
    return results


def main():
    print("=" * 70)
    print("全式別 回収率分析（年別分割クエリ）")
    print(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    all_results = []
    
    # 分析対象年（直近10年）
    years = ['2016', '2017', '2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025']
    
    for year in years:
        print(f"\n--- {year}年 分析中 ---")
        
        # 単勝
        print(f"  単勝...")
        tansho = analyze_tansho_by_year(year)
        all_results.extend(tansho)
        
        # 2連複
        print(f"  2連複...")
        nirenpuku = analyze_nirenpuku_by_year(year)
        all_results.extend(nirenpuku)
        
        # 2連単
        print(f"  2連単...")
        nirentan = analyze_nirentan_by_year(year)
        all_results.extend(nirentan)
        
        # 3連単
        print(f"  3連単...")
        sanrentan = analyze_sanrentan_by_year(year)
        all_results.extend(sanrentan)
        
        print(f"  {year}年完了")
    
    # 結果を保存
    with open('/home/ubuntu/yearly_all_bets_results.json', 'w') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    # 集計
    print("\n" + "=" * 70)
    print("【集計結果】")
    print("=" * 70)
    
    # 式別・組み合わせ別に集計
    aggregated = {}
    for r in all_results:
        key = f"{r['bet_type']}_{r.get('boat', r.get('combination', ''))}"
        if key not in aggregated:
            aggregated[key] = {
                'bet_type': r['bet_type'],
                'target': r.get('boat', r.get('combination', '')),
                'total_races': 0,
                'hit_count': 0,
                'total_payout': 0
            }
        aggregated[key]['total_races'] += r['total_races']
        aggregated[key]['hit_count'] += r['hit_count']
        aggregated[key]['total_payout'] += r['total_payout']
    
    # 回収率を計算して表示
    print("\n【単勝】")
    for key, data in sorted(aggregated.items()):
        if data['bet_type'] == 'tansho' and data['total_races'] > 0:
            return_rate = data['total_payout'] / data['total_races']
            hit_rate = data['hit_count'] / data['total_races'] * 100
            marker = " ✓✓" if return_rate >= 110 else (" ✓" if return_rate >= 100 else "")
            print(f"  {data['target']}号艇: {data['total_races']:,}レース, 的中率{hit_rate:.1f}%, 回収率{return_rate:.1f}%{marker}")
    
    print("\n【2連複】")
    for key, data in sorted(aggregated.items()):
        if data['bet_type'] == 'nirenpuku' and data['total_races'] > 0:
            return_rate = data['total_payout'] / data['total_races']
            hit_rate = data['hit_count'] / data['total_races'] * 100
            marker = " ✓✓" if return_rate >= 110 else (" ✓" if return_rate >= 100 else "")
            print(f"  {data['target']}: {data['total_races']:,}レース, 的中率{hit_rate:.1f}%, 回収率{return_rate:.1f}%{marker}")
    
    print("\n【2連単】")
    for key, data in sorted(aggregated.items()):
        if data['bet_type'] == 'nirentan' and data['total_races'] > 0:
            return_rate = data['total_payout'] / data['total_races']
            hit_rate = data['hit_count'] / data['total_races'] * 100
            marker = " ✓✓" if return_rate >= 110 else (" ✓" if return_rate >= 100 else "")
            print(f"  {data['target']}: {data['total_races']:,}レース, 的中率{hit_rate:.1f}%, 回収率{return_rate:.1f}%{marker}")
    
    print("\n【3連単】")
    for key, data in sorted(aggregated.items()):
        if data['bet_type'] == 'sanrentan' and data['total_races'] > 0:
            return_rate = data['total_payout'] / data['total_races']
            hit_rate = data['hit_count'] / data['total_races'] * 100
            marker = " ✓✓" if return_rate >= 110 else (" ✓" if return_rate >= 100 else "")
            print(f"  {data['target']}: {data['total_races']:,}レース, 的中率{hit_rate:.1f}%, 回収率{return_rate:.1f}%{marker}")
    
    print("\n結果を /home/ubuntu/yearly_all_bets_results.json に保存しました")

if __name__ == "__main__":
    main()

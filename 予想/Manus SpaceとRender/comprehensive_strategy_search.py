#!/usr/bin/env python3
"""
全式別で回収率110%以上の条件を探索する包括的な検証スクリプト

検証対象:
1. 単勝 - 号艇別、当地勝率別、R別、場別
2. 2連単/2連複 - 組み合わせ別、当地勝率別
3. 3連単/3連複 - 人気パターン別

目標: 回収率110%以上の条件を発見する
"""

import psycopg2
import time
import json
from datetime import datetime

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def execute_query(query, timeout=180):
    """クエリを実行し、結果を返す"""
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=timeout)
        cur = conn.cursor()
        cur.execute(query)
        result = cur.fetchall()
        cur.close()
        conn.close()
        return result
    except Exception as e:
        return [('error', str(e))]


def search_tansho_conditions():
    """単勝の回収率110%以上条件を探索"""
    print("\n" + "=" * 70)
    print("【単勝戦略】回収率110%以上の条件を探索")
    print("=" * 70)
    
    results = []
    
    # 1. 号艇 × 当地勝率範囲
    print("\n--- 号艇 × 当地勝率範囲 ---")
    for boat in ['1', '2', '3', '4', '5', '6']:
        for low, high in [(3.0, 4.0), (4.0, 5.0), (5.0, 6.0), (6.0, 7.0), (7.0, 8.0), (8.0, 10.0)]:
            query = f"""
                WITH qualified_races AS (
                    SELECT DISTINCT race_date, stadium_code, race_no
                    FROM historical_programs
                    WHERE boat_no = '{boat}'
                      AND local_win_rate >= {low}
                      AND local_win_rate < {high}
                ),
                payoffs AS (
                    SELECT qr.race_date, qr.stadium_code, qr.race_no,
                           COALESCE(hp.payout, 0) as payout
                    FROM qualified_races qr
                    LEFT JOIN historical_payoffs hp
                        ON hp.race_date = qr.race_date
                        AND hp.stadium_code = qr.stadium_code
                        AND hp.race_no = qr.race_no
                        AND hp.bet_type = 'tansho'
                        AND hp.combination = '{boat}'
                )
                SELECT COUNT(*), SUM(payout)
                FROM payoffs
            """
            rows = execute_query(query)
            if rows and rows[0][0] != 'error':
                total_races = rows[0][0] or 0
                total_payout = int(rows[0][1] or 0)
                if total_races > 100:  # 最低100レース以上
                    return_rate = total_payout / (total_races * 100) * 100 if total_races > 0 else 0
                    marker = " ✓✓" if return_rate >= 110 else (" ✓" if return_rate >= 100 else "")
                    result = {
                        'type': 'tansho',
                        'boat': boat,
                        'local_win_rate': f'{low}-{high}',
                        'races': total_races,
                        'return_rate': return_rate
                    }
                    results.append(result)
                    if return_rate >= 100:
                        print(f"  {boat}号艇 × 当地勝率{low}-{high}: {total_races:,}レース, 回収率{return_rate:.1f}%{marker}")
            time.sleep(1)
    
    # 2. 号艇 × R番号
    print("\n--- 号艇 × R番号 ---")
    for boat in ['1', '2', '3']:
        for race_no in ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']:
            query = f"""
                SELECT COUNT(*), SUM(payout)
                FROM historical_payoffs
                WHERE bet_type = 'tansho'
                  AND combination = '{boat}'
                  AND race_no = '{race_no}'
            """
            rows = execute_query(query)
            if rows and rows[0][0] != 'error':
                total_races = rows[0][0] or 0
                total_payout = int(rows[0][1] or 0)
                if total_races > 1000:
                    return_rate = total_payout / (total_races * 100) * 100 if total_races > 0 else 0
                    result = {
                        'type': 'tansho',
                        'boat': boat,
                        'race_no': race_no,
                        'races': total_races,
                        'return_rate': return_rate
                    }
                    results.append(result)
                    if return_rate >= 100:
                        marker = " ✓✓" if return_rate >= 110 else " ✓"
                        print(f"  {boat}号艇 × {race_no}R: {total_races:,}レース, 回収率{return_rate:.1f}%{marker}")
            time.sleep(0.5)
    
    return results


def search_niren_conditions():
    """2連単/2連複の回収率110%以上条件を探索"""
    print("\n" + "=" * 70)
    print("【2連戦略】回収率110%以上の条件を探索")
    print("=" * 70)
    
    results = []
    
    # 1. 組み合わせ × 当地勝率範囲（2連単と2連複の高い方）
    print("\n--- 組み合わせ × 当地勝率範囲（オッズ高い方選択）---")
    combinations = ['1-2', '1-3', '1-4', '1-5', '1-6', '2-3', '2-4', '2-5', '2-6', '3-4', '3-5', '3-6']
    
    for combo in combinations:
        first_boat = combo.split('-')[0]
        for low, high in [(3.0, 4.0), (4.0, 5.0), (5.0, 6.0), (6.0, 7.0), (7.0, 8.0)]:
            query = f"""
                WITH qualified_races AS (
                    SELECT DISTINCT race_date, stadium_code, race_no
                    FROM historical_programs
                    WHERE boat_no = '{first_boat}'
                      AND local_win_rate >= {low}
                      AND local_win_rate < {high}
                ),
                payoffs AS (
                    SELECT qr.race_date, qr.stadium_code, qr.race_no,
                           MAX(CASE WHEN hp.bet_type = 'nirentan' THEN hp.payout ELSE 0 END) as nirentan,
                           MAX(CASE WHEN hp.bet_type = 'nirenpuku' THEN hp.payout ELSE 0 END) as nirenpuku
                    FROM qualified_races qr
                    LEFT JOIN historical_payoffs hp
                        ON hp.race_date = qr.race_date
                        AND hp.stadium_code = qr.stadium_code
                        AND hp.race_no = qr.race_no
                        AND hp.combination = '{combo}'
                        AND hp.bet_type IN ('nirentan', 'nirenpuku')
                    GROUP BY qr.race_date, qr.stadium_code, qr.race_no
                )
                SELECT COUNT(*), SUM(GREATEST(nirentan, nirenpuku))
                FROM payoffs
            """
            rows = execute_query(query)
            if rows and rows[0][0] != 'error':
                total_races = rows[0][0] or 0
                total_payout = int(rows[0][1] or 0)
                if total_races > 100:
                    return_rate = total_payout / (total_races * 100) * 100 if total_races > 0 else 0
                    result = {
                        'type': 'niren_max',
                        'combination': combo,
                        'local_win_rate': f'{low}-{high}',
                        'races': total_races,
                        'return_rate': return_rate
                    }
                    results.append(result)
                    if return_rate >= 100:
                        marker = " ✓✓" if return_rate >= 110 else " ✓"
                        print(f"  {combo} × 当地勝率{low}-{high}: {total_races:,}レース, 回収率{return_rate:.1f}%{marker}")
            time.sleep(1)
    
    return results


def search_sanren_conditions():
    """3連単/3連複の回収率110%以上条件を探索"""
    print("\n" + "=" * 70)
    print("【3連戦略】回収率110%以上の条件を探索")
    print("=" * 70)
    
    results = []
    
    # 1. 人気パターン（1-2-3, 1-2-4, 1-3-2など）× 当地勝率
    print("\n--- 人気パターン × 当地勝率範囲（3連単/3連複の高い方）---")
    patterns = ['1-2-3', '1-2-4', '1-3-2', '1-3-4', '1-4-2', '1-4-3', '2-1-3', '2-1-4', '2-3-1', '3-1-2']
    
    for pattern in patterns:
        first_boat = pattern.split('-')[0]
        for low, high in [(4.0, 5.0), (5.0, 6.0), (6.0, 7.0), (7.0, 8.0)]:
            # 3連複用の組み合わせ（ソート）
            sorted_combo = '-'.join(sorted(pattern.split('-')))
            
            query = f"""
                WITH qualified_races AS (
                    SELECT DISTINCT race_date, stadium_code, race_no
                    FROM historical_programs
                    WHERE boat_no = '{first_boat}'
                      AND local_win_rate >= {low}
                      AND local_win_rate < {high}
                ),
                payoffs AS (
                    SELECT qr.race_date, qr.stadium_code, qr.race_no,
                           MAX(CASE WHEN hp.bet_type = 'sanrentan' AND hp.combination = '{pattern}' THEN hp.payout ELSE 0 END) as sanrentan,
                           MAX(CASE WHEN hp.bet_type = 'sanrenpuku' AND hp.combination = '{sorted_combo}' THEN hp.payout ELSE 0 END) as sanrenpuku
                    FROM qualified_races qr
                    LEFT JOIN historical_payoffs hp
                        ON hp.race_date = qr.race_date
                        AND hp.stadium_code = qr.stadium_code
                        AND hp.race_no = qr.race_no
                    GROUP BY qr.race_date, qr.stadium_code, qr.race_no
                )
                SELECT COUNT(*), SUM(GREATEST(sanrentan, sanrenpuku))
                FROM payoffs
            """
            rows = execute_query(query)
            if rows and rows[0][0] != 'error':
                total_races = rows[0][0] or 0
                total_payout = int(rows[0][1] or 0)
                if total_races > 100:
                    return_rate = total_payout / (total_races * 100) * 100 if total_races > 0 else 0
                    result = {
                        'type': 'sanren_max',
                        'pattern': pattern,
                        'local_win_rate': f'{low}-{high}',
                        'races': total_races,
                        'return_rate': return_rate
                    }
                    results.append(result)
                    if return_rate >= 100:
                        marker = " ✓✓" if return_rate >= 110 else " ✓"
                        print(f"  {pattern} × 当地勝率{low}-{high}: {total_races:,}レース, 回収率{return_rate:.1f}%{marker}")
            time.sleep(1)
    
    return results


def main():
    print("=" * 70)
    print("全式別 回収率110%以上条件探索")
    print(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    all_results = {}
    
    # 単勝戦略
    tansho_results = search_tansho_conditions()
    all_results['tansho'] = tansho_results
    
    # 2連戦略
    niren_results = search_niren_conditions()
    all_results['niren'] = niren_results
    
    # 3連戦略
    sanren_results = search_sanren_conditions()
    all_results['sanren'] = sanren_results
    
    # 結果を保存
    with open('/home/ubuntu/comprehensive_strategy_results.json', 'w') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    # サマリー
    print("\n" + "=" * 70)
    print("【サマリー】回収率110%以上の条件")
    print("=" * 70)
    
    for category, results in all_results.items():
        high_return = [r for r in results if r.get('return_rate', 0) >= 110]
        if high_return:
            print(f"\n{category}:")
            for r in sorted(high_return, key=lambda x: x['return_rate'], reverse=True)[:5]:
                print(f"  {r}")
    
    print("\n結果を /home/ubuntu/comprehensive_strategy_results.json に保存しました")

if __name__ == "__main__":
    main()

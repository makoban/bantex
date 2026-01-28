#!/usr/bin/env python3
"""
特定の競艇場に絞った詳細分析

回収率100%超えが確認された競艇場:
- 05 多摩川: 109.0%
- 11 琵琶湖: 108.6%
- 13 尼崎: 106.8%
- 18 徳山: 106.4%
- 24 大村: 105.7%

これらの競艇場で、さらに条件を絞り込んで110%超えを探す
"""

import psycopg2
import time
import json
from datetime import datetime

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def execute_query(query, timeout=180):
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
        print(f"  Error: {str(e)[:50]}")
        return None


def analyze_stadium_by_race_no(stadium_code, stadium_name):
    """競艇場×R番号別の分析"""
    print(f"\n--- {stadium_name}（{stadium_code}）R番号別分析 ---")
    
    results = []
    for race_no in ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']:
        query = f"""
            WITH qualified_races AS (
                SELECT DISTINCT hp.race_date, hp.stadium_code, hp.race_no
                FROM historical_programs hp
                WHERE hp.stadium_code = '{stadium_code}'
                  AND hp.race_no = '{race_no}'
                  AND hp.boat_no = '1'
                  AND hp.local_win_rate >= 4.5
                  AND hp.local_win_rate < 6.0
            ),
            payoffs AS (
                SELECT qr.race_date, qr.stadium_code, qr.race_no,
                       MAX(CASE WHEN p.bet_type = 'nirentan' THEN p.payout ELSE 0 END) as nirentan,
                       MAX(CASE WHEN p.bet_type = 'nirenpuku' THEN p.payout ELSE 0 END) as nirenpuku
                FROM qualified_races qr
                LEFT JOIN historical_payoffs p
                    ON p.race_date = qr.race_date
                    AND p.stadium_code = qr.stadium_code
                    AND p.race_no = qr.race_no
                    AND p.combination IN ('1-3', '1=3')
                GROUP BY qr.race_date, qr.stadium_code, qr.race_no
            )
            SELECT COUNT(*), SUM(GREATEST(nirentan, nirenpuku))
            FROM payoffs
        """
        result = execute_query(query)
        if result and result[0][0]:
            total_races = result[0][0]
            total_payout = int(result[0][1] or 0)
            if total_races > 50:
                return_rate = total_payout / (total_races * 100) * 100
                marker = " ✓✓" if return_rate >= 110 else (" ✓" if return_rate >= 100 else "")
                if return_rate >= 95:
                    print(f"  {race_no}R: {total_races}レース, 回収率{return_rate:.1f}%{marker}")
                results.append({
                    'stadium': stadium_name,
                    'stadium_code': stadium_code,
                    'race_no': race_no,
                    'total_races': total_races,
                    'total_payout': total_payout,
                    'return_rate': return_rate
                })
        time.sleep(1)
    
    return results


def analyze_tansho_by_stadium(stadium_code, stadium_name):
    """競艇場×号艇別の単勝分析"""
    print(f"\n--- {stadium_name}（{stadium_code}）単勝分析 ---")
    
    results = []
    for boat in ['1', '2', '3']:
        query = f"""
            WITH race_counts AS (
                SELECT COUNT(DISTINCT (race_date, race_no)) as total_races
                FROM historical_race_results
                WHERE stadium_code = '{stadium_code}'
                  AND boat_no = '1'
                  AND rank IS NOT NULL AND rank != 'F' AND rank != ''
            ),
            payoffs AS (
                SELECT COUNT(*) as hit_count, SUM(payout) as total_payout
                FROM historical_payoffs
                WHERE stadium_code = '{stadium_code}'
                  AND bet_type = 'tansho'
                  AND combination = '{boat}'
            )
            SELECT rc.total_races, p.hit_count, p.total_payout
            FROM race_counts rc, payoffs p
        """
        result = execute_query(query)
        if result and result[0][0]:
            total_races = result[0][0]
            hit_count = result[0][1] or 0
            total_payout = int(result[0][2] or 0)
            if total_races > 100:
                return_rate = total_payout / (total_races * 100) * 100
                hit_rate = hit_count / total_races * 100
                marker = " ✓✓" if return_rate >= 110 else (" ✓" if return_rate >= 100 else "")
                print(f"  {boat}号艇: {total_races:,}レース, 的中率{hit_rate:.1f}%, 回収率{return_rate:.1f}%{marker}")
                results.append({
                    'stadium': stadium_name,
                    'stadium_code': stadium_code,
                    'boat': boat,
                    'total_races': total_races,
                    'hit_count': hit_count,
                    'total_payout': total_payout,
                    'return_rate': return_rate
                })
        time.sleep(1)
    
    return results


def main():
    print("=" * 70)
    print("競艇場別詳細分析（回収率110%超え探索）")
    print(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 回収率100%超えが確認された競艇場
    target_stadiums = [
        ('05', '多摩川'),
        ('11', '琵琶湖'),
        ('13', '尼崎'),
        ('18', '徳山'),
        ('24', '大村'),
    ]
    
    all_results = {
        'niren_by_race': [],
        'tansho': []
    }
    
    for stadium_code, stadium_name in target_stadiums:
        # 2連（1-3）のR番号別分析
        niren_results = analyze_stadium_by_race_no(stadium_code, stadium_name)
        all_results['niren_by_race'].extend(niren_results)
        
        # 単勝の分析
        tansho_results = analyze_tansho_by_stadium(stadium_code, stadium_name)
        all_results['tansho'].extend(tansho_results)
    
    # 結果を保存
    with open('/home/ubuntu/stadium_detailed_results.json', 'w') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    # サマリー
    print("\n" + "=" * 70)
    print("【サマリー】回収率110%以上の条件")
    print("=" * 70)
    
    print("\n【2連1-3 × R番号】")
    high_return = [r for r in all_results['niren_by_race'] if r['return_rate'] >= 110]
    for r in sorted(high_return, key=lambda x: x['return_rate'], reverse=True):
        print(f"  {r['stadium']} {r['race_no']}R: {r['total_races']}レース, 回収率{r['return_rate']:.1f}%")
    
    print("\n【単勝】")
    high_return = [r for r in all_results['tansho'] if r['return_rate'] >= 100]
    for r in sorted(high_return, key=lambda x: x['return_rate'], reverse=True):
        print(f"  {r['stadium']} {r['boat']}号艇: {r['total_races']:,}レース, 回収率{r['return_rate']:.1f}%")
    
    print("\n結果を /home/ubuntu/stadium_detailed_results.json に保存しました")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
3連単/3連複の回収率分析

回収率110%以上の条件を探索
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


def analyze_sanrentan_by_stadium(stadium_code, stadium_name):
    """競艇場別の3連単分析（1号艇1着の組み合わせ）"""
    print(f"\n--- {stadium_name}（{stadium_code}）3連単分析 ---")
    
    results = []
    # 1号艇1着の主要な組み合わせ
    combinations = ['1-2-3', '1-2-4', '1-3-2', '1-3-4', '1-4-2', '1-4-3']
    
    for combo in combinations:
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
                  AND bet_type = 'sanrentan'
                  AND combination = '{combo}'
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
                if return_rate >= 70:
                    print(f"  {combo}: {total_races:,}レース, 的中率{hit_rate:.1f}%, 回収率{return_rate:.1f}%{marker}")
                results.append({
                    'stadium': stadium_name,
                    'stadium_code': stadium_code,
                    'combination': combo,
                    'total_races': total_races,
                    'hit_count': hit_count,
                    'total_payout': total_payout,
                    'return_rate': return_rate
                })
        time.sleep(1)
    
    return results


def analyze_sanrentan_with_local_win_rate(stadium_code, stadium_name):
    """当地勝率条件付きの3連単分析"""
    print(f"\n--- {stadium_name}（{stadium_code}）3連単（当地勝率4.5-6.0）---")
    
    results = []
    combinations = ['1-2-3', '1-3-2', '1-3-4']
    
    for combo in combinations:
        query = f"""
            WITH qualified_races AS (
                SELECT DISTINCT hp.race_date, hp.stadium_code, hp.race_no
                FROM historical_programs hp
                WHERE hp.stadium_code = '{stadium_code}'
                  AND hp.boat_no = '1'
                  AND hp.local_win_rate >= 4.5
                  AND hp.local_win_rate < 6.0
            ),
            payoffs AS (
                SELECT COUNT(*) as hit_count, SUM(payout) as total_payout
                FROM qualified_races qr
                JOIN historical_payoffs p
                    ON p.race_date = qr.race_date
                    AND p.stadium_code = qr.stadium_code
                    AND p.race_no = qr.race_no
                    AND p.bet_type = 'sanrentan'
                    AND p.combination = '{combo}'
            )
            SELECT (SELECT COUNT(*) FROM qualified_races), p.hit_count, p.total_payout
            FROM payoffs p
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
                if return_rate >= 70:
                    print(f"  {combo}: {total_races:,}レース, 的中率{hit_rate:.1f}%, 回収率{return_rate:.1f}%{marker}")
                results.append({
                    'stadium': stadium_name,
                    'stadium_code': stadium_code,
                    'combination': combo,
                    'condition': 'local_win_rate 4.5-6.0',
                    'total_races': total_races,
                    'hit_count': hit_count,
                    'total_payout': total_payout,
                    'return_rate': return_rate
                })
        time.sleep(1)
    
    return results


def main():
    print("=" * 70)
    print("3連単/3連複 回収率分析")
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
        'sanrentan_basic': [],
        'sanrentan_with_condition': []
    }
    
    for stadium_code, stadium_name in target_stadiums:
        # 基本的な3連単分析
        basic_results = analyze_sanrentan_by_stadium(stadium_code, stadium_name)
        all_results['sanrentan_basic'].extend(basic_results)
        
        # 当地勝率条件付きの3連単分析
        cond_results = analyze_sanrentan_with_local_win_rate(stadium_code, stadium_name)
        all_results['sanrentan_with_condition'].extend(cond_results)
    
    # 結果を保存
    with open('/home/ubuntu/sanren_analysis_results.json', 'w') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    # サマリー
    print("\n" + "=" * 70)
    print("【サマリー】回収率100%以上の条件")
    print("=" * 70)
    
    print("\n【3連単（基本）】")
    high_return = [r for r in all_results['sanrentan_basic'] if r['return_rate'] >= 100]
    for r in sorted(high_return, key=lambda x: x['return_rate'], reverse=True)[:10]:
        print(f"  {r['stadium']} {r['combination']}: {r['total_races']:,}レース, 回収率{r['return_rate']:.1f}%")
    
    print("\n【3連単（当地勝率4.5-6.0）】")
    high_return = [r for r in all_results['sanrentan_with_condition'] if r['return_rate'] >= 100]
    for r in sorted(high_return, key=lambda x: x['return_rate'], reverse=True)[:10]:
        print(f"  {r['stadium']} {r['combination']}: {r['total_races']:,}レース, 回収率{r['return_rate']:.1f}%")
    
    print("\n結果を /home/ubuntu/sanren_analysis_results.json に保存しました")

if __name__ == "__main__":
    main()

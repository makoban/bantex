#!/usr/bin/env python3
"""
競艇21年分データ - 年別に分割した2連複回収率分析
256MB RAM対応：1年ずつクエリを実行して結果を集計
"""

import psycopg2
import time
import json

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def get_yearly_nirenpuku_stats(year):
    """1年分の2連複統計を取得"""
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
        cur = conn.cursor()
        
        # 全レース数を取得
        cur.execute("""
            SELECT COUNT(DISTINCT (race_date, stadium_code, race_no))
            FROM historical_payoffs
            WHERE bet_type = 'nirenpuku'
              AND race_date >= %s
              AND race_date < %s
        """, (f'{year}-01-01', f'{year+1}-01-01'))
        
        total_races = cur.fetchone()[0]
        
        # 組み合わせ別の的中数と払戻金を取得
        cur.execute("""
            SELECT 
                combination,
                COUNT(*) as hits,
                SUM(payout) as total_payout
            FROM historical_payoffs
            WHERE bet_type = 'nirenpuku'
              AND race_date >= %s
              AND race_date < %s
            GROUP BY combination
            ORDER BY combination
        """, (f'{year}-01-01', f'{year+1}-01-01'))
        
        results = {}
        for row in cur.fetchall():
            results[row[0]] = {
                'hits': row[1],
                'total_payout': int(row[2] or 0)
            }
        
        cur.close()
        conn.close()
        
        return {'year': year, 'total_races': total_races, 'combinations': results}
    
    except Exception as e:
        print(f"  {year}年: エラー - {e}")
        return None

def main():
    print("=" * 60)
    print("競艇21年分データ - 年別2連複回収率分析")
    print("=" * 60)
    
    all_results = []
    
    # 2005年から2026年まで
    for year in range(2005, 2027):
        print(f"\n{year}年のデータを取得中...")
        result = get_yearly_nirenpuku_stats(year)
        
        if result:
            all_results.append(result)
            print(f"  レース数: {result['total_races']:,}")
            
            # 1=3の結果を表示
            if '1=3' in result['combinations']:
                data = result['combinations']['1=3']
                print(f"    1=3: 的中{data['hits']:,}回, 払戻¥{data['total_payout']:,}")
        
        time.sleep(2)  # 接続間隔を空ける
    
    # 全期間の集計
    print("\n" + "=" * 60)
    print("【全期間集計（2005-2026）】")
    print("=" * 60)
    
    total_races = sum(r['total_races'] for r in all_results if r)
    print(f"全レース数: {total_races:,}")
    
    # 1=3の集計
    hits_1_3 = sum(r['combinations'].get('1=3', {}).get('hits', 0) for r in all_results if r)
    payout_1_3 = sum(r['combinations'].get('1=3', {}).get('total_payout', 0) for r in all_results if r)
    
    hit_rate = hits_1_3 / total_races * 100 if total_races > 0 else 0
    return_rate = payout_1_3 / total_races if total_races > 0 else 0
    
    print(f"\n【2連複1=3の回収率】")
    print(f"  的中数: {hits_1_3:,}回 ({hit_rate:.2f}%)")
    print(f"  払戻合計: ¥{payout_1_3:,}")
    print(f"  回収率: {return_rate:.1f}%")
    
    # 全組み合わせの集計
    print("\n【2連複 全組み合わせ回収率TOP15】")
    combo_totals = {}
    for r in all_results:
        if r:
            for combo, data in r['combinations'].items():
                if combo not in combo_totals:
                    combo_totals[combo] = {'hits': 0, 'total_payout': 0}
                combo_totals[combo]['hits'] += data['hits']
                combo_totals[combo]['total_payout'] += data['total_payout']
    
    # 回収率でソート
    sorted_combos = sorted(combo_totals.items(), 
                           key=lambda x: x[1]['total_payout'] / total_races if total_races > 0 else 0, 
                           reverse=True)
    
    for combo, data in sorted_combos[:15]:
        hit_rate = data['hits'] / total_races * 100 if total_races > 0 else 0
        return_rate = data['total_payout'] / total_races if total_races > 0 else 0
        print(f"  {combo}: 的中{data['hits']:,}回 ({hit_rate:.2f}%), 回収率{return_rate:.1f}%")
    
    # 結果をJSONで保存
    output = {
        'total_races': total_races,
        'combo_1_3': {
            'hits': hits_1_3,
            'total_payout': payout_1_3,
            'hit_rate': hit_rate,
            'return_rate': return_rate
        },
        'all_combos': combo_totals,
        'yearly_data': all_results
    }
    
    with open('/home/ubuntu/nirenpuku_analysis_result.json', 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print("\n結果を /home/ubuntu/nirenpuku_analysis_result.json に保存しました")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
競艇21年分データ - 年別に分割した単勝回収率分析
256MB RAM対応：1年ずつクエリを実行して結果を集計
"""

import psycopg2
import time
import json

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def get_yearly_tansho_stats(year):
    """1年分の単勝統計を取得"""
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
        cur = conn.cursor()
        
        # 号艇別の勝利数と払戻金を取得
        cur.execute("""
            SELECT 
                combination as boat,
                COUNT(*) as wins,
                SUM(payout) as total_payout
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
              AND race_date >= %s
              AND race_date < %s
            GROUP BY combination
            ORDER BY combination
        """, (f'{year}-01-01', f'{year+1}-01-01'))
        
        results = {}
        for row in cur.fetchall():
            results[row[0]] = {
                'wins': row[1],
                'total_payout': int(row[2] or 0)
            }
        
        # 全レース数を取得
        cur.execute("""
            SELECT COUNT(DISTINCT (race_date, stadium_code, race_no))
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
              AND race_date >= %s
              AND race_date < %s
        """, (f'{year}-01-01', f'{year+1}-01-01'))
        
        total_races = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return {'year': year, 'total_races': total_races, 'boats': results}
    
    except Exception as e:
        print(f"  {year}年: エラー - {e}")
        return None

def main():
    print("=" * 60)
    print("競艇21年分データ - 年別単勝回収率分析")
    print("=" * 60)
    
    all_results = []
    
    # 2005年から2026年まで
    for year in range(2005, 2027):
        print(f"\n{year}年のデータを取得中...")
        result = get_yearly_tansho_stats(year)
        
        if result:
            all_results.append(result)
            print(f"  レース数: {result['total_races']:,}")
            for boat, data in result['boats'].items():
                print(f"    {boat}号艇: 勝利{data['wins']:,}回, 払戻¥{data['total_payout']:,}")
        
        time.sleep(2)  # 接続間隔を空ける
    
    # 全期間の集計
    print("\n" + "=" * 60)
    print("【全期間集計（2005-2026）】")
    print("=" * 60)
    
    total_races = sum(r['total_races'] for r in all_results)
    print(f"全レース数: {total_races:,}")
    
    # 号艇別集計
    boat_totals = {}
    for boat in ['1', '2', '3', '4', '5', '6']:
        wins = sum(r['boats'].get(boat, {}).get('wins', 0) for r in all_results)
        payout = sum(r['boats'].get(boat, {}).get('total_payout', 0) for r in all_results)
        boat_totals[boat] = {'wins': wins, 'total_payout': payout}
        
        win_rate = wins / total_races * 100 if total_races > 0 else 0
        return_rate = payout / total_races if total_races > 0 else 0
        
        print(f"{boat}号艇: 勝利{wins:,}回 ({win_rate:.1f}%), 払戻合計¥{payout:,}, 回収率{return_rate:.1f}%")
    
    # 結果をJSONで保存
    output = {
        'total_races': total_races,
        'boat_totals': boat_totals,
        'yearly_data': all_results
    }
    
    with open('/home/ubuntu/tansho_analysis_result.json', 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print("\n結果を /home/ubuntu/tansho_analysis_result.json に保存しました")

if __name__ == "__main__":
    main()

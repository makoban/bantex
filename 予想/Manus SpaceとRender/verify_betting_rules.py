#!/usr/bin/env python3
"""
競艇予想システム - 現在の購入ルールの回収率検証

購入ルール:
1. 11R・12R単勝戦略: 11R/12Rで1号艇単勝、オッズ1.5〜10.0
2. 1-3穴バイアス戦略: 全レースで2連複1-3、オッズ3.0〜50.0

※ オッズデータがhistorical_payoffsにはないため、払戻金から逆算
   単勝払戻金 = オッズ × 100円
   2連複払戻金 = オッズ × 100円
"""

import psycopg2
import time
import json

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def verify_rule1_11r_12r_tansho():
    """
    ルール1: 11R・12R単勝1号艇（オッズ1.5〜10.0）の回収率を検証
    オッズ1.5〜10.0 = 払戻金150円〜1000円
    """
    print("\n" + "=" * 60)
    print("【ルール1】11R・12R単勝1号艇（オッズ1.5〜10.0）")
    print("=" * 60)
    
    results = {'11': None, '12': None, 'total': None}
    
    for race_no in ['11', '12']:
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
            cur = conn.cursor()
            
            # 11R/12Rの1号艇単勝で、払戻金150-1000円（オッズ1.5-10.0）のレースを集計
            cur.execute("""
                SELECT 
                    COUNT(*) as hit_count,
                    SUM(payout) as total_payout
                FROM historical_payoffs
                WHERE bet_type = 'tansho' 
                  AND combination = '1'
                  AND race_no = %s
                  AND payout >= 150 
                  AND payout <= 1000
            """, (race_no,))
            
            hit_row = cur.fetchone()
            hit_count = hit_row[0]
            total_payout = int(hit_row[1] or 0)
            
            # 11R/12Rの全レース数（オッズ条件を満たすレース）を取得
            # ※ 単勝オッズは事前にわからないため、全レースを対象とする
            cur.execute("""
                SELECT COUNT(DISTINCT (race_date, stadium_code))
                FROM historical_payoffs
                WHERE bet_type = 'tansho' 
                  AND race_no = %s
            """, (race_no,))
            
            total_races = cur.fetchone()[0]
            
            cur.close()
            conn.close()
            
            # 回収率計算（全レース購入した場合）
            # 投資額 = 全レース数 × 100円
            investment = total_races * 100
            return_rate = total_payout / investment * 100 if investment > 0 else 0
            
            results[race_no] = {
                'total_races': total_races,
                'hit_count': hit_count,
                'hit_rate': hit_count / total_races * 100 if total_races > 0 else 0,
                'total_payout': total_payout,
                'investment': investment,
                'return_rate': return_rate
            }
            
            print(f"\n{race_no}R:")
            print(f"  全レース数: {total_races:,}")
            print(f"  的中数（オッズ1.5-10.0内）: {hit_count:,}")
            print(f"  払戻合計: ¥{total_payout:,}")
            print(f"  投資額: ¥{investment:,}")
            print(f"  回収率: {return_rate:.1f}%")
            
            time.sleep(2)
            
        except Exception as e:
            print(f"  {race_no}R: エラー - {e}")
    
    # 合計
    if results['11'] and results['12']:
        total_races = results['11']['total_races'] + results['12']['total_races']
        total_payout = results['11']['total_payout'] + results['12']['total_payout']
        investment = total_races * 100
        return_rate = total_payout / investment * 100 if investment > 0 else 0
        
        results['total'] = {
            'total_races': total_races,
            'total_payout': total_payout,
            'investment': investment,
            'return_rate': return_rate
        }
        
        print(f"\n【11R+12R合計】")
        print(f"  全レース数: {total_races:,}")
        print(f"  払戻合計: ¥{total_payout:,}")
        print(f"  投資額: ¥{investment:,}")
        print(f"  回収率: {return_rate:.1f}%")
    
    return results

def verify_rule2_nirenpuku_1_3():
    """
    ルール2: 2連複1-3（オッズ3.0〜50.0）の回収率を検証
    オッズ3.0〜50.0 = 払戻金300円〜5000円
    """
    print("\n" + "=" * 60)
    print("【ルール2】2連複1-3（オッズ3.0〜50.0）")
    print("=" * 60)
    
    results = []
    total_races_all = 0
    total_payout_all = 0
    total_hits_all = 0
    
    # 年別に分割して実行
    for year in range(2005, 2027):
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
            cur = conn.cursor()
            
            # 2連複1-3で、払戻金300-5000円（オッズ3.0-50.0）のレースを集計
            cur.execute("""
                SELECT 
                    COUNT(*) as hit_count,
                    SUM(payout) as total_payout
                FROM historical_payoffs
                WHERE bet_type = 'nirenpuku' 
                  AND combination = '1-3'
                  AND race_date >= %s
                  AND race_date < %s
                  AND payout >= 300 
                  AND payout <= 5000
            """, (f'{year}-01-01', f'{year+1}-01-01'))
            
            hit_row = cur.fetchone()
            hit_count = hit_row[0]
            total_payout = int(hit_row[1] or 0)
            
            # 全レース数を取得
            cur.execute("""
                SELECT COUNT(DISTINCT (race_date, stadium_code, race_no))
                FROM historical_payoffs
                WHERE bet_type = 'nirenpuku'
                  AND race_date >= %s
                  AND race_date < %s
            """, (f'{year}-01-01', f'{year+1}-01-01'))
            
            total_races = cur.fetchone()[0]
            
            cur.close()
            conn.close()
            
            total_races_all += total_races
            total_payout_all += total_payout
            total_hits_all += hit_count
            
            results.append({
                'year': year,
                'total_races': total_races,
                'hit_count': hit_count,
                'total_payout': total_payout
            })
            
            print(f"  {year}年: レース{total_races:,}, 的中{hit_count:,}, 払戻¥{total_payout:,}")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"  {year}年: エラー - {e}")
    
    # 全期間集計
    investment = total_races_all * 100
    return_rate = total_payout_all / investment * 100 if investment > 0 else 0
    hit_rate = total_hits_all / total_races_all * 100 if total_races_all > 0 else 0
    
    print(f"\n【全期間集計】")
    print(f"  全レース数: {total_races_all:,}")
    print(f"  的中数（オッズ3.0-50.0内）: {total_hits_all:,}")
    print(f"  的中率: {hit_rate:.2f}%")
    print(f"  払戻合計: ¥{total_payout_all:,}")
    print(f"  投資額: ¥{investment:,}")
    print(f"  回収率: {return_rate:.1f}%")
    
    return {
        'total_races': total_races_all,
        'hit_count': total_hits_all,
        'hit_rate': hit_rate,
        'total_payout': total_payout_all,
        'investment': investment,
        'return_rate': return_rate,
        'yearly_data': results
    }

def main():
    print("=" * 60)
    print("競艇予想システム - 購入ルール回収率検証")
    print("=" * 60)
    print("\n※ オッズ条件は払戻金から逆算")
    print("  単勝オッズ1.5-10.0 = 払戻金150-1000円")
    print("  2連複オッズ3.0-50.0 = 払戻金300-5000円")
    
    # ルール1: 11R・12R単勝1号艇
    rule1_results = verify_rule1_11r_12r_tansho()
    
    # ルール2: 2連複1-3
    rule2_results = verify_rule2_nirenpuku_1_3()
    
    # 結果をJSONで保存
    output = {
        'rule1_11r_12r_tansho': rule1_results,
        'rule2_nirenpuku_1_3': rule2_results
    }
    
    with open('/home/ubuntu/betting_rules_verification.json', 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print("検証完了")
    print("結果を /home/ubuntu/betting_rules_verification.json に保存しました")
    print("=" * 60)

if __name__ == "__main__":
    main()

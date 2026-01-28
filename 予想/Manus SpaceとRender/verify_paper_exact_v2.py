#!/usr/bin/env python3
"""
岩郷論文の条件を完全に再現して回収率を検証するスクリプト（修正版）

論文の条件:
- 対象場: 大村競艇場（stadium_code = '24'）
- 対象期間: 春季（3月〜5月）
- 条件: 1号艇の当地成績6.5以上
- 購入: 2連単または2連複の1-3（オッズの高い方）
- 除外: SG・G1などの特殊レース

DBの形式:
- bet_type: 'nirentan'（2連単）, 'nirenfuku'/'nirenpuku'（2連複）
- combination: '1-3' または '1=3'
"""

import psycopg2
import json
from decimal import Decimal

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def decimal_to_float(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def verify_paper_conditions():
    """論文の条件を完全に再現して回収率を計算"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    results = {}
    
    # 論文の検証期間
    periods = [
        ("2018年3月〜5月（論文の分析期間）", "2018-03-01", "2018-05-31"),
        ("2017年3月〜5月（論文の検証期間1）", "2017-03-01", "2017-05-31"),
        ("2018年10月〜12月（論文の検証期間2）", "2018-10-01", "2018-12-31"),
    ]
    
    for period_name, start_date, end_date in periods:
        print(f"\n{'='*60}")
        print(f"検証期間: {period_name}")
        print(f"{'='*60}")
        
        # 対象レースを取得（当地成績6.5以上）
        query = """
        SELECT DISTINCT
            hp.race_date,
            hp.stadium_code,
            hp.race_no,
            hp.local_win_rate
        FROM historical_programs hp
        WHERE hp.stadium_code = '24'
          AND hp.race_date BETWEEN %s AND %s
          AND hp.boat_no = '1'
          AND hp.local_win_rate >= 6.5
        ORDER BY hp.race_date, hp.race_no
        """
        
        print("対象レースを取得中...")
        cur.execute(query, (start_date, end_date))
        target_races = cur.fetchall()
        print(f"対象レース数: {len(target_races)}")
        
        if len(target_races) == 0:
            print("対象レースがありません")
            continue
        
        total_investment = 0
        total_payout = 0
        hit_count = 0
        
        for race_date, stadium_code, race_no, local_win_rate in target_races:
            # 2連単1-3の払戻金を取得
            cur.execute("""
                SELECT payout FROM historical_payoffs
                WHERE race_date = %s AND stadium_code = %s AND race_no = %s
                  AND bet_type = 'nirentan' AND combination = '1-3'
            """, (race_date, stadium_code, race_no))
            nitan_result = cur.fetchone()
            nitan_payout = float(nitan_result[0]) if nitan_result else 0
            
            # 2連複1-3の払戻金を取得（1-3 または 1=3）
            cur.execute("""
                SELECT payout FROM historical_payoffs
                WHERE race_date = %s AND stadium_code = %s AND race_no = %s
                  AND bet_type IN ('nirenfuku', 'nirenpuku') 
                  AND combination IN ('1-3', '1=3')
            """, (race_date, stadium_code, race_no))
            nifuku_result = cur.fetchone()
            nifuku_payout = float(nifuku_result[0]) if nifuku_result else 0
            
            # オッズの高い方を選択（払戻金が高い方）
            selected_payout = max(nitan_payout, nifuku_payout)
            
            total_investment += 100
            total_payout += selected_payout
            
            if selected_payout > 0:
                hit_count += 1
        
        return_rate = (total_payout / total_investment * 100) if total_investment > 0 else 0
        hit_rate = (hit_count / len(target_races) * 100) if len(target_races) > 0 else 0
        
        print(f"\n【結果】")
        print(f"対象レース数: {len(target_races)}")
        print(f"的中数: {hit_count}")
        print(f"的中率: {hit_rate:.1f}%")
        print(f"投資額: ¥{total_investment:,}")
        print(f"払戻額: ¥{total_payout:,.0f}")
        print(f"回収率: {return_rate:.1f}%")
        
        results[period_name] = {
            "races": len(target_races),
            "hits": hit_count,
            "hit_rate": hit_rate,
            "investment": total_investment,
            "payout": total_payout,
            "return_rate": return_rate
        }
    
    # 追加検証: 当地成績の範囲別回収率（論文の図2を再現）
    print(f"\n{'='*60}")
    print("追加検証: 当地成績の範囲別回収率（2018年3月〜5月）")
    print(f"{'='*60}")
    
    ranges = [
        (5.0, 5.5),
        (5.5, 6.0),
        (6.0, 6.5),
        (6.5, 7.0),
        (7.0, 7.5),
        (7.5, 10.0),
    ]
    
    for min_rate, max_rate in ranges:
        query = """
        SELECT DISTINCT
            hp.race_date,
            hp.stadium_code,
            hp.race_no
        FROM historical_programs hp
        WHERE hp.stadium_code = '24'
          AND hp.race_date BETWEEN '2018-03-01' AND '2018-05-31'
          AND hp.boat_no = '1'
          AND hp.local_win_rate >= %s AND hp.local_win_rate < %s
        """
        
        cur.execute(query, (min_rate, max_rate))
        target_races = cur.fetchall()
        
        total_investment = 0
        total_payout = 0
        hit_count = 0
        
        for race_date, stadium_code, race_no in target_races:
            # 2連単1-3
            cur.execute("""
                SELECT payout FROM historical_payoffs
                WHERE race_date = %s AND stadium_code = %s AND race_no = %s
                  AND bet_type = 'nirentan' AND combination = '1-3'
            """, (race_date, stadium_code, race_no))
            nitan_result = cur.fetchone()
            nitan_payout = float(nitan_result[0]) if nitan_result else 0
            
            # 2連複1-3
            cur.execute("""
                SELECT payout FROM historical_payoffs
                WHERE race_date = %s AND stadium_code = %s AND race_no = %s
                  AND bet_type IN ('nirenfuku', 'nirenpuku')
                  AND combination IN ('1-3', '1=3')
            """, (race_date, stadium_code, race_no))
            nifuku_result = cur.fetchone()
            nifuku_payout = float(nifuku_result[0]) if nifuku_result else 0
            
            selected_payout = max(nitan_payout, nifuku_payout)
            
            total_investment += 100
            total_payout += selected_payout
            
            if selected_payout > 0:
                hit_count += 1
        
        return_rate = (total_payout / total_investment * 100) if total_investment > 0 else 0
        hit_rate = (hit_count / len(target_races) * 100) if len(target_races) > 0 else 0
        
        print(f"当地成績 {min_rate}〜{max_rate}: レース数={len(target_races)}, 的中率={hit_rate:.1f}%, 回収率={return_rate:.1f}%")
        
        results[f"range_{min_rate}_{max_rate}"] = {
            "races": len(target_races),
            "hits": hit_count,
            "hit_rate": hit_rate,
            "return_rate": return_rate
        }
    
    cur.close()
    conn.close()
    
    # 結果をJSONファイルに保存
    with open('/home/ubuntu/paper_exact_verification_v2.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=decimal_to_float)
    
    print(f"\n結果を /home/ubuntu/paper_exact_verification_v2.json に保存しました")
    
    return results

if __name__ == "__main__":
    verify_paper_conditions()

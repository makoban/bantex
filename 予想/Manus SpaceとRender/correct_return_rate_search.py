#!/usr/bin/env python3
"""
正しい回収率計算を行う検証スクリプト

回収率の正しい計算方法:
- 投資額 = 対象レース数（全レース）× 100円
- 払戻額 = 的中した場合の払戻金合計
- 回収率 = 払戻額 / 投資額 × 100%

historical_payoffsテーブルには「的中した」レースのみが記録されている。
そのため、「対象条件を満たす全レース数」を別途取得する必要がある。

方法: historical_resultsテーブルから全レース数を取得
"""

import psycopg2
import time
import json

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def get_total_races_by_race_no(race_no):
    """R番号別の全レース数を取得"""
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
        cur = conn.cursor()
        
        query = f"""
            SELECT COUNT(DISTINCT (race_date, stadium_code, race_no))
            FROM historical_results
            WHERE race_no = '{race_no}'
        """
        cur.execute(query)
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        return row[0] or 0
    except Exception as e:
        print(f"Error: {e}")
        return 0


def get_tansho_payout_by_boat_and_race(boat, race_no):
    """号艇 × R番号の払戻金合計を取得（的中したレースのみ）"""
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
        cur = conn.cursor()
        
        query = f"""
            SELECT COUNT(*), SUM(payout)
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
              AND combination = '{boat}'
              AND race_no = '{race_no}'
        """
        cur.execute(query)
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        return row[0] or 0, int(row[1] or 0)
    except Exception as e:
        return 0, 0


def get_total_races_by_stadium(stadium_code):
    """競艇場別の全レース数を取得"""
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
        cur = conn.cursor()
        
        query = f"""
            SELECT COUNT(DISTINCT (race_date, stadium_code, race_no))
            FROM historical_results
            WHERE stadium_code = '{stadium_code}'
        """
        cur.execute(query)
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        return row[0] or 0
    except Exception as e:
        print(f"Error: {e}")
        return 0


def get_tansho_payout_by_boat_and_stadium(boat, stadium_code):
    """号艇 × 場の払戻金合計を取得"""
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=60)
        cur = conn.cursor()
        
        query = f"""
            SELECT COUNT(*), SUM(payout)
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
              AND combination = '{boat}'
              AND stadium_code = '{stadium_code}'
        """
        cur.execute(query)
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        return row[0] or 0, int(row[1] or 0)
    except Exception as e:
        return 0, 0


def main():
    print("=" * 70)
    print("【単勝戦略】正しい回収率計算で条件を探索")
    print("=" * 70)
    
    results = []
    
    # 競艇場名のマッピング
    stadium_names = {
        '01': '桐生', '02': '戸田', '03': '江戸川', '04': '平和島', '05': '多摩川',
        '06': '浜名湖', '07': '蒲郡', '08': '常滑', '09': '津', '10': '三国',
        '11': '琵琶湖', '12': '住之江', '13': '尼崎', '14': '鳴門', '15': '丸亀',
        '16': '児島', '17': '宮島', '18': '徳山', '19': '下関', '20': '若松',
        '21': '芦屋', '22': '福岡', '23': '唐津', '24': '大村'
    }
    
    # まず、R番号別の全レース数を取得
    print("\n--- R番号別の全レース数を取得 ---")
    total_races_by_race = {}
    for race_no in ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']:
        total = get_total_races_by_race_no(race_no)
        total_races_by_race[race_no] = total
        print(f"  {race_no}R: {total:,}レース")
        time.sleep(0.5)
    
    # 1. 号艇 × R番号（正しい回収率計算）
    print("\n--- 号艇 × R番号（正しい回収率計算）---")
    for boat in ['1', '2', '3', '4', '5', '6']:
        for race_no in ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']:
            total_races = total_races_by_race.get(race_no, 0)
            hit_count, payout = get_tansho_payout_by_boat_and_race(boat, race_no)
            
            if total_races > 1000:
                # 正しい回収率計算: 払戻額 / (全レース数 × 100円)
                return_rate = payout / (total_races * 100) * 100
                hit_rate = hit_count / total_races * 100 if total_races > 0 else 0
                
                result = {
                    'type': 'tansho',
                    'boat': boat,
                    'race_no': race_no,
                    'total_races': total_races,
                    'hit_count': hit_count,
                    'hit_rate': hit_rate,
                    'payout': payout,
                    'return_rate': return_rate
                }
                results.append(result)
                
                if return_rate >= 85:  # 85%以上を表示
                    marker = " ✓✓" if return_rate >= 110 else (" ✓" if return_rate >= 100 else "")
                    print(f"  {boat}号艇 × {race_no}R: 全{total_races:,}レース, "
                          f"的中{hit_count:,} ({hit_rate:.1f}%), 回収率{return_rate:.1f}%{marker}")
            time.sleep(0.3)
    
    # 2. 号艇 × 競艇場（正しい回収率計算）
    print("\n--- 号艇 × 競艇場（正しい回収率計算）---")
    
    # 競艇場別の全レース数を取得
    total_races_by_stadium = {}
    for stadium_code in stadium_names.keys():
        total = get_total_races_by_stadium(stadium_code)
        total_races_by_stadium[stadium_code] = total
        time.sleep(0.3)
    
    for boat in ['1', '2', '3']:  # 1-3号艇のみ
        for stadium_code in stadium_names.keys():
            total_races = total_races_by_stadium.get(stadium_code, 0)
            hit_count, payout = get_tansho_payout_by_boat_and_stadium(boat, stadium_code)
            
            if total_races > 1000:
                return_rate = payout / (total_races * 100) * 100
                hit_rate = hit_count / total_races * 100 if total_races > 0 else 0
                
                result = {
                    'type': 'tansho',
                    'boat': boat,
                    'stadium': stadium_names[stadium_code],
                    'stadium_code': stadium_code,
                    'total_races': total_races,
                    'hit_count': hit_count,
                    'hit_rate': hit_rate,
                    'payout': payout,
                    'return_rate': return_rate
                }
                results.append(result)
                
                if return_rate >= 85:
                    marker = " ✓✓" if return_rate >= 110 else (" ✓" if return_rate >= 100 else "")
                    name = stadium_names[stadium_code]
                    print(f"  {boat}号艇 × {name}: 全{total_races:,}レース, "
                          f"的中{hit_count:,} ({hit_rate:.1f}%), 回収率{return_rate:.1f}%{marker}")
            time.sleep(0.3)
    
    # 結果を保存
    with open('/home/ubuntu/correct_tansho_results.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # サマリー
    print("\n" + "=" * 70)
    print("【サマリー】回収率90%以上の条件（上位10件）")
    print("=" * 70)
    high_return = [r for r in results if r['return_rate'] >= 90]
    for r in sorted(high_return, key=lambda x: x['return_rate'], reverse=True)[:10]:
        print(f"  {r['boat']}号艇: 回収率{r['return_rate']:.1f}%, 的中率{r['hit_rate']:.1f}%")
    
    print("\n結果を /home/ubuntu/correct_tansho_results.json に保存しました")

if __name__ == "__main__":
    main()

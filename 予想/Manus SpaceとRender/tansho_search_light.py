#!/usr/bin/env python3
"""
単勝の回収率110%以上条件を探索（軽量版）
- 年別に分割してクエリを実行
- 結果を集計
"""

import psycopg2
import time
import json

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def query_tansho_by_boat_and_race(boat, race_no):
    """号艇 × R番号の回収率を取得"""
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

def query_tansho_by_boat_and_stadium(boat, stadium_code):
    """号艇 × 場の回収率を取得"""
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
    print("【単勝戦略】回収率110%以上の条件を探索")
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
    
    # 1. 号艇 × R番号
    print("\n--- 号艇 × R番号 ---")
    for boat in ['1', '2', '3', '4', '5', '6']:
        for race_no in ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']:
            races, payout = query_tansho_by_boat_and_race(boat, race_no)
            if races > 1000:
                return_rate = payout / (races * 100) * 100
                if return_rate >= 95:
                    marker = " ✓✓" if return_rate >= 110 else (" ✓" if return_rate >= 100 else "")
                    print(f"  {boat}号艇 × {race_no}R: {races:,}レース, 回収率{return_rate:.1f}%{marker}")
                    results.append({
                        'type': 'tansho',
                        'boat': boat,
                        'race_no': race_no,
                        'races': races,
                        'return_rate': return_rate
                    })
            time.sleep(0.5)
    
    # 2. 号艇 × 場
    print("\n--- 号艇 × 競艇場 ---")
    for boat in ['1', '2', '3', '4', '5', '6']:
        for stadium_code in stadium_names.keys():
            races, payout = query_tansho_by_boat_and_stadium(boat, stadium_code)
            if races > 1000:
                return_rate = payout / (races * 100) * 100
                if return_rate >= 95:
                    marker = " ✓✓" if return_rate >= 110 else (" ✓" if return_rate >= 100 else "")
                    name = stadium_names[stadium_code]
                    print(f"  {boat}号艇 × {name}: {races:,}レース, 回収率{return_rate:.1f}%{marker}")
                    results.append({
                        'type': 'tansho',
                        'boat': boat,
                        'stadium': name,
                        'stadium_code': stadium_code,
                        'races': races,
                        'return_rate': return_rate
                    })
            time.sleep(0.5)
    
    # 結果を保存
    with open('/home/ubuntu/tansho_search_results.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # サマリー
    print("\n" + "=" * 70)
    print("【サマリー】回収率100%以上の条件")
    print("=" * 70)
    high_return = [r for r in results if r['return_rate'] >= 100]
    for r in sorted(high_return, key=lambda x: x['return_rate'], reverse=True)[:10]:
        print(f"  {r}")
    
    print("\n結果を /home/ubuntu/tansho_search_results.json に保存しました")

if __name__ == "__main__":
    main()

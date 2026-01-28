#!/usr/bin/env python3
"""
岩郷戦略の検証スクリプト v3 - オッズの歪みを考慮した追加検証

穴バイアスの本質:
- 1-3が「本来の本命」なのに、大衆が1-2を本命と思い込む
- その結果、1-3のオッズが「実力以上に高くなる」
- この「歪み」を利用して期待値プラスを狙う

追加検証:
1. 当地勝率5.0-5.5の範囲での詳細検証（回収率105.7%だった）
2. 全競艇場への拡大検証
3. 最適な条件の特定
"""

import psycopg2
import time
import json

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def verify_strategy_all_stadiums(threshold_low, threshold_high):
    """
    全競艇場での検証
    """
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=180)
        cur = conn.cursor()
        
        query = f"""
            WITH qualified_races AS (
                SELECT DISTINCT race_date, stadium_code, race_no
                FROM historical_programs
                WHERE boat_no = '1'
                  AND local_win_rate >= {threshold_low}
                  AND local_win_rate < {threshold_high}
            ),
            payoffs AS (
                SELECT 
                    qr.race_date,
                    qr.stadium_code,
                    qr.race_no,
                    MAX(CASE WHEN hp.bet_type = 'nirentan' THEN hp.payout ELSE 0 END) as nirentan_payout,
                    MAX(CASE WHEN hp.bet_type = 'nirenpuku' THEN hp.payout ELSE 0 END) as nirenpuku_payout
                FROM qualified_races qr
                LEFT JOIN historical_payoffs hp
                    ON hp.race_date = qr.race_date
                    AND hp.stadium_code = qr.stadium_code
                    AND hp.race_no = qr.race_no
                    AND hp.combination = '1-3'
                    AND hp.bet_type IN ('nirentan', 'nirenpuku')
                GROUP BY qr.race_date, qr.stadium_code, qr.race_no
            )
            SELECT 
                COUNT(*) as total_races,
                SUM(CASE WHEN nirentan_payout > 0 OR nirenpuku_payout > 0 THEN 1 ELSE 0 END) as hit_count,
                SUM(GREATEST(nirentan_payout, nirenpuku_payout)) as total_payout_max
            FROM payoffs
        """
        
        cur.execute(query)
        row = cur.fetchone()
        
        cur.close()
        conn.close()
        
        total_races = row[0] or 0
        hit_count = row[1] or 0
        total_payout_max = int(row[2] or 0)
        
        return {
            'range': f'{threshold_low}-{threshold_high}',
            'total_races': total_races,
            'hit_count': hit_count,
            'hit_rate': hit_count / total_races * 100 if total_races > 0 else 0,
            'total_payout': total_payout_max,
            'investment': total_races * 100,
            'return_rate': total_payout_max / (total_races * 100) * 100 if total_races > 0 else 0
        }
        
    except Exception as e:
        return {'range': f'{threshold_low}-{threshold_high}', 'error': str(e)}


def verify_strategy_by_stadium(threshold_low, threshold_high):
    """
    競艇場別の検証
    """
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=180)
        cur = conn.cursor()
        
        query = f"""
            WITH qualified_races AS (
                SELECT DISTINCT race_date, stadium_code, race_no
                FROM historical_programs
                WHERE boat_no = '1'
                  AND local_win_rate >= {threshold_low}
                  AND local_win_rate < {threshold_high}
            ),
            payoffs AS (
                SELECT 
                    qr.race_date,
                    qr.stadium_code,
                    qr.race_no,
                    MAX(CASE WHEN hp.bet_type = 'nirentan' THEN hp.payout ELSE 0 END) as nirentan_payout,
                    MAX(CASE WHEN hp.bet_type = 'nirenpuku' THEN hp.payout ELSE 0 END) as nirenpuku_payout
                FROM qualified_races qr
                LEFT JOIN historical_payoffs hp
                    ON hp.race_date = qr.race_date
                    AND hp.stadium_code = qr.stadium_code
                    AND hp.race_no = qr.race_no
                    AND hp.combination = '1-3'
                    AND hp.bet_type IN ('nirentan', 'nirenpuku')
                GROUP BY qr.race_date, qr.stadium_code, qr.race_no
            )
            SELECT 
                stadium_code,
                COUNT(*) as total_races,
                SUM(CASE WHEN nirentan_payout > 0 OR nirenpuku_payout > 0 THEN 1 ELSE 0 END) as hit_count,
                SUM(GREATEST(nirentan_payout, nirenpuku_payout)) as total_payout_max
            FROM payoffs
            GROUP BY stadium_code
            ORDER BY stadium_code
        """
        
        cur.execute(query)
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        
        results = []
        for row in rows:
            stadium_code = row[0]
            total_races = row[1] or 0
            hit_count = row[2] or 0
            total_payout = int(row[3] or 0)
            
            results.append({
                'stadium_code': stadium_code,
                'total_races': total_races,
                'hit_count': hit_count,
                'hit_rate': hit_count / total_races * 100 if total_races > 0 else 0,
                'total_payout': total_payout,
                'return_rate': total_payout / (total_races * 100) * 100 if total_races > 0 else 0
            })
        
        return results
        
    except Exception as e:
        return [{'error': str(e)}]


def main():
    print("=" * 70)
    print("岩郷戦略の検証 v3 - オッズの歪みを考慮した追加検証")
    print("=" * 70)
    
    results = {}
    
    # ============================================================
    # 検証1: 全競艇場での当地勝率範囲別検証
    # ============================================================
    print("\n【検証1】全競艇場での当地勝率範囲別検証")
    print("-" * 50)
    
    ranges = [
        (4.5, 5.0), (5.0, 5.5), (5.5, 6.0), (6.0, 6.5), 
        (6.5, 7.0), (7.0, 7.5), (7.5, 8.0), (8.0, 10.0)
    ]
    range_results = []
    
    for low, high in ranges:
        result = verify_strategy_all_stadiums(low, high)
        range_results.append(result)
        
        if 'error' not in result:
            marker = " ✓" if result['return_rate'] >= 100 else ""
            print(f"  {result['range']}: レース{result['total_races']:,}, "
                  f"的中{result['hit_count']:,} ({result['hit_rate']:.1f}%), "
                  f"回収率{result['return_rate']:.1f}%{marker}")
        else:
            print(f"  {result['range']}: エラー - {result['error']}")
        
        time.sleep(3)
    
    results['range_analysis_all'] = range_results
    
    # ============================================================
    # 検証2: 当地勝率5.0-5.5での競艇場別検証
    # ============================================================
    print("\n【検証2】当地勝率5.0-5.5での競艇場別検証")
    print("-" * 50)
    
    stadium_results = verify_strategy_by_stadium(5.0, 5.5)
    
    # 競艇場名のマッピング
    stadium_names = {
        '01': '桐生', '02': '戸田', '03': '江戸川', '04': '平和島', '05': '多摩川',
        '06': '浜名湖', '07': '蒲郡', '08': '常滑', '09': '津', '10': '三国',
        '11': '琵琶湖', '12': '住之江', '13': '尼崎', '14': '鳴門', '15': '丸亀',
        '16': '児島', '17': '宮島', '18': '徳山', '19': '下関', '20': '若松',
        '21': '芦屋', '22': '福岡', '23': '唐津', '24': '大村'
    }
    
    if 'error' not in stadium_results[0]:
        # 回収率でソート
        sorted_results = sorted(stadium_results, key=lambda x: x['return_rate'], reverse=True)
        
        print("  回収率100%以上の競艇場:")
        for r in sorted_results:
            if r['return_rate'] >= 100:
                name = stadium_names.get(r['stadium_code'], r['stadium_code'])
                print(f"    {name}({r['stadium_code']}): レース{r['total_races']:,}, "
                      f"的中{r['hit_rate']:.1f}%, 回収率{r['return_rate']:.1f}%")
        
        print("\n  回収率90%以上100%未満の競艇場:")
        for r in sorted_results:
            if 90 <= r['return_rate'] < 100:
                name = stadium_names.get(r['stadium_code'], r['stadium_code'])
                print(f"    {name}({r['stadium_code']}): レース{r['total_races']:,}, "
                      f"的中{r['hit_rate']:.1f}%, 回収率{r['return_rate']:.1f}%")
    else:
        print(f"  エラー: {stadium_results[0]['error']}")
    
    results['stadium_analysis'] = stadium_results
    
    # 結果を保存
    with open('/home/ubuntu/iwago_strategy_verification_v3.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 70)
    print("検証完了")
    print("結果を /home/ubuntu/iwago_strategy_verification_v3.json に保存しました")
    print("=" * 70)

if __name__ == "__main__":
    main()

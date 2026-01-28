#!/usr/bin/env python3
"""
岩郷戦略の検証スクリプト v2 - 論文の条件に忠実な検証

論文の戦略:
1. 対象場: 大村競艇場（stadium_code = '24'）
2. 条件: 1号艇の当地成績（local_win_rate）が6.5以上
3. 購入: 2連単または2連複の1-3（オッズの高い方を選択）
4. 除外: SG・G1などの特殊レース（人気が分散するため）

穴バイアスの本質:
- 1号艇の当地成績が6.5以上のレースでは、1-3の出現率が37.2%で最も高い
- しかし大衆は1-2を本命と思い込む → 1-3のオッズが実力以上に高くなる
- この「歪み」を利用して期待値プラスを狙う
"""

import psycopg2
import time
import json

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def verify_iwago_strategy_with_both_bet_types(year, stadium_code='24'):
    """
    論文の条件に忠実な検証:
    - 2連単と2連複の両方を取得し、オッズ（払戻金）の高い方を選択
    """
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=180)
        cur = conn.cursor()
        
        # 1号艇の当地勝率が6.5以上のレースを特定し、2連単と2連複の1-3の結果を取得
        query = f"""
            WITH qualified_races AS (
                SELECT DISTINCT race_date, stadium_code, race_no
                FROM historical_programs
                WHERE boat_no = '1'
                  AND local_win_rate >= 6.5
                  AND stadium_code = '{stadium_code}'
                  AND race_date >= '{year}0101'
                  AND race_date < '{year+1}0101'
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
                SUM(GREATEST(nirentan_payout, nirenpuku_payout)) as total_payout_max,
                SUM(nirentan_payout) as total_nirentan,
                SUM(nirenpuku_payout) as total_nirenpuku
            FROM payoffs
        """
        
        cur.execute(query)
        row = cur.fetchone()
        
        cur.close()
        conn.close()
        
        total_races = row[0] or 0
        hit_count = row[1] or 0
        total_payout_max = int(row[2] or 0)
        total_nirentan = int(row[3] or 0)
        total_nirenpuku = int(row[4] or 0)
        
        return {
            'year': year,
            'total_races': total_races,
            'hit_count': hit_count,
            'hit_rate': hit_count / total_races * 100 if total_races > 0 else 0,
            'total_payout_max': total_payout_max,
            'total_nirentan': total_nirentan,
            'total_nirenpuku': total_nirenpuku,
            'investment': total_races * 100,
            'return_rate_max': total_payout_max / (total_races * 100) * 100 if total_races > 0 else 0,
            'return_rate_nirentan': total_nirentan / (total_races * 100) * 100 if total_races > 0 else 0,
            'return_rate_nirenpuku': total_nirenpuku / (total_races * 100) * 100 if total_races > 0 else 0
        }
        
    except Exception as e:
        return {'year': year, 'error': str(e)}


def verify_by_local_win_rate_range(threshold_low, threshold_high, stadium_code='24'):
    """
    当地勝率の範囲別に回収率を検証（論文の図2を再現）
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
                  AND stadium_code = '{stadium_code}'
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


def verify_1_3_appearance_rate(stadium_code='24'):
    """
    論文の表1を再現: 当地成績6.5以上で1号艇が1着の場合の各組の出現率
    """
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=180)
        cur = conn.cursor()
        
        # 1号艇の当地勝率が6.5以上で、1号艇が1着のレースを特定
        query = f"""
            WITH qualified_races AS (
                SELECT DISTINCT p.race_date, p.stadium_code, p.race_no
                FROM historical_programs p
                WHERE p.boat_no = '1'
                  AND p.local_win_rate >= 6.5
                  AND p.stadium_code = '{stadium_code}'
            ),
            first_place_1 AS (
                -- 1号艇が1着のレース（2連単の組み合わせが1-Xで始まるもの）
                SELECT qr.race_date, qr.stadium_code, qr.race_no, hp.combination
                FROM qualified_races qr
                INNER JOIN historical_payoffs hp
                    ON hp.race_date = qr.race_date
                    AND hp.stadium_code = qr.stadium_code
                    AND hp.race_no = qr.race_no
                    AND hp.bet_type = 'nirentan'
                    AND hp.combination LIKE '1-%'
            )
            SELECT 
                combination,
                COUNT(*) as count
            FROM first_place_1
            GROUP BY combination
            ORDER BY count DESC
        """
        
        cur.execute(query)
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        
        total = sum(row[1] for row in rows)
        results = []
        for row in rows:
            results.append({
                'combination': row[0],
                'count': row[1],
                'rate': row[1] / total * 100 if total > 0 else 0
            })
        
        return {'total': total, 'combinations': results}
        
    except Exception as e:
        return {'error': str(e)}


def main():
    print("=" * 70)
    print("岩郷戦略の検証 v2 - 論文の条件に忠実な検証")
    print("=" * 70)
    print("条件: 1号艇の当地勝率6.5以上、2連単/2連複の高い方を選択")
    print("対象: 大村競艇場（場コード24）")
    print("=" * 70)
    
    results = {}
    
    # ============================================================
    # 検証1: 当地成績6.5以上で1号艇が1着の場合の各組の出現率
    # ============================================================
    print("\n【検証1】当地成績6.5以上で1号艇1着時の2着艇出現率（論文の表1を再現）")
    print("-" * 50)
    
    appearance = verify_1_3_appearance_rate(stadium_code='24')
    if 'error' not in appearance:
        print(f"  1号艇1着のレース総数: {appearance['total']:,}")
        print("\n  2着艇の出現率:")
        for combo in appearance['combinations'][:5]:
            print(f"    {combo['combination']}: {combo['count']:,}回 ({combo['rate']:.1f}%)")
        results['appearance_rate'] = appearance
    else:
        print(f"  エラー: {appearance['error']}")
    
    time.sleep(3)
    
    # ============================================================
    # 検証2: 当地勝率の範囲別回収率（論文の図2を再現）
    # ============================================================
    print("\n【検証2】当地勝率の範囲別回収率（論文の図2を再現）")
    print("-" * 50)
    
    ranges = [
        (5.0, 5.5), (5.5, 6.0), (6.0, 6.5), (6.5, 7.0), 
        (7.0, 7.5), (7.5, 8.0), (8.0, 10.0)
    ]
    range_results = []
    
    for low, high in ranges:
        result = verify_by_local_win_rate_range(low, high, stadium_code='24')
        range_results.append(result)
        
        if 'error' not in result:
            print(f"  {result['range']}: レース{result['total_races']:,}, "
                  f"的中{result['hit_count']:,} ({result['hit_rate']:.1f}%), "
                  f"回収率{result['return_rate']:.1f}%")
        else:
            print(f"  {result['range']}: エラー - {result['error']}")
        
        time.sleep(2)
    
    results['range_analysis'] = range_results
    
    # ============================================================
    # 検証3: 年別検証（2連単/2連複の高い方を選択）
    # ============================================================
    print("\n【検証3】年別検証（2連単/2連複の高い方を選択）- 大村競艇場")
    print("-" * 50)
    
    yearly_results = []
    total = {'total_races': 0, 'hit_count': 0, 'total_payout': 0}
    
    for year in range(2018, 2027):
        result = verify_iwago_strategy_with_both_bet_types(year, stadium_code='24')
        yearly_results.append(result)
        
        if 'error' not in result:
            total['total_races'] += result['total_races']
            total['hit_count'] += result['hit_count']
            total['total_payout'] += result['total_payout_max']
            
            print(f"  {year}年: レース{result['total_races']:,}, "
                  f"的中{result['hit_count']:,} ({result['hit_rate']:.1f}%), "
                  f"回収率{result['return_rate_max']:.1f}% "
                  f"(2連単:{result['return_rate_nirentan']:.1f}%, 2連複:{result['return_rate_nirenpuku']:.1f}%)")
        else:
            print(f"  {year}年: エラー - {result['error']}")
        
        time.sleep(2)
    
    # 合計
    if total['total_races'] > 0:
        total_return_rate = total['total_payout'] / (total['total_races'] * 100) * 100
        print(f"\n  【合計】")
        print(f"    レース数: {total['total_races']:,}")
        print(f"    的中数: {total['hit_count']:,}")
        print(f"    払戻合計: ¥{total['total_payout']:,}")
        print(f"    投資額: ¥{total['total_races'] * 100:,}")
        print(f"    回収率: {total_return_rate:.1f}%")
    
    results['yearly'] = yearly_results
    results['total'] = total
    
    # 結果を保存
    with open('/home/ubuntu/iwago_strategy_verification_v2.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 70)
    print("検証完了")
    print("結果を /home/ubuntu/iwago_strategy_verification_v2.json に保存しました")
    print("=" * 70)

if __name__ == "__main__":
    main()

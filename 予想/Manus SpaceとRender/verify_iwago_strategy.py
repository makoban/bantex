#!/usr/bin/env python3
"""
岩郷戦略の検証スクリプト

戦略: 1号艇の当地勝率（local_win_rate）が6.5以上のレースで2連複1-3を購入
対象: 大村競艇場（stadium_code = '24'）→ 全競艇場に拡大

論文の検証結果:
- 2018年3月〜5月（分析期間）: 回収率122%
- 2017年3月〜5月（検証期間）: 回収率101.8%
- 2018年10月〜12月（検証期間）: 回収率100.2%
"""

import psycopg2
import time
import json

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def verify_iwago_strategy_by_year(year, stadium_code=None):
    """
    岩郷戦略を年別に検証
    """
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=120)
        cur = conn.cursor()
        
        # 1号艇の当地勝率が6.5以上のレースを特定し、2連複1-3の結果を取得
        # historical_programsとhistorical_payoffsを結合
        
        stadium_filter = f"AND stadium_code = '{stadium_code}'" if stadium_code else ""
        
        query = f"""
            SELECT 
                COUNT(*) as total_races,
                SUM(CASE WHEN hp.payout IS NOT NULL THEN 1 ELSE 0 END) as hit_count,
                SUM(COALESCE(hp.payout, 0)) as total_payout
            FROM (
                SELECT DISTINCT race_date, stadium_code, race_no
                FROM historical_programs
                WHERE boat_no = '1'
                  AND local_win_rate >= 6.5
                  AND race_date >= '{year}0101'
                  AND race_date < '{year+1}0101'
                  {stadium_filter}
            ) AS qualified_races
            LEFT JOIN historical_payoffs hp
                ON hp.race_date = qualified_races.race_date
                AND hp.stadium_code = qualified_races.stadium_code
                AND hp.race_no = qualified_races.race_no
                AND hp.bet_type = 'nirenpuku'
                AND hp.combination = '1-3'
        """
        
        cur.execute(query)
        row = cur.fetchone()
        
        cur.close()
        conn.close()
        
        total_races = row[0] or 0
        hit_count = row[1] or 0
        total_payout = int(row[2] or 0)
        
        return {
            'year': year,
            'total_races': total_races,
            'hit_count': hit_count,
            'hit_rate': hit_count / total_races * 100 if total_races > 0 else 0,
            'total_payout': total_payout,
            'investment': total_races * 100,
            'return_rate': total_payout / (total_races * 100) * 100 if total_races > 0 else 0
        }
        
    except Exception as e:
        return {'year': year, 'error': str(e)}

def verify_iwago_strategy_by_threshold(threshold, stadium_code=None):
    """
    当地勝率の閾値別に回収率を検証（2018年以降）
    """
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=180)
        cur = conn.cursor()
        
        stadium_filter = f"AND stadium_code = '{stadium_code}'" if stadium_code else ""
        
        query = f"""
            SELECT 
                COUNT(*) as total_races,
                SUM(CASE WHEN hp.payout IS NOT NULL THEN 1 ELSE 0 END) as hit_count,
                SUM(COALESCE(hp.payout, 0)) as total_payout
            FROM (
                SELECT DISTINCT race_date, stadium_code, race_no
                FROM historical_programs
                WHERE boat_no = '1'
                  AND local_win_rate >= {threshold}
                  AND race_date >= '20180101'
                  {stadium_filter}
            ) AS qualified_races
            LEFT JOIN historical_payoffs hp
                ON hp.race_date = qualified_races.race_date
                AND hp.stadium_code = qualified_races.stadium_code
                AND hp.race_no = qualified_races.race_no
                AND hp.bet_type = 'nirenpuku'
                AND hp.combination = '1-3'
        """
        
        cur.execute(query)
        row = cur.fetchone()
        
        cur.close()
        conn.close()
        
        total_races = row[0] or 0
        hit_count = row[1] or 0
        total_payout = int(row[2] or 0)
        
        return {
            'threshold': threshold,
            'total_races': total_races,
            'hit_count': hit_count,
            'hit_rate': hit_count / total_races * 100 if total_races > 0 else 0,
            'total_payout': total_payout,
            'investment': total_races * 100,
            'return_rate': total_payout / (total_races * 100) * 100 if total_races > 0 else 0
        }
        
    except Exception as e:
        return {'threshold': threshold, 'error': str(e)}

def main():
    print("=" * 70)
    print("岩郷戦略の検証: 1号艇当地勝率6.5以上で2連複1-3購入")
    print("=" * 70)
    
    results = {}
    
    # ============================================================
    # 検証1: 大村競艇場（stadium_code = '24'）での年別検証
    # ============================================================
    print("\n【検証1】大村競艇場（場コード24）での年別検証")
    print("-" * 50)
    
    omura_results = []
    omura_total = {'total_races': 0, 'hit_count': 0, 'total_payout': 0}
    
    for year in range(2018, 2027):  # 論文の期間を含む
        result = verify_iwago_strategy_by_year(year, stadium_code='24')
        omura_results.append(result)
        
        if 'error' not in result:
            omura_total['total_races'] += result['total_races']
            omura_total['hit_count'] += result['hit_count']
            omura_total['total_payout'] += result['total_payout']
            
            print(f"  {year}年: レース{result['total_races']:,}, "
                  f"的中{result['hit_count']:,} ({result['hit_rate']:.1f}%), "
                  f"回収率{result['return_rate']:.1f}%")
        else:
            print(f"  {year}年: エラー - {result['error']}")
        
        time.sleep(2)
    
    # 大村合計
    if omura_total['total_races'] > 0:
        omura_return_rate = omura_total['total_payout'] / (omura_total['total_races'] * 100) * 100
        print(f"\n  【大村合計】")
        print(f"    レース数: {omura_total['total_races']:,}")
        print(f"    的中数: {omura_total['hit_count']:,}")
        print(f"    払戻合計: ¥{omura_total['total_payout']:,}")
        print(f"    投資額: ¥{omura_total['total_races'] * 100:,}")
        print(f"    回収率: {omura_return_rate:.1f}%")
    
    results['omura'] = {'yearly': omura_results, 'total': omura_total}
    
    # ============================================================
    # 検証2: 全競艇場での年別検証
    # ============================================================
    print("\n【検証2】全競艇場での年別検証")
    print("-" * 50)
    
    all_results = []
    all_total = {'total_races': 0, 'hit_count': 0, 'total_payout': 0}
    
    for year in range(2018, 2027):
        result = verify_iwago_strategy_by_year(year, stadium_code=None)
        all_results.append(result)
        
        if 'error' not in result:
            all_total['total_races'] += result['total_races']
            all_total['hit_count'] += result['hit_count']
            all_total['total_payout'] += result['total_payout']
            
            print(f"  {year}年: レース{result['total_races']:,}, "
                  f"的中{result['hit_count']:,} ({result['hit_rate']:.1f}%), "
                  f"回収率{result['return_rate']:.1f}%")
        else:
            print(f"  {year}年: エラー - {result['error']}")
        
        time.sleep(2)
    
    # 全競艇場合計
    if all_total['total_races'] > 0:
        all_return_rate = all_total['total_payout'] / (all_total['total_races'] * 100) * 100
        print(f"\n  【全競艇場合計】")
        print(f"    レース数: {all_total['total_races']:,}")
        print(f"    的中数: {all_total['hit_count']:,}")
        print(f"    払戻合計: ¥{all_total['total_payout']:,}")
        print(f"    投資額: ¥{all_total['total_races'] * 100:,}")
        print(f"    回収率: {all_return_rate:.1f}%")
    
    results['all_stadiums'] = {'yearly': all_results, 'total': all_total}
    
    # ============================================================
    # 検証3: 当地勝率の閾値別検証（全競艇場、2018年以降）
    # ============================================================
    print("\n【検証3】当地勝率の閾値別検証（全競艇場、2018年以降）")
    print("-" * 50)
    
    threshold_results = []
    for threshold in [5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0]:
        result = verify_iwago_strategy_by_threshold(threshold, stadium_code=None)
        threshold_results.append(result)
        
        if 'error' not in result:
            print(f"  閾値{threshold}: レース{result['total_races']:,}, "
                  f"的中{result['hit_count']:,} ({result['hit_rate']:.1f}%), "
                  f"回収率{result['return_rate']:.1f}%")
        else:
            print(f"  閾値{threshold}: エラー - {result['error']}")
        
        time.sleep(3)
    
    results['threshold_analysis'] = threshold_results
    
    # 結果を保存
    with open('/home/ubuntu/iwago_strategy_verification.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 70)
    print("検証完了")
    print("結果を /home/ubuntu/iwago_strategy_verification.json に保存しました")
    print("=" * 70)

if __name__ == "__main__":
    main()

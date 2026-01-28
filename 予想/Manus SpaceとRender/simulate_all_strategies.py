"""
3戦略の動的購入金額シミュレーション
実際のDBデータから計算

使用方法:
1. Render.comのDBシェルで実行する場合: SQLファイルを使用
2. ローカルPythonで実行する場合: このスクリプトを実行

DB接続情報:
postgresql://kokotomo_db_staging_user:NjYJqLGOOmjB6I9ToqBuhz0BxdwcZJL5@dpg-ctds0hrtq21c73b6ibeg-a.singapore-postgres.render.com/kokotomo_db_staging
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import json

# DB接続設定
DATABASE_URL = "postgresql://kokotomo_db_staging_user:NjYJqLGOOmjB6I9ToqBuhz0BxdwcZJL5@dpg-ctds0hrtq21c73b6ibeg-a.singapore-postgres.render.com/kokotomo_db_staging"

# 購入金額計算関数
BASE_AMOUNT = 1000
MIN_AMOUNT = 1000
MAX_AMOUNT = 10000

def calculate_bet_amount_tansho(odds):
    """関東4場単勝の購入金額"""
    if odds < 1.5:
        multiplier = 1.0
    elif odds < 2.0:
        multiplier = 2.0
    elif odds < 3.0:
        multiplier = 3.0
    elif odds < 5.0:
        multiplier = 4.0
    elif odds < 8.0:
        multiplier = 3.0
    else:
        multiplier = 2.0
    
    amount = int(BASE_AMOUNT * multiplier / 100) * 100
    return max(MIN_AMOUNT, min(MAX_AMOUNT, amount))


def calculate_bet_amount_bias(odds, local_win_rate, strategy='bias_1_3'):
    """3穴戦略の購入金額"""
    if strategy == 'bias_1_3':
        # 当地勝率による基本倍率
        if local_win_rate < 7.0:
            rate_multiplier = 1.0
        elif local_win_rate < 7.5:
            rate_multiplier = 1.5
        elif local_win_rate < 8.0:
            rate_multiplier = 2.0
        else:
            rate_multiplier = 2.5
    else:  # bias_1_3_2nd
        if local_win_rate < 5.0:
            rate_multiplier = 1.0
        elif local_win_rate < 5.5:
            rate_multiplier = 1.5
        else:
            rate_multiplier = 2.0
    
    # オッズによる調整
    if odds < 4.0:
        odds_multiplier = 1.5
    elif odds < 8.0:
        odds_multiplier = 1.2
    elif odds < 15.0:
        odds_multiplier = 1.0
    elif odds < 25.0:
        odds_multiplier = 0.8
    else:
        odds_multiplier = 0.5
    
    multiplier = rate_multiplier * odds_multiplier
    amount = int(BASE_AMOUNT * multiplier / 100) * 100
    return max(MIN_AMOUNT, min(MAX_AMOUNT, amount))


def simulate_tansho_kanto(conn):
    """
    関東4場単勝戦略のシミュレーション
    対象: 桐生(01)1-4R, 戸田(02)1-4,6,8R, 平和島(04)1-4,6-8R, 多摩川(05)2-7R
    """
    print("\n" + "="*70)
    print("【関東4場単勝戦略】シミュレーション")
    print("="*70)
    
    cur = conn.cursor()
    
    # 対象条件
    conditions = [
        ("'01'", "('01','02','03','04')"),           # 桐生: 1-4R
        ("'02'", "('01','02','03','04','06','08')"), # 戸田: 1-4,6,8R
        ("'04'", "('01','02','03','04','06','07','08')"), # 平和島: 1-4,6-8R
        ("'05'", "('02','03','04','05','06','07')"), # 多摩川: 2-7R
    ]
    
    total_dynamic_bet = 0
    total_dynamic_return = 0
    total_fixed_bet = 0
    total_fixed_return = 0
    total_count = 0
    total_hits = 0
    
    for stadium, races in conditions:
        query = f"""
        SELECT 
            r.race_date,
            r.stadium_code,
            r.race_no,
            r.first_place,
            COALESCE(p.win_odds_1, 0) as odds,
            COALESCE(p.win_payoff, 0) as payoff
        FROM historical_race_results r
        JOIN historical_programs p ON r.race_date = p.race_date 
            AND r.stadium_code = p.stadium_code 
            AND r.race_no = p.race_no
        WHERE r.stadium_code = {stadium}
            AND r.race_no IN {races}
            AND p.win_odds_1 IS NOT NULL
            AND p.win_odds_1 > 0
        """
        
        cur.execute(query)
        rows = cur.fetchall()
        
        stadium_count = 0
        stadium_hits = 0
        stadium_dynamic_bet = 0
        stadium_dynamic_return = 0
        stadium_fixed_bet = 0
        stadium_fixed_return = 0
        
        for row in rows:
            odds = float(row['odds'])
            is_hit = str(row['first_place']) == '1'
            payoff = float(row['payoff']) if row['payoff'] else odds * 100
            
            # 動的金額
            bet_amount = calculate_bet_amount_tansho(odds)
            stadium_dynamic_bet += bet_amount
            stadium_count += 1
            
            # 固定金額
            stadium_fixed_bet += 1000
            
            if is_hit:
                stadium_hits += 1
                # 払戻 = (払戻金/100) × 購入金額
                stadium_dynamic_return += (payoff / 100) * bet_amount
                stadium_fixed_return += (payoff / 100) * 1000
        
        total_count += stadium_count
        total_hits += stadium_hits
        total_dynamic_bet += stadium_dynamic_bet
        total_dynamic_return += stadium_dynamic_return
        total_fixed_bet += stadium_fixed_bet
        total_fixed_return += stadium_fixed_return
        
        if stadium_count > 0:
            print(f"\n場{stadium}: {stadium_count:,}件, 的中{stadium_hits:,}件 ({stadium_hits/stadium_count*100:.1f}%)")
            print(f"  動的: 投資¥{stadium_dynamic_bet:,} → 払戻¥{stadium_dynamic_return:,.0f} (回収率{stadium_dynamic_return/stadium_dynamic_bet*100:.1f}%)")
            print(f"  固定: 投資¥{stadium_fixed_bet:,} → 払戻¥{stadium_fixed_return:,.0f} (回収率{stadium_fixed_return/stadium_fixed_bet*100:.1f}%)")
    
    print(f"\n" + "-"*70)
    print(f"【合計】")
    print(f"  対象レース数: {total_count:,}件")
    print(f"  的中数: {total_hits:,}件 ({total_hits/total_count*100:.2f}%)")
    print(f"\n  【動的金額】")
    print(f"    総投資額: ¥{total_dynamic_bet:,}")
    print(f"    総払戻額: ¥{total_dynamic_return:,.0f}")
    print(f"    収支: ¥{total_dynamic_return - total_dynamic_bet:+,.0f}")
    print(f"    回収率: {total_dynamic_return/total_dynamic_bet*100:.2f}%")
    print(f"\n  【固定金額（1,000円）】")
    print(f"    総投資額: ¥{total_fixed_bet:,}")
    print(f"    総払戻額: ¥{total_fixed_return:,.0f}")
    print(f"    収支: ¥{total_fixed_return - total_fixed_bet:+,.0f}")
    print(f"    回収率: {total_fixed_return/total_fixed_bet*100:.2f}%")
    
    return {
        'strategy': '関東4場単勝',
        'count': total_count,
        'hits': total_hits,
        'dynamic_bet': total_dynamic_bet,
        'dynamic_return': total_dynamic_return,
        'fixed_bet': total_fixed_bet,
        'fixed_return': total_fixed_return,
    }


def simulate_bias_1_3(conn):
    """
    3穴戦略（論文準拠）のシミュレーション
    対象: 大村(24)、当地勝率6.5以上、2連単/2連複の高い方
    """
    print("\n" + "="*70)
    print("【3穴戦略（論文準拠）】シミュレーション")
    print("="*70)
    
    cur = conn.cursor()
    
    query = """
    SELECT 
        r.race_date,
        r.race_no,
        r.first_place,
        r.second_place,
        COALESCE(p.local_win_rate, 0) as local_win_rate,
        COALESCE(p.exacta_odds_1_3, 0) as exacta_odds,
        COALESCE(p.quinella_odds_1_3, 0) as quinella_odds,
        COALESCE(p.exacta_payoff_1_3, 0) as exacta_payoff,
        COALESCE(p.quinella_payoff_1_3, 0) as quinella_payoff
    FROM historical_race_results r
    JOIN historical_programs p ON r.race_date = p.race_date 
        AND r.stadium_code = p.stadium_code 
        AND r.race_no = p.race_no
    WHERE r.stadium_code = '24'
        AND p.local_win_rate >= 6.5
        AND (p.exacta_odds_1_3 > 0 OR p.quinella_odds_1_3 > 0)
    """
    
    cur.execute(query)
    rows = cur.fetchall()
    
    total_dynamic_bet = 0
    total_dynamic_return = 0
    total_fixed_bet = 0
    total_fixed_return = 0
    total_count = 0
    total_hits = 0
    
    for row in rows:
        local_win_rate = float(row['local_win_rate'])
        exacta_odds = float(row['exacta_odds'])
        quinella_odds = float(row['quinella_odds'])
        
        # 高い方を選択
        if exacta_odds >= quinella_odds and exacta_odds > 0:
            odds = exacta_odds
            is_exacta = True
            payoff = float(row['exacta_payoff']) if row['exacta_payoff'] else exacta_odds * 100
        elif quinella_odds > 0:
            odds = quinella_odds
            is_exacta = False
            payoff = float(row['quinella_payoff']) if row['quinella_payoff'] else quinella_odds * 100
        else:
            continue
        
        # 的中判定
        first = str(row['first_place'])
        second = str(row['second_place'])
        
        if is_exacta:
            is_hit = (first == '1' and second == '3')
        else:
            is_hit = ((first == '1' and second == '3') or (first == '3' and second == '1'))
        
        # 動的金額
        bet_amount = calculate_bet_amount_bias(odds, local_win_rate, 'bias_1_3')
        total_dynamic_bet += bet_amount
        total_count += 1
        total_fixed_bet += 1000
        
        if is_hit:
            total_hits += 1
            total_dynamic_return += (payoff / 100) * bet_amount
            total_fixed_return += (payoff / 100) * 1000
    
    print(f"\n【結果】")
    print(f"  対象レース数: {total_count:,}件")
    print(f"  的中数: {total_hits:,}件 ({total_hits/total_count*100:.2f}%)" if total_count > 0 else "  対象データなし")
    
    if total_count > 0:
        print(f"\n  【動的金額】")
        print(f"    総投資額: ¥{total_dynamic_bet:,}")
        print(f"    総払戻額: ¥{total_dynamic_return:,.0f}")
        print(f"    収支: ¥{total_dynamic_return - total_dynamic_bet:+,.0f}")
        print(f"    回収率: {total_dynamic_return/total_dynamic_bet*100:.2f}%")
        print(f"\n  【固定金額（1,000円）】")
        print(f"    総投資額: ¥{total_fixed_bet:,}")
        print(f"    総払戻額: ¥{total_fixed_return:,.0f}")
        print(f"    収支: ¥{total_fixed_return - total_fixed_bet:+,.0f}")
        print(f"    回収率: {total_fixed_return/total_fixed_bet*100:.2f}%")
    
    return {
        'strategy': '3穴（論文準拠）',
        'count': total_count,
        'hits': total_hits,
        'dynamic_bet': total_dynamic_bet,
        'dynamic_return': total_dynamic_return,
        'fixed_bet': total_fixed_bet,
        'fixed_return': total_fixed_return,
    }


def simulate_bias_1_3_2nd(conn):
    """
    3穴2nd戦略のシミュレーション
    対象: 特定場×R（15条件）、当地勝率4.5〜6.0、オッズ3.0〜100.0
    """
    print("\n" + "="*70)
    print("【3穴2nd戦略】シミュレーション")
    print("="*70)
    
    cur = conn.cursor()
    
    # 対象条件
    target_conditions = [
        ('11', '04'),   # 琵琶湖 4R
        ('18', '10'),   # 徳山 10R
        ('13', '04'),   # 尼崎 4R
        ('18', '06'),   # 徳山 6R
        ('05', '02'),   # 多摩川 2R
        ('11', '02'),   # 琵琶湖 2R
        ('24', '04'),   # 大村 4R
        ('05', '04'),   # 多摩川 4R
        ('11', '05'),   # 琵琶湖 5R
        ('11', '09'),   # 琵琶湖 9R
        ('18', '03'),   # 徳山 3R
        ('05', '11'),   # 多摩川 11R
        ('13', '06'),   # 尼崎 6R
        ('05', '06'),   # 多摩川 6R
        ('13', '01'),   # 尼崎 1R
    ]
    
    total_dynamic_bet = 0
    total_dynamic_return = 0
    total_fixed_bet = 0
    total_fixed_return = 0
    total_count = 0
    total_hits = 0
    
    for stadium_code, race_no in target_conditions:
        query = f"""
        SELECT 
            r.race_date,
            r.first_place,
            r.second_place,
            COALESCE(p.local_win_rate, 0) as local_win_rate,
            COALESCE(p.exacta_odds_1_3, 0) as exacta_odds,
            COALESCE(p.quinella_odds_1_3, 0) as quinella_odds,
            COALESCE(p.exacta_payoff_1_3, 0) as exacta_payoff,
            COALESCE(p.quinella_payoff_1_3, 0) as quinella_payoff
        FROM historical_race_results r
        JOIN historical_programs p ON r.race_date = p.race_date 
            AND r.stadium_code = p.stadium_code 
            AND r.race_no = p.race_no
        WHERE r.stadium_code = '{stadium_code}'
            AND r.race_no = '{race_no}'
            AND p.local_win_rate >= 4.5
            AND p.local_win_rate < 6.0
            AND (p.exacta_odds_1_3 > 0 OR p.quinella_odds_1_3 > 0)
        """
        
        cur.execute(query)
        rows = cur.fetchall()
        
        for row in rows:
            local_win_rate = float(row['local_win_rate'])
            exacta_odds = float(row['exacta_odds'])
            quinella_odds = float(row['quinella_odds'])
            
            # 高い方を選択
            if exacta_odds >= quinella_odds and exacta_odds > 0:
                odds = exacta_odds
                is_exacta = True
                payoff = float(row['exacta_payoff']) if row['exacta_payoff'] else exacta_odds * 100
            elif quinella_odds > 0:
                odds = quinella_odds
                is_exacta = False
                payoff = float(row['quinella_payoff']) if row['quinella_payoff'] else quinella_odds * 100
            else:
                continue
            
            # オッズ条件
            if odds < 3.0 or odds > 100.0:
                continue
            
            # 的中判定
            first = str(row['first_place'])
            second = str(row['second_place'])
            
            if is_exacta:
                is_hit = (first == '1' and second == '3')
            else:
                is_hit = ((first == '1' and second == '3') or (first == '3' and second == '1'))
            
            # 動的金額
            bet_amount = calculate_bet_amount_bias(odds, local_win_rate, 'bias_1_3_2nd')
            total_dynamic_bet += bet_amount
            total_count += 1
            total_fixed_bet += 1000
            
            if is_hit:
                total_hits += 1
                total_dynamic_return += (payoff / 100) * bet_amount
                total_fixed_return += (payoff / 100) * 1000
    
    print(f"\n【結果】")
    print(f"  対象レース数: {total_count:,}件")
    print(f"  的中数: {total_hits:,}件 ({total_hits/total_count*100:.2f}%)" if total_count > 0 else "  対象データなし")
    
    if total_count > 0:
        print(f"\n  【動的金額】")
        print(f"    総投資額: ¥{total_dynamic_bet:,}")
        print(f"    総払戻額: ¥{total_dynamic_return:,.0f}")
        print(f"    収支: ¥{total_dynamic_return - total_dynamic_bet:+,.0f}")
        print(f"    回収率: {total_dynamic_return/total_dynamic_bet*100:.2f}%")
        print(f"\n  【固定金額（1,000円）】")
        print(f"    総投資額: ¥{total_fixed_bet:,}")
        print(f"    総払戻額: ¥{total_fixed_return:,.0f}")
        print(f"    収支: ¥{total_fixed_return - total_fixed_bet:+,.0f}")
        print(f"    回収率: {total_fixed_return/total_fixed_bet*100:.2f}%")
    
    return {
        'strategy': '3穴2nd',
        'count': total_count,
        'hits': total_hits,
        'dynamic_bet': total_dynamic_bet,
        'dynamic_return': total_dynamic_return,
        'fixed_bet': total_fixed_bet,
        'fixed_return': total_fixed_return,
    }


def main():
    print("="*70)
    print("3戦略 動的購入金額シミュレーション（実DBデータ）")
    print("="*70)
    
    try:
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor,
            connect_timeout=60,
            options='-c statement_timeout=600000'
        )
        print("DB接続成功")
    except Exception as e:
        print(f"DB接続エラー: {e}")
        return
    
    results = []
    
    try:
        r1 = simulate_tansho_kanto(conn)
        results.append(r1)
    except Exception as e:
        print(f"関東4場単勝エラー: {e}")
    
    try:
        r2 = simulate_bias_1_3(conn)
        results.append(r2)
    except Exception as e:
        print(f"3穴戦略エラー: {e}")
    
    try:
        r3 = simulate_bias_1_3_2nd(conn)
        results.append(r3)
    except Exception as e:
        print(f"3穴2ndエラー: {e}")
    
    conn.close()
    
    # サマリー
    print("\n" + "="*70)
    print("【総合サマリー】")
    print("="*70)
    
    for r in results:
        if r['count'] > 0:
            hit_rate = r['hits']/r['count']*100
            dynamic_rate = r['dynamic_return']/r['dynamic_bet']*100 if r['dynamic_bet'] > 0 else 0
            fixed_rate = r['fixed_return']/r['fixed_bet']*100 if r['fixed_bet'] > 0 else 0
            
            print(f"\n{r['strategy']}:")
            print(f"  レース数: {r['count']:,}件, 的中: {r['hits']:,}件 ({hit_rate:.1f}%)")
            print(f"  動的: 投資¥{r['dynamic_bet']:,} → 収支¥{r['dynamic_return']-r['dynamic_bet']:+,.0f} (回収率{dynamic_rate:.1f}%)")
            print(f"  固定: 投資¥{r['fixed_bet']:,} → 収支¥{r['fixed_return']-r['fixed_bet']:+,.0f} (回収率{fixed_rate:.1f}%)")
            print(f"  → 回収率変化: {dynamic_rate - fixed_rate:+.1f}ポイント")


if __name__ == "__main__":
    main()

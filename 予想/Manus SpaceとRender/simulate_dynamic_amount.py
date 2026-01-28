"""
動的購入金額による21年分収支シミュレーション
3戦略それぞれの結果を算出
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os

# DB接続
DATABASE_URL = "postgresql://kokotomo_db_staging_user:NjYJqLGOOmjB6I9ToqBuhz0BxdwcZJL5@dpg-ctds0hrtq21c73b6ibeg-a.singapore-postgres.render.com/kokotomo_db_staging"

# 購入金額計算関数
BASE_AMOUNT = 1000
MIN_AMOUNT = 1000
MAX_AMOUNT = 10000

def calculate_bet_amount(strategy_type, odds, local_win_rate=None):
    """購入金額を計算"""
    
    if strategy_type == 'tansho_kanto':
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
    
    elif strategy_type == 'bias_1_3':
        if local_win_rate is None:
            rate_multiplier = 1.0
        elif local_win_rate < 7.0:
            rate_multiplier = 1.0
        elif local_win_rate < 7.5:
            rate_multiplier = 1.5
        elif local_win_rate < 8.0:
            rate_multiplier = 2.0
        else:
            rate_multiplier = 2.5
        
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
    
    elif strategy_type == 'bias_1_3_2nd':
        if local_win_rate is None:
            rate_multiplier = 1.0
        elif local_win_rate < 5.0:
            rate_multiplier = 1.0
        elif local_win_rate < 5.5:
            rate_multiplier = 1.5
        else:
            rate_multiplier = 2.0
        
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
    
    else:
        multiplier = 1.0
    
    amount = int(BASE_AMOUNT * multiplier / 100) * 100
    return max(MIN_AMOUNT, min(MAX_AMOUNT, amount))


def simulate_tansho_kanto():
    """関東4場単勝戦略のシミュレーション"""
    print("\n" + "="*60)
    print("【関東4場単勝戦略】シミュレーション")
    print("="*60)
    
    # 対象条件
    conditions = [
        ('01', [1, 2, 3, 4]),           # 桐生: 1-4R
        ('02', [1, 2, 3, 4, 6, 8]),     # 戸田: 1-4,6,8R
        ('04', [1, 2, 3, 4, 6, 7, 8]),  # 平和島: 1-4,6-8R
        ('05', [2, 3, 4, 5, 6, 7]),     # 多摩川: 2-7R
    ]
    
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor,
                           connect_timeout=30,
                           options='-c statement_timeout=300000')
    cur = conn.cursor()
    
    total_bet = 0
    total_return = 0
    total_count = 0
    hit_count = 0
    
    # 固定金額での比較用
    fixed_bet = 0
    fixed_return = 0
    
    for stadium_code, races in conditions:
        race_list = ','.join([f"'{r:02d}'" for r in races])
        
        query = f"""
        SELECT 
            r.race_date,
            r.stadium_code,
            r.race_no,
            r.first_place,
            p.win_odds_1 as odds,
            p.win_payoff
        FROM historical_race_results r
        JOIN historical_programs p ON r.race_date = p.race_date 
            AND r.stadium_code = p.stadium_code 
            AND r.race_no = p.race_no
        WHERE r.stadium_code = '{stadium_code}'
            AND r.race_no IN ({race_list})
            AND p.win_odds_1 IS NOT NULL
            AND p.win_odds_1 > 0
        """
        
        cur.execute(query)
        rows = cur.fetchall()
        
        for row in rows:
            odds = float(row['odds'])
            is_hit = str(row['first_place']) == '1'
            
            # 動的金額
            bet_amount = calculate_bet_amount('tansho_kanto', odds)
            total_bet += bet_amount
            total_count += 1
            
            # 固定金額
            fixed_bet += 1000
            
            if is_hit:
                hit_count += 1
                payoff = float(row['win_payoff']) if row['win_payoff'] else odds * 100
                # 動的金額での払戻
                total_return += (payoff / 100) * bet_amount
                # 固定金額での払戻
                fixed_return += payoff
    
    conn.close()
    
    print(f"\n対象レース数: {total_count:,}件")
    print(f"的中数: {hit_count:,}件")
    print(f"的中率: {hit_count/total_count*100:.2f}%")
    
    print(f"\n【動的金額】")
    print(f"  総投資額: ¥{total_bet:,.0f}")
    print(f"  総払戻額: ¥{total_return:,.0f}")
    print(f"  収支: ¥{total_return - total_bet:,.0f}")
    print(f"  回収率: {total_return/total_bet*100:.2f}%")
    
    print(f"\n【固定金額（1,000円）】")
    print(f"  総投資額: ¥{fixed_bet:,.0f}")
    print(f"  総払戻額: ¥{fixed_return:,.0f}")
    print(f"  収支: ¥{fixed_return - fixed_bet:,.0f}")
    print(f"  回収率: {fixed_return/fixed_bet*100:.2f}%")
    
    return {
        'strategy': '関東4場単勝',
        'count': total_count,
        'hit_count': hit_count,
        'hit_rate': hit_count/total_count*100,
        'dynamic_bet': total_bet,
        'dynamic_return': total_return,
        'dynamic_profit': total_return - total_bet,
        'dynamic_rate': total_return/total_bet*100,
        'fixed_bet': fixed_bet,
        'fixed_return': fixed_return,
        'fixed_profit': fixed_return - fixed_bet,
        'fixed_rate': fixed_return/fixed_bet*100,
    }


def simulate_bias_1_3():
    """3穴戦略（論文準拠）のシミュレーション"""
    print("\n" + "="*60)
    print("【3穴戦略（論文準拠）】シミュレーション")
    print("="*60)
    
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor,
                           connect_timeout=30,
                           options='-c statement_timeout=300000')
    cur = conn.cursor()
    
    # 大村競艇場（24）、当地勝率6.5以上、2連単/2連複の高い方
    query = """
    SELECT 
        r.race_date,
        r.race_no,
        r.first_place,
        r.second_place,
        p.local_win_rate,
        p.exacta_odds_1_3,
        p.quinella_odds_1_3,
        p.exacta_payoff_1_3,
        p.quinella_payoff_1_3
    FROM historical_race_results r
    JOIN historical_programs p ON r.race_date = p.race_date 
        AND r.stadium_code = p.stadium_code 
        AND r.race_no = p.race_no
    WHERE r.stadium_code = '24'
        AND p.local_win_rate >= 6.5
        AND (p.exacta_odds_1_3 IS NOT NULL OR p.quinella_odds_1_3 IS NOT NULL)
    """
    
    cur.execute(query)
    rows = cur.fetchall()
    
    total_bet = 0
    total_return = 0
    total_count = 0
    hit_count = 0
    fixed_bet = 0
    fixed_return = 0
    
    for row in rows:
        local_win_rate = float(row['local_win_rate']) if row['local_win_rate'] else 6.5
        exacta_odds = float(row['exacta_odds_1_3']) if row['exacta_odds_1_3'] else None
        quinella_odds = float(row['quinella_odds_1_3']) if row['quinella_odds_1_3'] else None
        
        # 高い方を選択
        if exacta_odds and quinella_odds:
            if exacta_odds >= quinella_odds:
                odds = exacta_odds
                is_exacta = True
            else:
                odds = quinella_odds
                is_exacta = False
        elif exacta_odds:
            odds = exacta_odds
            is_exacta = True
        elif quinella_odds:
            odds = quinella_odds
            is_exacta = False
        else:
            continue
        
        # 的中判定
        first = str(row['first_place'])
        second = str(row['second_place'])
        
        if is_exacta:
            is_hit = (first == '1' and second == '3')
            payoff = float(row['exacta_payoff_1_3']) if row['exacta_payoff_1_3'] else odds * 100
        else:
            is_hit = ((first == '1' and second == '3') or (first == '3' and second == '1'))
            payoff = float(row['quinella_payoff_1_3']) if row['quinella_payoff_1_3'] else odds * 100
        
        # 動的金額
        bet_amount = calculate_bet_amount('bias_1_3', odds, local_win_rate)
        total_bet += bet_amount
        total_count += 1
        fixed_bet += 1000
        
        if is_hit:
            hit_count += 1
            total_return += (payoff / 100) * bet_amount
            fixed_return += payoff
    
    conn.close()
    
    print(f"\n対象レース数: {total_count:,}件")
    print(f"的中数: {hit_count:,}件")
    print(f"的中率: {hit_count/total_count*100:.2f}%")
    
    print(f"\n【動的金額】")
    print(f"  総投資額: ¥{total_bet:,.0f}")
    print(f"  総払戻額: ¥{total_return:,.0f}")
    print(f"  収支: ¥{total_return - total_bet:,.0f}")
    print(f"  回収率: {total_return/total_bet*100:.2f}%")
    
    print(f"\n【固定金額（1,000円）】")
    print(f"  総投資額: ¥{fixed_bet:,.0f}")
    print(f"  総払戻額: ¥{fixed_return:,.0f}")
    print(f"  収支: ¥{fixed_return - fixed_bet:,.0f}")
    print(f"  回収率: {fixed_return/fixed_bet*100:.2f}%")
    
    return {
        'strategy': '3穴（論文準拠）',
        'count': total_count,
        'hit_count': hit_count,
        'hit_rate': hit_count/total_count*100 if total_count > 0 else 0,
        'dynamic_bet': total_bet,
        'dynamic_return': total_return,
        'dynamic_profit': total_return - total_bet,
        'dynamic_rate': total_return/total_bet*100 if total_bet > 0 else 0,
        'fixed_bet': fixed_bet,
        'fixed_return': fixed_return,
        'fixed_profit': fixed_return - fixed_bet,
        'fixed_rate': fixed_return/fixed_bet*100 if fixed_bet > 0 else 0,
    }


def simulate_bias_1_3_2nd():
    """3穴2nd戦略のシミュレーション"""
    print("\n" + "="*60)
    print("【3穴2nd戦略】シミュレーション")
    print("="*60)
    
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
    
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor,
                           connect_timeout=30,
                           options='-c statement_timeout=300000')
    cur = conn.cursor()
    
    total_bet = 0
    total_return = 0
    total_count = 0
    hit_count = 0
    fixed_bet = 0
    fixed_return = 0
    
    for stadium_code, race_no in target_conditions:
        query = f"""
        SELECT 
            r.race_date,
            r.first_place,
            r.second_place,
            p.local_win_rate,
            p.exacta_odds_1_3,
            p.quinella_odds_1_3,
            p.exacta_payoff_1_3,
            p.quinella_payoff_1_3
        FROM historical_race_results r
        JOIN historical_programs p ON r.race_date = p.race_date 
            AND r.stadium_code = p.stadium_code 
            AND r.race_no = p.race_no
        WHERE r.stadium_code = '{stadium_code}'
            AND r.race_no = '{race_no}'
            AND p.local_win_rate >= 4.5
            AND p.local_win_rate < 6.0
            AND (p.exacta_odds_1_3 IS NOT NULL OR p.quinella_odds_1_3 IS NOT NULL)
        """
        
        cur.execute(query)
        rows = cur.fetchall()
        
        for row in rows:
            local_win_rate = float(row['local_win_rate']) if row['local_win_rate'] else 5.0
            exacta_odds = float(row['exacta_odds_1_3']) if row['exacta_odds_1_3'] else None
            quinella_odds = float(row['quinella_odds_1_3']) if row['quinella_odds_1_3'] else None
            
            # 高い方を選択
            if exacta_odds and quinella_odds:
                if exacta_odds >= quinella_odds:
                    odds = exacta_odds
                    is_exacta = True
                else:
                    odds = quinella_odds
                    is_exacta = False
            elif exacta_odds:
                odds = exacta_odds
                is_exacta = True
            elif quinella_odds:
                odds = quinella_odds
                is_exacta = False
            else:
                continue
            
            # オッズ条件（3.0〜100.0）
            if odds < 3.0 or odds > 100.0:
                continue
            
            # 的中判定
            first = str(row['first_place'])
            second = str(row['second_place'])
            
            if is_exacta:
                is_hit = (first == '1' and second == '3')
                payoff = float(row['exacta_payoff_1_3']) if row['exacta_payoff_1_3'] else odds * 100
            else:
                is_hit = ((first == '1' and second == '3') or (first == '3' and second == '1'))
                payoff = float(row['quinella_payoff_1_3']) if row['quinella_payoff_1_3'] else odds * 100
            
            # 動的金額
            bet_amount = calculate_bet_amount('bias_1_3_2nd', odds, local_win_rate)
            total_bet += bet_amount
            total_count += 1
            fixed_bet += 1000
            
            if is_hit:
                hit_count += 1
                total_return += (payoff / 100) * bet_amount
                fixed_return += payoff
    
    conn.close()
    
    if total_count > 0:
        print(f"\n対象レース数: {total_count:,}件")
        print(f"的中数: {hit_count:,}件")
        print(f"的中率: {hit_count/total_count*100:.2f}%")
        
        print(f"\n【動的金額】")
        print(f"  総投資額: ¥{total_bet:,.0f}")
        print(f"  総払戻額: ¥{total_return:,.0f}")
        print(f"  収支: ¥{total_return - total_bet:,.0f}")
        print(f"  回収率: {total_return/total_bet*100:.2f}%")
        
        print(f"\n【固定金額（1,000円）】")
        print(f"  総投資額: ¥{fixed_bet:,.0f}")
        print(f"  総払戻額: ¥{fixed_return:,.0f}")
        print(f"  収支: ¥{fixed_return - fixed_bet:,.0f}")
        print(f"  回収率: {fixed_return/fixed_bet*100:.2f}%")
    else:
        print("対象データなし")
    
    return {
        'strategy': '3穴2nd',
        'count': total_count,
        'hit_count': hit_count,
        'hit_rate': hit_count/total_count*100 if total_count > 0 else 0,
        'dynamic_bet': total_bet,
        'dynamic_return': total_return,
        'dynamic_profit': total_return - total_bet,
        'dynamic_rate': total_return/total_bet*100 if total_bet > 0 else 0,
        'fixed_bet': fixed_bet,
        'fixed_return': fixed_return,
        'fixed_profit': fixed_return - fixed_bet,
        'fixed_rate': fixed_return/fixed_bet*100 if fixed_bet > 0 else 0,
    }


if __name__ == "__main__":
    print("="*60)
    print("動的購入金額 21年分収支シミュレーション")
    print("="*60)
    
    results = []
    
    # 1. 関東4場単勝戦略
    try:
        r1 = simulate_tansho_kanto()
        results.append(r1)
    except Exception as e:
        print(f"関東4場単勝戦略エラー: {e}")
    
    # 2. 3穴戦略（論文準拠）
    try:
        r2 = simulate_bias_1_3()
        results.append(r2)
    except Exception as e:
        print(f"3穴戦略エラー: {e}")
    
    # 3. 3穴2nd戦略
    try:
        r3 = simulate_bias_1_3_2nd()
        results.append(r3)
    except Exception as e:
        print(f"3穴2nd戦略エラー: {e}")
    
    # サマリー
    print("\n" + "="*60)
    print("【総合サマリー】")
    print("="*60)
    
    for r in results:
        print(f"\n{r['strategy']}:")
        print(f"  レース数: {r['count']:,}件, 的中率: {r['hit_rate']:.2f}%")
        print(f"  動的金額: 投資¥{r['dynamic_bet']:,.0f} → 収支¥{r['dynamic_profit']:+,.0f} (回収率{r['dynamic_rate']:.2f}%)")
        print(f"  固定金額: 投資¥{r['fixed_bet']:,.0f} → 収支¥{r['fixed_profit']:+,.0f} (回収率{r['fixed_rate']:.2f}%)")

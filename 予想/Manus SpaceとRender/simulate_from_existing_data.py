"""
既存の分析データを基にした動的購入金額シミュレーション
DB接続なしで計算
"""

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
    """
    関東4場単勝戦略のシミュレーション
    
    既存の分析結果:
    - 対象レース数: 約58,000件（21年分）
    - 的中率: 47.21%
    - 平均払戻: 273.5円（1号艇単勝）
    - 固定金額回収率: 129.12%
    
    オッズ分布（推定）:
    - 1.0〜1.5倍: 30%（低オッズ）
    - 1.5〜2.0倍: 25%
    - 2.0〜3.0倍: 25%
    - 3.0〜5.0倍: 15%
    - 5.0倍以上: 5%
    """
    print("\n" + "="*60)
    print("【関東4場単勝戦略】シミュレーション")
    print("="*60)
    
    total_races = 58000
    hit_rate = 0.4721
    
    # オッズ帯別の分布と的中時の平均払戻
    odds_distribution = [
        # (オッズ帯, 分布率, 平均オッズ, 的中率, 平均払戻)
        (1.0, 1.5, 0.30, 1.25, 0.55, 125),   # 低オッズ: 勝率高い
        (1.5, 2.0, 0.25, 1.75, 0.50, 175),   # 中低オッズ
        (2.0, 3.0, 0.25, 2.50, 0.45, 250),   # 中オッズ
        (3.0, 5.0, 0.15, 4.00, 0.35, 400),   # 中高オッズ
        (5.0, 10.0, 0.05, 7.00, 0.25, 700),  # 高オッズ
    ]
    
    total_dynamic_bet = 0
    total_dynamic_return = 0
    total_fixed_bet = 0
    total_fixed_return = 0
    total_hits = 0
    
    for odds_min, odds_max, dist_rate, avg_odds, hit_rate_band, avg_payoff in odds_distribution:
        races_in_band = int(total_races * dist_rate)
        hits_in_band = int(races_in_band * hit_rate_band)
        
        # 動的金額
        bet_amount = calculate_bet_amount('tansho_kanto', avg_odds)
        dynamic_bet = races_in_band * bet_amount
        dynamic_return = hits_in_band * (avg_payoff / 100) * bet_amount
        
        # 固定金額
        fixed_bet = races_in_band * 1000
        fixed_return = hits_in_band * avg_payoff
        
        total_dynamic_bet += dynamic_bet
        total_dynamic_return += dynamic_return
        total_fixed_bet += fixed_bet
        total_fixed_return += fixed_return
        total_hits += hits_in_band
        
        print(f"\nオッズ{odds_min}〜{odds_max}倍 ({dist_rate*100:.0f}%): {races_in_band:,}件")
        print(f"  購入金額: {bet_amount:,}円, 的中: {hits_in_band:,}件")
        print(f"  動的投資: ¥{dynamic_bet:,.0f} → 払戻: ¥{dynamic_return:,.0f}")
    
    print(f"\n" + "-"*40)
    print(f"対象レース数: {total_races:,}件")
    print(f"的中数: {total_hits:,}件 ({total_hits/total_races*100:.2f}%)")
    
    print(f"\n【動的金額】")
    print(f"  総投資額: ¥{total_dynamic_bet:,.0f}")
    print(f"  総払戻額: ¥{total_dynamic_return:,.0f}")
    print(f"  収支: ¥{total_dynamic_return - total_dynamic_bet:+,.0f}")
    print(f"  回収率: {total_dynamic_return/total_dynamic_bet*100:.2f}%")
    
    print(f"\n【固定金額（1,000円）】")
    print(f"  総投資額: ¥{total_fixed_bet:,.0f}")
    print(f"  総払戻額: ¥{total_fixed_return:,.0f}")
    print(f"  収支: ¥{total_fixed_return - total_fixed_bet:+,.0f}")
    print(f"  回収率: {total_fixed_return/total_fixed_bet*100:.2f}%")
    
    return {
        'strategy': '関東4場単勝',
        'count': total_races,
        'hit_count': total_hits,
        'dynamic_bet': total_dynamic_bet,
        'dynamic_return': total_dynamic_return,
        'dynamic_profit': total_dynamic_return - total_dynamic_bet,
        'dynamic_rate': total_dynamic_return/total_dynamic_bet*100,
        'fixed_bet': total_fixed_bet,
        'fixed_return': total_fixed_return,
        'fixed_profit': total_fixed_return - total_fixed_bet,
        'fixed_rate': total_fixed_return/total_fixed_bet*100,
    }


def simulate_bias_1_3():
    """
    3穴戦略（論文準拠）のシミュレーション
    
    既存の分析結果（論文検証）:
    - 対象: 大村競艇場、当地勝率6.5以上
    - 対象レース数: 約3,000件（21年分）
    - 的中率: 約12%
    - 平均オッズ: 約10倍
    - 固定金額回収率: 約115%
    
    当地勝率分布（推定）:
    - 6.5〜7.0: 40%
    - 7.0〜7.5: 30%
    - 7.5〜8.0: 20%
    - 8.0以上: 10%
    """
    print("\n" + "="*60)
    print("【3穴戦略（論文準拠）】シミュレーション")
    print("="*60)
    
    total_races = 3000
    
    # 当地勝率×オッズ帯別の分布
    # (当地勝率帯, 分布率, 平均当地勝率, オッズ帯分布)
    local_rate_distribution = [
        (6.5, 7.0, 0.40, 6.75),   # 条件ギリギリ
        (7.0, 7.5, 0.30, 7.25),   # 良好
        (7.5, 8.0, 0.20, 7.75),   # 優秀
        (8.0, 9.0, 0.10, 8.25),   # 非常に優秀
    ]
    
    # オッズ分布（2連単/2連複の高い方）
    odds_distribution = [
        # (オッズ帯, 分布率, 平均オッズ, 的中率)
        (3.0, 6.0, 0.20, 4.5, 0.15),    # 低オッズ
        (6.0, 10.0, 0.35, 8.0, 0.12),   # 中オッズ
        (10.0, 20.0, 0.30, 15.0, 0.10), # 中高オッズ
        (20.0, 50.0, 0.15, 30.0, 0.08), # 高オッズ
    ]
    
    total_dynamic_bet = 0
    total_dynamic_return = 0
    total_fixed_bet = 0
    total_fixed_return = 0
    total_hits = 0
    
    for lr_min, lr_max, lr_dist, avg_lr in local_rate_distribution:
        races_by_lr = int(total_races * lr_dist)
        
        print(f"\n当地勝率{lr_min}〜{lr_max} ({lr_dist*100:.0f}%): {races_by_lr:,}件")
        
        for odds_min, odds_max, odds_dist, avg_odds, hit_rate in odds_distribution:
            races_in_cell = int(races_by_lr * odds_dist)
            hits_in_cell = int(races_in_cell * hit_rate)
            
            # 動的金額
            bet_amount = calculate_bet_amount('bias_1_3', avg_odds, avg_lr)
            dynamic_bet = races_in_cell * bet_amount
            dynamic_return = hits_in_cell * avg_odds * bet_amount
            
            # 固定金額
            fixed_bet = races_in_cell * 1000
            fixed_return = hits_in_cell * avg_odds * 1000
            
            total_dynamic_bet += dynamic_bet
            total_dynamic_return += dynamic_return
            total_fixed_bet += fixed_bet
            total_fixed_return += fixed_return
            total_hits += hits_in_cell
            
            print(f"  オッズ{odds_min}〜{odds_max}: {races_in_cell}件, 金額{bet_amount}円, 的中{hits_in_cell}件")
    
    print(f"\n" + "-"*40)
    print(f"対象レース数: {total_races:,}件")
    print(f"的中数: {total_hits:,}件 ({total_hits/total_races*100:.2f}%)")
    
    print(f"\n【動的金額】")
    print(f"  総投資額: ¥{total_dynamic_bet:,.0f}")
    print(f"  総払戻額: ¥{total_dynamic_return:,.0f}")
    print(f"  収支: ¥{total_dynamic_return - total_dynamic_bet:+,.0f}")
    print(f"  回収率: {total_dynamic_return/total_dynamic_bet*100:.2f}%")
    
    print(f"\n【固定金額（1,000円）】")
    print(f"  総投資額: ¥{total_fixed_bet:,.0f}")
    print(f"  総払戻額: ¥{total_fixed_return:,.0f}")
    print(f"  収支: ¥{total_fixed_return - total_fixed_bet:+,.0f}")
    print(f"  回収率: {total_fixed_return/total_fixed_bet*100:.2f}%")
    
    return {
        'strategy': '3穴（論文準拠）',
        'count': total_races,
        'hit_count': total_hits,
        'dynamic_bet': total_dynamic_bet,
        'dynamic_return': total_dynamic_return,
        'dynamic_profit': total_dynamic_return - total_dynamic_bet,
        'dynamic_rate': total_dynamic_return/total_dynamic_bet*100,
        'fixed_bet': total_fixed_bet,
        'fixed_return': total_fixed_return,
        'fixed_profit': total_fixed_return - total_fixed_bet,
        'fixed_rate': total_fixed_return/total_fixed_bet*100,
    }


def simulate_bias_1_3_2nd():
    """
    3穴2nd戦略のシミュレーション
    
    既存の分析結果:
    - 対象: 特定場×R（15条件）、当地勝率4.5〜6.0
    - 対象レース数: 約5,000件（21年分）
    - 的中率: 約11%
    - 平均オッズ: 約8倍
    - 固定金額回収率: 約110%
    """
    print("\n" + "="*60)
    print("【3穴2nd戦略】シミュレーション")
    print("="*60)
    
    total_races = 5000
    
    # 当地勝率分布
    local_rate_distribution = [
        (4.5, 5.0, 0.35, 4.75),   # 条件ギリギリ
        (5.0, 5.5, 0.40, 5.25),   # 良好
        (5.5, 6.0, 0.25, 5.75),   # 優秀
    ]
    
    # オッズ分布
    odds_distribution = [
        (3.0, 6.0, 0.25, 4.5, 0.14),
        (6.0, 10.0, 0.35, 8.0, 0.11),
        (10.0, 20.0, 0.25, 15.0, 0.09),
        (20.0, 50.0, 0.15, 30.0, 0.07),
    ]
    
    total_dynamic_bet = 0
    total_dynamic_return = 0
    total_fixed_bet = 0
    total_fixed_return = 0
    total_hits = 0
    
    for lr_min, lr_max, lr_dist, avg_lr in local_rate_distribution:
        races_by_lr = int(total_races * lr_dist)
        
        print(f"\n当地勝率{lr_min}〜{lr_max} ({lr_dist*100:.0f}%): {races_by_lr:,}件")
        
        for odds_min, odds_max, odds_dist, avg_odds, hit_rate in odds_distribution:
            races_in_cell = int(races_by_lr * odds_dist)
            hits_in_cell = int(races_in_cell * hit_rate)
            
            # 動的金額
            bet_amount = calculate_bet_amount('bias_1_3_2nd', avg_odds, avg_lr)
            dynamic_bet = races_in_cell * bet_amount
            dynamic_return = hits_in_cell * avg_odds * bet_amount
            
            # 固定金額
            fixed_bet = races_in_cell * 1000
            fixed_return = hits_in_cell * avg_odds * 1000
            
            total_dynamic_bet += dynamic_bet
            total_dynamic_return += dynamic_return
            total_fixed_bet += fixed_bet
            total_fixed_return += fixed_return
            total_hits += hits_in_cell
            
            print(f"  オッズ{odds_min}〜{odds_max}: {races_in_cell}件, 金額{bet_amount}円, 的中{hits_in_cell}件")
    
    print(f"\n" + "-"*40)
    print(f"対象レース数: {total_races:,}件")
    print(f"的中数: {total_hits:,}件 ({total_hits/total_races*100:.2f}%)")
    
    print(f"\n【動的金額】")
    print(f"  総投資額: ¥{total_dynamic_bet:,.0f}")
    print(f"  総払戻額: ¥{total_dynamic_return:,.0f}")
    print(f"  収支: ¥{total_dynamic_return - total_dynamic_bet:+,.0f}")
    print(f"  回収率: {total_dynamic_return/total_dynamic_bet*100:.2f}%")
    
    print(f"\n【固定金額（1,000円）】")
    print(f"  総投資額: ¥{total_fixed_bet:,.0f}")
    print(f"  総払戻額: ¥{total_fixed_return:,.0f}")
    print(f"  収支: ¥{total_fixed_return - total_fixed_bet:+,.0f}")
    print(f"  回収率: {total_fixed_return/total_fixed_bet*100:.2f}%")
    
    return {
        'strategy': '3穴2nd',
        'count': total_races,
        'hit_count': total_hits,
        'dynamic_bet': total_dynamic_bet,
        'dynamic_return': total_dynamic_return,
        'dynamic_profit': total_dynamic_return - total_dynamic_bet,
        'dynamic_rate': total_dynamic_return/total_dynamic_bet*100,
        'fixed_bet': total_fixed_bet,
        'fixed_return': total_fixed_return,
        'fixed_profit': total_fixed_return - total_fixed_bet,
        'fixed_rate': total_fixed_return/total_fixed_bet*100,
    }


if __name__ == "__main__":
    print("="*60)
    print("動的購入金額 21年分収支シミュレーション")
    print("（既存分析データに基づく推定）")
    print("="*60)
    
    results = []
    
    r1 = simulate_tansho_kanto()
    results.append(r1)
    
    r2 = simulate_bias_1_3()
    results.append(r2)
    
    r3 = simulate_bias_1_3_2nd()
    results.append(r3)
    
    # サマリー
    print("\n" + "="*60)
    print("【総合サマリー】")
    print("="*60)
    
    total_dynamic_bet = 0
    total_dynamic_return = 0
    total_fixed_bet = 0
    total_fixed_return = 0
    
    for r in results:
        print(f"\n{r['strategy']}:")
        print(f"  レース数: {r['count']:,}件, 的中: {r['hit_count']:,}件 ({r['hit_count']/r['count']*100:.1f}%)")
        print(f"  動的金額: 投資¥{r['dynamic_bet']:,.0f} → 収支¥{r['dynamic_profit']:+,.0f} (回収率{r['dynamic_rate']:.1f}%)")
        print(f"  固定金額: 投資¥{r['fixed_bet']:,.0f} → 収支¥{r['fixed_profit']:+,.0f} (回収率{r['fixed_rate']:.1f}%)")
        
        total_dynamic_bet += r['dynamic_bet']
        total_dynamic_return += r['dynamic_return']
        total_fixed_bet += r['fixed_bet']
        total_fixed_return += r['fixed_return']
    
    print("\n" + "-"*60)
    print("【3戦略合計】")
    print(f"  動的金額: 投資¥{total_dynamic_bet:,.0f} → 収支¥{total_dynamic_return - total_dynamic_bet:+,.0f} (回収率{total_dynamic_return/total_dynamic_bet*100:.1f}%)")
    print(f"  固定金額: 投資¥{total_fixed_bet:,.0f} → 収支¥{total_fixed_return - total_fixed_bet:+,.0f} (回収率{total_fixed_return/total_fixed_bet*100:.1f}%)")

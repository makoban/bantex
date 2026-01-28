#!/usr/bin/env python3
"""
Benterモデル構築 - Step 3: バックテスト
ファンダメンタルモデルを使用して回収率をシミュレーション
"""
import psycopg2
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def get_test_data_with_payoffs():
    """テストデータと払戻金を取得"""
    print("テストデータ取得中（2025年10月〜12月）...")
    
    conn = get_connection()
    
    # 番組表・結果・払戻金を結合
    query = """
    WITH programs AS (
        SELECT 
            race_date,
            stadium_code,
            race_no,
            boat_no,
            COALESCE(national_win_rate, 0) as national_win_rate,
            COALESCE(national_2nd_rate, 0) as national_2nd_rate,
            COALESCE(local_win_rate, 0) as local_win_rate,
            COALESCE(local_2nd_rate, 0) as local_2nd_rate,
            COALESCE(motor_2nd_rate, 0) as motor_2nd_rate,
            COALESCE(boat_2nd_rate, 0) as boat_2nd_rate,
            CASE 
                WHEN rank = 'A1' THEN 4
                WHEN rank = 'A2' THEN 3
                WHEN rank = 'B1' THEN 2
                WHEN rank = 'B2' THEN 1
                ELSE 0
            END as rank_score
        FROM historical_programs
        WHERE race_date >= '20251001' AND race_date <= '20251231'
    ),
    winners AS (
        SELECT 
            race_date,
            stadium_code,
            race_no,
            boat_no,
            1 as is_winner
        FROM historical_race_results
        WHERE race_date >= '20251001' AND race_date <= '20251231'
          AND rank = '01'
    ),
    payoffs AS (
        SELECT 
            race_date,
            stadium_code,
            race_no,
            combination as winning_boat,
            payout as win_payout
        FROM historical_payoffs
        WHERE race_date >= '20251001' AND race_date <= '20251231'
          AND bet_type = '単勝'
    )
    SELECT 
        p.*,
        COALESCE(w.is_winner, 0) as is_winner,
        pay.win_payout
    FROM programs p
    LEFT JOIN winners w 
        ON p.race_date = w.race_date 
        AND p.stadium_code = w.stadium_code 
        AND p.race_no = w.race_no 
        AND p.boat_no = w.boat_no
    LEFT JOIN payoffs pay
        ON p.race_date = pay.race_date 
        AND p.stadium_code = pay.stadium_code 
        AND p.race_no = pay.race_no 
        AND p.boat_no = pay.winning_boat
    ORDER BY p.race_date, p.stadium_code, p.race_no, p.boat_no
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    print(f"取得件数: {len(df):,}件")
    print(f"払戻金データあり: {df['win_payout'].notna().sum():,}件")
    
    return df

def get_training_data():
    """訓練データを取得（2025年1月〜9月）"""
    print("訓練データ取得中（2025年1月〜9月）...")
    
    conn = get_connection()
    
    query = """
    WITH programs AS (
        SELECT 
            race_date,
            stadium_code,
            race_no,
            boat_no,
            COALESCE(national_win_rate, 0) as national_win_rate,
            COALESCE(national_2nd_rate, 0) as national_2nd_rate,
            COALESCE(local_win_rate, 0) as local_win_rate,
            COALESCE(local_2nd_rate, 0) as local_2nd_rate,
            COALESCE(motor_2nd_rate, 0) as motor_2nd_rate,
            COALESCE(boat_2nd_rate, 0) as boat_2nd_rate,
            CASE 
                WHEN rank = 'A1' THEN 4
                WHEN rank = 'A2' THEN 3
                WHEN rank = 'B1' THEN 2
                WHEN rank = 'B2' THEN 1
                ELSE 0
            END as rank_score
        FROM historical_programs
        WHERE race_date >= '20250101' AND race_date <= '20250930'
    ),
    winners AS (
        SELECT 
            race_date,
            stadium_code,
            race_no,
            boat_no,
            1 as is_winner
        FROM historical_race_results
        WHERE race_date >= '20250101' AND race_date <= '20250930'
          AND rank = '01'
    )
    SELECT 
        p.*,
        COALESCE(w.is_winner, 0) as is_winner
    FROM programs p
    LEFT JOIN winners w 
        ON p.race_date = w.race_date 
        AND p.stadium_code = w.stadium_code 
        AND p.race_no = w.race_no 
        AND p.boat_no = w.boat_no
    ORDER BY p.race_date, p.stadium_code, p.race_no, p.boat_no
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    print(f"取得件数: {len(df):,}件")
    return df

def prepare_features(df):
    """特徴量を準備"""
    df['boat_no'] = df['boat_no'].astype(int)
    for i in range(2, 7):
        df[f'boat_{i}'] = (df['boat_no'] == i).astype(int)
    
    major_stadiums = ['01', '04', '06', '12', '21', '24']
    for stadium in major_stadiums:
        df[f'stadium_{stadium}'] = (df['stadium_code'] == stadium).astype(int)
    
    feature_cols = [
        'national_win_rate', 'national_2nd_rate', 
        'local_win_rate', 'local_2nd_rate',
        'motor_2nd_rate', 'boat_2nd_rate', 'rank_score',
        'boat_2', 'boat_3', 'boat_4', 'boat_5', 'boat_6',
        'stadium_01', 'stadium_04', 'stadium_06', 'stadium_12', 'stadium_21', 'stadium_24'
    ]
    
    return df, feature_cols

def train_model(df_train, feature_cols):
    """モデルを訓練"""
    print("\nモデル訓練中...")
    
    X = df_train[feature_cols].values
    y = df_train['is_winner'].values
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_scaled, y)
    
    return model, scaler

def simulate_betting(df_test, model, scaler, feature_cols):
    """ベッティングシミュレーション"""
    print("\nベッティングシミュレーション実行中...")
    
    # 予測確率を算出
    X = df_test[feature_cols].values
    X_scaled = scaler.transform(X)
    df_test['pred_prob'] = model.predict_proba(X_scaled)[:, 1]
    
    # レースごとにグループ化
    df_test['race_id'] = df_test['race_date'] + '_' + df_test['stadium_code'] + '_' + df_test['race_no']
    
    results = []
    
    for race_id, race_df in df_test.groupby('race_id'):
        if len(race_df) != 6:
            continue
        
        # 払戻金データがあるレースのみ
        winner_row = race_df[race_df['is_winner'] == 1]
        if len(winner_row) == 0 or winner_row['win_payout'].isna().all():
            continue
        
        win_payout = winner_row['win_payout'].values[0]
        if pd.isna(win_payout):
            continue
        
        # 各艇の予測確率
        race_df = race_df.sort_values('boat_no')
        probs = race_df['pred_prob'].values
        
        # 確率を正規化（合計1に）
        probs_normalized = probs / probs.sum()
        
        # 最も確率が高い艇を選択
        best_boat = race_df.iloc[np.argmax(probs_normalized)]['boat_no']
        winning_boat = winner_row['boat_no'].values[0]
        
        # 単純戦略: 最も確率が高い艇に賭ける
        bet_amount = 100
        if best_boat == int(winning_boat):
            profit = win_payout - bet_amount
        else:
            profit = -bet_amount
        
        results.append({
            'race_id': race_id,
            'best_boat': best_boat,
            'winning_boat': int(winning_boat),
            'win_payout': win_payout,
            'bet_amount': bet_amount,
            'profit': profit,
            'hit': best_boat == int(winning_boat)
        })
    
    return pd.DataFrame(results)

def simulate_value_betting(df_test, model, scaler, feature_cols):
    """バリューベッティング戦略（Benter方式）"""
    print("\nバリューベッティング戦略シミュレーション...")
    
    X = df_test[feature_cols].values
    X_scaled = scaler.transform(X)
    df_test['pred_prob'] = model.predict_proba(X_scaled)[:, 1]
    
    df_test['race_id'] = df_test['race_date'] + '_' + df_test['stadium_code'] + '_' + df_test['race_no']
    
    results = []
    
    for race_id, race_df in df_test.groupby('race_id'):
        if len(race_df) != 6:
            continue
        
        winner_row = race_df[race_df['is_winner'] == 1]
        if len(winner_row) == 0 or winner_row['win_payout'].isna().all():
            continue
        
        win_payout = winner_row['win_payout'].values[0]
        winning_boat = int(winner_row['boat_no'].values[0])
        
        if pd.isna(win_payout):
            continue
        
        # 各艇の予測確率を正規化
        race_df = race_df.sort_values('boat_no').copy()
        probs = race_df['pred_prob'].values
        probs_normalized = probs / probs.sum()
        
        # 各艇について期待値を計算
        # オッズは払戻金から逆算（勝者の払戻金のみ利用可能なので、予測確率から推定）
        for idx, row in race_df.iterrows():
            boat = int(row['boat_no'])
            pred_prob = probs_normalized[boat - 1]
            
            # 仮想オッズ = 1 / 市場確率（ここでは予測確率の逆数を使用）
            # 実際のオッズデータがあればそれを使用
            implied_odds = 1 / pred_prob if pred_prob > 0 else 100
            
            # 期待値 = 予測確率 × オッズ
            expected_return = pred_prob * implied_odds
            
            # 期待値が1.1以上（10%以上のエッジ）の場合のみ賭ける
            if expected_return >= 1.1 and pred_prob >= 0.3:  # 30%以上の勝率予測
                bet_amount = 100
                if boat == winning_boat:
                    profit = win_payout - bet_amount
                else:
                    profit = -bet_amount
                
                results.append({
                    'race_id': race_id,
                    'bet_boat': boat,
                    'winning_boat': winning_boat,
                    'pred_prob': pred_prob,
                    'expected_return': expected_return,
                    'win_payout': win_payout if boat == winning_boat else 0,
                    'bet_amount': bet_amount,
                    'profit': profit,
                    'hit': boat == winning_boat
                })
    
    return pd.DataFrame(results)

def analyze_results(df_results, strategy_name):
    """結果を分析"""
    print(f"\n【{strategy_name}の結果】")
    print("-" * 50)
    
    total_bets = len(df_results)
    total_bet_amount = df_results['bet_amount'].sum()
    total_profit = df_results['profit'].sum()
    total_return = total_bet_amount + total_profit
    roi = (total_return / total_bet_amount) * 100 if total_bet_amount > 0 else 0
    hit_rate = df_results['hit'].mean() * 100
    
    print(f"総賭け回数: {total_bets:,}回")
    print(f"総投資額: {total_bet_amount:,}円")
    print(f"総回収額: {total_return:,.0f}円")
    print(f"総損益: {total_profit:+,.0f}円")
    print(f"回収率: {roi:.1f}%")
    print(f"的中率: {hit_rate:.1f}%")
    
    return {
        'total_bets': total_bets,
        'total_bet_amount': total_bet_amount,
        'total_profit': total_profit,
        'roi': roi,
        'hit_rate': hit_rate
    }

def main():
    print("=" * 60)
    print("Benterモデル - バックテスト")
    print("=" * 60)
    
    # 訓練データ取得
    df_train = get_training_data()
    df_train, feature_cols = prepare_features(df_train)
    
    # モデル訓練
    model, scaler = train_model(df_train, feature_cols)
    
    # テストデータ取得
    df_test = get_test_data_with_payoffs()
    df_test, _ = prepare_features(df_test)
    
    # 戦略1: 単純最高確率戦略
    results_simple = simulate_betting(df_test.copy(), model, scaler, feature_cols)
    stats_simple = analyze_results(results_simple, "単純最高確率戦略")
    
    # 戦略2: バリューベッティング戦略
    results_value = simulate_value_betting(df_test.copy(), model, scaler, feature_cols)
    stats_value = analyze_results(results_value, "バリューベッティング戦略")
    
    # サマリー
    print("\n" + "=" * 60)
    print("【サマリー】")
    print("=" * 60)
    print(f"訓練期間: 2025年1月〜9月")
    print(f"テスト期間: 2025年10月〜12月")
    print(f"\n単純戦略 回収率: {stats_simple['roi']:.1f}%")
    print(f"バリュー戦略 回収率: {stats_value['roi']:.1f}%")
    
    # 結果を保存
    results_simple.to_csv('/home/ubuntu/benter_model/backtest_simple.csv', index=False)
    results_value.to_csv('/home/ubuntu/benter_model/backtest_value.csv', index=False)
    
    print("\n結果をCSVに保存しました")

if __name__ == "__main__":
    main()

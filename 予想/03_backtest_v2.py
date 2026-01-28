#!/usr/bin/env python3
"""
Benterモデル構築 - Step 3: バックテスト（修正版）
bet_type = 'tansho' を使用
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

def get_training_data():
    """訓練データを取得（2024年）"""
    print("訓練データ取得中（2024年）...")
    
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
        WHERE race_date >= '20240101' AND race_date <= '20241231'
    ),
    winners AS (
        SELECT 
            race_date,
            stadium_code,
            race_no,
            boat_no,
            1 as is_winner
        FROM historical_race_results
        WHERE race_date >= '20240101' AND race_date <= '20241231'
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

def get_test_data_with_payoffs():
    """テストデータと払戻金を取得（2024年10-12月）"""
    print("テストデータ取得中（2024年10月〜12月）...")
    
    conn = get_connection()
    
    # 払戻金データの確認
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) 
        FROM historical_payoffs
        WHERE race_date >= '20241001' AND race_date <= '20241231'
          AND bet_type = 'tansho'
    """)
    payoff_count = cur.fetchone()[0]
    print(f"払戻金データ件数: {payoff_count:,}件")
    
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
        WHERE race_date >= '20241001' AND race_date <= '20241231'
    ),
    winners AS (
        SELECT 
            race_date,
            stadium_code,
            race_no,
            boat_no,
            1 as is_winner
        FROM historical_race_results
        WHERE race_date >= '20241001' AND race_date <= '20241231'
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
        WHERE race_date >= '20241001' AND race_date <= '20241231'
          AND bet_type = 'tansho'
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
    
    print("訓練完了")
    return model, scaler

def simulate_betting(df_test, model, scaler, feature_cols):
    """ベッティングシミュレーション"""
    print("\nベッティングシミュレーション実行中...")
    
    # 予測確率を算出
    X = df_test[feature_cols].values
    X_scaled = scaler.transform(X)
    df_test = df_test.copy()
    df_test['pred_prob'] = model.predict_proba(X_scaled)[:, 1]
    
    # レースごとにグループ化
    df_test['race_id'] = df_test['race_date'] + '_' + df_test['stadium_code'] + '_' + df_test['race_no']
    
    results = []
    
    for race_id, race_df in df_test.groupby('race_id'):
        if len(race_df) != 6:
            continue
        
        # 払戻金データがあるレースのみ
        winner_row = race_df[race_df['is_winner'] == 1]
        if len(winner_row) == 0:
            continue
        
        win_payout = winner_row['win_payout'].values[0]
        if pd.isna(win_payout):
            continue
        
        # 各艇の予測確率
        race_df = race_df.sort_values('boat_no')
        probs = race_df['pred_prob'].values
        probs_normalized = probs / probs.sum()
        
        # 最も確率が高い艇を選択
        best_idx = np.argmax(probs_normalized)
        best_boat = race_df.iloc[best_idx]['boat_no']
        winning_boat = int(winner_row['boat_no'].values[0])
        
        # 単純戦略: 最も確率が高い艇に賭ける
        bet_amount = 100
        if best_boat == winning_boat:
            profit = win_payout - bet_amount
        else:
            profit = -bet_amount
        
        results.append({
            'race_id': race_id,
            'best_boat': best_boat,
            'winning_boat': winning_boat,
            'pred_prob': probs_normalized[best_idx],
            'win_payout': win_payout,
            'bet_amount': bet_amount,
            'profit': profit,
            'hit': best_boat == winning_boat
        })
    
    return pd.DataFrame(results)

def simulate_threshold_betting(df_test, model, scaler, feature_cols, threshold=0.5):
    """閾値ベッティング戦略（高確率のみ賭ける）"""
    print(f"\n閾値ベッティング戦略（閾値: {threshold}）...")
    
    X = df_test[feature_cols].values
    X_scaled = scaler.transform(X)
    df_test = df_test.copy()
    df_test['pred_prob'] = model.predict_proba(X_scaled)[:, 1]
    
    df_test['race_id'] = df_test['race_date'] + '_' + df_test['stadium_code'] + '_' + df_test['race_no']
    
    results = []
    
    for race_id, race_df in df_test.groupby('race_id'):
        if len(race_df) != 6:
            continue
        
        winner_row = race_df[race_df['is_winner'] == 1]
        if len(winner_row) == 0:
            continue
        
        win_payout = winner_row['win_payout'].values[0]
        if pd.isna(win_payout):
            continue
        
        race_df = race_df.sort_values('boat_no')
        probs = race_df['pred_prob'].values
        probs_normalized = probs / probs.sum()
        
        best_idx = np.argmax(probs_normalized)
        best_prob = probs_normalized[best_idx]
        
        # 閾値以上の確率の場合のみ賭ける
        if best_prob < threshold:
            continue
        
        best_boat = race_df.iloc[best_idx]['boat_no']
        winning_boat = int(winner_row['boat_no'].values[0])
        
        bet_amount = 100
        if best_boat == winning_boat:
            profit = win_payout - bet_amount
        else:
            profit = -bet_amount
        
        results.append({
            'race_id': race_id,
            'best_boat': best_boat,
            'winning_boat': winning_boat,
            'pred_prob': best_prob,
            'win_payout': win_payout,
            'bet_amount': bet_amount,
            'profit': profit,
            'hit': best_boat == winning_boat
        })
    
    return pd.DataFrame(results)

def analyze_results(df_results, strategy_name):
    """結果を分析"""
    print(f"\n【{strategy_name}の結果】")
    print("-" * 50)
    
    if len(df_results) == 0:
        print("該当するベットがありませんでした")
        return None
    
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
        'strategy': strategy_name,
        'total_bets': total_bets,
        'total_bet_amount': total_bet_amount,
        'total_profit': total_profit,
        'roi': roi,
        'hit_rate': hit_rate
    }

def main():
    print("=" * 60)
    print("Benterモデル - バックテスト（修正版）")
    print("=" * 60)
    
    # 訓練データ取得（2024年1-9月）
    df_train = get_training_data()
    df_train, feature_cols = prepare_features(df_train)
    
    # 2024年1-9月のデータのみ使用
    df_train = df_train[df_train['race_date'] < '20241001']
    print(f"訓練データ（2024年1-9月）: {len(df_train):,}件")
    
    # モデル訓練
    model, scaler = train_model(df_train, feature_cols)
    
    # テストデータ取得
    df_test = get_test_data_with_payoffs()
    df_test, _ = prepare_features(df_test)
    
    all_results = []
    
    # 戦略1: 全レースに賭ける
    results_all = simulate_betting(df_test.copy(), model, scaler, feature_cols)
    stats_all = analyze_results(results_all, "全レース戦略")
    if stats_all:
        all_results.append(stats_all)
    
    # 戦略2-5: 閾値別
    for threshold in [0.4, 0.5, 0.6, 0.7]:
        results_th = simulate_threshold_betting(df_test.copy(), model, scaler, feature_cols, threshold)
        stats_th = analyze_results(results_th, f"閾値{int(threshold*100)}%戦略")
        if stats_th:
            all_results.append(stats_th)
    
    # サマリー
    print("\n" + "=" * 60)
    print("【サマリー】")
    print("=" * 60)
    
    if all_results:
        summary_df = pd.DataFrame(all_results)
        print(summary_df[['strategy', 'total_bets', 'hit_rate', 'roi']].to_string(index=False))
        summary_df.to_csv('/home/ubuntu/benter_model/backtest_summary.csv', index=False)
    
    print("\n結果をCSVに保存しました")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Benterモデル構築 - Step 2: ファンダメンタルモデル
多項ロジットモデルを用いて各艇の勝率を推定する
"""
import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# データベース接続情報
DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def get_connection():
    """データベース接続を取得"""
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def extract_training_data(start_date='20230101', end_date='20251231'):
    """
    訓練データを抽出
    番組表と競走結果を結合し、各レースの勝者を特定
    """
    print(f"データ抽出中: {start_date} 〜 {end_date}")
    
    conn = get_connection()
    
    # 番組表データを取得（特徴量）
    query_programs = f"""
    SELECT 
        race_date,
        stadium_code,
        race_no,
        boat_no,
        racer_no,
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
        END as rank_score,
        COALESCE(age, 30) as age,
        COALESCE(weight, 52) as weight
    FROM historical_programs
    WHERE race_date >= '{start_date}' AND race_date <= '{end_date}'
    ORDER BY race_date, stadium_code, race_no, boat_no
    """
    
    print("番組表データ取得中...")
    df_programs = pd.read_sql(query_programs, conn)
    print(f"  取得件数: {len(df_programs):,}件")
    
    # 競走結果データを取得（目的変数）
    query_results = f"""
    SELECT 
        race_date,
        stadium_code,
        race_no,
        boat_no,
        rank
    FROM historical_race_results
    WHERE race_date >= '{start_date}' AND race_date <= '{end_date}'
      AND rank = '01'
    """
    
    print("競走結果データ取得中...")
    df_results = pd.read_sql(query_results, conn)
    print(f"  取得件数: {len(df_results):,}件")
    
    conn.close()
    
    # 勝者フラグを作成
    df_results['is_winner'] = 1
    
    # 結合
    df = df_programs.merge(
        df_results[['race_date', 'stadium_code', 'race_no', 'boat_no', 'is_winner']],
        on=['race_date', 'stadium_code', 'race_no', 'boat_no'],
        how='left'
    )
    df['is_winner'] = df['is_winner'].fillna(0).astype(int)
    
    # レースIDを作成
    df['race_id'] = df['race_date'] + '_' + df['stadium_code'] + '_' + df['race_no']
    
    print(f"結合後データ: {len(df):,}件")
    print(f"勝者数: {df['is_winner'].sum():,}件")
    
    return df

def prepare_features(df):
    """
    特徴量を準備
    Benterモデルに基づき、ファンダメンタル要因を数値化
    """
    print("\n特徴量準備中...")
    
    # 枠番をダミー変数化（1号艇を基準）
    df['boat_no'] = df['boat_no'].astype(int)
    for i in range(2, 7):
        df[f'boat_{i}'] = (df['boat_no'] == i).astype(int)
    
    # 競艇場をダミー変数化（一部の主要場のみ）
    # 1:桐生, 4:平和島, 6:浜名湖, 12:住之江, 21:芦屋, 24:大村
    major_stadiums = ['01', '04', '06', '12', '21', '24']
    for stadium in major_stadiums:
        df[f'stadium_{stadium}'] = (df['stadium_code'] == stadium).astype(int)
    
    # 特徴量リスト
    feature_cols = [
        'national_win_rate',
        'national_2nd_rate', 
        'local_win_rate',
        'local_2nd_rate',
        'motor_2nd_rate',
        'boat_2nd_rate',
        'rank_score',
        'boat_2', 'boat_3', 'boat_4', 'boat_5', 'boat_6',
        'stadium_01', 'stadium_04', 'stadium_06', 'stadium_12', 'stadium_21', 'stadium_24'
    ]
    
    print(f"特徴量数: {len(feature_cols)}")
    
    return df, feature_cols

def train_logistic_model(df, feature_cols):
    """
    ロジスティック回帰モデルを訓練
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
    
    print("\nモデル訓練中...")
    
    X = df[feature_cols].values
    y = df['is_winner'].values
    
    # 訓練/テスト分割（時系列を考慮）
    # 最後の20%をテストデータとする
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    print(f"訓練データ: {len(X_train):,}件")
    print(f"テストデータ: {len(X_test):,}件")
    
    # 標準化
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # ロジスティック回帰
    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_train_scaled, y_train)
    
    # 予測
    y_pred_proba_train = model.predict_proba(X_train_scaled)[:, 1]
    y_pred_proba_test = model.predict_proba(X_test_scaled)[:, 1]
    
    # 評価
    print("\n【モデル評価】")
    print("-" * 40)
    
    # 訓練データ
    train_logloss = log_loss(y_train, y_pred_proba_train)
    train_auc = roc_auc_score(y_train, y_pred_proba_train)
    print(f"訓練データ:")
    print(f"  Log Loss: {train_logloss:.4f}")
    print(f"  AUC: {train_auc:.4f}")
    
    # テストデータ
    test_logloss = log_loss(y_test, y_pred_proba_test)
    test_auc = roc_auc_score(y_test, y_pred_proba_test)
    print(f"テストデータ:")
    print(f"  Log Loss: {test_logloss:.4f}")
    print(f"  AUC: {test_auc:.4f}")
    
    # 特徴量の重要度
    print("\n【特徴量の重要度（係数）】")
    print("-" * 40)
    coef_df = pd.DataFrame({
        'feature': feature_cols,
        'coefficient': model.coef_[0]
    }).sort_values('coefficient', ascending=False)
    
    for _, row in coef_df.iterrows():
        print(f"  {row['feature']}: {row['coefficient']:.4f}")
    
    return model, scaler, coef_df, {
        'train_logloss': train_logloss,
        'train_auc': train_auc,
        'test_logloss': test_logloss,
        'test_auc': test_auc
    }

def calculate_mcfadden_r2(df, model, scaler, feature_cols):
    """
    McFadden's R² を計算
    Benter論文で使用されている予測精度指標
    """
    from sklearn.metrics import log_loss
    
    print("\n【McFadden's R² の計算】")
    print("-" * 40)
    
    X = df[feature_cols].values
    y = df['is_winner'].values
    
    X_scaled = scaler.transform(X)
    y_pred_proba = model.predict_proba(X_scaled)[:, 1]
    
    # モデルのLog-Likelihood
    ll_model = -log_loss(y, y_pred_proba, normalize=False)
    
    # Null Model（切片のみ）のLog-Likelihood
    # 競艇の場合、6艇中1艇が勝つので基準確率は1/6 ≈ 0.1667
    base_prob = y.mean()  # 実際の勝率
    ll_null = np.sum(y * np.log(base_prob) + (1-y) * np.log(1-base_prob))
    
    # McFadden's R²
    r2 = 1 - (ll_model / ll_null)
    
    print(f"モデルのLog-Likelihood: {ll_model:.2f}")
    print(f"NullモデルのLog-Likelihood: {ll_null:.2f}")
    print(f"McFadden's R²: {r2:.4f}")
    
    # Benter論文との比較
    print("\n【Benter論文との比較】")
    print("-" * 40)
    print(f"Benter論文のファンダメンタルモデル R²: 約0.08")
    print(f"本モデルの R²: {r2:.4f}")
    
    if r2 > 0.05:
        print("→ 予測に有意な情報を持っている可能性が高い")
    else:
        print("→ 追加の特徴量が必要かもしれない")
    
    return r2

def analyze_by_boat_position(df, model, scaler, feature_cols):
    """
    枠番別の予測精度を分析
    """
    print("\n【枠番別の分析】")
    print("-" * 40)
    
    X = df[feature_cols].values
    X_scaled = scaler.transform(X)
    df['pred_prob'] = model.predict_proba(X_scaled)[:, 1]
    
    # 枠番別の実際の勝率と予測勝率
    boat_analysis = df.groupby('boat_no').agg({
        'is_winner': ['mean', 'sum', 'count'],
        'pred_prob': 'mean'
    }).round(4)
    
    boat_analysis.columns = ['actual_win_rate', 'wins', 'races', 'pred_win_rate']
    boat_analysis['calibration'] = boat_analysis['pred_win_rate'] / boat_analysis['actual_win_rate']
    
    print(boat_analysis.to_string())
    
    return boat_analysis

def main():
    print("=" * 60)
    print("Benterモデル - ファンダメンタルモデル構築")
    print("=" * 60)
    
    # データ抽出（直近3年分）
    df = extract_training_data('20230101', '20251231')
    
    # 特徴量準備
    df, feature_cols = prepare_features(df)
    
    # モデル訓練
    model, scaler, coef_df, metrics = train_logistic_model(df, feature_cols)
    
    # McFadden's R² 計算
    r2 = calculate_mcfadden_r2(df, model, scaler, feature_cols)
    
    # 枠番別分析
    boat_analysis = analyze_by_boat_position(df, model, scaler, feature_cols)
    
    # 結果を保存
    print("\n結果を保存中...")
    coef_df.to_csv('/home/ubuntu/benter_model/feature_coefficients.csv', index=False)
    boat_analysis.to_csv('/home/ubuntu/benter_model/boat_analysis.csv')
    
    # サマリー
    print("\n" + "=" * 60)
    print("【サマリー】")
    print("=" * 60)
    print(f"訓練データ期間: 2023/01/01 〜 2025/12/31")
    print(f"総レコード数: {len(df):,}件")
    print(f"テストAUC: {metrics['test_auc']:.4f}")
    print(f"McFadden's R²: {r2:.4f}")
    print(f"最重要特徴量: {coef_df.iloc[0]['feature']} (係数: {coef_df.iloc[0]['coefficient']:.4f})")
    
    return model, scaler, feature_cols, metrics, r2

if __name__ == "__main__":
    model, scaler, feature_cols, metrics, r2 = main()

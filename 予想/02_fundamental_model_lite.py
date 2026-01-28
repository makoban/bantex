#!/usr/bin/env python3
"""
Benterモデル構築 - Step 2: ファンダメンタルモデル（軽量版）
直近1年分のデータで多項ロジットモデルを構築
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

def extract_training_data():
    """
    訓練データを抽出（直近1年分）
    """
    print("データ抽出中: 2025年のデータ")
    
    conn = get_connection()
    
    # 番組表と結果を結合したクエリ（効率化）
    query = """
    WITH programs AS (
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
            END as rank_score
        FROM historical_programs
        WHERE race_date >= '20250101' AND race_date <= '20251231'
    ),
    winners AS (
        SELECT 
            race_date,
            stadium_code,
            race_no,
            boat_no,
            1 as is_winner
        FROM historical_race_results
        WHERE race_date >= '20250101' AND race_date <= '20251231'
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
    
    print("クエリ実行中...")
    df = pd.read_sql(query, conn)
    conn.close()
    
    print(f"取得件数: {len(df):,}件")
    print(f"勝者数: {df['is_winner'].sum():,}件")
    
    return df

def prepare_features(df):
    """特徴量を準備"""
    print("\n特徴量準備中...")
    
    # 枠番をダミー変数化
    df['boat_no'] = df['boat_no'].astype(int)
    for i in range(2, 7):
        df[f'boat_{i}'] = (df['boat_no'] == i).astype(int)
    
    # 競艇場をダミー変数化（主要場のみ）
    major_stadiums = ['01', '04', '06', '12', '21', '24']
    for stadium in major_stadiums:
        df[f'stadium_{stadium}'] = (df['stadium_code'] == stadium).astype(int)
    
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

def train_model(df, feature_cols):
    """ロジスティック回帰モデルを訓練"""
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import log_loss, roc_auc_score
    
    print("\nモデル訓練中...")
    
    X = df[feature_cols].values
    y = df['is_winner'].values
    
    # 時系列分割（80:20）
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    print(f"訓練データ: {len(X_train):,}件")
    print(f"テストデータ: {len(X_test):,}件")
    
    # 標準化
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # モデル訓練
    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_train_scaled, y_train)
    
    # 予測
    y_pred_train = model.predict_proba(X_train_scaled)[:, 1]
    y_pred_test = model.predict_proba(X_test_scaled)[:, 1]
    
    # 評価
    print("\n【モデル評価】")
    print("-" * 40)
    print(f"訓練 Log Loss: {log_loss(y_train, y_pred_train):.4f}")
    print(f"訓練 AUC: {roc_auc_score(y_train, y_pred_train):.4f}")
    print(f"テスト Log Loss: {log_loss(y_test, y_pred_test):.4f}")
    print(f"テスト AUC: {roc_auc_score(y_test, y_pred_test):.4f}")
    
    # 特徴量重要度
    print("\n【特徴量の係数】")
    print("-" * 40)
    coef_df = pd.DataFrame({
        'feature': feature_cols,
        'coefficient': model.coef_[0]
    }).sort_values('coefficient', ascending=False)
    
    for _, row in coef_df.iterrows():
        print(f"  {row['feature']}: {row['coefficient']:.4f}")
    
    # McFadden's R²
    X_all_scaled = scaler.transform(X)
    y_pred_all = model.predict_proba(X_all_scaled)[:, 1]
    ll_model = -log_loss(y, y_pred_all, normalize=False)
    base_prob = y.mean()
    ll_null = np.sum(y * np.log(base_prob) + (1-y) * np.log(1-base_prob))
    r2 = 1 - (ll_model / ll_null)
    
    print(f"\n【McFadden's R²】")
    print("-" * 40)
    print(f"R² = {r2:.4f}")
    print(f"(Benter論文のファンダメンタルモデル: 約0.08)")
    
    return model, scaler, coef_df, r2, roc_auc_score(y_test, y_pred_test)

def analyze_boat_position(df, model, scaler, feature_cols):
    """枠番別分析"""
    print("\n【枠番別の勝率分析】")
    print("-" * 40)
    
    X = df[feature_cols].values
    X_scaled = scaler.transform(X)
    df['pred_prob'] = model.predict_proba(X_scaled)[:, 1]
    
    result = df.groupby('boat_no').agg({
        'is_winner': ['mean', 'sum'],
        'pred_prob': 'mean'
    }).round(4)
    result.columns = ['actual_win_rate', 'wins', 'pred_win_rate']
    
    print(result.to_string())
    return result

def main():
    print("=" * 60)
    print("Benterモデル - ファンダメンタルモデル構築（軽量版）")
    print("=" * 60)
    
    # データ抽出
    df = extract_training_data()
    
    # 特徴量準備
    df, feature_cols = prepare_features(df)
    
    # モデル訓練
    model, scaler, coef_df, r2, test_auc = train_model(df, feature_cols)
    
    # 枠番別分析
    boat_analysis = analyze_boat_position(df, model, scaler, feature_cols)
    
    # 結果保存
    coef_df.to_csv('/home/ubuntu/benter_model/feature_coefficients.csv', index=False)
    boat_analysis.to_csv('/home/ubuntu/benter_model/boat_analysis.csv')
    
    # サマリー
    print("\n" + "=" * 60)
    print("【サマリー】")
    print("=" * 60)
    print(f"データ期間: 2025年")
    print(f"総レコード数: {len(df):,}件")
    print(f"テストAUC: {test_auc:.4f}")
    print(f"McFadden's R²: {r2:.4f}")
    print(f"最重要特徴量: {coef_df.iloc[0]['feature']}")
    
    # 結論
    print("\n【結論】")
    print("-" * 40)
    if r2 > 0.05:
        print("✅ モデルは予測に有意な情報を持っています")
        print("→ Benterモデルの統合フェーズに進む価値があります")
    else:
        print("⚠️ モデルの予測力が弱い可能性があります")
        print("→ 追加の特徴量を検討してください")

if __name__ == "__main__":
    main()

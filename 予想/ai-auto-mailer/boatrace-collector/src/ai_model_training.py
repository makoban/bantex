"""
競艇AI予想モデル - 初期学習スクリプト
20年分の過去データでLightGBMモデルを学習
"""
import os
import json
import pickle
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import numpy as np

# LightGBMのインポート（インストールされていない場合はスキップ）
try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    print("⚠️ LightGBMがインストールされていません。pip install lightgbm でインストールしてください。")

DATABASE_URL = os.environ.get('DATABASE_URL')
JST = timezone(timedelta(hours=9))

# モデル保存先
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
os.makedirs(MODEL_DIR, exist_ok=True)

# 競艇場名マップ
STADIUM_NAMES = {
    '01': '桐生', '02': '戸田', '03': '江戸川', '04': '平和島',
    '05': '多摩川', '06': '浜名湖', '07': '蒲郡', '08': '常滑',
    '09': '津', '10': '三国', '11': 'びわこ', '12': '住之江',
    '13': '尼崎', '14': '鳴門', '15': '丸亀', '16': '児島',
    '17': '宮島', '18': '徳山', '19': '下関', '20': '若松',
    '21': '芦屋', '22': '福岡', '23': '唐津', '24': '大村'
}


def fetch_training_data(cur, start_year=2015, end_year=2025):
    """学習データを取得（直近10年分）"""
    print(f"\n📊 学習データ取得中 ({start_year}-{end_year})...")

    query = """
        SELECT
            p.race_date,
            p.stadium_code,
            p.race_no,
            p.boat_no,
            p.national_win_rate,
            p.local_win_rate,
            p.motor_2nd_rate,
            p.boat_2nd_rate,
            p.rank as racer_rank,
            res.rank as finish_rank
        FROM historical_programs p
        JOIN historical_race_results res
            ON p.race_date = res.race_date
            AND p.stadium_code = res.stadium_code
            AND p.race_no = res.race_no
            AND p.boat_no = res.boat_no
        WHERE p.race_date >= %s AND p.race_date < %s
        ORDER BY race_date, stadium_code, race_no, boat_no
        LIMIT 3000000
    """

    start_date = f"{start_year}-01-01"
    end_date = f"{end_year + 1}-01-01"

    cur.execute(query, (start_date, end_date))
    rows = cur.fetchall()

    print(f"   取得件数: {len(rows):,}行")
    return rows


def prepare_features(rows):
    """特徴量を準備"""
    print("\n🔧 特徴量準備中...")

    df = pd.DataFrame(rows)

    # レースごとにピボット（6艇分の特徴量を横に展開）
    races = []
    current_race = None
    race_boats = []

    for _, row in df.iterrows():
        race_key = (row['race_date'], row['stadium_code'], row['race_no'])

        if current_race != race_key:
            if race_boats and len(race_boats) == 6:
                races.append(race_boats)
            current_race = race_key
            race_boats = []

        race_boats.append(row)

    # 最後のレースを追加
    if race_boats and len(race_boats) == 6:
        races.append(race_boats)

    print(f"   有効レース数: {len(races):,}件")

    # 特徴量作成
    X = []
    y = []
    race_info = []

    for race in races:
        features = []
        winner = None

        for boat in race:
            boat_no = int(boat['boat_no'])

            # 数値特徴量（安全に変換）
            def safe_float(val):
                if val is None:
                    return 0.0
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return 0.0

            features.extend([
                safe_float(boat['national_win_rate']),
                safe_float(boat['local_win_rate']),
                safe_float(boat['motor_2nd_rate']),
                safe_float(boat['boat_2nd_rate']),
            ])

            # ランクを数値化
            rank_map = {'A1': 4, 'A2': 3, 'B1': 2, 'B2': 1}
            features.append(rank_map.get(boat['racer_rank'], 0))

            # 勝者判定
            try:
                if boat['finish_rank'] == '01' or boat['finish_rank'] == 1:
                    winner = boat_no
            except:
                pass

        if winner is not None and len(features) == 30:  # 5特徴量 × 6艇 = 30
            # 場コードを追加
            stadium_code = int(race[0]['stadium_code'])
            race_no = int(race[0]['race_no'])
            features.extend([stadium_code, race_no])

            X.append(features)
            y.append(winner)
            race_info.append({
                'race_date': race[0]['race_date'],
                'stadium_code': race[0]['stadium_code'],
                'race_no': race[0]['race_no']
            })

    print(f"   学習用データ: {len(X):,}件")

    return np.array(X), np.array(y), race_info


def train_model(X, y):
    """LightGBMモデルを学習"""
    print("\n🤖 モデル学習中...")

    if not HAS_LIGHTGBM:
        print("   ❌ LightGBMがインストールされていないため、学習をスキップします。")
        return None

    # 学習・検証データ分割（最後の20%を検証用）
    split_idx = int(len(X) * 0.8)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    print(f"   学習データ: {len(X_train):,}件")
    print(f"   検証データ: {len(X_val):,}件")

    # 特徴量名
    feature_names = []
    for i in range(1, 7):
        feature_names.extend([
            f'boat{i}_national_win_rate',
            f'boat{i}_local_win_rate',
            f'boat{i}_motor_2nd_rate',
            f'boat{i}_boat_2nd_rate',
            f'boat{i}_rank',
        ])
    feature_names.extend(['stadium_code', 'race_no'])

    # データセット作成
    train_data = lgb.Dataset(X_train, label=y_train - 1, feature_name=feature_names)  # 0-indexedに
    val_data = lgb.Dataset(X_val, label=y_val - 1, reference=train_data)

    # パラメータ
    params = {
        'objective': 'multiclass',
        'num_class': 6,
        'metric': 'multi_logloss',
        'boosting_type': 'gbdt',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.9,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': -1
    }

    # 学習
    model = lgb.train(
        params,
        train_data,
        num_boost_round=500,
        valid_sets=[train_data, val_data],
        valid_names=['train', 'valid'],
        callbacks=[
            lgb.early_stopping(stopping_rounds=50),
            lgb.log_evaluation(period=100)
        ]
    )

    # 検証データでの精度
    y_pred = model.predict(X_val)
    y_pred_class = np.argmax(y_pred, axis=1) + 1  # 1-indexedに戻す
    accuracy = np.mean(y_pred_class == y_val)

    print(f"\n   ✅ 学習完了")
    print(f"   検証精度（単勝的中率）: {accuracy * 100:.2f}%")

    # 1号艇の予測精度
    boat1_correct = np.sum((y_pred_class == 1) & (y_val == 1))
    boat1_predicted = np.sum(y_pred_class == 1)
    boat1_actual = np.sum(y_val == 1)
    print(f"   1号艇予測精度: {boat1_correct}/{boat1_predicted} ({boat1_correct/boat1_predicted*100:.1f}%)")
    print(f"   1号艇実際勝率: {boat1_actual}/{len(y_val)} ({boat1_actual/len(y_val)*100:.1f}%)")

    return model


def save_model(model, version="v1.0"):
    """モデルを保存"""
    if model is None:
        print("\n❌ モデルがNoneのため、保存をスキップします。")
        return None

    model_path = os.path.join(MODEL_DIR, f'boatrace_ai_{version}.pkl')

    with open(model_path, 'wb') as f:
        pickle.dump(model, f)

    print(f"\n💾 モデル保存: {model_path}")
    return model_path


def main():
    print("=" * 60)
    print("競艇AI予想モデル - 初期学習")
    print("=" * 60)

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    # データ取得
    rows = fetch_training_data(cur, start_year=2015, end_year=2025)

    if not rows:
        print("❌ データが取得できませんでした。")
        conn.close()
        return

    # 特徴量準備
    X, y, race_info = prepare_features(rows)

    if len(X) == 0:
        print("❌ 有効なデータがありませんでした。")
        conn.close()
        return

    # モデル学習
    model = train_model(X, y)

    # モデル保存
    model_path = save_model(model, version="v1.0")

    conn.close()

    print("\n" + "=" * 60)
    print("✅ 初期学習完了")
    print("=" * 60)


if __name__ == "__main__":
    main()

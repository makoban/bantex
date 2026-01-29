"""
競艇AI予想 - 予想生成バッチ
締切5分前に予想を生成してDBに保存
"""
import os
import json
import pickle
from datetime import datetime, timezone, timedelta, date
from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor
import numpy as np

DATABASE_URL = os.environ.get('DATABASE_URL')
JST = timezone(timedelta(hours=9))

# モデルパス
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
MODEL_PATH = os.path.join(MODEL_DIR, 'boatrace_ai_v1.0.pkl')
MODEL_VERSION = 'v1.0'

# 競艇場名マップ
STADIUM_NAMES = {
    '01': '桐生', '02': '戸田', '03': '江戸川', '04': '平和島',
    '05': '多摩川', '06': '浜名湖', '07': '蒲郡', '08': '常滑',
    '09': '津', '10': '三国', '11': 'びわこ', '12': '住之江',
    '13': '尼崎', '14': '鳴門', '15': '丸亀', '16': '児島',
    '17': '宮島', '18': '徳山', '19': '下関', '20': '若松',
    '21': '芦屋', '22': '福岡', '23': '唐津', '24': '大村'
}


def load_model():
    """学習済みモデルを読み込み"""
    if not os.path.exists(MODEL_PATH):
        print(f"❌ モデルが見つかりません: {MODEL_PATH}")
        return None

    with open(MODEL_PATH, 'rb') as f:
        model = pickle.load(f)

    print(f"✅ モデル読み込み完了: {MODEL_VERSION}")
    return model


def safe_float(val):
    """安全に数値変換"""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def get_race_features(cur, race_date, stadium_code, race_no):
    """レースの特徴量を取得"""
    cur.execute("""
        SELECT
            boat_no as boat_number,
            national_win_rate,
            local_win_rate,
            motor_2nd_rate as motor_2rate,
            boat_2nd_rate as boat_2rate,
            rank as grade
        FROM historical_programs
        WHERE race_date = %s AND stadium_code = %s AND race_no = %s
        ORDER BY boat_no
    """, (race_date, stadium_code, race_no))

    rows = cur.fetchall()

    if len(rows) != 6:
        return None, None

    # 特徴量を作成
    features = []
    boat_info = []

    for row in rows:
        features.extend([
            safe_float(row['national_win_rate']),
            safe_float(row['local_win_rate']),
            safe_float(row['motor_2rate']),
            safe_float(row['boat_2rate']),
        ])

        # グレードを数値化
        grade_map = {'A1': 4, 'A2': 3, 'B1': 2, 'B2': 1}
        features.append(grade_map.get(row['grade'], 0))

        boat_info.append({
            'boat_no': row['boat_number'],
            'national_win_rate': safe_float(row['national_win_rate']),
            'local_win_rate': safe_float(row['local_win_rate']),
            'motor_2rate': safe_float(row['motor_2rate']),
            'grade': row['grade']
        })

    # 場コード、R番号を追加
    features.extend([int(stadium_code), int(race_no)])

    return np.array([features]), boat_info


def calculate_confidence(probs):
    """信頼度を計算（最大確率の艇とその他の差）"""
    sorted_probs = sorted(probs, reverse=True)
    # 1位と2位の差 + 1位の確率
    gap = sorted_probs[0] - sorted_probs[1]
    confidence = (sorted_probs[0] * 0.6 + gap * 0.4) * 100
    return min(100, max(0, confidence))


def generate_reasons(boat_info, probs):
    """予想理由を生成"""
    reasons = []

    # 勝率が高い艇を特定
    sorted_boats = sorted(enumerate(boat_info), key=lambda x: probs[x[0]], reverse=True)

    # 上位3艇の理由
    for i, (idx, boat) in enumerate(sorted_boats[:3]):
        boat_no = idx + 1

        if i == 0:  # 本命
            if boat['grade'] == 'A1':
                reasons.append({
                    'type': 'positive',
                    'text': f"{boat_no}号艇: A1ランク、全国勝率{boat['national_win_rate']:.1f}%"
                })
            elif boat['national_win_rate'] >= 7.0:
                reasons.append({
                    'type': 'positive',
                    'text': f"{boat_no}号艇: 全国勝率{boat['national_win_rate']:.1f}%（高勝率）"
                })
            else:
                reasons.append({
                    'type': 'positive',
                    'text': f"{boat_no}号艇: 本命（AI予測勝率{probs[idx]*100:.1f}%）"
                })

        elif i == 1:  # 対抗
            if boat['motor_2rate'] >= 40:
                reasons.append({
                    'type': 'positive',
                    'text': f"{boat_no}号艇: モーター2連率{boat['motor_2rate']:.1f}%（好調機）"
                })
            elif boat['local_win_rate'] >= 6.0:
                reasons.append({
                    'type': 'positive',
                    'text': f"{boat_no}号艇: 当地勝率{boat['local_win_rate']:.1f}%（地元◎）"
                })

        elif i == 2:  # 穴
            if probs[idx] >= 0.10:
                reasons.append({
                    'type': 'warning',
                    'text': f"{boat_no}号艇: 穴候補（AI予測{probs[idx]*100:.1f}%）"
                })

    return reasons[:3]  # 最大3つ


def generate_predictions(model, cur, race_date, stadium_code, race_no):
    """1レースの予想を生成"""

    # 特徴量取得
    X, boat_info = get_race_features(cur, race_date, stadium_code, race_no)

    if X is None:
        return None

    # 予測
    probs = model.predict(X)[0]  # 6艇の勝率

    # 信頼度計算
    confidence = calculate_confidence(probs)

    # 各券種の予測
    sorted_indices = np.argsort(probs)[::-1]  # 勝率高い順

    # 単勝
    tansho = int(sorted_indices[0] + 1)

    # 2連単・2連複
    top2 = sorted(sorted_indices[:2] + 1)
    nirentan = f"{sorted_indices[0]+1}-{sorted_indices[1]+1}"
    nirenfuku = f"{top2[0]}-{top2[1]}"

    # 3連単・3連複
    top3 = sorted(sorted_indices[:3] + 1)
    sanrentan = f"{sorted_indices[0]+1}-{sorted_indices[1]+1}-{sorted_indices[2]+1}"
    sanrenfuku = f"{top3[0]}-{top3[1]}-{top3[2]}"

    # 理由生成
    reasons = generate_reasons(boat_info, probs)

    # 特徴量重要度（簡易版）
    feature_importance = []
    for i, boat in enumerate(boat_info):
        if probs[i] == max(probs):
            feature_importance.append({
                'feature': f'{i+1}号艇全国勝率',
                'impact': probs[i]
            })

    # 予想データ
    predictions_json = {
        'tansho': {'boat': tansho, 'probability': float(probs[sorted_indices[0]])},
        'fukusho': [
            {'boat': int(sorted_indices[0]+1), 'probability': float(probs[sorted_indices[0]])},
            {'boat': int(sorted_indices[1]+1), 'probability': float(probs[sorted_indices[1]])}
        ],
        'nirentan': [
            {'combination': nirentan, 'probability': float(probs[sorted_indices[0]] * probs[sorted_indices[1]])}
        ],
        'nirenfuku': [
            {'combination': nirenfuku, 'probability': float(probs[sorted_indices[0]] * probs[sorted_indices[1]] * 1.2)}
        ],
        'sanrentan': [
            {'combination': sanrentan, 'probability': float(probs[sorted_indices[0]] * probs[sorted_indices[1]] * probs[sorted_indices[2]])}
        ],
        'sanrenfuku': [
            {'combination': sanrenfuku, 'probability': float(probs[sorted_indices[0]] * probs[sorted_indices[1]] * probs[sorted_indices[2]] * 1.5)}
        ]
    }

    return {
        'confidence': confidence,
        'tansho_prediction': tansho,
        'nirentan_prediction': nirentan,
        'nirenfuku_prediction': nirenfuku,
        'sanrentan_prediction': sanrentan,
        'sanrenfuku_prediction': sanrenfuku,
        'predictions_json': predictions_json,
        'reasons_json': reasons,
        'feature_importance_json': feature_importance
    }


def save_prediction(cur, race_date, stadium_code, race_no, prediction):
    """予想をDBに保存"""
    cur.execute("""
        INSERT INTO ai_predictions (
            race_date, stadium_code, race_number,
            confidence, tansho_prediction,
            nirentan_prediction, nirenfuku_prediction,
            sanrentan_prediction, sanrenfuku_prediction,
            predictions_json, reasons_json, feature_importance_json,
            model_version, predicted_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (race_date, stadium_code, race_number)
        DO UPDATE SET
            confidence = EXCLUDED.confidence,
            tansho_prediction = EXCLUDED.tansho_prediction,
            nirentan_prediction = EXCLUDED.nirentan_prediction,
            nirenfuku_prediction = EXCLUDED.nirenfuku_prediction,
            sanrentan_prediction = EXCLUDED.sanrentan_prediction,
            sanrenfuku_prediction = EXCLUDED.sanrenfuku_prediction,
            predictions_json = EXCLUDED.predictions_json,
            reasons_json = EXCLUDED.reasons_json,
            feature_importance_json = EXCLUDED.feature_importance_json,
            model_version = EXCLUDED.model_version,
            predicted_at = EXCLUDED.predicted_at
    """, (
        race_date, stadium_code, race_no,
        prediction['confidence'],
        prediction['tansho_prediction'],
        prediction['nirentan_prediction'],
        prediction['nirenfuku_prediction'],
        prediction['sanrentan_prediction'],
        prediction['sanrenfuku_prediction'],
        json.dumps(prediction['predictions_json']),
        json.dumps(prediction['reasons_json']),
        json.dumps(prediction['feature_importance_json']),
        MODEL_VERSION,
        datetime.now(JST)
    ))


def predict_single_race(database_url: str, race_date: str, stadium_code: str, race_no: int) -> dict:
    """
    直前予想: 1レース分のAI予想を生成してDBに保存

    Args:
        database_url: データベースURL
        race_date: レース日（YYYYMMDD形式）
        stadium_code: 場コード（01~24）
        race_no: レース番号（1~12）

    Returns:
        dict: 予想結果（成功時）、None（失敗時）
    """
    import logging
    logger = logging.getLogger(__name__)

    # モデル読み込み
    model = load_model()
    if model is None:
        logger.error(f"モデル読み込み失敗")
        return None

    conn = None
    try:
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        cur = conn.cursor()

        # 予想生成
        prediction = generate_predictions(model, cur, race_date, stadium_code, race_no)

        if prediction is None:
            logger.warning(f"予想生成失敗: {stadium_code} {race_no}R - 特徴量取得エラー")
            return None

        # DB保存
        # race_dateがYYYYMMDD文字列の場合、date型に変換
        if isinstance(race_date, str) and len(race_date) == 8:
            race_date_obj = datetime.strptime(race_date, '%Y%m%d').date()
        else:
            race_date_obj = race_date

        save_prediction(cur, race_date_obj, stadium_code, race_no, prediction)
        conn.commit()

        stadium_name = STADIUM_NAMES.get(stadium_code, stadium_code)
        logger.info(f"✅ AI予想生成: {stadium_name} {race_no}R - 信頼度: {prediction['confidence']:.1f}%")

        return {
            'stadium_code': stadium_code,
            'stadium_name': stadium_name,
            'race_number': race_no,
            'confidence': prediction['confidence'],
            'tansho': prediction['tansho_prediction'],
            'nirentan': prediction['nirentan_prediction'],
            'nirenfuku': prediction['nirenfuku_prediction'],
            'sanrentan': prediction['sanrentan_prediction'],
        }

    except Exception as e:
        logger.error(f"AI予想エラー: {stadium_code} {race_no}R - {e}")
        if conn:
            conn.rollback()
        return None

    finally:
        if conn:
            conn.close()


def run_batch(target_date=None):
    """バッチ実行"""
    print("=" * 60)
    print("競艇AI予想 - 予想生成バッチ")
    print("=" * 60)

    # モデル読み込み
    model = load_model()
    if model is None:
        return

    # DB接続
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    # 対象日（YYYYMMDD形式の文字列に変換）
    if target_date is None:
        target_date = datetime.now(JST).date()

    race_date_str = target_date.strftime('%Y%m%d')
    print(f"\n📅 対象日: {target_date} ({race_date_str})")

    # 今日のレース一覧を取得
    cur.execute("""
        SELECT DISTINCT stadium_code, race_no as race_number
        FROM historical_programs
        WHERE race_date = %s
        ORDER BY stadium_code, race_no
    """, (race_date_str,))

    races = cur.fetchall()
    print(f"   対象レース: {len(races)}件")

    # 各レースで予想生成
    success_count = 0
    for race in races:
        stadium_code = race['stadium_code']
        race_no = race['race_number']

        prediction = generate_predictions(model, cur, race_date_str, stadium_code, race_no)

        if prediction:
            save_prediction(cur, target_date, stadium_code, race_no, prediction)
            success_count += 1
            success_count += 1
            stadium_name = STADIUM_NAMES.get(stadium_code, stadium_code)
            print(f"   ✅ {stadium_name} {race_no}R - 信頼度: {prediction['confidence']:.1f}%")

    conn.commit()
    conn.close()

    print(f"\n" + "=" * 60)
    print(f"✅ 予想生成完了: {success_count}/{len(races)}件")
    print("=" * 60)


if __name__ == "__main__":
    run_batch()

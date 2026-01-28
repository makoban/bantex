"""
自動購入バッチ処理
PostgreSQL（kokotomo-db-staging）のみを使用

機能:
1. 毎朝8:00に購入予定を自動登録（レースデータ収集も同時実行）
2. 締切1分前に購入判断
3. 結果収集後に当選/外れを更新
"""

import os
import time

# タイムゾーンを日本時間に設定（pyjpboatraceの日付バリデーション対策）
os.environ['TZ'] = 'Asia/Tokyo'
if hasattr(time, 'tzset'):
    time.tzset()

import logging
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Optional, Any
from decimal import Decimal
import json
import re

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
import requests
from bs4 import BeautifulSoup

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 日本時間
JST = timezone(timedelta(hours=9))

# データベースURL
DATABASE_URL = os.environ.get("DATABASE_URL")

# 競艇場名とコードのマッピング
STADIUM_MAP = {
    '桐生': 1, '戸田': 2, '江戸川': 3, '平和島': 4, '多摩川': 5, '浜名湖': 6,
    '蒲郡': 7, '常滑': 8, '津': 9, '三国': 10, 'びわこ': 11, '住之江': 12,
    '尼崎': 13, '鳴門': 14, '丸亀': 15, '児島': 16, '宮島': 17, '徳山': 18,
    '下関': 19, '若松': 20, '芦屋': 21, '福岡': 22, '唐津': 23, '大村': 24
}

def get_adjusted_date() -> date:
    """現在の日付を返す（JST）"""
    now_jst = datetime.now(JST)
    return date(now_jst.year, now_jst.month, now_jst.day)

# 戦略設定（v9.0: bias_1_3_2ndのみに変更）
STRATEGIES = {
    'bias_1_3_2nd': {
        'name': '3穴2nd戦略',
        'target_conditions': [
            # 回収率110%以上の条件（競艇場コード, R番号）
            ('11', 4),   # 琵琶湖 4R - 122.9%
            ('18', 10),  # 徳山 10R - 122.2%
            ('13', 4),   # 尼崎 4R - 116.4%
            ('18', 6),   # 徳山 6R - 114.9%
            ('05', 2),   # 多摩川 2R - 114.6%
            ('11', 2),   # 琵琶湖 2R - 114.5%
            ('24', 4),   # 大村 4R - 114.0%
            ('05', 4),   # 多摩川 4R - 113.5%
            ('11', 5),   # 琵琶湖 5R - 112.1%
            ('11', 9),   # 琵琶湖 9R - 112.0%
            ('18', 3),   # 徳山 3R - 111.9%
            ('05', 11),  # 多摩川 11R - 111.4%
            ('13', 6),   # 尼崎 6R - 111.0%
            ('05', 6),   # 多摩川 6R - 110.9%
            ('13', 1),   # 尼崎 1R - 110.5%
        ],
        'bet_type': 'auto',  # 2連単/2連複の高い方を自動選択
        'combination': '1-3',
        'min_odds': 3.0,
        'max_odds': 100.0,
        'bet_amount': 1000,
        'min_local_win_rate': 4.5,  # 1号艇の当地勝率下限
        'max_local_win_rate': 6.0,  # 1号艇の当地勝率上限
    }
}



# 購入金額設定
BASE_AMOUNT = 1000   # 基本金額
MIN_AMOUNT = 1000    # 最低金額
MAX_AMOUNT = 10000   # 最高金額


def calculate_bet_amount(strategy_type: str, odds: float, local_win_rate: float = None) -> int:
    """
    購入金額を計算（ケリー基準ベース）

    Args:
        strategy_type: 戦略タイプ
        odds: 最終オッズ
        local_win_rate: 当地勝率（3穴戦略のみ使用）

    Returns:
        購入金額（1,000〜10,000円、100円単位）
    """

    if strategy_type == 'tansho_kanto':
        # 関東4場単勝戦略: オッズベースの調整
        # 特性: 勝率47%、期待回収率129%
        if odds < 1.5:
            multiplier = 1.0  # 低オッズ: リターン小
        elif odds < 2.0:
            multiplier = 2.0  # 中低オッズ: バランス良い
        elif odds < 3.0:
            multiplier = 3.0  # 中オッズ: 期待値高い
        elif odds < 5.0:
            multiplier = 4.0  # 中高オッズ: 高リターン期待
        elif odds < 8.0:
            multiplier = 3.0  # 高オッズ: リスク軽減
        else:
            multiplier = 2.0  # 超高オッズ: リスク軽減

    elif strategy_type == 'bias_1_3':
        # 3穴戦略（論文準拠）: 当地勝率×オッズの調整
        # 特性: 勝率12%、期待回収率110-120%

        # 当地勝率による調整
        if local_win_rate is None:
            rate_multiplier = 1.0
        elif local_win_rate < 7.0:
            rate_multiplier = 1.0  # 条件ギリギリ
        elif local_win_rate < 7.5:
            rate_multiplier = 1.5  # 良好
        elif local_win_rate < 8.0:
            rate_multiplier = 2.0  # 優秀
        else:
            rate_multiplier = 2.5  # 非常に優秀

        # オッズによる調整
        if odds < 4.0:
            odds_multiplier = 1.5  # 低オッズ: 期待値高い
        elif odds < 8.0:
            odds_multiplier = 1.2  # 適正オッズ
        elif odds < 15.0:
            odds_multiplier = 1.0  # 中オッズ
        elif odds < 25.0:
            odds_multiplier = 0.8  # 高オッズ: リスク軽減
        else:
            odds_multiplier = 0.5  # 超高オッズ: 大幅リスク軽減

        multiplier = rate_multiplier * odds_multiplier

    elif strategy_type == 'bias_1_3_2nd':
        # 3穴2nd戦略: 当地勝率×オッズの調整
        # 特性: 勝率12%、期待回収率110%

        # 当地勝率による調整
        if local_win_rate is None:
            rate_multiplier = 1.0
        elif local_win_rate < 5.0:
            rate_multiplier = 1.0  # 条件ギリギリ
        elif local_win_rate < 5.5:
            rate_multiplier = 1.5  # 良好
        else:
            rate_multiplier = 2.0  # 優秀

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

    else:
        multiplier = 1.0

    # 最終金額を計算（100円単位に丸め）
    amount = int(BASE_AMOUNT * multiplier / 100) * 100

    # 上下限を適用
    return max(MIN_AMOUNT, min(MAX_AMOUNT, amount))


def get_db_connection():
    """データベース接続を取得"""
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not configured")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def collect_today_races() -> List[Dict[str, Any]]:
    """
    今日のレース情報を公式サイトから収集
    pyjpboatraceライブラリを使用
    """
    logger.info("=== レースデータ収集開始 ===")
    races = []
    target_date = datetime.now(JST)

    try:
        from pyjpboatrace import PyJPBoatrace
        boatrace = PyJPBoatrace()

        stadiums_info = boatrace.get_stadiums(d=target_date.date())
        if not stadiums_info:
            logger.info("開催中のレース情報はありませんでした。")
            return []

        for stadium_name, info in stadiums_info.items():
            # infoが辞書型でない場合（例: 'date'キー）、スキップ
            if not isinstance(info, dict):
                continue

            # statusが発売中でない場合はスキップ
            status = info.get("status", "")
            if "発売中" not in status:
                continue

            stadium_code = STADIUM_MAP.get(stadium_name)
            if not stadium_code:
                logger.warning(f"不明な競艇場名です: {stadium_name}")
                continue

            # 締切時刻を取得
            deadlines = get_race_deadlines(target_date, stadium_code)

            # この場は開催中、各レースの情報を取得
            for race_num in range(1, 13):
                races.append({
                    "race_date": target_date.date(),
                    "stadium_code": stadium_code,
                    "race_number": race_num,
                    "title": info.get("title", ""),
                    "deadline_at": deadlines.get(race_num),
                })

    except Exception as e:
        logger.error(f"レース情報取得中にエラーが発生しました: {e}", exc_info=True)

    logger.info(f"収集したレース数: {len(races)}")
    return races


def get_race_deadlines(target_date: datetime, stadium_code: int) -> Dict[int, datetime]:
    """公式サイトから各レースの締切時刻を取得"""
    deadlines = {}
    try:
        url = f'https://www.boatrace.jp/owpc/pc/race/raceindex?jcd={stadium_code:02d}&hd={target_date.strftime("%Y%m%d")}'
        response = requests.get(url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')

        # 各レースの行を探す
        race_rows = soup.select('table tr')
        for row in race_rows:
            cells = row.select('td')
            if len(cells) >= 2:
                race_text = cells[0].text.strip()
                time_text = cells[1].text.strip()

                # レース番号を抽出
                race_match = re.match(r'(\d+)R', race_text)
                if race_match:
                    race_num = int(race_match.group(1))
                    # 時刻を抽出
                    time_match = re.match(r'(\d{1,2}):(\d{2})', time_text)
                    if time_match:
                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2))
                        deadline = target_date.replace(
                            hour=hour, minute=minute, second=0, microsecond=0,
                            tzinfo=JST
                        )
                        deadlines[race_num] = deadline

        logger.info(f"場{stadium_code}: {len(deadlines)}件の締切時刻を取得")
    except Exception as e:
        logger.warning(f"締切時刻取得エラー (場:{stadium_code}): {e}")

    return deadlines


def save_races_to_db(races: List[Dict[str, Any]]) -> int:
    """レース情報をDBに保存"""
    if not races:
        return 0

    conn = get_db_connection()
    saved_count = 0

    try:
        with conn.cursor() as cur:
            # 既存のレースIDを先に取得
            race_keys = [(r['race_date'], r['stadium_code'], r['race_number']) for r in races]

            cur.execute(
                "SELECT id, race_date, stadium_code, race_number FROM races WHERE (race_date, stadium_code, race_number) IN %s",
                (tuple(race_keys),)
            )
            existing_races = {(row['race_date'], row['stadium_code'], row['race_number']): row['id'] for row in cur.fetchall()}

            # 新規レースと更新レースを分ける
            new_races = []
            races_to_update = []

            for race in races:
                key = (race['race_date'], race['stadium_code'], race['race_number'])
                if key in existing_races:
                    # 締切時刻があれば更新対象に追加
                    if race.get('deadline_at'):
                        races_to_update.append({
                            'id': existing_races[key],
                            'deadline_at': race['deadline_at']
                        })
                else:
                    new_races.append(race)

            # 既存レースの締切時刻を更新
            for race in races_to_update:
                cur.execute(
                    "UPDATE races SET deadline_at = %s WHERE id = %s AND deadline_at IS NULL",
                    (race['deadline_at'], race['id'])
                )

            # 新規レースを一括登録
            if new_races:
                insert_query = """
                    INSERT INTO races (race_date, stadium_code, race_number, title, deadline_at)
                    VALUES %s
                    ON CONFLICT (race_date, stadium_code, race_number) DO UPDATE
                    SET deadline_at = COALESCE(EXCLUDED.deadline_at, races.deadline_at)
                """
                values = [
                    (r['race_date'], r['stadium_code'], r['race_number'], r['title'], r['deadline_at'])
                    for r in new_races
                ]
                execute_values(cur, insert_query, values)
                saved_count = len(new_races)

            conn.commit()
            logger.info(f"レース保存完了: 新規{saved_count}件, 更新{len(races_to_update)}件")

    except Exception as e:
        logger.error(f"レース保存エラー: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

    return saved_count


def register_daily_bets():
    """
    毎朝8:00に実行: 今日の購入予定を登録

    【根本修正】レースデータ収集を先に行ってから購入予定を登録
    これにより、boatrace-daily-collectionとの実行順序に依存しなくなる
    """
    logger.info("=== 日次購入予定登録開始 ===")

    # ステップ1: レースデータを収集してDBに保存
    logger.info("ステップ1: レースデータ収集")
    races = collect_today_races()
    if races:
        save_races_to_db(races)
    else:
        logger.warning("レースデータが取得できませんでした")

    # ステップ2: 購入予定を登録
    logger.info("ステップ2: 購入予定登録")
    today = get_adjusted_date()

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 今日のレース一覧を取得（DBから）
            cur.execute("""
                SELECT r.id, r.race_date, r.stadium_code, r.race_number, r.deadline_at, s.name as stadium_name
                FROM races r
                JOIN stadiums s ON r.stadium_code = s.stadium_code
                WHERE r.race_date = %s AND r.is_canceled = FALSE
                ORDER BY r.deadline_at
            """, (today,))
            races = cur.fetchall()

            logger.info(f"今日のレース数: {len(races)}")

            if not races:
                logger.warning("今日のレースがありません")
                return

            # 既存の購入予定を取得
            cur.execute("""
                SELECT strategy_type, stadium_code, race_number
                FROM virtual_bets
                WHERE race_date = %s
            """, (today,))
            existing = set((r['strategy_type'], r['stadium_code'], r['race_number']) for r in cur.fetchall())

            # 一括登録用のデータを準備
            insert_data = []
            now_str = datetime.now(JST).isoformat()

            for race in races:
                race_number = race['race_number']
                stadium_code = str(race['stadium_code']).zfill(2)
                deadline_at = race['deadline_at']

                for strategy_type, config in STRATEGIES.items():
                    # tansho_kanto戦略の場合は特定の場×Rのみ
                    if strategy_type == 'tansho_kanto':
                        target_stadiums = config.get('target_stadiums', [])
                        if stadium_code not in target_stadiums:
                            continue
                        target_races_by_stadium = config.get('target_races_by_stadium', {})
                        target_races = target_races_by_stadium.get(stadium_code, [])
                        if race_number not in target_races:
                            continue
                    # bias_1_3_2nd戦略の場合は特別な条件チェック
                    elif strategy_type == 'bias_1_3_2nd':
                        target_conditions = config.get('target_conditions', [])
                        if (stadium_code, race_number) not in target_conditions:
                            continue
                    # bias_1_3戦略の場合は大村競艇場のみ（論文準拠）
                    elif strategy_type == 'bias_1_3':
                        target_stadium = config.get('target_stadium')
                        if target_stadium and stadium_code != target_stadium:
                            continue
                    else:
                        # 対象レースかチェック
                        target_races = config.get('target_races')
                        if target_races != 'all' and race_number not in target_races:
                            continue

                    # 既存チェック
                    if (strategy_type, stadium_code, race_number) in existing:
                        continue

                    # 組み合わせと購入タイプを決定
                    if strategy_type == 'tansho_kanto':
                        combination = '1'
                        bet_type = config['bet_type']
                    elif strategy_type == 'bias_1_3':
                        combination = '1-3'  # 論文に合わせて変更
                        bet_type = 'auto'  # 2連単/2連複の高い方を自動選択（論文の条件）
                    elif strategy_type == 'bias_1_3_2nd':
                        combination = '1-3'
                        bet_type = 'auto'  # 締切前に2連単/2連複の高い方を選択
                    else:
                        continue

                    insert_data.append((
                        strategy_type,
                        today,
                        stadium_code,
                        race_number,
                        bet_type,
                        combination,
                        config['bet_amount'],
                        deadline_at,
                        json.dumps({'strategy': config['name'], 'registered_at': now_str})
                    ))

            # 一括INSERT
            if insert_data:
                execute_values(cur, """
                    INSERT INTO virtual_bets (
                        strategy_type, race_date, stadium_code, race_number,
                        bet_type, combination, bet_amount, scheduled_deadline, reason
                    ) VALUES %s
                """, insert_data)

            conn.commit()
            logger.info(f"購入予定登録完了: {len(insert_data)}件")

    except Exception as e:
        logger.error(f"購入予定登録エラー: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def expire_overdue_bets():
    """
    締切が過ぎたpending状態の購入予定をexpiredに更新
    """
    logger.info("=== 期限切れ購入予定の処理開始 ===")

    # aware datetime(JST)で統一して比較
    now = datetime.now(JST)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 締切が過ぎたpendingの購入予定を取得してexpiredに更新
            cur.execute("""
                UPDATE virtual_bets
                SET status = 'expired',
                    reason = jsonb_set(
                        COALESCE(reason::jsonb, '{}'::jsonb),
                        '{expiredReason}',
                        '"\u7de0\u5207\u6642\u523b\u3092\u904e\u304e\u305f\u305f\u3081\u81ea\u52d5\u7121\u52b9\u5316"'::jsonb
                    ),
                    updated_at = NOW()
                WHERE status = 'pending'
                AND scheduled_deadline < %s
                RETURNING id, stadium_code, race_number, scheduled_deadline
            """, (now,))

            expired_bets = cur.fetchall()

            if expired_bets:
                logger.info(f"期限切れで無効化: {len(expired_bets)}件")
                for bet in expired_bets:
                    logger.info(f"  - bet_id={bet['id']}, {bet['stadium_code']} {bet['race_number']}R, 締切={bet['scheduled_deadline']}")
            else:
                logger.info("期限切れの購入予定はありません")

            conn.commit()
            return len(expired_bets)

    except Exception as e:
        logger.error(f"期限切れ処理エラー: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def process_deadline_bets():
    """
    締切1分前の購入判断処理
    """
    logger.info("=== 締切1分前の購入判断処理開始 ===")

    # まず、期限切れの購入予定を処理
    expire_overdue_bets()

    # aware datetime(JST)で統一して比較
    now = datetime.now(JST)
    # 締切1分前〜2分前のレースを対象
    deadline_start = now + timedelta(seconds=30)
    deadline_end = now + timedelta(minutes=2)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 対象の購入予定を取得
            cur.execute("""
                SELECT * FROM virtual_bets
                WHERE status = 'pending'
                AND scheduled_deadline BETWEEN %s AND %s
            """, (deadline_start, deadline_end))
            pending_bets = cur.fetchall()

            if not pending_bets:
                logger.info("処理対象の購入予定がありません")
                return

            logger.info(f"処理対象: {len(pending_bets)}件")

            for bet in pending_bets:
                try:
                    process_single_bet(cur, bet)
                except Exception as e:
                    logger.error(f"購入処理エラー: bet_id={bet['id']}, error={e}")

            conn.commit()

    except Exception as e:
        logger.error(f"購入判断処理エラー: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def process_single_bet(cur, bet: Dict):
    """単一の購入予定を処理"""
    bet_id = bet['id']
    strategy_type = bet['strategy_type']
    race_date = bet['race_date']
    stadium_code = bet['stadium_code']
    race_number = bet['race_number']
    combination = bet['combination']
    bet_type = bet['bet_type']

    config = STRATEGIES.get(strategy_type, {})

    logger.info(f"処理中: {stadium_code} {race_number}R {combination} ({strategy_type})")

    race_date_str = race_date.strftime('%Y-%m-%d') if hasattr(race_date, 'strftime') else str(race_date)
    race_date_yyyymmdd = race_date_str.replace('-', '')

    # bias_1_3戦略の場合は論文準拠の処理（当地勝率6.5以上、2連単/2連複の高い方）
    if strategy_type == 'bias_1_3':
        # 1号艇の当地勝率をチェック
        local_win_rate = get_boat1_local_win_rate(cur, race_date_yyyymmdd, stadium_code, race_number)

        if local_win_rate is None:
            skip_bet(cur, bet_id, "当地勝率取得失敗")
            return

        min_local_win_rate = config.get('min_local_win_rate', 6.5)

        if local_win_rate < min_local_win_rate:
            skip_bet(cur, bet_id, f"当地勝率が下限未満 ({local_win_rate:.1f} < {min_local_win_rate})")
            return

        # 2連単と2連複のオッズを取得し、高い方を選択（論文の条件）
        exacta_odds = get_odds(cur, race_date_str, stadium_code, race_number, '2t', '1-3')
        quinella_odds = get_odds(cur, race_date_str, stadium_code, race_number, '2f', '1-3')

        if exacta_odds is None and quinella_odds is None:
            skip_bet(cur, bet_id, "オッズ取得失敗")
            return

        # 高い方を選択
        if exacta_odds is not None and quinella_odds is not None:
            if exacta_odds >= quinella_odds:
                final_odds = exacta_odds
                selected_bet_type = 'exacta'
            else:
                final_odds = quinella_odds
                selected_bet_type = 'quinella'
        elif exacta_odds is not None:
            final_odds = exacta_odds
            selected_bet_type = 'exacta'
        else:
            final_odds = quinella_odds
            selected_bet_type = 'quinella'

        logger.info(f"3穴(論文準拠): 当地勝率={local_win_rate:.1f}, 2連単={exacta_odds}, 2連複={quinella_odds} -> {selected_bet_type}")

        # 購入確定（選択した購入タイプで更新、動的金額計算）
        confirm_bet_with_type(cur, bet_id, final_odds, selected_bet_type, local_win_rate, strategy_type)
        return

    # bias_1_3_2nd戦略の場合は特別な処理
    if strategy_type == 'bias_1_3_2nd':
        # 1号艇の当地勝率をチェック
        local_win_rate = get_boat1_local_win_rate(cur, race_date_yyyymmdd, stadium_code, race_number)

        if local_win_rate is None:
            skip_bet(cur, bet_id, "当地勝率取得失敗")
            return

        min_local_win_rate = config.get('min_local_win_rate', 4.5)
        max_local_win_rate = config.get('max_local_win_rate', 6.0)

        if local_win_rate < min_local_win_rate or local_win_rate >= max_local_win_rate:
            skip_bet(cur, bet_id, f"当地勝率が範囲外 ({local_win_rate:.1f} not in [{min_local_win_rate}, {max_local_win_rate}))")
            return

        # 2連単と2連複のオッズを取得し、高い方を選択
        exacta_odds = get_odds(cur, race_date_str, stadium_code, race_number, '2t', '1-3')
        quinella_odds = get_odds(cur, race_date_str, stadium_code, race_number, '2f', '1-3')

        if exacta_odds is None and quinella_odds is None:
            skip_bet(cur, bet_id, "オッズ取得失敗")
            return

        # 高い方を選択
        if exacta_odds is not None and quinella_odds is not None:
            if exacta_odds >= quinella_odds:
                final_odds = exacta_odds
                selected_bet_type = 'exacta'
            else:
                final_odds = quinella_odds
                selected_bet_type = 'quinella'
        elif exacta_odds is not None:
            final_odds = exacta_odds
            selected_bet_type = 'exacta'
        else:
            final_odds = quinella_odds
            selected_bet_type = 'quinella'

        logger.info(f"3穴2nd: 当地勝率={local_win_rate:.1f}, 2連単={exacta_odds}, 2連複={quinella_odds} -> {selected_bet_type}")

        # オッズ条件判定
        min_odds = config.get('min_odds', 3.0)
        max_odds = config.get('max_odds', 100.0)

        if final_odds < min_odds:
            skip_bet(cur, bet_id, f"オッズが低すぎる ({final_odds} < {min_odds})")
            return

        if final_odds > max_odds:
            skip_bet(cur, bet_id, f"オッズが高すぎる ({final_odds} > {max_odds})")
            return

        # 購入確定（選択した購入タイプで更新、動的金額計算）
        confirm_bet_with_type(cur, bet_id, final_odds, selected_bet_type, local_win_rate, strategy_type)
        return

    # 通常の戦略の処理
    # オッズタイプを変換
    odds_type_map = {'win': 'win', 'quinella': '2f', 'exacta': '2t'}
    odds_type = odds_type_map.get(bet_type, 'win')

    # 最新オッズを取得
    final_odds = get_odds(cur, race_date_str, stadium_code, race_number, odds_type, combination)

    if final_odds is None or final_odds == 0:
        skip_bet(cur, bet_id, "オッズ取得失敗")
        return

    # 条件判定
    min_odds = config.get('min_odds', 1.0)
    max_odds = config.get('max_odds', 100.0)

    if final_odds < min_odds:
        skip_bet(cur, bet_id, f"オッズが低すぎる ({final_odds} < {min_odds})")
        return

    if final_odds > max_odds:
        skip_bet(cur, bet_id, f"オッズが高すぎる ({final_odds} > {max_odds})")
        return

    # 購入確定（動的金額計算）
    confirm_bet(cur, bet_id, final_odds, strategy_type)


def get_odds(cur, race_date_str: str, stadium_code: str, race_number: int, odds_type: str, combination: str) -> Optional[float]:
    """オッズを取得"""
    cur.execute("""
        SELECT odds_value, odds_min, odds_max
        FROM odds_history
        WHERE race_date = %s AND stadium_code = %s AND race_number = %s
        AND odds_type = %s AND combination = %s
        ORDER BY scraped_at DESC
        LIMIT 1
    """, (race_date_str, stadium_code, race_number, odds_type, combination))

    odds_row = cur.fetchone()

    if not odds_row:
        return None

    odds_value = odds_row.get('odds_value')
    if odds_value:
        return float(odds_value)

    odds_min = odds_row.get('odds_min')
    if odds_min:
        return float(odds_min)

    return None


def get_boat1_local_win_rate(cur, race_date_yyyymmdd: str, stadium_code: str, race_number: int) -> Optional[float]:
    """
    1号艇の当地勝率を取得
    historical_programsテーブルから取得
    """
    # stadium_codeを2桁にパディング
    stadium_code_padded = str(stadium_code).zfill(2)
    race_no_padded = str(race_number).zfill(2)

    cur.execute("""
        SELECT local_win_rate
        FROM historical_programs
        WHERE race_date = %s AND stadium_code = %s AND race_no = %s AND boat_no = '1'
        LIMIT 1
    """, (race_date_yyyymmdd, stadium_code_padded, race_no_padded))

    row = cur.fetchone()

    if row and row.get('local_win_rate') is not None:
        return float(row['local_win_rate'])

    return None


def fetch_local_win_rate_from_web(race_date_yyyymmdd: str, stadium_code: str, race_number: int) -> Optional[float]:
    """
    公式サイトの出走表から1号艇の当地勝率を直接取得
    DBにデータがない場合のフォールバック用
    """
    try:
        url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={race_number}&jcd={stadium_code}&hd={race_date_yyyymmdd}"
        logger.info(f"Webサイトから当地勝率を取得: {url}")

        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            logger.warning(f"出走表ページ取得失敗: {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        # 1号艇のデータが入っているtbodyを取得
        tbodies = soup.find_all('tbody')
        if len(tbodies) < 2:
            return None

        tbody1 = tbodies[1] # 1号艇
        rows = tbody1.find_all('tr')
        if not rows:
            return None

        first_row = rows[0]
        tds = first_row.find_all('td')
        if len(tds) < 5:
            return None

        # 勝率が記載されているエリアから当地勝率を探す
        rate_text = ''
        for td in tds[4:]:
            rate_text += td.get_text(strip=True)

        # X.XX 形式の数値をすべて抽出
        rates = re.findall(r'\d\.\d{2}', rate_text)

        # 通常の順序: 全国勝率[0], 全国2連[1], 当地勝率[2], 当地2連[3]
        if len(rates) >= 3:
            local_win_rate = float(rates[2])
            logger.info(f"Webから当地勝率の取得に成功: {local_win_rate}")
            return local_win_rate

        return None

    except Exception as e:
        logger.error(f"Webからの当地勝率取得エラー: {e}")
        return None


def confirm_bet_with_type(cur, bet_id: int, final_odds: float, selected_bet_type: str, local_win_rate: float, strategy_type: str = None):
    """購入を確定（購入タイプも更新、動的金額計算）"""
    now = datetime.now(JST)

    # 購入金額を動的に計算
    if strategy_type:
        bet_amount = calculate_bet_amount(strategy_type, final_odds, local_win_rate)
    else:
        bet_amount = BASE_AMOUNT

    # reasonに当地勝率と選択した購入タイプを記録
    cur.execute("SELECT reason FROM virtual_bets WHERE id = %s", (bet_id,))
    row = cur.fetchone()

    current_reason = row['reason'] if row and row['reason'] else {}
    if isinstance(current_reason, str):
        try:
            current_reason = json.loads(current_reason)
        except:
            current_reason = {}

    current_reason['localWinRate'] = local_win_rate
    current_reason['selectedBetType'] = selected_bet_type
    current_reason['decision'] = 'confirmed'
    current_reason['calculatedBetAmount'] = bet_amount
    current_reason['amountReason'] = f"オッズ{final_odds:.1f}倍, 当地勝率{local_win_rate:.1f}"

    cur.execute("""
        UPDATE virtual_bets
        SET status = 'confirmed',
            bet_type = %s,
            odds = %s,
            bet_amount = %s,
            decision_time = %s,
            executed_at = %s,
            updated_at = %s,
            reason = %s
        WHERE id = %s
    """, (selected_bet_type, final_odds, bet_amount, now, now, now, json.dumps(current_reason, ensure_ascii=False), bet_id))

    logger.info(f"購入確定: bet_id={bet_id}, odds={final_odds}, type={selected_bet_type}, local_win_rate={local_win_rate}, amount={bet_amount}円")


def confirm_bet(cur, bet_id: int, final_odds: float, strategy_type: str = None):
    """購入を確定（動的金額計算）"""
    now = datetime.now(JST)

    # 購入金額を動的に計算
    if strategy_type:
        bet_amount = calculate_bet_amount(strategy_type, final_odds)
    else:
        bet_amount = BASE_AMOUNT

    # reasonに金額計算理由を記録
    cur.execute("SELECT reason FROM virtual_bets WHERE id = %s", (bet_id,))
    row = cur.fetchone()

    current_reason = row['reason'] if row and row['reason'] else {}
    if isinstance(current_reason, str):
        try:
            current_reason = json.loads(current_reason)
        except:
            current_reason = {}

    current_reason['decision'] = 'confirmed'
    current_reason['calculatedBetAmount'] = bet_amount
    current_reason['amountReason'] = f"オッズ{final_odds:.1f}倍"

    cur.execute("""
        UPDATE virtual_bets
        SET status = 'confirmed',
            odds = %s,
            bet_amount = %s,
            decision_time = %s,
            executed_at = %s,
            updated_at = %s,
            reason = %s
        WHERE id = %s
    """, (final_odds, bet_amount, now, now, now, json.dumps(current_reason, ensure_ascii=False), bet_id))

    logger.info(f"購入確定: bet_id={bet_id}, odds={final_odds}, amount={bet_amount}円")


def skip_bet(cur, bet_id: int, reason: str):
    """購入を見送り"""
    now = datetime.now(JST)

    # 現在の理由を取得して更新
    cur.execute("SELECT reason FROM virtual_bets WHERE id = %s", (bet_id,))
    row = cur.fetchone()

    current_reason = row['reason'] if row and row['reason'] else {}
    if isinstance(current_reason, str):
        try:
            current_reason = json.loads(current_reason)
        except:
            current_reason = {}

    current_reason['skipReason'] = reason
    current_reason['decision'] = 'skipped'

    cur.execute("""
        UPDATE virtual_bets
        SET status = 'skipped',
            reason = %s,
            decision_time = %s,
            updated_at = %s
        WHERE id = %s
    """, (json.dumps(current_reason, ensure_ascii=False), now, now, bet_id))

    logger.info(f"購入見送り: bet_id={bet_id}, reason={reason}")


def update_results():
    """
    結果を更新
    confirmed状態の購入で、レース結果が出ているものを更新
    """
    logger.info("=== 結果更新処理開始 ===")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 結果待ちの購入を取得
            cur.execute("""
                SELECT vb.*, r.id as race_id
                FROM virtual_bets vb
                JOIN races r ON vb.race_date = r.race_date
                    AND vb.stadium_code::int = r.stadium_code
                    AND vb.race_number = r.race_number
                WHERE vb.status = 'confirmed'
            """)
            confirmed_bets = cur.fetchall()

            if not confirmed_bets:
                logger.info("結果待ちの購入がありません")
                return

            logger.info(f"結果待ち: {len(confirmed_bets)}件")

            for bet in confirmed_bets:
                try:
                    update_single_result(cur, bet)
                except Exception as e:
                    logger.error(f"結果更新エラー: bet_id={bet['id']}, error={e}")

            conn.commit()

    except Exception as e:
        logger.error(f"結果更新処理エラー: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def update_single_result(cur, bet: Dict):
    """単一の購入結果を更新"""
    bet_id = bet['id']
    race_id = bet['race_id']
    bet_type = bet['bet_type']
    combination = bet['combination']
    bet_amount = bet['bet_amount']
    odds = float(bet['odds']) if bet['odds'] else 0
    strategy_type = bet['strategy_type']

    # レース結果を取得
    cur.execute("""
        SELECT first_place, second_place, third_place, race_status
        FROM race_results
        WHERE race_id = %s
    """, (race_id,))
    result = cur.fetchone()

    if not result:
        return  # まだ結果が出ていない

    if result['race_status'] and result['race_status'] != '成立':
        # レース不成立
        cur.execute("""
            UPDATE virtual_bets
            SET status = 'canceled',
                actual_result = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (result['race_status'], bet_id))
        logger.info(f"レース不成立: bet_id={bet_id}, status={result['race_status']}")
        return

    first = result['first_place']
    second = result['second_place']
    third = result['third_place']

    if not first or not second:
        return  # 結果が不完全

    actual_result = f"{first}-{second}-{third}" if third else f"{first}-{second}"

    # 的中判定
    is_hit = False
    if bet_type == 'win':
        is_hit = str(first) == combination
    elif bet_type == 'quinella':
        # 2連複: 順不同
        actual_pair = set([str(first), str(second)])
        bet_pair = set(combination.replace('-', '=').split('='))
        is_hit = actual_pair == bet_pair
    elif bet_type == 'exacta':
        # 2連単: 順番通り
        actual_exacta = f"{first}-{second}"
        is_hit = actual_exacta == combination

    # 払戻金を取得
    payoff = 0
    if is_hit:
        payoff_type_map = {'win': 'win', 'quinella': 'quinella', 'exacta': 'exacta'}
        payoff_type = payoff_type_map.get(bet_type, bet_type)

        cur.execute("""
            SELECT payoff FROM payoffs
            WHERE race_id = %s AND bet_type = %s AND combination = %s
        """, (race_id, payoff_type, combination))
        payoff_row = cur.fetchone()
        if payoff_row:
            payoff = payoff_row['payoff']

    # 損益計算
    return_amount = int(payoff * bet_amount / 100) if is_hit else 0
    profit = return_amount - bet_amount

    now = datetime.now(JST)
    status = 'won' if is_hit else 'lost'

    cur.execute("""
        UPDATE virtual_bets
        SET status = %s,
            actual_result = %s,
            payoff = %s,
            return_amount = %s,
            profit = %s,
            result_confirmed_at = %s,
            updated_at = %s
        WHERE id = %s
    """, (status, actual_result, payoff, return_amount, profit, now, now, bet_id))

    logger.info(f"結果更新: bet_id={bet_id}, status={status}, profit={profit}")

    # 資金を更新
    update_fund(cur, strategy_type, profit, is_hit, bet_amount, return_amount)


def update_fund(cur, strategy_type: str, profit: float, is_hit: bool, bet_amount: int, return_amount: int):
    """資金を更新"""
    cur.execute("""
        SELECT * FROM virtual_funds
        WHERE strategy_type = %s AND is_active = TRUE
        LIMIT 1
    """, (strategy_type,))
    fund = cur.fetchone()

    if not fund:
        logger.warning(f"アクティブな資金が見つかりません: {strategy_type}")
        return

    current_fund = float(fund['current_fund']) + profit
    total_profit = float(fund['total_profit']) + profit
    total_bets = fund['total_bets'] + 1
    total_hits = fund['total_hits'] + (1 if is_hit else 0)
    hit_rate = (total_hits / total_bets * 100) if total_bets > 0 else 0

    total_bet_amount = float(fund['total_bet_amount']) + bet_amount
    total_return_amount = float(fund['total_return_amount']) + return_amount
    return_rate = (total_return_amount / total_bet_amount * 100) if total_bet_amount > 0 else 0

    cur.execute("""
        UPDATE virtual_funds
        SET current_fund = %s,
            total_profit = %s,
            total_bets = %s,
            total_hits = %s,
            hit_rate = %s,
            total_bet_amount = %s,
            total_return_amount = %s,
            return_rate = %s,
            updated_at = NOW()
        WHERE id = %s
    """, (current_fund, total_profit, total_bets, total_hits, hit_rate,
          total_bet_amount, total_return_amount, return_rate, fund['id']))

    logger.info(f"資金更新: {strategy_type}, current={current_fund}, profit={profit}")


def update_skipped_results():
    """
    見送りレースの結果も更新（表示用）
    """
    logger.info("=== 見送りレース結果更新開始 ===")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 見送りで結果未設定の購入を取得
            cur.execute("""
                SELECT vb.*, r.id as race_id
                FROM virtual_bets vb
                JOIN races r ON vb.race_date = r.race_date
                    AND vb.stadium_code::int = r.stadium_code
                    AND vb.race_number = r.race_number
                WHERE vb.status = 'skipped'
                AND vb.actual_result IS NULL
            """)
            skipped_bets = cur.fetchall()

            if not skipped_bets:
                logger.info("更新対象の見送りレースがありません")
                return

            logger.info(f"見送りレース: {len(skipped_bets)}件")

            for bet in skipped_bets:
                race_id = bet['race_id']
                bet_id = bet['id']

                # レース結果を取得
                cur.execute("""
                    SELECT first_place, second_place, third_place, race_status
                    FROM race_results
                    WHERE race_id = %s
                """, (race_id,))
                result = cur.fetchone()

                if not result or not result['first_place']:
                    continue

                actual_result = f"{result['first_place']}-{result['second_place']}-{result['third_place']}"

                cur.execute("""
                    UPDATE virtual_bets
                    SET actual_result = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (actual_result, bet_id))

            conn.commit()
            logger.info("見送りレース結果更新完了")

    except Exception as e:
        logger.error(f"見送りレース結果更新エラー: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python auto_betting.py <command>")
        print("Commands: register, decide, result, skipped")
        sys.exit(1)

    command = sys.argv[1]

    if command == "register":
        register_daily_bets()
    elif command == "decide":
        process_deadline_bets()
    elif command == "expire":
        expire_overdue_bets()
    elif command == "result":
        update_results()
        update_skipped_results()
    elif command == "skipped":
        update_skipped_results()
    else:
        print(f"Unknown command: {command}")
        print("Commands: register, decide, expire, result, skipped")
        sys.exit(1)

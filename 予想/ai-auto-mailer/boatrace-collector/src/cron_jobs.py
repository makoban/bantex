"""
競艇データ収集システム - Cron Job エントリポイント
Renderのスケジュールジョブから呼び出されるスクリプトです。
"""

import os
import sys
import logging
from datetime import datetime, timedelta, timezone

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 日本時間
JST = timezone(timedelta(hours=9))

# 運用時間設定
OPERATION_START_HOUR = 8   # 8:00 JST
OPERATION_END_HOUR = 21    # 21:30 JST
OPERATION_END_MINUTE = 30


def is_within_operation_hours() -> bool:
    """
    運用時間内かどうかをチェック
    運用時間: 8:00〜21:30 JST
    """
    now_jst = datetime.now(JST)

    # 8:00前は運用時間外
    if now_jst.hour < OPERATION_START_HOUR:
        return False

    # 21:30以降は運用時間外
    if now_jst.hour > OPERATION_END_HOUR:
        return False
    if now_jst.hour == OPERATION_END_HOUR and now_jst.minute > OPERATION_END_MINUTE:
        return False

    return True


def get_database_url():
    """データベースURLを取得"""
    url = os.environ.get('DATABASE_URL')
    if not url:
        logger.error("DATABASE_URL環境変数が設定されていません")
        sys.exit(1)
    return url


def has_races_near_deadline(minutes: int = 2) -> bool:
    """
    締切N分以内のレースがあるかをチェック（軽量版）

    v9.2: DBからスケジュール取得に変更（公式サイトスクレイピング→SQLで高速化）

    Args:
        minutes: 締切まで何分以内のレースを対象とするか

    Returns:
        bool: 締切N分以内のレースがあればTrue
    """
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        database_url = get_database_url()
        now = datetime.now(JST)
        deadline_threshold = now + timedelta(minutes=minutes)

        conn = psycopg2.connect(database_url)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT stadium_code, race_number, deadline_at
                    FROM races
                    WHERE race_date = %s
                    AND deadline_at IS NOT NULL
                    AND deadline_at > %s
                    AND deadline_at <= %s
                    LIMIT 1
                """, (now.date(), now, deadline_threshold))
                race = cursor.fetchone()

                if race:
                    deadline = race['deadline_at']
                    if deadline.tzinfo is None:
                        deadline = deadline.replace(tzinfo=JST)
                    delta = (deadline - now).total_seconds() / 60
                    stadium_names = {'01': '桐生', '02': '戸田', '03': '江戸川', '04': '平和島', '05': '多摩川',
                                   '06': '浜名湖', '07': '蒲郡', '08': '常滑', '09': '津', '10': '三国',
                                   '11': '琵琶湖', '12': '住之江', '13': '尼崎', '14': '鳴門', '15': '丸亀',
                                   '16': '児島', '17': '宮島', '18': '徳山', '19': '下関', '20': '若松',
                                   '21': '芦屋', '22': '福岡', '23': '唐津', '24': '大村'}
                    stadium_code = f"{race['stadium_code']:02d}"
                    stadium_name = stadium_names.get(stadium_code, stadium_code)
                    logger.info(f"締切{delta:.1f}分前のレースあり: {stadium_name} {race['race_number']}R")
                    return True
                return False
        finally:
            conn.close()

    except Exception as e:
        logger.warning(f"レーススケジュール取得エラー（処理続行）: {e}")
        # エラー時は念のため処理を実行する
        return True


def has_races_after_deadline(minutes: int = 15) -> bool:
    """
    締切後N分以内のレースがあるかをチェック（結果収集用）

    DB接続せずに公式サイトのスケジュールから判断。
    従量課金を最小化するための早期終了チェック用。

    Args:
        minutes: 締切後何分以内のレースを対象とするか

    Returns:
        bool: 締切後N分以内のレースがあればTrue
    """
    try:
        from collect_odds import OddsCollector

        collector = OddsCollector()
        races = collector.get_today_race_schedule()

        if not races:
            return False

        now = datetime.now(JST)

        for race in races:
            deadline = race.get('deadline_time')
            if deadline:
                # タイムゾーンなしの場合はJSTを付与
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=JST)
                delta = (now - deadline).total_seconds() / 60  # 締切後なので逆
                # 締切後N分以内のレースがあればTrue（結果待ち）
                if 0 < delta <= minutes:
                    logger.info(f"締切後{delta:.1f}分のレースあり: {race.get('stadium_name', '')} {race.get('race_number', '')}R")
                    return True

        return False

    except Exception as e:
        logger.warning(f"レーススケジュール取得エラー（処理続行）: {e}")
        # エラー時は念のため処理を実行する
        return True

def job_daily_collection():
    """
    日次収集ジョブ
    毎朝8:00 JSTに実行。当日の全レース情報と初期オッズを収集。
    """
    from collector import run_daily_collection

    logger.info("=== 日次収集ジョブ開始 ===")
    database_url = get_database_url()

    try:
        run_daily_collection(database_url)
        logger.info("=== 日次収集ジョブ完了 ===")
    except Exception as e:
        logger.error(f"日次収集ジョブ失敗: {e}")
        sys.exit(1)


def fetch_today_programs(database_url: str):
    """
    当日の番組表（出走表）を公式サイトから取得してDBに保存

    1号艇の当地勝率を取得するために必要。
    bias_1_3_2nd戦略の購入判断で使用する。

    v9.3（2026/01/26）: 新規追加
    v9.4（2026/01/26）: HTMLパース修正（tbodyは選手ごとに分かれている）
    """
    import requests
    import re
    from bs4 import BeautifulSoup
    import psycopg2
    from psycopg2.extras import RealDictCursor

    logger.info("=== 当日番組表取得開始 ===")

    now = datetime.now(JST)
    today = now.strftime('%Y%m%d')

    # 本日開催の競艇場をDBから取得
    conn = psycopg2.connect(database_url)
    stadiums = []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT DISTINCT stadium_code
                FROM races
                WHERE race_date = %s
                ORDER BY stadium_code
            """, (now.date(),))
            stadiums = [f"{row['stadium_code']:02d}" for row in cursor.fetchall()]
    except Exception as e:
        logger.warning(f"開催場取得エラー: {e}")
    finally:
        conn.close()

    if not stadiums:
        logger.info("本日の開催場なし")
        return

    logger.info(f"開催場: {len(stadiums)}場")

    # 各場の番組表を取得
    total_saved = 0
    conn = psycopg2.connect(database_url)

    try:
        for stadium_code in stadiums:
            for race_no in range(1, 13):  # 1R〜12R
                try:
                    # 公式サイトから番組表を取得
                    url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={race_no}&jcd={stadium_code}&hd={today}"
                    response = requests.get(url, timeout=15)
                    if response.status_code != 200:
                        continue

                    soup = BeautifulSoup(response.text, 'html.parser')

                    # v9.4: 番組表のtbodyは選手ごとに分かれている（tbody[1]〜[6]が1〜6号艇）
                    tbodies = soup.find_all('tbody')
                    if len(tbodies) < 7:
                        continue

                    for boat_idx, tbody in enumerate(tbodies[1:7], start=1):  # tbody[1]〜[6]
                        rows = tbody.find_all('tr')
                        if not rows:
                            continue

                        first_row = rows[0]
                        tds = first_row.find_all('td')
                        if len(tds) < 5:
                            continue

                        # 艇番（1〜6）
                        boat_no = str(boat_idx)

                        # 登番を取得（リンクから）
                        racer_no = None
                        racer_link = None
                        for td in tds[1:4]:
                            link = td.find('a')
                            if link:
                                href = link.get('href', '')
                                match = re.search(r'toban=(\d{4})', href)
                                if match:
                                    racer_no = match.group(1)
                                    racer_link = link
                                    break

                        # 選手名
                        racer_name = racer_link.get_text(strip=True)[:10] if racer_link else None

                        # 勝率は複数のtdに分かれているか結合されている
                        # 全テキストからX.XX形式（1桁.2桁）を抽出
                        rate_text = ''
                        for td in tds[4:]:
                            rate_text += td.get_text(strip=True)

                        rates = re.findall(r'\d\.\d{2}', rate_text)

                        # 通常順序: 全国勝率, 全国2連, 当地勝率, 当地2連
                        national_win_rate = float(rates[0]) if len(rates) > 0 else None
                        national_2nd_rate = float(rates[1]) if len(rates) > 1 else None
                        local_win_rate = float(rates[2]) if len(rates) > 2 else None
                        local_2nd_rate = float(rates[3]) if len(rates) > 3 else None

                        # DBに保存
                        with conn.cursor() as cursor:
                            cursor.execute("""
                                INSERT INTO historical_programs
                                (race_date, stadium_code, race_no, boat_no, racer_no, racer_name,
                                 national_win_rate, national_2nd_rate, local_win_rate, local_2nd_rate)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (race_date, stadium_code, race_no, boat_no)
                                DO UPDATE SET
                                    racer_no = EXCLUDED.racer_no,
                                    racer_name = EXCLUDED.racer_name,
                                    national_win_rate = EXCLUDED.national_win_rate,
                                    national_2nd_rate = EXCLUDED.national_2nd_rate,
                                    local_win_rate = EXCLUDED.local_win_rate,
                                    local_2nd_rate = EXCLUDED.local_2nd_rate
                            """, (
                                today, stadium_code, f"{race_no:02d}", boat_no,
                                racer_no, racer_name,
                                national_win_rate, national_2nd_rate,
                                local_win_rate, local_2nd_rate
                            ))
                            total_saved += 1

                    conn.commit()

                except Exception as e:
                    logger.warning(f"番組表取得エラー ({stadium_code} {race_no}R): {e}")
                    continue

        logger.info(f"番組表保存完了: {total_saved}件")

    except Exception as e:
        logger.error(f"番組表取得処理エラー: {e}")
        conn.rollback()
    finally:
        conn.close()

    logger.info("=== 当日番組表取得完了 ===")


def job_odds_collection_regular():
    """
    定期オッズ収集ジョブ
    10分ごとに実行。未終了レースのオッズを収集。
    """
    from collector import run_odds_regular_collection

    logger.info("=== 定期オッズ収集ジョブ開始 ===")
    database_url = get_database_url()

    try:
        run_odds_regular_collection(database_url)
        logger.info("=== 定期オッズ収集ジョブ完了 ===")
    except Exception as e:
        logger.error(f"定期オッズ収集ジョブ失敗: {e}")
        sys.exit(1)


def job_odds_collection_high_freq():
    """
    高頻度オッズ収集ジョブ
    締切5分前のレースのオッズを10秒間隔で収集。

    仕様（確定）:
    - 3連単・3連複は使わない
    - 2連単・2連複・単勝・複勝のみ
    - 締切5分前から10秒間隔で収集
    - 通常は10分間隔
    - レース開催日のみ稼働（毎朝チェック）
    - 運用時間: 8:00〜21:30 JST
    """
    logger.info("=== 高頻度オッズ収集ジョブ開始 ===")

    # 運用時間チェック
    if not is_within_operation_hours():
        now_jst = datetime.now(JST)
        logger.info(f"運用時間外のためスキップ (現在: {now_jst.strftime('%H:%M')} JST, 運用時間: {OPERATION_START_HOUR}:00〜{OPERATION_END_HOUR}:{OPERATION_END_MINUTE:02d})")
        logger.info("=== 高頻度オッズ収集ジョブ完了 ===")
        return

    from collect_odds import OddsCollector

    database_url = get_database_url()

    try:
        collector = OddsCollector(database_url)
        # 締切5分以内のレースを取得し、9回（10秒×9=90秒）収集
        collector.collect_near_deadline_races(minutes_before=5, interval_seconds=10, iterations=9)
        logger.info("=== 高頻度オッズ収集ジョブ完了 ===")
    except Exception as e:
        logger.error(f"高頻度オッズ収集ジョブ失敗: {e}")
        sys.exit(1)


def job_result_collection():
    """
    結果収集ジョブ
    5分ごとに実行。終了したレースの結果と払戻金を収集。

    v9.0（2026/01/25）:
    - 締切後15分以内のレースがある場合のみ処理を実行
    - 対象レースがなければ早期終了（従量課金を最小化）

    追加機能（2026/01/19）:
    - 結果収集後にPostgreSQLのvirtual_betsを更新
    """
    logger.info("=== 結果収集ジョブ開始 (v9.1) ===")

    # 運用時間チェック
    if not is_within_operation_hours():
        # 運用時間外でも結果が確定するまでは収集を続ける
        pass

    # 早期チェック: 締切後15分以内のレースがあるか確認
    if not has_races_after_deadline(minutes=15):
        logger.info("締切後15分以内のレースがないためスキップ")
        logger.info("=== 結果収集ジョブ完了 ===")
        return

    from collector import run_result_collection

    database_url = get_database_url()

    try:
        # 今日の結果を収集
        target_date = datetime.now(JST)
        logger.info(f"結果収集対象日: {target_date.strftime('%Y-%m-%d')}")
        run_result_collection(database_url, target_date)

        # PostgreSQLのvirtual_betsを更新
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            conn = psycopg2.connect(database_url)
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # confirmedステータスで結果が確定しているレコードを取得
                    cur.execute("""
                        SELECT vb.id, vb.bet_type, vb.combination, vb.bet_amount,
                               vb.strategy_type,
                               rr.first_place, rr.second_place, rr.third_place,
                               r.id as race_id
                        FROM virtual_bets vb
                        JOIN races r ON vb.race_date = r.race_date
                            AND vb.stadium_code::int = r.stadium_code
                            AND vb.race_number = r.race_number
                        JOIN race_results rr ON r.id = rr.race_id
                        WHERE vb.status = 'confirmed'
                          AND rr.first_place IS NOT NULL
                    """)
                    confirmed_bets = cur.fetchall()

                    # 払戻金を一括取得
                    if confirmed_bets:
                        race_ids = [b['race_id'] for b in confirmed_bets]
                        cur.execute("""
                            SELECT race_id, bet_type, combination, payoff
                            FROM payoffs
                            WHERE race_id = ANY(%s)
                        """, (race_ids,))
                        bet_type_map = {
                            '2連複': 'quinella', '2連単': 'exacta',
                            '単勝': 'win', '複勝': 'place',
                        }
                        payoffs_map = {}
                        for p in cur.fetchall():
                            bt = p['bet_type']
                            bt_en = bet_type_map.get(bt, bt)
                            key = (p['race_id'], bt_en, p['combination'])
                            payoffs_map[key] = p['payoff']

                    updated_count = 0
                    for bet in confirmed_bets:
                        bet_type = bet['bet_type']
                        combination = bet['combination']
                        bet_amount = bet['bet_amount'] or 100
                        strategy_type = bet['strategy_type']

                        # 的中判定
                        is_hit = False
                        payoff = 0

                        if bet_type in ('quinella', 'auto'):
                            actual_pair = set([str(bet['first_place']), str(bet['second_place'])])
                            bet_pair = set(combination.replace('-', '=').split('='))
                            is_hit = actual_pair == bet_pair
                            if is_hit:
                                pair_list = sorted([str(bet['first_place']), str(bet['second_place'])])
                                payoff_comb = f"{pair_list[0]}={pair_list[1]}"
                                payoff = payoffs_map.get((bet['race_id'], 'quinella', payoff_comb), 0) or 0
                        elif bet_type == 'exacta':
                            actual_exacta = f"{bet['first_place']}-{bet['second_place']}"
                            is_hit = actual_exacta == combination
                            if is_hit:
                                payoff = payoffs_map.get((bet['race_id'], 'exacta', actual_exacta), 0) or 0
                        elif bet_type == 'win':
                            is_hit = str(bet['first_place']) == combination
                            if is_hit:
                                payoff = payoffs_map.get((bet['race_id'], 'win', str(bet['first_place'])), 0) or 0

                        # 払戻金と損益を計算
                        return_amount = int((payoff / 100) * bet_amount) if payoff else 0
                        profit = return_amount - bet_amount if is_hit else -bet_amount
                        new_status = 'won' if is_hit else 'lost'
                        actual_result = f"{bet['first_place']}-{bet['second_place']}-{bet['third_place']}"

                        # virtual_betsを更新
                        cur.execute("""
                            UPDATE virtual_bets
                            SET status = %s, actual_result = %s,
                                payoff = %s, return_amount = %s, profit = %s
                            WHERE id = %s
                        """, (new_status, actual_result, payoff if is_hit else 0,
                              return_amount, profit, bet['id']))

                        # virtual_fundsを更新
                        cur.execute("""
                            SELECT * FROM virtual_funds
                            WHERE strategy_type = %s AND is_active = TRUE
                            LIMIT 1
                        """, (strategy_type,))
                        fund = cur.fetchone()

                        if fund:
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
                            logger.info(f"資金更新: {strategy_type}, profit={profit}, current={current_fund}")

                        updated_count += 1

                    conn.commit()
                    logger.info(f"仮想購入結果更新完了: {updated_count}件")
            finally:
                conn.close()
        except Exception as e:
            logger.warning(f"仮想購入結果更新エラー（続行）: {e}")

        logger.info("=== 結果収集ジョブ完了 ===")
    except Exception as e:
        logger.error(f"結果収集ジョブ失敗: {e}")
        sys.exit(1)


def update_manus_virtual_bets(boatrace_db_url: str):
    """
    Manus Space DBのvirtualBetsを更新

    - confirmedステータスで結果未確定のレースを取得
    - 外部DBから結果を取得
    - 的中/不的中を判定してvirtualBetsを更新
    - 資金（virtualFunds）も更新
    """
    manus_db_url = os.environ.get('MANUS_DATABASE_URL')
    if not manus_db_url:
        logger.debug("MANUS_DATABASE_URL未設定、仮想購入結果更新をスキップ")
        return

    logger.info("=== Manus Space DB 仮想購入結果更新開始 ===")

    try:
        import pymysql
        from pymysql.cursors import DictCursor
        import psycopg2
        from psycopg2.extras import DictCursor as PgDictCursor
        import json
        import re

        # MySQL URL解析
        def parse_mysql_url(url: str) -> dict:
            pattern = r'mysql://([^:]+):([^@]+)@([^:/]+):?(\d+)?/([^?]+)(?:\?(.*))?'
            match = re.match(pattern, url)
            if not match:
                raise ValueError(f"Invalid MySQL URL: {url}")

            user, password, host, port, database, params = match.groups()

            config = {
                'host': host,
                'user': user,
                'password': password,
                'database': database,
                'port': int(port) if port else 4000,
                'charset': 'utf8mb4',
                'cursorclass': DictCursor,
            }

            if params and 'ssl' in params.lower():
                config['ssl'] = {'ssl': {}}

            return config

        # Manus Space DBに接続
        manus_config = parse_mysql_url(manus_db_url)
        manus_config['ssl'] = {'ssl': {}}
        manus_conn = pymysql.connect(**manus_config)

        # 外部DBに接続
        pg_conn = psycopg2.connect(boatrace_db_url)

        try:
            # confirmedステータスで結果未確定のレースを取得
            with manus_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM virtualBets
                    WHERE status = 'confirmed'
                    AND resultConfirmedAt IS NULL
                """)
                confirmed_bets = cursor.fetchall()

            if not confirmed_bets:
                logger.info("結果待ちの購入がありません")
                return

            logger.info(f"結果確認対象: {len(confirmed_bets)}件")

            for bet in confirmed_bets:
                try:
                    process_single_bet_result(bet, manus_conn, pg_conn)
                except Exception as e:
                    logger.error(f"結果処理エラー: bet_id={bet['id']}, error={e}")

        finally:
            manus_conn.close()
            pg_conn.close()

        logger.info("=== Manus Space DB 仮想購入結果更新完了 ===")

    except ImportError as e:
        logger.error(f"必要なモジュールがインストールされていません: {e}")
    except Exception as e:
        logger.error(f"Manus Space DB更新エラー: {e}")


def process_single_bet_result(bet: dict, manus_conn, pg_conn):
    """単一の購入結果を処理"""
    from psycopg2.extras import DictCursor as PgDictCursor
    import json

    bet_id = bet['id']
    strategy_type = bet['strategyType']
    race_date = bet['raceDate'].strftime('%Y%m%d') if hasattr(bet['raceDate'], 'strftime') else str(bet['raceDate']).replace('-', '')
    stadium_code = bet['stadiumCode']
    race_number = bet['raceNumber']
    combination = bet['combination']
    bet_type = bet['betType']
    bet_amount = float(bet['betAmount'])

    logger.info(f"結果確認: {stadium_code} {race_number}R {combination}")

    # 外部DBから結果を取得
    with pg_conn.cursor(cursor_factory=PgDictCursor) as cursor:
        # historical_race_resultsから結果を取得
        cursor.execute("""
            SELECT
                hrr.stadium_code,
                hrr.race_no::integer as race_number,
                hrr.race_date,
                MAX(CASE WHEN hrr.rank IN ('1', '01') THEN hrr.boat_no::integer END) as rank1,
                MAX(CASE WHEN hrr.rank IN ('2', '02') THEN hrr.boat_no::integer END) as rank2,
                MAX(CASE WHEN hrr.rank IN ('3', '03') THEN hrr.boat_no::integer END) as rank3
            FROM historical_race_results hrr
            WHERE hrr.stadium_code = %s
              AND hrr.race_no = %s
              AND hrr.race_date = %s
            GROUP BY hrr.stadium_code, hrr.race_no, hrr.race_date
        """, (stadium_code, str(race_number).zfill(2), race_date))
        result = cursor.fetchone()

        if not result:
            # race_resultsテーブルからも試す
            cursor.execute("""
                SELECT
                    rr.first_place as rank1,
                    rr.second_place as rank2,
                    rr.third_place as rank3
                FROM race_results rr
                JOIN races r ON rr.race_id = r.id
                WHERE r.stadium_code = %s
                  AND r.race_number = %s
                  AND r.race_date = %s
            """, (int(stadium_code), race_number, race_date.replace('/', '-') if '/' in race_date else f"{race_date[:4]}-{race_date[4:6]}-{race_date[6:8]}"))
            result = cursor.fetchone()

        if not result or not result['rank1']:
            logger.info(f"レース結果未確定: {stadium_code} {race_number}R")
            return

        # 的中判定
        actual_result = str(result['rank1'])
        is_hit = False
        payoff = 0

        if bet_type == 'win':
            # 単勝の場合
            is_hit = (combination == actual_result)
            if is_hit:
                # 払戻金を取得
                cursor.execute("""
                    SELECT payoff FROM payoffs p
                    JOIN races r ON p.race_id = r.id
                    WHERE r.stadium_code = %s
                      AND r.race_number = %s
                      AND r.race_date = %s
                      AND p.bet_type = 'win'
                """, (int(stadium_code), race_number, f"{race_date[:4]}-{race_date[4:6]}-{race_date[6:8]}"))
                payoff_row = cursor.fetchone()
                if payoff_row:
                    payoff = float(payoff_row['payoff'])

        elif bet_type == 'quinella':
            # 2連複の場合
            result_combo = f"{min(result['rank1'], result['rank2'])}-{max(result['rank1'], result['rank2'])}"
            actual_result = result_combo
            is_hit = (combination == result_combo)
            if is_hit:
                cursor.execute("""
                    SELECT payoff FROM payoffs p
                    JOIN races r ON p.race_id = r.id
                    WHERE r.stadium_code = %s
                      AND r.race_number = %s
                      AND r.race_date = %s
                      AND p.bet_type = 'quinella'
                      AND p.combination = %s
                """, (int(stadium_code), race_number, f"{race_date[:4]}-{race_date[4:6]}-{race_date[6:8]}", combination))
                payoff_row = cursor.fetchone()
                if payoff_row:
                    payoff = float(payoff_row['payoff'])

        elif bet_type == 'exacta':
            # 2連単の場合
            result_combo = f"{result['rank1']}-{result['rank2']}"
            actual_result = result_combo
            is_hit = (combination == result_combo)
            if is_hit:
                cursor.execute("""
                    SELECT payoff FROM payoffs p
                    JOIN races r ON p.race_id = r.id
                    WHERE r.stadium_code = %s
                      AND r.race_number = %s
                      AND r.race_date = %s
                      AND p.bet_type = 'exacta'
                      AND p.combination = %s
                """, (int(stadium_code), race_number, f"{race_date[:4]}-{race_date[4:6]}-{race_date[6:8]}", combination))
                payoff_row = cursor.fetchone()
                if payoff_row:
                    payoff = float(payoff_row['payoff'])

    # 回収額と損益を計算
    return_amount = (payoff / 100 * bet_amount) if is_hit else 0
    profit = return_amount - bet_amount

    # Manus Space DBを更新
    now = datetime.now(JST)
    status = 'won' if is_hit else 'lost'

    with manus_conn.cursor() as cursor:
        # virtualBetsを更新
        cursor.execute("""
            UPDATE virtualBets
            SET status = %s,
                actualResult = %s,
                payoff = %s,
                returnAmount = %s,
                profit = %s,
                resultConfirmedAt = %s,
                updatedAt = %s
            WHERE id = %s
        """, (status, actual_result, payoff, return_amount, profit, now, now, bet_id))

        # virtualFundsを更新
        cursor.execute("""
            SELECT * FROM virtualFunds
            WHERE strategyType = %s AND isActive = 1
            LIMIT 1
        """, (strategy_type,))
        fund = cursor.fetchone()

        if fund:
            current_fund = float(fund['currentFund']) + profit
            total_profit = float(fund['totalProfit']) + profit
            total_bets = fund['totalBets'] + 1
            total_hits = fund['totalHits'] + (1 if is_hit else 0)
            hit_rate = (total_hits / total_bets * 100) if total_bets > 0 else 0

            total_bet_amount = float(fund['totalBetAmount']) + bet_amount
            total_return_amount = float(fund['totalReturnAmount']) + return_amount
            return_rate = (total_return_amount / total_bet_amount * 100) if total_bet_amount > 0 else 0

            cursor.execute("""
                UPDATE virtualFunds
                SET currentFund = %s,
                    totalProfit = %s,
                    totalBets = %s,
                    totalHits = %s,
                    hitRate = %s,
                    totalBetAmount = %s,
                    totalReturnAmount = %s,
                    returnRate = %s,
                    updatedAt = %s
                WHERE id = %s
            """, (current_fund, total_profit, total_bets, total_hits, hit_rate,
                  total_bet_amount, total_return_amount, return_rate, now, fund['id']))

        manus_conn.commit()

    logger.info(f"結果更新完了: bet_id={bet_id}, status={status}, profit={profit}")


def job_betting_process():
    """
    オッズ収集+購入判断ジョブ
    1分ごとに実行。

    v9.0（2026/01/25）:
    - 締切10分以内のレースがあればオッズ収集
    - 締切2分以内のレースがあれば購入判断
    - どちらもなければ早期終了（従量課金を最小化）

    処理内容:
    1. 締切10分以内のレースのオッズを収集
    2. 締切2分以内のpendingレースの購入判断
    3. 締切超過のpendingレースをskippedに更新
    """
    logger.info("=== オッズ収集+購入判断ジョブ開始 (v9.1) ===")

    # 運用時間チェック
    if not is_within_operation_hours():
        now_jst = datetime.now(JST)
        logger.info(f"運用時間外のためスキップ (現在: {now_jst.strftime('%H:%M')} JST)")
        logger.info("=== オッズ収集+購入判断ジョブ完了 ===")
        return

    # 早期チェック: 締切5分以内のレースがあるか確認
    # v9.2: オッズ収集と購入判断の両方で5分以内をチェック
    has_odds_target = has_races_near_deadline(minutes=5)
    # v9.3: 締切超過対策により3分前に拡大
    has_betting_target = has_races_near_deadline(minutes=3)

    if not has_odds_target and not has_betting_target:
        logger.info("締切10分以内のレースがないためスキップ")
        logger.info("=== オッズ収集+購入判断ジョブ完了 ===")
        return

    database_url = get_database_url()

    try:
        # Step 1: オッズ収集（締切5分以内のレース）
        # v9.2: DBからスケジュール取得に変更（公式サイト24場スクレイピング→SQLで数秒）
        if has_odds_target:
            logger.info("--- オッズ収集 ---")
            try:
                from collect_odds import OddsCollector
                import psycopg2
                from psycopg2.extras import RealDictCursor

                collector = OddsCollector(database_url)
                now = datetime.now(JST)
                deadline_threshold = now + timedelta(minutes=5)  # 締切5分以内

                # DBからスケジュール取得（高速化）
                conn = psycopg2.connect(database_url)
                try:
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute("""
                            SELECT stadium_code, race_number, deadline_at, race_date
                            FROM races
                            WHERE race_date = %s
                            AND deadline_at IS NOT NULL
                            AND deadline_at > %s
                            AND deadline_at <= %s
                            ORDER BY deadline_at
                        """, (now.date(), now, deadline_threshold))
                        races = cursor.fetchall()

                    logger.info(f"締切5分以内のレース: {len(races)}件")

                    collected_count = 0
                    odds_conn = None

                    for race in races:
                        stadium_code = f"{race['stadium_code']:02d}"
                        race_number = race['race_number']
                        race_date = race['race_date'].strftime('%Y%m%d') if hasattr(race['race_date'], 'strftime') else str(race['race_date']).replace('-', '')
                        deadline = race['deadline_at']
                        if deadline.tzinfo is None:
                            deadline = deadline.replace(tzinfo=JST)
                        delta = (deadline - now).total_seconds() / 60

                        if odds_conn is None:
                            odds_conn = collector.get_db_connection()
                            collector.create_odds_table(odds_conn)

                        # リアルタイムでオッズ取得（公式サイトから）
                        odds_list = collector.fetch_all_odds(stadium_code, race_number, race_date)

                        if odds_list:
                            collector.save_odds(odds_conn, race_date, stadium_code, race_number, odds_list, int(delta))
                            collected_count += len(odds_list)
                            # 場名を取得
                            stadium_names = {'01': '桐生', '02': '戸田', '03': '江戸川', '04': '平和島', '05': '多摩川',
                                           '06': '浜名湖', '07': '蒲郡', '08': '常滑', '09': '津', '10': '三国',
                                           '11': '琵琶湖', '12': '住之江', '13': '尼崎', '14': '鳴門', '15': '丸亀',
                                           '16': '児島', '17': '宮島', '18': '徳山', '19': '下関', '20': '若松',
                                           '21': '芦屋', '22': '福岡', '23': '唐津', '24': '大村'}
                            stadium_name = stadium_names.get(stadium_code, stadium_code)
                            logger.info(f"  {stadium_name} {race_number}R: {len(odds_list)}件収集")

                    if odds_conn:
                        odds_conn.close()
                finally:
                    conn.close()

                logger.info(f"オッズ収集完了: {collected_count}件")

                # Step 1.5: 直前AI予想生成（締切15-5分前のレース）
                # v9.5: 直前のデータを使った予想生成
                try:
                    from ai_prediction_batch import predict_single_race

                    # 締切15-5分前のレースを取得
                    ai_conn = psycopg2.connect(database_url)
                    try:
                        with ai_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                            now_for_ai = datetime.now(JST)
                            ai_min_threshold = now_for_ai + timedelta(minutes=5)
                            ai_max_threshold = now_for_ai + timedelta(minutes=15)

                            cursor.execute("""
                                SELECT stadium_code, race_number, deadline_at, race_date
                                FROM races
                                WHERE race_date = %s
                                AND deadline_at IS NOT NULL
                                AND deadline_at > %s
                                AND deadline_at <= %s
                                ORDER BY deadline_at
                            """, (now_for_ai.date(), ai_min_threshold, ai_max_threshold))
                            ai_races = cursor.fetchall()

                        if ai_races:
                            logger.info(f"--- 直前AI予想 (締切15-5分前) ---")
                            ai_count = 0
                            for race in ai_races:
                                stadium_code = f"{race['stadium_code']:02d}"
                                race_number = race['race_number']
                                race_date_str = race['race_date'].strftime('%Y%m%d') if hasattr(race['race_date'], 'strftime') else str(race['race_date']).replace('-', '')

                                result = predict_single_race(database_url, race_date_str, stadium_code, race_number)
                                if result:
                                    ai_count += 1

                            logger.info(f"AI予想生成完了: {ai_count}件")
                    finally:
                        ai_conn.close()

                except ImportError as e:
                    logger.warning(f"AI予想モジュール読み込みエラー（スキップ）: {e}")
                except Exception as e:
                    logger.warning(f"AI予想生成エラー（続行）: {e}")

            except Exception as e:
                logger.warning(f"オッズ収集エラー（続行）: {e}")

        # Step 2: 購入判断（締切3分以内のレース）
        if has_betting_target:
            logger.info("--- 購入判断 ---")
            from virtual_betting import VirtualBettingManager
            manager = VirtualBettingManager(database_url)

            # 締切2分前のレースの購入判断を実行
            manager.process_deadline_bets()

            # 締切超過のレースを見送りに更新
            expired_count = manager.expire_overdue_bets()
            logger.info(f"締切超過で見送り: {expired_count}件")

        logger.info("=== オッズ収集+購入判断ジョブ完了 ===")

    except Exception as e:
        logger.error(f"オッズ収集+購入判断ジョブ失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def job_test():
    """
    テストジョブ
    デプロイ確認用。DB接続をテストして終了。
    """
    import psycopg2

    logger.info("=== テストジョブ開始 ===")
    database_url = get_database_url()

    try:
        conn = psycopg2.connect(database_url)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stadiums")
            count = cur.fetchone()[0]
            logger.info(f"stadiumsテーブルのレコード数: {count}")

            cur.execute("SELECT NOW()")
            db_time = cur.fetchone()[0]
            logger.info(f"データベース時刻: {db_time}")

        conn.close()
        logger.info("=== テストジョブ完了: DB接続成功 ===")
    except Exception as e:
        logger.error(f"テストジョブ失敗: {e}")
        sys.exit(1)


def job_daily_batch():
    """
    統合日次バッチジョブ
    毎朝6:00 JSTに実行。

    処理内容（順番に実行）:
    1. 前日結果LZHインポート（公式サイトからLZHファイル取得）
    2. 過去データ一括インポート（未取得月のみ）
    3. 当日レース情報収集
    4. 購入予定登録

    v9.0（2026/01/25）: 3つの日次バッチを統合
    """
    logger.info("=" * 60)
    logger.info("=== 統合日次バッチ開始 (v9.1) ===")
    logger.info("=" * 60)

    database_url = get_database_url()

    # Step 1: 前日結果LZHインポート
    logger.info("")
    logger.info("--- Step 1/4: 前日結果LZHインポート ---")
    try:
        import subprocess
        result = subprocess.run(
            ['python', 'import_historical_data.py', 'yesterday'],
            capture_output=True,
            text=True,
            timeout=600  # 10分タイムアウト
        )
        if result.returncode == 0:
            logger.info("前日結果LZHインポート完了")
        else:
            logger.warning(f"前日結果LZHインポート警告: {result.stderr}")
    except Exception as e:
        logger.warning(f"前日結果LZHインポートエラー（続行）: {e}")

    # Step 2: 過去データ一括インポート
    logger.info("")
    logger.info("--- Step 2/4: 過去データ一括インポート ---")
    try:
        import subprocess
        result = subprocess.run(
            ['python', 'import_historical_data.py', 'all'],
            capture_output=True,
            text=True,
            timeout=1800  # 30分タイムアウト
        )
        if result.returncode == 0:
            logger.info("過去データ一括インポート完了")
        else:
            logger.warning(f"過去データ一括インポート警告: {result.stderr}")
    except Exception as e:
        logger.warning(f"過去データ一括インポートエラー（続行）: {e}")

    # Step 3: 当日レース情報収集
    logger.info("")
    logger.info("--- Step 3/5: 当日レース情報収集 ---")
    try:
        from collector import run_daily_collection
        run_daily_collection(database_url)
        logger.info("当日レース情報収集完了")
    except Exception as e:
        logger.warning(f"当日レース情報収集エラー（続行）: {e}")

    # Step 4: 当日番組表取得（1号艇の当地勝率を取得するために必要）
    logger.info("")
    logger.info("--- Step 4/5: 当日番組表取得 ---")
    try:
        fetch_today_programs(database_url)
        logger.info("当日番組表取得完了")
    except Exception as e:
        logger.warning(f"当日番組表取得エラー（続行）: {e}")

    # Step 5: 購入予定登録
    logger.info("")
    logger.info("--- Step 5/5: 購入予定登録 ---")
    try:
        # auto_betting.pyのregister_daily_betsを直接インポートして実行
        # ただしboatrace-dashboardにあるので、virtual_bettingのregister機能を使う
        from virtual_betting import VirtualBettingManager
        manager = VirtualBettingManager(database_url)
        manager.register_daily_bets()
        logger.info("購入予定登録完了")
    except ImportError:
        logger.warning("購入予定登録: virtual_bettingモジュールにregister機能なし（スキップ）")
    except Exception as e:
        logger.warning(f"購入予定登録エラー（続行）: {e}")

    logger.info("")
    logger.info("=" * 60)
    logger.info("=== 統合日次バッチ完了 ===")
    logger.info("=" * 60)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python cron_jobs.py <job_name>")
        print("Available jobs: daily_batch, betting, result, daily, odds_regular, test")
        sys.exit(1)

    job_name = sys.argv[1]

    jobs = {
        # 新しい統合バッチ（推奨）
        'daily_batch': job_daily_batch,      # 毎朝6時: LZH+過去データ+レース情報+購入予定
        'betting': job_betting_process,       # 毎分: オッズ収集+購入判断
        # レガシー（後方互換性のため残す）
        'daily': job_daily_collection,
        'odds_regular': job_odds_collection_regular,
        'odds_high_freq': job_odds_collection_high_freq,
        'result': job_result_collection,
        'test': job_test,
    }

    if job_name not in jobs:
        logger.error(f"不明なジョブ名: {job_name}")
        print(f"Available jobs: {', '.join(jobs.keys())}")
        sys.exit(1)

    jobs[job_name]()

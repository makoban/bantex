"""
競艇オッズ高頻度収集Worker

常時起動のBackground Workerとして動作し、APSchedulerを使用して
締切直前のレースのオッズを収集します。

実装仕様:
- 締切60秒前から60秒間隔で収集
- 通常時は10分間隔で全レースのオッズを収集
- 運用時間: 8:00〜21:30 JST

修正（2026/01/24 v8.8）:
- オッズ取得間隔を30秒から60秒に変更（負荷軽減）
- 仮想購入処理をboatrace-betting-process Cron Jobに移行
"""

import os
import sys
import time
import logging
import signal
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 日本時間
JST = timezone(timedelta(hours=9))

# 運用時間設定
OPERATION_START_HOUR = 8
OPERATION_END_HOUR = 21
OPERATION_END_MINUTE = 30

# 高頻度収集設定
HIGH_FREQ_SECONDS_BEFORE = 60  # 締切60秒前から高頻度収集開始
HIGH_FREQ_INTERVAL = 60  # 60秒間隔（負荷軽減のため増加）
NORMAL_INTERVAL_MINUTES = 10  # 通常は10分間隔

# 結果収集設定
RESULT_COLLECTION_INTERVAL_MINUTES = 5  # 5分間隔で結果収集

# 注意: 仮想購入処理は boatrace-betting-process Cron Job で1分ごとに実行

# グローバル変数
scheduler = None
running = True


def is_within_operation_hours() -> bool:
    """運用時間内かどうかをチェック"""
    now_jst = datetime.now(JST)

    if now_jst.hour < OPERATION_START_HOUR:
        return False

    if now_jst.hour > OPERATION_END_HOUR:
        return False
    if now_jst.hour == OPERATION_END_HOUR and now_jst.minute > OPERATION_END_MINUTE:
        return False

    return True


def get_database_url() -> Optional[str]:
    """
    データベースURLを取得

    Returns:
        str: データベースURL、未設定の場合はNone
    """
    url = os.environ.get('DATABASE_URL')
    if not url:
        logger.warning("DATABASE_URL環境変数が設定されていません。ジョブをスキップします。")
        return None
    return url


def collect_high_frequency_odds():
    """
    締切直前のレースのオッズを高頻度で収集
    この関数は5秒ごとに呼び出される
    """
    if not is_within_operation_hours():
        return

    try:
        database_url = get_database_url()
        if not database_url:
            return  # 環境変数未設定の場合はスキップ

        from collect_odds import OddsCollector

        collector = OddsCollector(database_url)

        # 本日のレーススケジュールを取得
        races = collector.get_today_race_schedule()
        if not races:
            return

        now = datetime.now(JST)

        # 締切30秒以内のレースを探す
        for race in races:
            deadline = race.get('deadline_time')
            if not deadline:
                continue

            delta = (deadline - now).total_seconds()

            # 締切30秒以内かつ締切前のレース
            if 0 < delta <= HIGH_FREQ_SECONDS_BEFORE:
                logger.info(f"高頻度収集: {race['stadium_name']} {race['race_number']}R (残り{delta:.0f}秒)")

                # オッズを取得して保存
                conn = collector.get_db_connection()
                collector.create_odds_table(conn)

                odds_list = collector.fetch_all_odds(
                    race['stadium_code'],
                    race['race_number'],
                    race['date']
                )

                if odds_list:
                    minutes_to_deadline = int(delta / 60)
                    collector.save_odds(
                        conn, race['date'],
                        race['stadium_code'],
                        race['race_number'],
                        odds_list,
                        minutes_to_deadline
                    )
                    logger.info(f"  -> {len(odds_list)}件保存")

                conn.close()

    except Exception as e:
        logger.error(f"高頻度収集エラー: {e}", exc_info=True)


def collect_regular_odds():
    """
    通常のオッズ収集（10分間隔）
    全ての未終了レースのオッズを収集
    """
    if not is_within_operation_hours():
        logger.info("運用時間外のためスキップ")
        return

    try:
        database_url = get_database_url()
        if not database_url:
            return  # 環境変数未設定の場合はスキップ

        from collect_odds import OddsCollector

        collector = OddsCollector(database_url)

        logger.info("=== 定期オッズ収集開始 ===")

        # 本日のレーススケジュールを取得
        races = collector.get_today_race_schedule()
        if not races:
            logger.info("本日のレースがありません")
            return

        now = datetime.now(JST)
        conn = collector.get_db_connection()
        collector.create_odds_table(conn)

        collected_count = 0

        for race in races:
            deadline = race.get('deadline_time')
            if not deadline:
                continue

            # 締切前のレースのみ
            if now > deadline:
                continue

            # 締切30秒以内は高頻度収集に任せる
            delta = (deadline - now).total_seconds()
            if delta <= HIGH_FREQ_SECONDS_BEFORE:
                continue

            # オッズを取得して保存
            odds_list = collector.fetch_all_odds(
                race['stadium_code'],
                race['race_number'],
                race['date']
            )

            if odds_list:
                minutes_to_deadline = int(delta / 60)
                collector.save_odds(
                    conn, race['date'],
                    race['stadium_code'],
                    race['race_number'],
                    odds_list,
                    minutes_to_deadline
                )
                collected_count += len(odds_list)

        conn.close()
        logger.info(f"=== 定期オッズ収集完了: {collected_count}件 ===")

    except Exception as e:
        logger.error(f"定期オッズ収集エラー: {e}", exc_info=True)


def collect_race_results_job():
    """
    レース結果収集ジョブ
    5分ごとに実行され、終了したレースの結果と払戻金を収集
    結果はhistorical_race_resultsとhistorical_payoffsテーブルにも保存
    """
    if not is_within_operation_hours():
        return

    try:
        database_url = get_database_url()
        if not database_url:
            return

        from collector import run_result_collection
        from datetime import datetime

        logger.info("=== レース結果収集開始 ===")

        # 今日の結果を収集
        now_jst = datetime.now(JST)
        run_result_collection(database_url, now_jst)

        # 履歴テーブルにも保存
        save_results_to_historical(database_url, now_jst)

        logger.info("=== レース結果収集完了 ===")

    except Exception as e:
        logger.error(f"レース結果収集エラー: {e}", exc_info=True)


def save_results_to_historical(database_url: str, target_date):
    """
    当日の結果をhistorical_race_resultsとhistorical_payoffsテーブルにも保存
    """
    import psycopg2

    try:
        conn = psycopg2.connect(database_url)

        # historical_race_resultsテーブルが存在するか確認
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'historical_race_results'
                )
            """)
            if not cur.fetchone()[0]:
                logger.info("historical_race_resultsテーブルが存在しません。スキップします。")
                conn.close()
                return

        # race_resultsから今日の結果を取得してhistorical_race_resultsに保存
        date_str = target_date.strftime('%Y%m%d')

        with conn.cursor() as cur:
            # race_resultsテーブルから結果を取得
            cur.execute("""
                SELECT r.race_date, r.stadium_code, r.race_number, r.id as race_id,
                       rr.first_place, rr.second_place, rr.third_place,
                       rr.fourth_place, rr.fifth_place, rr.sixth_place
                FROM races r
                JOIN race_results rr ON r.id = rr.race_id
                WHERE r.race_date = %s::date
                AND rr.first_place IS NOT NULL
            """, (target_date.strftime('%Y-%m-%d'),))

            results = cur.fetchall()

            if not results:
                logger.info("保存対象の結果がありません")
                conn.close()
                return

            saved_count = 0
            payoff_count = 0

            # 払戻金の種別マッピング
            bet_type_map = {
                '単勝': '単勝',
                '複勝': '複勝',
                '2連単': '2連単',
                '2連複': '2連複',
                'ワイド': 'ワイド',
                '3連単': '3連単',
                '3連複': '3連複'
            }

            for row in results:
                race_date, stadium_code, race_number, race_id, first, second, third, fourth, fifth, sixth = row

                # historical_race_resultsに保存（艇番ごとに1レコード）
                places = [
                    (first, '01'), (second, '02'), (third, '03'),
                    (fourth, '04'), (fifth, '05'), (sixth, '06')
                ]

                for boat_no, rank in places:
                    if boat_no:
                        cur.execute("""
                            INSERT INTO historical_race_results
                            (race_date, stadium_code, race_no, boat_no, rank)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (race_date, stadium_code, race_no, boat_no) DO UPDATE SET
                                rank = EXCLUDED.rank
                        """, (date_str, f"{stadium_code:02d}", f"{race_number:02d}", str(boat_no), rank))
                        saved_count += 1

                # payoffsテーブルから払戻金データを取得してhistorical_payoffsに保存
                cur.execute("""
                    SELECT bet_type, combination, payoff, popularity
                    FROM payoffs
                    WHERE race_id = %s
                """, (race_id,))
                payoffs = cur.fetchall()

                for payoff_row in payoffs:
                    bet_type, combination, payoff, popularity = payoff_row

                    # bet_typeを日本語に変換
                    jp_bet_type = bet_type_map.get(bet_type, bet_type)

                    cur.execute("""
                        INSERT INTO historical_payoffs
                        (race_date, stadium_code, race_no, bet_type, combination, payout, popularity)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (race_date, stadium_code, race_no, bet_type, combination) DO UPDATE SET
                            payout = EXCLUDED.payout,
                            popularity = EXCLUDED.popularity
                    """, (date_str, f"{stadium_code:02d}", f"{race_number:02d}", jp_bet_type, combination, payoff, popularity))
                    payoff_count += 1

            conn.commit()
            logger.info(f"履歴テーブルに保存: 結果{saved_count}件, 払戻金{payoff_count}件")

    except Exception as e:
        logger.error(f"履歴テーブル保存エラー: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


# 仮想購入処理は boatrace-betting-process Cron Job に移行しました
# cron_jobs.py の job_betting_process() を使用


def signal_handler(signum, frame):
    """シグナルハンドラ"""
    global running
    logger.info(f"シグナル {signum} を受信しました。シャットダウンします...")
    running = False
    if scheduler:
        scheduler.shutdown(wait=False)


def main():
    """メイン関数"""
    global scheduler, running

    logger.info("=== 競艇オッズ収集Worker起動 (v8.8 軽量版) ===")
    logger.info(f"高頻度収集: 締切{HIGH_FREQ_SECONDS_BEFORE}秒前から{HIGH_FREQ_INTERVAL}秒間隔")
    logger.info(f"通常収集: {NORMAL_INTERVAL_MINUTES}分間隔")
    logger.info(f"結果収集: {RESULT_COLLECTION_INTERVAL_MINUTES}分間隔")
    logger.info(f"運用時間: {OPERATION_START_HOUR}:00〜{OPERATION_END_HOUR}:{OPERATION_END_MINUTE:02d} JST")
    logger.info("注意: 仮想購入処理は boatrace-betting-process で実行されます")

    # 環境変数チェック（起動時に警告を出す）
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.warning("警告: DATABASE_URL環境変数が設定されていません。")
        logger.warning("環境変数が設定されるまでデータ収集は行われません。")
    else:
        logger.info("DATABASE_URL: 設定済み")

    # シグナルハンドラを設定
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # スケジューラを作成（オッズ収集と結果収集用）
    scheduler = BackgroundScheduler(timezone=JST)

    # 高頻度収集ジョブ（5秒間隔）
    scheduler.add_job(
        collect_high_frequency_odds,
        IntervalTrigger(seconds=HIGH_FREQ_INTERVAL),
        id='high_freq_odds',
        name='高頻度オッズ収集',
        max_instances=1,
        coalesce=True
    )

    # 通常収集ジョブ（10分間隔）
    scheduler.add_job(
        collect_regular_odds,
        IntervalTrigger(minutes=NORMAL_INTERVAL_MINUTES),
        id='regular_odds',
        name='定期オッズ収集',
        max_instances=1,
        coalesce=True
    )

    # 結果収集ジョブ（5分間隔）
    scheduler.add_job(
        collect_race_results_job,
        IntervalTrigger(minutes=RESULT_COLLECTION_INTERVAL_MINUTES),
        id='result_collection',
        name='レース結果収集',
        max_instances=1,
        coalesce=True
    )

    # 注意: 仮想購入処理は boatrace-betting-process Cron Job に移行しました
    # 注意: LZHバッチはboatrace-historical-importサービスに移動しました

    # スケジューラを開始
    scheduler.start()
    logger.info("スケジューラを開始しました")

    # 起動時に一度通常収集を実行
    collect_regular_odds()

    # メインループ - シンプルにスケジューラの監視のみ
    try:
        while running:
            time.sleep(10)  # 10秒ごとにループ（シグナル受信用）
    except (KeyboardInterrupt, SystemExit):
        logger.info("シャットダウン要求を受信しました")
    finally:
        if scheduler and scheduler.running:
            scheduler.shutdown(wait=False)
        logger.info("=== Worker終了 ===")


if __name__ == '__main__':
    main()

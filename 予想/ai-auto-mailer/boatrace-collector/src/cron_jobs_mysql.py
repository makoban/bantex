"""
競艇データ収集システム - Cron Job エントリポイント (MySQL/TiDB対応版)
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


def get_database_url():
    """データベースURLを取得"""
    url = os.environ.get('DATABASE_URL')
    if not url:
        logger.error("DATABASE_URL環境変数が設定されていません")
        sys.exit(1)
    return url


def job_daily_collection():
    """
    日次収集ジョブ
    毎朝8:00 JSTに実行。当日の全レース情報と初期オッズを収集。
    """
    from collector_mysql import run_daily_collection
    
    logger.info("=== 日次収集ジョブ開始 ===")
    database_url = get_database_url()
    
    try:
        run_daily_collection(database_url)
        logger.info("=== 日次収集ジョブ完了 ===")
    except Exception as e:
        logger.error(f"日次収集ジョブ失敗: {e}")
        sys.exit(1)


def job_odds_collection_regular():
    """
    定期オッズ収集ジョブ
    10分ごとに実行。未終了レースのオッズを収集。
    """
    from collector_mysql import run_odds_regular_collection
    
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
    """
    from collect_odds_mysql import OddsCollector
    
    logger.info("=== 高頻度オッズ収集ジョブ開始 ===")
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
    15分ごとに実行。終了したレースの結果と払戻金を収集。
    """
    from collector_mysql import run_result_collection
    
    logger.info("=== 結果収集ジョブ開始 ===")
    database_url = get_database_url()
    
    try:
        run_result_collection(database_url)
        logger.info("=== 結果収集ジョブ完了 ===")
    except Exception as e:
        logger.error(f"結果収集ジョブ失敗: {e}")
        sys.exit(1)


def job_test():
    """
    テストジョブ
    デプロイ確認用。DB接続をテストして終了。
    """
    import mysql.connector
    from collect_odds_mysql import parse_database_url
    
    logger.info("=== テストジョブ開始 ===")
    database_url = get_database_url()
    
    try:
        db_config = parse_database_url(database_url)
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # テーブル一覧を取得
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        logger.info(f"テーブル一覧: {[t[0] for t in tables]}")
        
        # 現在時刻を取得
        cursor.execute("SELECT NOW()")
        db_time = cursor.fetchone()[0]
        logger.info(f"データベース時刻: {db_time}")
        
        cursor.close()
        conn.close()
        logger.info("=== テストジョブ完了: DB接続成功 ===")
    except Exception as e:
        logger.error(f"テストジョブ失敗: {e}")
        sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python cron_jobs_mysql.py <job_name>")
        print("Available jobs: daily, odds_regular, odds_high_freq, result, test")
        sys.exit(1)
        
    job_name = sys.argv[1]
    
    jobs = {
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

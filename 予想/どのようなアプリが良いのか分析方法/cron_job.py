#!/usr/bin/env python3
"""
Render Cron Job エントリポイント
定期実行されるメインスクリプト
"""

import os
import sys
import logging
from datetime import datetime, date, timedelta
import time

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def run_odds_collection():
    """オッズ収集を実行"""
    from collector import BoatraceCollector
    
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL is not set")
        return False

    try:
        collector = BoatraceCollector(db_url)
        collector.collect_realtime_odds()
        return True
    except Exception as e:
        logger.error(f"Odds collection failed: {e}")
        return False


def run_high_frequency_collection():
    """高頻度オッズ収集（締切直前用）"""
    from collector import BoatraceCollector
    
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL is not set")
        return False

    try:
        collector = BoatraceCollector(db_url)
        today = date.today()
        stadiums = collector.get_today_stadiums(today)
        
        # 現在時刻から1時間以内に締切のレースを特定して高頻度収集
        # （実装は締切時刻の取得が必要）
        
        collector.collect_realtime_odds()
        return True
    except Exception as e:
        logger.error(f"High frequency collection failed: {e}")
        return False


def run_historical_collection():
    """過去データ収集"""
    from collector import BoatraceCollector
    
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL is not set")
        return False

    try:
        collector = BoatraceCollector(db_url)
        
        # 過去30日分を収集
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=30)
        
        collector.collect_historical_data(start_date, end_date)
        return True
    except Exception as e:
        logger.error(f"Historical collection failed: {e}")
        return False


def main():
    """メイン関数"""
    logger.info("=" * 50)
    logger.info("Boatrace Data Collector - Cron Job Started")
    logger.info(f"Current time: {datetime.now()}")
    logger.info("=" * 50)

    # コマンドライン引数でモードを指定
    mode = sys.argv[1] if len(sys.argv) > 1 else 'realtime'
    
    if mode == 'realtime':
        success = run_odds_collection()
    elif mode == 'highfreq':
        success = run_high_frequency_collection()
    elif mode == 'historical':
        success = run_historical_collection()
    else:
        logger.error(f"Unknown mode: {mode}")
        success = False

    logger.info("=" * 50)
    logger.info(f"Cron Job Completed - Success: {success}")
    logger.info("=" * 50)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

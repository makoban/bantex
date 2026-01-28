"""手動復旧スクリプト: 収集と購入予定作成のみ実行"""
import os
import sys
import logging
from datetime import datetime
import pytz

# カレントディレクトリをパスに追加
sys.path.append(os.getcwd())

from collector import BoatRaceCollector
from virtual_betting import VirtualBettingManager

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def manual_recovery():
    print("=== 手動復旧開始 ===")

    # 1. レース情報収集
    print("Step 1: レース情報収集開始...")
    collector = BoatRaceCollector()
    collector.run_daily_collection()
    print("Step 1: 完了")

    # 2. 購入予定作成
    print("Step 2: 購入予定作成開始...")
    manager = VirtualBettingManager()
    manager.register_daily_bets()
    print("Step 2: 完了")

if __name__ == "__main__":
    manual_recovery()

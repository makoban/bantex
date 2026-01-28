"""
競艇データ自動収集システム（高機能版）
pyjpboatraceライブラリを活用したデータ収集
"""

import os
import sys
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
import time
import json

import psycopg2
from psycopg2.extras import execute_values

# pyjpboatraceライブラリ
from pyjpboatrace import PyJPBoatrace
from pyjpboatrace.drivers import create_httpget_driver

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 競艇場コード一覧
STADIUM_NAMES = {
    1: '桐生', 2: '戸田', 3: '江戸川', 4: '平和島', 5: '多摩川', 6: '浜名湖',
    7: '蒲郡', 8: '常滑', 9: '津', 10: '三国', 11: 'びわこ', 12: '住之江',
    13: '尼崎', 14: '鳴門', 15: '丸亀', 16: '児島', 17: '宮島', 18: '徳山',
    19: '下関', 20: '若松', 21: '芦屋', 22: '福岡', 23: '唐津', 24: '大村'
}


class AdvancedBoatraceCollector:
    """pyjpboatraceを活用した高機能データ収集クラス"""

    def __init__(self, db_url: str):
        self.db_url = db_url
        # HTTPGetドライバーを使用（ブラウザ不要）
        self.driver = create_httpget_driver()
        self.boatrace = PyJPBoatrace(driver=self.driver)

    def get_db_connection(self):
        """データベース接続を取得"""
        return psycopg2.connect(self.db_url)

    def get_today_stadiums(self, target_date: date) -> Dict[int, Any]:
        """指定日に開催している競艇場を取得"""
        try:
            result = self.boatrace.get_stadiums(target_date)
            logger.info(f"Fetched stadiums for {target_date}: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to get stadiums: {e}")
            return {}

    def get_race_info(self, target_date: date, stadium: int, race: int) -> Optional[Dict]:
        """レース基本情報を取得"""
        try:
            result = self.boatrace.get_race_info(target_date, stadium, race)
            return result
        except Exception as e:
            logger.error(f"Failed to get race info for {stadium}-{race}: {e}")
            return None

    def get_odds_trifecta(self, target_date: date, stadium: int, race: int) -> Optional[Dict]:
        """三連単オッズを取得"""
        try:
            result = self.boatrace.get_odds_trifecta(target_date, stadium, race)
            return result
        except Exception as e:
            logger.error(f"Failed to get trifecta odds for {stadium}-{race}: {e}")
            return None

    def get_odds_trio(self, target_date: date, stadium: int, race: int) -> Optional[Dict]:
        """三連複オッズを取得"""
        try:
            result = self.boatrace.get_odds_trio(target_date, stadium, race)
            return result
        except Exception as e:
            logger.error(f"Failed to get trio odds for {stadium}-{race}: {e}")
            return None

    def get_odds_exacta_quinella(self, target_date: date, stadium: int, race: int) -> Optional[Dict]:
        """二連単・二連複オッズを取得"""
        try:
            result = self.boatrace.get_odds_exacta_quinella(target_date, stadium, race)
            return result
        except Exception as e:
            logger.error(f"Failed to get exacta/quinella odds for {stadium}-{race}: {e}")
            return None

    def get_odds_quinellaplace(self, target_date: date, stadium: int, race: int) -> Optional[Dict]:
        """拡連複オッズを取得"""
        try:
            result = self.boatrace.get_odds_quinellaplace(target_date, stadium, race)
            return result
        except Exception as e:
            logger.error(f"Failed to get quinellaplace odds for {stadium}-{race}: {e}")
            return None

    def get_odds_win_placeshow(self, target_date: date, stadium: int, race: int) -> Optional[Dict]:
        """単勝・複勝オッズを取得"""
        try:
            result = self.boatrace.get_odds_win_placeshow(target_date, stadium, race)
            return result
        except Exception as e:
            logger.error(f"Failed to get win/placeshow odds for {stadium}-{race}: {e}")
            return None

    def get_just_before_info(self, target_date: date, stadium: int, race: int) -> Optional[Dict]:
        """直前情報を取得"""
        try:
            result = self.boatrace.get_just_before_info(target_date, stadium, race)
            return result
        except Exception as e:
            logger.error(f"Failed to get just before info for {stadium}-{race}: {e}")
            return None

    def get_race_result(self, target_date: date, stadium: int, race: int) -> Optional[Dict]:
        """レース結果を取得"""
        try:
            result = self.boatrace.get_race_result(target_date, stadium, race)
            return result
        except Exception as e:
            logger.error(f"Failed to get race result for {stadium}-{race}: {e}")
            return None

    def save_race(self, conn, race_info: Dict) -> int:
        """レース情報をDBに保存"""
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO races (race_date, stadium_code, race_number, title, distance, deadline_time)
                VALUES (%(race_date)s, %(stadium_code)s, %(race_number)s, %(title)s, %(distance)s, %(deadline_time)s)
                ON CONFLICT (race_date, stadium_code, race_number)
                DO UPDATE SET title = EXCLUDED.title, updated_at = NOW()
                RETURNING id
            """, race_info)
            race_id = cur.fetchone()[0]
            conn.commit()
        return race_id

    def save_odds_batch(self, conn, race_id: int, odds_data: Dict, odds_type: str):
        """オッズデータをバッチでDBに保存"""
        if not odds_data:
            return

        scraped_at = datetime.utcnow()
        values = []

        # オッズデータの形式に応じてパース
        if isinstance(odds_data, dict):
            for combination, odds_value in odds_data.items():
                if odds_value is not None and combination != 'timestamp':
                    try:
                        values.append((
                            race_id,
                            odds_type,
                            str(combination),
                            float(odds_value) if odds_value else 0,
                            scraped_at
                        ))
                    except (ValueError, TypeError):
                        continue

        if values:
            with conn.cursor() as cur:
                execute_values(cur, """
                    INSERT INTO odds (race_id, odds_type, bet_combination, odds_value, scraped_at)
                    VALUES %s
                """, values)
                conn.commit()
            logger.info(f"Saved {len(values)} {odds_type} odds for race_id={race_id}")

    def collect_all_odds_for_race(self, conn, target_date: date, stadium: int, race: int, race_id: int):
        """1レースの全オッズを収集・保存"""
        
        # 三連単
        trifecta = self.get_odds_trifecta(target_date, stadium, race)
        if trifecta:
            self.save_odds_batch(conn, race_id, trifecta.get('odds', {}), 'trifecta')
        time.sleep(0.5)

        # 三連複
        trio = self.get_odds_trio(target_date, stadium, race)
        if trio:
            self.save_odds_batch(conn, race_id, trio.get('odds', {}), 'trio')
        time.sleep(0.5)

        # 二連単・二連複
        exacta_quinella = self.get_odds_exacta_quinella(target_date, stadium, race)
        if exacta_quinella:
            self.save_odds_batch(conn, race_id, exacta_quinella.get('exacta', {}), 'exacta')
            self.save_odds_batch(conn, race_id, exacta_quinella.get('quinella', {}), 'quinella')
        time.sleep(0.5)

        # 拡連複
        quinellaplace = self.get_odds_quinellaplace(target_date, stadium, race)
        if quinellaplace:
            self.save_odds_batch(conn, race_id, quinellaplace.get('odds', {}), 'quinellaplace')
        time.sleep(0.5)

        # 単勝・複勝
        win_placeshow = self.get_odds_win_placeshow(target_date, stadium, race)
        if win_placeshow:
            self.save_odds_batch(conn, race_id, win_placeshow.get('win', {}), 'win')
            self.save_odds_batch(conn, race_id, win_placeshow.get('placeshow', {}), 'placeshow')

    def collect_realtime_odds(self, target_date: date = None):
        """リアルタイムオッズ収集（メインエントリポイント）"""
        if target_date is None:
            target_date = date.today()

        logger.info(f"Starting realtime odds collection for {target_date}")

        # 開催場を取得
        stadiums_data = self.get_today_stadiums(target_date)
        if not stadiums_data:
            logger.warning("No stadiums data available")
            return

        conn = self.get_db_connection()
        try:
            # 各競艇場について処理
            for stadium_code in range(1, 25):
                stadium_name = STADIUM_NAMES.get(stadium_code, f"Stadium {stadium_code}")
                
                # 12レース分を処理
                for race_number in range(1, 13):
                    try:
                        logger.info(f"Collecting {stadium_name} Race {race_number}")

                        # レース情報を作成
                        race_info = {
                            'race_date': target_date,
                            'stadium_code': stadium_code,
                            'race_number': race_number,
                            'title': None,
                            'distance': 1800,
                            'deadline_time': None
                        }

                        # レース情報を保存してIDを取得
                        race_id = self.save_race(conn, race_info)

                        # 全オッズを収集
                        self.collect_all_odds_for_race(conn, target_date, stadium_code, race_number, race_id)

                        time.sleep(1)  # レース間の待機

                    except Exception as e:
                        logger.error(f"Error collecting {stadium_name} Race {race_number}: {e}")
                        continue

                time.sleep(2)  # 競艇場間の待機

        finally:
            conn.close()
            self.driver.quit()

        logger.info("Realtime odds collection completed")

    def collect_single_race_odds(self, target_date: date, stadium: int, race: int):
        """単一レースのオッズを収集（高頻度収集用）"""
        conn = self.get_db_connection()
        try:
            race_info = {
                'race_date': target_date,
                'stadium_code': stadium,
                'race_number': race,
                'title': None,
                'distance': 1800,
                'deadline_time': None
            }
            race_id = self.save_race(conn, race_info)
            self.collect_all_odds_for_race(conn, target_date, stadium, race, race_id)
        finally:
            conn.close()


def main():
    """メイン関数"""
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL environment variable is not set")
        sys.exit(1)

    collector = AdvancedBoatraceCollector(db_url)

    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == 'single' and len(sys.argv) >= 5:
            # 単一レース収集モード: python collector_advanced.py single 2026-01-04 1 1
            target_date = date.fromisoformat(sys.argv[2])
            stadium = int(sys.argv[3])
            race = int(sys.argv[4])
            collector.collect_single_race_odds(target_date, stadium, race)
        elif mode == 'test':
            logger.info("Running in test mode")
            stadiums = collector.get_today_stadiums(date.today())
            logger.info(f"Today's stadiums: {stadiums}")
    else:
        collector.collect_realtime_odds()


if __name__ == '__main__':
    main()

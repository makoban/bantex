"""
競艇データ自動収集システム
Render Cron Job で定期実行するメインスクリプト
"""

import os
import sys
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
import time
import json

import requests
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import execute_values

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 定数
BASE_URL = "https://www.boatrace.jp/owpc/pc/race"
STADIUM_CODES = list(range(1, 25))  # 01-24
RACE_NUMBERS = list(range(1, 13))   # 1-12

# オッズ種別とURLパス
ODDS_TYPES = {
    'trifecta': 'odds3t',      # 三連単
    'trio': 'odds3f',          # 三連複
    'exacta_quinella': 'odds2tf',  # 二連単・二連複
    'quinellaplace': 'oddsk',  # 拡連複
    'win_placeshow': 'oddstf', # 単勝・複勝
}


class BoatraceCollector:
    """競艇データ収集クラス"""

    def __init__(self, db_url: str):
        """
        Args:
            db_url: PostgreSQL接続URL
        """
        self.db_url = db_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_db_connection(self):
        """データベース接続を取得"""
        return psycopg2.connect(self.db_url)

    def fetch_page(self, url: str, retry: int = 3) -> Optional[BeautifulSoup]:
        """ページを取得してBeautifulSoupオブジェクトを返す"""
        for attempt in range(retry):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return BeautifulSoup(response.content, 'html.parser')
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < retry - 1:
                    time.sleep(2 ** attempt)  # 指数バックオフ
        return None

    def get_today_stadiums(self, target_date: date) -> List[int]:
        """指定日に開催している競艇場コードのリストを取得"""
        date_str = target_date.strftime('%Y%m%d')
        url = f"{BASE_URL}/index?hd={date_str}"
        soup = self.fetch_page(url)
        
        if not soup:
            logger.error(f"Failed to fetch stadium list for {date_str}")
            return []

        stadiums = []
        # レース一覧から開催場を抽出
        for jcd in STADIUM_CODES:
            link = soup.find('a', href=lambda x: x and f'jcd={jcd:02d}' in x and f'hd={date_str}' in x)
            if link:
                stadiums.append(jcd)
        
        logger.info(f"Found {len(stadiums)} stadiums for {date_str}: {stadiums}")
        return stadiums

    def get_race_info(self, target_date: date, stadium_code: int, race_number: int) -> Optional[Dict]:
        """レース基本情報を取得"""
        date_str = target_date.strftime('%Y%m%d')
        url = f"{BASE_URL}/racelist?rno={race_number}&jcd={stadium_code:02d}&hd={date_str}"
        soup = self.fetch_page(url)
        
        if not soup:
            return None

        race_info = {
            'race_date': target_date,
            'stadium_code': stadium_code,
            'race_number': race_number,
            'title': None,
            'distance': None,
            'deadline_time': None,
        }

        # レースタイトル取得
        title_elem = soup.find('h2', class_='heading2_title')
        if title_elem:
            race_info['title'] = title_elem.get_text(strip=True)

        return race_info

    def get_odds_trifecta(self, target_date: date, stadium_code: int, race_number: int) -> List[Dict]:
        """三連単オッズを取得"""
        date_str = target_date.strftime('%Y%m%d')
        url = f"{BASE_URL}/odds3t?rno={race_number}&jcd={stadium_code:02d}&hd={date_str}"
        soup = self.fetch_page(url)
        
        if not soup:
            return []

        odds_list = []
        scraped_at = datetime.utcnow()

        # オッズテーブルをパース
        odds_table = soup.find('div', class_='table1')
        if odds_table:
            rows = odds_table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                for i in range(0, len(cells), 2):
                    if i + 1 < len(cells):
                        combination = cells[i].get_text(strip=True)
                        odds_value = cells[i + 1].get_text(strip=True)
                        if combination and odds_value:
                            try:
                                odds_list.append({
                                    'odds_type': 'trifecta',
                                    'bet_combination': combination,
                                    'odds_value': float(odds_value.replace(',', '')),
                                    'scraped_at': scraped_at
                                })
                            except ValueError:
                                continue

        return odds_list

    def get_all_odds(self, target_date: date, stadium_code: int, race_number: int) -> List[Dict]:
        """全種類のオッズを取得"""
        all_odds = []
        scraped_at = datetime.utcnow()
        date_str = target_date.strftime('%Y%m%d')

        for odds_type, url_path in ODDS_TYPES.items():
            url = f"{BASE_URL}/{url_path}?rno={race_number}&jcd={stadium_code:02d}&hd={date_str}"
            soup = self.fetch_page(url)
            
            if not soup:
                continue

            # オッズテーブルをパース（簡易版）
            odds_table = soup.find('table', class_='is-w495')
            if not odds_table:
                odds_table = soup.find('div', class_='table1')
            
            if odds_table:
                # テーブル内のテキストからオッズを抽出
                text = odds_table.get_text()
                # 実際のパース処理は公式サイトの構造に合わせて調整が必要
                logger.debug(f"Fetched {odds_type} odds for race {race_number}")

            time.sleep(0.5)  # サーバー負荷軽減

        return all_odds

    def save_race(self, conn, race_info: Dict) -> int:
        """レース情報をDBに保存し、race_idを返す"""
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

    def save_odds(self, conn, race_id: int, odds_list: List[Dict]):
        """オッズデータをDBに保存"""
        if not odds_list:
            return
        
        with conn.cursor() as cur:
            values = [
                (race_id, o['odds_type'], o['bet_combination'], o['odds_value'], o['scraped_at'])
                for o in odds_list
            ]
            execute_values(cur, """
                INSERT INTO odds (race_id, odds_type, bet_combination, odds_value, scraped_at)
                VALUES %s
            """, values)
            conn.commit()
        logger.info(f"Saved {len(odds_list)} odds records for race_id={race_id}")

    def collect_realtime_odds(self, target_date: date = None):
        """リアルタイムオッズを収集（メインエントリポイント）"""
        if target_date is None:
            target_date = date.today()

        logger.info(f"Starting realtime odds collection for {target_date}")

        # 開催場を取得
        stadiums = self.get_today_stadiums(target_date)
        if not stadiums:
            logger.warning("No stadiums found for today")
            return

        conn = self.get_db_connection()
        try:
            for stadium_code in stadiums:
                for race_number in RACE_NUMBERS:
                    try:
                        # レース情報を取得・保存
                        race_info = self.get_race_info(target_date, stadium_code, race_number)
                        if not race_info:
                            continue

                        race_id = self.save_race(conn, race_info)

                        # オッズを取得・保存
                        odds = self.get_odds_trifecta(target_date, stadium_code, race_number)
                        self.save_odds(conn, race_id, odds)

                        time.sleep(1)  # サーバー負荷軽減

                    except Exception as e:
                        logger.error(f"Error collecting race {stadium_code}-{race_number}: {e}")
                        continue

        finally:
            conn.close()

        logger.info("Realtime odds collection completed")

    def collect_historical_data(self, start_date: date, end_date: date):
        """過去データを収集"""
        logger.info(f"Starting historical data collection from {start_date} to {end_date}")
        
        current_date = start_date
        while current_date <= end_date:
            self.collect_realtime_odds(current_date)
            current_date += timedelta(days=1)
            time.sleep(5)  # 日付間の待機

        logger.info("Historical data collection completed")


def main():
    """メイン関数"""
    # 環境変数からDB接続情報を取得
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL environment variable is not set")
        sys.exit(1)

    collector = BoatraceCollector(db_url)

    # コマンドライン引数で動作モードを切り替え
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == 'historical':
            # 過去データ収集モード
            start_date = date(2025, 1, 1)  # 開始日
            end_date = date.today() - timedelta(days=1)  # 昨日まで
            collector.collect_historical_data(start_date, end_date)
        elif mode == 'test':
            # テストモード
            logger.info("Running in test mode")
            stadiums = collector.get_today_stadiums(date.today())
            logger.info(f"Today's stadiums: {stadiums}")
    else:
        # デフォルト: リアルタイム収集
        collector.collect_realtime_odds()


if __name__ == '__main__':
    main()

'''
競艇オッズ収集スクリプト (MySQL/TiDB対応版)

確定仕様:
- 対象: 2連単・2連複・単勝・複勝（3連は無し）
- 締切5分前から10秒間隔で収集
- 通常は10分間隔で収集
- 開催日のみ稼働（毎朝チェック）
- 運用時間: 8:00〜21:30
'''

import os
import re
import time
import logging
import requests
from datetime import datetime, timedelta, timezone

# JSTタイムゾーン定義
JST = timezone(timedelta(hours=9))
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
import mysql.connector
from mysql.connector import Error as MySQLError

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 競艇場コード
STADIUM_CODES = {
    '01': '桐生', '02': '戸田', '03': '江戸川', '04': '平和島', '05': '多摩川',
    '06': '浜名湖', '07': '蒲郡', '08': '常滑', '09': '津', '10': '三国',
    '11': '琵琶湖', '12': '住之江', '13': '尼崎', '14': '鳴門', '15': '丸亀',
    '16': '児島', '17': '宮島', '18': '徳山', '19': '下関', '20': '若松',
    '21': '芦屋', '22': '福岡', '23': '唐津', '24': '大村'
}


def parse_database_url(url: str) -> dict:
    """DATABASE_URLをパースしてMySQL接続パラメータに変換"""
    # mysql://user:pass@host:port/dbname?ssl=true
    import urllib.parse
    
    if url.startswith('mysql://'):
        url = url[8:]
    elif url.startswith('mysql+pymysql://'):
        url = url[16:]
    
    # クエリパラメータを分離
    if '?' in url:
        url, query_string = url.split('?', 1)
        query_params = urllib.parse.parse_qs(query_string)
    else:
        query_params = {}
    
    # user:pass@host:port/dbname をパース
    if '@' in url:
        userpass, hostdb = url.split('@', 1)
        if ':' in userpass:
            user, password = userpass.split(':', 1)
            password = urllib.parse.unquote(password)
        else:
            user = userpass
            password = ''
    else:
        user = ''
        password = ''
        hostdb = url
    
    if '/' in hostdb:
        hostport, database = hostdb.split('/', 1)
    else:
        hostport = hostdb
        database = ''
    
    if ':' in hostport:
        host, port = hostport.split(':', 1)
        port = int(port)
    else:
        host = hostport
        port = 3306
    
    config = {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'database': database,
    }
    
    # SSL設定
    if 'ssl' in query_params or 'sslmode' in query_params:
        config['ssl_disabled'] = False
        config['ssl_verify_cert'] = False
    
    return config


class OddsCollector:
    """オッズ収集クラス (MySQL/TiDB対応)"""
    
    BASE_URL = 'https://www.boatrace.jp/owpc/pc/race'
    
    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.environ.get('DATABASE_URL')
        self.db_config = parse_database_url(self.db_url) if self.db_url else None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_db_connection(self, retries=3, delay=5):
        """データベース接続を取得（リトライ機能付き）"""
        for attempt in range(retries):
            try:
                conn = mysql.connector.connect(**self.db_config)
                return conn
            except MySQLError as e:
                if attempt < retries - 1:
                    logger.warning(f"接続失敗、{delay}秒後にリトライ... ({attempt + 1}/{retries})")
                    time.sleep(delay)
                else:
                    raise e
    
    def create_odds_table(self, conn):
        """オッズテーブルを作成"""
        cursor = conn.cursor()
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS odds_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    race_date DATE NOT NULL,
                    stadium_code VARCHAR(2) NOT NULL,
                    race_number INT NOT NULL,
                    odds_type VARCHAR(10) NOT NULL,
                    combination VARCHAR(10) NOT NULL,
                    odds_value DECIMAL(10,1),
                    odds_min DECIMAL(10,1),
                    odds_max DECIMAL(10,1),
                    scraped_at DATETIME NOT NULL,
                    minutes_to_deadline INT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_odds_history_race (race_date, stadium_code, race_number),
                    INDEX idx_odds_history_scraped (scraped_at),
                    INDEX idx_odds_history_combination (combination)
                )
            ''')
            conn.commit()
            logger.info("オッズテーブルを作成/確認しました")
        finally:
            cursor.close()
    
    def check_today_races(self) -> bool:
        """本日のレース開催をチェック"""
        today = datetime.now(JST).strftime('%Y%m%d')
        url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={today}"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 開催場のリンクを探す
            stadium_links = soup.find_all('a', href=re.compile(r'jcd=\d{2}'))
            
            if stadium_links:
                logger.info(f"本日の開催: {len(stadium_links)}場")
                return True
            else:
                logger.info("本日の開催はありません")
                return False
                
        except Exception as e:
            logger.error(f"開催チェックエラー: {e}")
            return False
    
    def get_today_race_schedule(self) -> List[Dict]:
        """本日のレーススケジュールを取得"""
        today = datetime.now(JST).strftime('%Y%m%d')
        races = []
        
        # 各場のレース情報を取得
        for stadium_code in STADIUM_CODES.keys():
            schedule = self._get_stadium_schedule(stadium_code, today)
            if schedule:
                races.extend(schedule)
        
        # 締切時刻でソート
        races.sort(key=lambda x: x.get('deadline_time', datetime.max))
        
        logger.info(f"本日のレース数: {len(races)}")
        return races
    
    def _get_stadium_schedule(self, stadium_code: str, race_date: str) -> List[Dict]:
        """特定場のレーススケジュールを取得（オッズページから締切時刻を取得）"""
        url = f"{self.BASE_URL}/odds2tf?rno=1&jcd={stadium_code}&hd={race_date}"
        logger.info(f"URL created: {url}")
        
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            races = []
            
            # 締切時刻行を探す
            deadline_row = None
            for table in soup.find_all('table'):
                for row in table.find_all('tr'):
                    if '締切予定時刻' in row.get_text():
                        deadline_row = row
                        break
                if deadline_row:
                    break
            
            if not deadline_row:
                return []
            
            cells = deadline_row.find_all(['th', 'td'])
            race_num = 0
            
            for cell in cells:
                text = cell.get_text(strip=True)
                time_match = re.match(r'(\d{1,2}):(\d{2})', text)
                if time_match:
                    race_num += 1
                    hour, minute = int(time_match.group(1)), int(time_match.group(2))
                    deadline = datetime.now(JST).replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )
                    
                    races.append({
                        'date': race_date,
                        'stadium_code': stadium_code,
                        'stadium_name': STADIUM_CODES.get(stadium_code, stadium_code),
                        'race_number': race_num,
                        'deadline_time': deadline
                    })
            
            return races
            
        except Exception as e:
            logger.debug(f"スケジュール取得エラー ({stadium_code}): {e}")
            return []
    
    def fetch_2tf_odds(self, stadium_code: str, race_number: int, race_date: str) -> List[Dict]:
        """2連単・2連複オッズを取得"""
        url = f"{self.BASE_URL}/odds2tf?rno={race_number}&jcd={stadium_code}&hd={race_date}"
        logger.info(f"URL created: {url}")
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            odds_list = []
            scraped_at = datetime.now(JST)
            
            # テーブルを取得
            tables = soup.find_all('table')
            
            for table_idx, table in enumerate(tables):
                rows = table.find_all('tr')
                if len(rows) < 2:
                    continue
                
                first_row = rows[0]
                first_cells = first_row.find_all(['th', 'td'])
                if not first_cells:
                    continue
                
                has_boat_color = any('is-boatColor' in ' '.join(c.get('class', [])) for c in first_cells)
                if not has_boat_color:
                    continue
                
                odds_type = '2t' if table_idx == 1 else '2f'
                
                first_place_boats = []
                for i, cell in enumerate(first_cells):
                    if i % 2 == 0:
                        text = cell.get_text(strip=True)
                        if text.isdigit():
                            first_place_boats.append(int(text))
                
                for row in rows[1:]:
                    cells = row.find_all('td')
                    if not cells:
                        continue
                    
                    for pair_idx in range(0, len(cells), 2):
                        if pair_idx + 1 >= len(cells):
                            break
                        
                        boat_cell = cells[pair_idx]
                        odds_cell = cells[pair_idx + 1]
                        
                        boat_text = boat_cell.get_text(strip=True)
                        if not boat_text.isdigit():
                            continue
                        second = int(boat_text)
                        
                        odds_classes = ' '.join(odds_cell.get('class', []))
                        if 'is-disabled' in odds_classes:
                            continue
                        
                        odds_text = odds_cell.get_text(strip=True)
                        odds_value = self._parse_odds(odds_text)
                        
                        if odds_value:
                            first_idx = pair_idx // 2
                            if first_idx < len(first_place_boats):
                                first = first_place_boats[first_idx]
                                combination = f"{first}-{second}"
                                
                                odds_list.append({
                                    'odds_type': odds_type,
                                    'combination': combination,
                                    'odds_value': odds_value,
                                    'scraped_at': scraped_at
                                })
            
            return odds_list
            
        except Exception as e:
            logger.error(f"2連オッズ取得エラー: {stadium_code} {race_number}R - {e}")
            return []
    
    def fetch_tf_odds(self, stadium_code: str, race_number: int, race_date: str) -> List[Dict]:
        """単勝・複勝オッズを取得"""
        url = f"{self.BASE_URL}/oddstf?rno={race_number}&jcd={stadium_code}&hd={race_date}"
        logger.info(f"URL created: {url}")
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            odds_list = []
            scraped_at = datetime.now(JST)
            
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                
                header = table.find('tr')
                if header:
                    header_text = header.get_text()
                    if '単勝' in header_text:
                        odds_type = 'win'
                    elif '複勝' in header_text:
                        odds_type = 'place'
                    else:
                        continue
                else:
                    continue
                
                for row in rows[1:]:
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        boat_num = cells[0].get_text(strip=True)
                        if not boat_num.isdigit():
                            continue
                        
                        odds_text = cells[2].get_text(strip=True)
                        
                        if odds_type == 'win':
                            odds_value = self._parse_odds(odds_text)
                            if odds_value:
                                odds_list.append({
                                    'odds_type': 'win',
                                    'combination': boat_num,
                                    'odds_value': odds_value,
                                    'scraped_at': scraped_at
                                })
                        else:
                            odds_range = self._parse_odds_range(odds_text)
                            if odds_range:
                                odds_list.append({
                                    'odds_type': 'place',
                                    'combination': boat_num,
                                    'odds_min': odds_range[0],
                                    'odds_max': odds_range[1],
                                    'scraped_at': scraped_at
                                })
            
            return odds_list
            
        except Exception as e:
            logger.error(f"単複オッズ取得エラー: {stadium_code} {race_number}R - {e}")
            return []
    
    def fetch_all_odds(self, stadium_code: str, race_number: int, race_date: str) -> List[Dict]:
        """全オッズを取得（2連単・2連複・単勝・複勝）"""
        all_odds = []
        
        odds_2tf = self.fetch_2tf_odds(stadium_code, race_number, race_date)
        all_odds.extend(odds_2tf)
        
        odds_tf = self.fetch_tf_odds(stadium_code, race_number, race_date)
        all_odds.extend(odds_tf)
        
        return all_odds
    
    def _parse_odds(self, text: str) -> Optional[float]:
        """オッズ文字列をパース"""
        try:
            cleaned = re.sub(r'[^\d.]', '', text)
            if cleaned:
                return float(cleaned)
        except:
            pass
        return None
    
    def _parse_odds_range(self, text: str) -> Optional[Tuple[float, float]]:
        """範囲オッズをパース（例: "1.3-1.9"）"""
        try:
            match = re.match(r'([\d.]+)-([\d.]+)', text)
            if match:
                return float(match.group(1)), float(match.group(2))
        except:
            pass
        return None
    
    def save_odds(self, conn, race_date: str, stadium_code: str, race_number: int,
                  odds_list: List[Dict], minutes_to_deadline: int = None):
        """オッズをデータベースに保存"""
        if not odds_list:
            return
        
        cursor = conn.cursor()
        try:
            for odds in odds_list:
                # 日付をフォーマット
                if len(race_date) == 8:
                    formatted_date = f"{race_date[:4]}-{race_date[4:6]}-{race_date[6:8]}"
                else:
                    formatted_date = race_date
                
                cursor.execute('''
                    INSERT INTO odds_history (
                        race_date, stadium_code, race_number, odds_type, combination,
                        odds_value, odds_min, odds_max, scraped_at, minutes_to_deadline
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    formatted_date,
                    stadium_code,
                    race_number,
                    odds['odds_type'],
                    odds['combination'],
                    odds.get('odds_value'),
                    odds.get('odds_min'),
                    odds.get('odds_max'),
                    odds['scraped_at'],
                    minutes_to_deadline
                ))
            
            conn.commit()
            logger.info(f"保存完了: {len(odds_list)}件")
        finally:
            cursor.close()
    
    def collect_near_deadline_races(self, minutes_before: int = 5, 
                                      interval_seconds: int = 10, iterations: int = 9):
        """
        締切間近のレースのオッズを収集
        """
        conn = self.get_db_connection()
        self.create_odds_table(conn)
        
        today = datetime.now(JST).strftime('%Y%m%d')
        races = self.get_today_race_schedule()
        
        if not races:
            logger.info("本日のレースがありません")
            conn.close()
            return
        
        now = datetime.now(JST)
        target_races = []
        for race in races:
            deadline = race.get('deadline_time')
            if deadline:
                delta = (deadline - now).total_seconds() / 60
                if 0 < delta <= minutes_before:
                    target_races.append(race)
        
        if not target_races:
            logger.info(f"締切{minutes_before}分以内のレースはありません")
            conn.close()
            return
        
        logger.info(f"高頻度収集対象: {len(target_races)}レース")
        
        for i in range(iterations):
            for race in target_races:
                deadline = race.get('deadline_time')
                now = datetime.now(JST)
                
                if deadline and now > deadline:
                    continue
                
                minutes_to_deadline = int((deadline - now).total_seconds() / 60) if deadline else None
                
                odds_list = self.fetch_all_odds(
                    race['stadium_code'],
                    race['race_number'],
                    race['date']
                )
                
                if odds_list:
                    self.save_odds(
                        conn, race['date'],
                        race['stadium_code'],
                        race['race_number'],
                        odds_list,
                        minutes_to_deadline
                    )
                    logger.info(f"収集: {race['stadium_name']} {race['race_number']}R {len(odds_list)}件 (残{minutes_to_deadline}分)")
            
            if i < iterations - 1:
                time.sleep(interval_seconds)
        
        conn.close()
        logger.info("高頻度収集完了")
    
    def run_regular_collection(self):
        """定期オッズ収集（10分間隔用）"""
        conn = self.get_db_connection()
        self.create_odds_table(conn)
        
        today = datetime.now(JST).strftime('%Y%m%d')
        races = self.get_today_race_schedule()
        
        if not races:
            logger.info("本日のレースがありません")
            conn.close()
            return 0
        
        now = datetime.now(JST)
        collected_count = 0
        
        # 未終了のレースのオッズを収集
        for race in races:
            deadline = race.get('deadline_time')
            if deadline and now < deadline:
                odds_list = self.fetch_all_odds(
                    race['stadium_code'],
                    race['race_number'],
                    race['date']
                )
                
                if odds_list:
                    minutes_to_deadline = int((deadline - now).total_seconds() / 60)
                    self.save_odds(
                        conn, race['date'],
                        race['stadium_code'],
                        race['race_number'],
                        odds_list,
                        minutes_to_deadline
                    )
                    collected_count += len(odds_list)
                    logger.info(f"収集: {race['stadium_name']} {race['race_number']}R {len(odds_list)}件")
        
        conn.close()
        logger.info(f"オッズ収集完了: {collected_count} レース")
        return collected_count


def test_connection():
    """DB接続テスト"""
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("DATABASE_URL環境変数が設定されていません")
        return
    
    collector = OddsCollector(db_url)
    try:
        conn = collector.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        print(f"接続成功: {result}")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"接続失敗: {e}")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python collect_odds_mysql.py test       # DB接続テスト")
        print("  python collect_odds_mysql.py regular    # 定期収集")
        print("  python collect_odds_mysql.py high_freq  # 高頻度収集")
        sys.exit(1)
    
    if sys.argv[1] == 'test':
        test_connection()
    elif sys.argv[1] == 'regular':
        collector = OddsCollector()
        collector.run_regular_collection()
    elif sys.argv[1] == 'high_freq':
        collector = OddsCollector()
        collector.collect_near_deadline_races(minutes_before=5, interval_seconds=10, iterations=9)

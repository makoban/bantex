'''
競艇オッズ収集スクリプト

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
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import execute_values

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


class OddsCollector:
    """オッズ収集クラス"""
    
    BASE_URL = 'https://www.boatrace.jp/owpc/pc/race'
    DEFAULT_TIMEOUT = 15  # タイムアウト秒数
    MAX_RETRIES = 2  # 最大リトライ回数
    
    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.environ.get('DATABASE_URL')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def _request_with_retry(self, url: str, timeout: int = None) -> requests.Response:
        """リトライ機能付きHTTPリクエスト"""
        timeout = timeout or self.DEFAULT_TIMEOUT
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.get(url, timeout=timeout)
                response.raise_for_status()
                return response
            except (requests.Timeout, requests.ConnectionError) as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1)  # 1秒待ってリトライ
                    continue
                raise
            except Exception as e:
                raise
        
        raise last_error
    
    def get_db_connection(self, retries=3, delay=5):
        """データベース接続を取得（リトライ機能付き）"""
        for attempt in range(retries):
            try:
                return psycopg2.connect(self.db_url)
            except psycopg2.OperationalError as e:
                if attempt < retries - 1:
                    logger.warning(f"接続失敗、{delay}秒後にリトライ... ({attempt + 1}/{retries})")
                    time.sleep(delay)
                else:
                    raise e
    
    def create_odds_table(self, conn):
        """オッズテーブルを作成"""
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS odds_history (
                    id SERIAL PRIMARY KEY,
                    race_date DATE NOT NULL,
                    stadium_code VARCHAR(2) NOT NULL,
                    race_number INTEGER NOT NULL,
                    odds_type VARCHAR(10) NOT NULL,
                    combination VARCHAR(10) NOT NULL,
                    odds_value DECIMAL(10,1),
                    odds_min DECIMAL(10,1),
                    odds_max DECIMAL(10,1),
                    scraped_at TIMESTAMP NOT NULL,
                    minutes_to_deadline INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # インデックス作成
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_odds_history_race 
                ON odds_history(race_date, stadium_code, race_number)
            ''')
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_odds_history_scraped 
                ON odds_history(scraped_at)
            ''')
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_odds_history_combination 
                ON odds_history(combination)
            ''')
            
            conn.commit()
            logger.info("オッズテーブルを作成/確認しました")
    
    def check_today_races(self) -> bool:
        """本日のレース開催をチェック"""
        today = datetime.now().strftime('%Y%m%d')
        url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={today}"
        
        try:
            response = self._request_with_retry(url)
            
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
        today = datetime.now().strftime('%Y%m%d')
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
        # オッズページには全レースの締切時刻が記載されている
        url = f"{self.BASE_URL}/odds2tf?rno=1&jcd={stadium_code}&hd={race_date}"
        
        try:
            response = self._request_with_retry(url)
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
            
            # race_dateからdatetimeオブジェクトを作成（日付を明示的に指定）
            race_date_obj = datetime.strptime(race_date, '%Y%m%d')
            
            for cell in cells:
                text = cell.get_text(strip=True)
                time_match = re.match(r'(\d{1,2}):(\d{2})', text)
                if time_match:
                    race_num += 1
                    hour, minute = int(time_match.group(1)), int(time_match.group(2))
                    # 日付はrace_dateを使用（datetime.now()ではなく）
                    deadline = race_date_obj.replace(
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
        
        try:
            response = self._request_with_retry(url)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            odds_list = []
            scraped_at = datetime.now()
            
            # テーブルを取得（Table 1が2連単、Table 2が2連複）
            tables = soup.find_all('table')
            
            for table_idx, table in enumerate(tables):
                rows = table.find_all('tr')
                if len(rows) < 2:
                    continue
                
                # 最初の行でヘッダーかどうか判断
                first_row = rows[0]
                first_cells = first_row.find_all(['th', 'td'])
                if not first_cells:
                    continue
                
                # 艇番とレーサー名のヘッダー行を探す
                has_boat_color = any('is-boatColor' in ' '.join(c.get('class', [])) for c in first_cells)
                if not has_boat_color:
                    continue
                
                # テーブルの位置で2連単/2連複を判断
                # Table 1 (index 1) = 2連単, Table 2 (index 2) = 2連複
                odds_type = '2t' if table_idx == 1 else '2f'
                
                # ヘッダー行から1着の艇番を取得（偶数番目のセルが艇番）
                first_place_boats = []
                for i, cell in enumerate(first_cells):
                    if i % 2 == 0:  # 0, 2, 4, 6, 8, 10
                        text = cell.get_text(strip=True)
                        if text.isdigit():
                            first_place_boats.append(int(text))
                
                # 各行を処理（ヘッダー以降）
                # 各行は「2着艇番, オッズ, 2着艇番, オッズ, ...」の繰り返し
                for row in rows[1:]:
                    cells = row.find_all('td')
                    if not cells:
                        continue
                    
                    # セルをペアで処理（艇番 + オッズ）
                    for pair_idx in range(0, len(cells), 2):
                        if pair_idx + 1 >= len(cells):
                            break
                        
                        boat_cell = cells[pair_idx]
                        odds_cell = cells[pair_idx + 1]
                        
                        # 2着の艇番
                        boat_text = boat_cell.get_text(strip=True)
                        if not boat_text.isdigit():
                            continue
                        second = int(boat_text)
                        
                        # オッズ値
                        odds_classes = ' '.join(odds_cell.get('class', []))
                        if 'is-disabled' in odds_classes:
                            continue
                        
                        odds_text = odds_cell.get_text(strip=True)
                        odds_value = self._parse_odds(odds_text)
                        
                        if odds_value:
                            # 1着を特定（列の位置から）
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
        
        try:
            response = self._request_with_retry(url)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            odds_list = []
            scraped_at = datetime.now()
            
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                
                # ヘッダーからオッズ種別を判断
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
                
                for row in rows[1:]:  # ヘッダーをスキップ
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        # 艇番
                        boat_num = cells[0].get_text(strip=True)
                        if not boat_num.isdigit():
                            continue
                        
                        # オッズ値
                        odds_text = cells[2].get_text(strip=True)
                        
                        if odds_type == 'win':
                            odds_value = self._parse_odds(odds_text)
                            # 0.0も有効なオッズとして保存（発売前や投票が少ない場合）
                            if odds_value is not None:
                                odds_list.append({
                                    'odds_type': 'win',
                                    'combination': boat_num,
                                    'odds_value': odds_value,
                                    'scraped_at': scraped_at
                                })
                        else:  # 複勝（範囲オッズ）
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
        
        # 2連単・2連複
        odds_2tf = self.fetch_2tf_odds(stadium_code, race_number, race_date)
        all_odds.extend(odds_2tf)
        
        # 単勝・複勝
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
        
        with conn.cursor() as cur:
            values = []
            for odds in odds_list:
                # 日付をフォーマット
                if len(race_date) == 8:
                    formatted_date = f"{race_date[:4]}-{race_date[4:6]}-{race_date[6:8]}"
                else:
                    formatted_date = race_date
                
                values.append((
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
            
            execute_values(cur, '''
                INSERT INTO odds_history (
                    race_date, stadium_code, race_number, odds_type, combination,
                    odds_value, odds_min, odds_max, scraped_at, minutes_to_deadline
                ) VALUES %s
            ''', values)
            
            conn.commit()
    
    def collect_race_odds(self, stadium_code: str, race_number: int, race_date: str,
                          deadline_time: datetime = None, high_freq_minutes: int = 5,
                          high_freq_interval: int = 10, normal_interval: int = 600) -> int:
        """
        レースのオッズを収集
        
        Args:
            stadium_code: 競艇場コード
            race_number: レース番号
            race_date: レース日（YYYYMMDD形式）
            deadline_time: 締切時刻
            high_freq_minutes: 高頻度収集開始（締切何分前から）
            high_freq_interval: 高頻度収集間隔（秒）
            normal_interval: 通常収集間隔（秒）
            
        Returns:
            収集したオッズ数
        """
        conn = self.get_db_connection()
        self.create_odds_table(conn)
        
        total_collected = 0
        stadium_name = STADIUM_CODES.get(stadium_code, stadium_code)
        
        logger.info(f"オッズ収集開始: {stadium_name} {race_number}R")
        
        try:
            while True:
                now = datetime.now()
                
                # 締切時刻を過ぎたら終了
                if deadline_time and now > deadline_time:
                    logger.info(f"締切時刻を過ぎました: {stadium_name} {race_number}R")
                    break
                
                # 締切までの残り時間を計算
                minutes_to_deadline = None
                if deadline_time:
                    delta = deadline_time - now
                    minutes_to_deadline = int(delta.total_seconds() / 60)
                
                # オッズを取得
                odds_list = self.fetch_all_odds(stadium_code, race_number, race_date)
                
                if odds_list:
                    self.save_odds(conn, race_date, stadium_code, race_number,
                                  odds_list, minutes_to_deadline)
                    total_collected += len(odds_list)
                    logger.info(f"収集: {len(odds_list)}件 (残り{minutes_to_deadline}分)")
                
                # 次の収集間隔を決定
                if deadline_time and minutes_to_deadline is not None:
                    if minutes_to_deadline <= high_freq_minutes:
                        # 締切5分前から10秒間隔
                        interval = high_freq_interval
                    else:
                        # 通常は10分間隔
                        interval = normal_interval
                else:
                    interval = normal_interval
                
                # 待機
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("収集を中断しました")
        finally:
            conn.close()
        
        logger.info(f"オッズ収集完了: {stadium_name} {race_number}R 合計 {total_collected}件")
        return total_collected
    
    def run_scheduler(self):
        """
        スケジューラーを実行
        - 毎朝8:00に開催チェック
        - 開催があれば10分間隔で監視
        - 締切5分前から10秒間隔で収集
        """
        logger.info("オッズ収集スケジューラー開始")
        
        # 運用時間: 8:00〜21:30
        start_hour = 8
        end_hour = 21
        end_minute = 30
        
        while True:
            now = datetime.now()
            
            # 運用時間外は待機
            if now.hour < start_hour:
                wait_until = now.replace(hour=start_hour, minute=0, second=0)
                wait_seconds = (wait_until - now).total_seconds()
                logger.info(f"運用時間外。{start_hour}:00まで待機します")
                time.sleep(wait_seconds)
                continue
            
            if now.hour > end_hour or (now.hour == end_hour and now.minute > end_minute):
                # 翌日の8:00まで待機
                tomorrow = now + timedelta(days=1)
                wait_until = tomorrow.replace(hour=start_hour, minute=0, second=0)
                wait_seconds = (wait_until - now).total_seconds()
                logger.info(f"運用時間終了。翌日{start_hour}:00まで待機します")
                time.sleep(wait_seconds)
                continue
            
            # 本日の開催をチェック
            if not self.check_today_races():
                # 開催なし → 翌日まで待機
                tomorrow = now + timedelta(days=1)
                wait_until = tomorrow.replace(hour=start_hour, minute=0, second=0)
                wait_seconds = (wait_until - now).total_seconds()
                logger.info(f"本日の開催なし。翌日{start_hour}:00まで待機します")
                time.sleep(wait_seconds)
                continue
            
            # レーススケジュールを取得
            races = self.get_today_race_schedule()
            
            if not races:
                # スケジュール取得失敗 → 10分後に再試行
                logger.warning("スケジュール取得失敗。10分後に再試行します")
                time.sleep(600)
                continue
            
            # 次のレースを探す
            next_race = None
            for race in races:
                deadline = race.get('deadline_time')
                if deadline and deadline > now:
                    next_race = race
                    break
            
            if not next_race:
                # 本日のレース終了 → 翌日まで待機
                logger.info("本日のレース終了")
                tomorrow = now + timedelta(days=1)
                wait_until = tomorrow.replace(hour=start_hour, minute=0, second=0)
                wait_seconds = (wait_until - now).total_seconds()
                time.sleep(wait_seconds)
                continue
            
            # 次のレースまでの時間を計算
            deadline = next_race['deadline_time']
            minutes_to_deadline = (deadline - now).total_seconds() / 60
            
            if minutes_to_deadline <= 5:
                # 締切5分以内 → 高頻度収集開始
                logger.info(f"高頻度収集開始: {next_race['stadium_name']} {next_race['race_number']}R")
                self.collect_race_odds(
                    stadium_code=next_race['stadium_code'],
                    race_number=next_race['race_number'],
                    race_date=next_race['date'],
                    deadline_time=deadline,
                    high_freq_minutes=5,
                    high_freq_interval=10
                )
            else:
                # 通常収集（1回だけ）
                odds_list = self.fetch_all_odds(
                    next_race['stadium_code'],
                    next_race['race_number'],
                    next_race['date']
                )
                
                if odds_list:
                    conn = self.get_db_connection()
                    self.create_odds_table(conn)
                    self.save_odds(
                        conn, next_race['date'],
                        next_race['stadium_code'],
                        next_race['race_number'],
                        odds_list,
                        int(minutes_to_deadline)
                    )
                    conn.close()
                    logger.info(f"通常収集: {next_race['stadium_name']} {next_race['race_number']}R {len(odds_list)}件")
                
                # 次の収集まで待機（10分または締切5分前まで）
                wait_minutes = min(10, minutes_to_deadline - 5)
                if wait_minutes > 0:
                    logger.info(f"次の収集まで{wait_minutes:.1f}分待機")
                    time.sleep(wait_minutes * 60)


    def collect_near_deadline_races(self, minutes_before: int = 5, 
                                      interval_seconds: int = 10, iterations: int = 9):
        """
        締切間近のレースのオッズを収集
        
        Args:
            minutes_before: 締切何分前のレースを対象とするか
            interval_seconds: 収集間隔（秒）
            iterations: 収集回数
        """
        conn = self.get_db_connection()
        self.create_odds_table(conn)
        
        today = datetime.now().strftime('%Y%m%d')
        races = self.get_today_race_schedule()
        
        if not races:
            logger.info("本日のレースがありません")
            conn.close()
            return
        
        # 締切minutes_before分以内のレースを取得
        now = datetime.now()
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
        
        # 指定回数収集
        for i in range(iterations):
            for race in target_races:
                deadline = race.get('deadline_time')
                now = datetime.now()
                
                # 締切を過ぎたらスキップ
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
            
            # 次の収集まで待機
            if i < iterations - 1:
                time.sleep(interval_seconds)
        
        conn.close()
        logger.info("高頻度収集完了")


def test_fetch():
    """オッズ取得テスト"""
    collector = OddsCollector()
    
    today = datetime.now().strftime('%Y%m%d')
    
    print("=== 2連単・2連複オッズ ===")
    odds_2tf = collector.fetch_2tf_odds('01', 1, today)
    print(f"取得数: {len(odds_2tf)}")
    for o in odds_2tf[:5]:
        print(f"  {o}")
    
    print("\n=== 単勝・複勝オッズ ===")
    odds_tf = collector.fetch_tf_odds('01', 1, today)
    print(f"取得数: {len(odds_tf)}")
    for o in odds_tf:
        print(f"  {o}")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python collect_odds.py test              # オッズ取得テスト")
        print("  python collect_odds.py scheduler         # スケジューラー実行")
        print("  python collect_odds.py <場コード> <R番号> [日付]  # 単発収集")
        sys.exit(1)
    
    if sys.argv[1] == 'test':
        test_fetch()
    elif sys.argv[1] == 'scheduler':
        collector = OddsCollector()
        collector.run_scheduler()
    else:
        stadium_code = sys.argv[1]
        race_number = int(sys.argv[2])
        race_date = sys.argv[3] if len(sys.argv) > 3 else datetime.now().strftime('%Y%m%d')
        
        collector = OddsCollector()
        collector.collect_race_odds(
            stadium_code=stadium_code,
            race_number=race_number,
            race_date=race_date
        )

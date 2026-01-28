'''
競艇データ収集システム - メインコレクター (MySQL/TiDB対応版)
pyjpboatraceライブラリを使用して公式サイトからデータを取得します。
'''

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
import json
import urllib.parse

import mysql.connector
from mysql.connector import Error as MySQLError
from pyjpboatrace import PyJPBoatrace

# ロギング設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 日本時間
JST = timezone(timedelta(hours=9))

# 競艇場名とコードのマッピング
STADIUM_MAP = {
    '桐生': 1, '戸田': 2, '江戸川': 3, '平和島': 4, '多摩川': 5, '浜名湖': 6,
    '蒲郡': 7, '常滑': 8, '津': 9, '三国': 10, 'びわこ': 11, '住之江': 12,
    '尼崎': 13, '鳴門': 14, '丸亀': 15, '児島': 16, '宮島': 17, '徳山': 18,
    '下関': 19, '若松': 20, '芦屋': 21, '福岡': 22, '唐津': 23, '大村': 24
}

# 逆引きマップ
STADIUM_CODE_TO_NAME = {v: k for k, v in STADIUM_MAP.items()}


def parse_database_url(url: str) -> dict:
    """DATABASE_URLをパースしてMySQL接続パラメータに変換"""
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


class BoatraceCollector:
    '''競艇データ収集クラス (MySQL/TiDB対応)'''

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.db_config = parse_database_url(database_url)
        self.boatrace = PyJPBoatrace()
        self.conn = None

    def connect_db(self):
        '''データベースに接続'''
        if self.conn is None or not self.conn.is_connected():
            self.conn = mysql.connector.connect(**self.db_config)
            logger.info("データベースに接続しました")

    def close_db(self):
        '''データベース接続を閉じる'''
        if self.conn and self.conn.is_connected():
            self.conn.close()
            logger.info("データベース接続を閉じました")

    def get_today_races(self, target_date: datetime) -> List[Dict[str, Any]]:
        '''指定日の全レース情報を取得'''
        races = []
        try:
            stadiums_info = self.boatrace.get_stadiums(d=target_date.date())
            if not stadiums_info:
                logger.info("開催中のレース情報はありませんでした。")
                return []

            for stadium_name, info in stadiums_info.items():
                if not isinstance(info, dict):
                    continue

                status = info.get("status", "")
                if "発売中" not in status:
                    continue

                stadium_code = STADIUM_MAP.get(stadium_name)
                if not stadium_code:
                    logger.warning(f"不明な競艇場名です: {stadium_name}")
                    continue

                for race_num in range(1, 13):
                    races.append({
                        "race_date": target_date.date(),
                        "stadium_code": stadium_code,
                        "race_number": race_num,
                        "title": info.get("title", ""),
                        "deadline_at": None,
                    })

        except Exception as e:
            logger.error(f"レース情報取得中にエラーが発生しました: {e}", exc_info=True)

        logger.info(f"{target_date.date()} のレース数: {len(races)}")
        return races

    def save_races(self, races: List[Dict[str, Any]]) -> Dict[tuple, int]:
        '''レース情報をDBに保存し、race_idのマッピングを返す'''
        self.connect_db()
        race_id_map = {}
        cursor = self.conn.cursor()
        
        try:
            # 既存のレースIDを先に取得
            existing_races = {}
            for race in races:
                cursor.execute(
                    "SELECT id FROM races WHERE race_date = %s AND stadium_code = %s AND race_number = %s",
                    (race['race_date'], race['stadium_code'], race['race_number'])
                )
                row = cursor.fetchone()
                key = (race['race_date'], race['stadium_code'], race['race_number'])
                if row:
                    existing_races[key] = row[0]

            # 新規レースと更新レースを分ける
            new_races_to_insert = []
            for race in races:
                key = (race['race_date'], race['stadium_code'], race['race_number'])
                if key in existing_races:
                    race_id_map[key] = existing_races[key]
                else:
                    new_races_to_insert.append(race)

            # 新規レースを一括登録
            if new_races_to_insert:
                for race in new_races_to_insert:
                    cursor.execute('''
                        INSERT INTO races (race_date, stadium_code, race_number, title, deadline_at)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', (
                        race['race_date'], race['stadium_code'], race['race_number'],
                        race['title'], race['deadline_at']
                    ))
                    race_id = cursor.lastrowid
                    key = (race['race_date'], race['stadium_code'], race['race_number'])
                    race_id_map[key] = race_id
                
                self.conn.commit()
                logger.info(f"{len(new_races_to_insert)} 件の新規レースを保存しました")
            else:
                logger.info("新規レースはありませんでした。")
        except Exception as e:
            logger.error(f"レース保存中にエラーが発生しました: {e}")
            self.conn.rollback()
        finally:
            cursor.close()

        return race_id_map

    def get_active_races(self, target_date: datetime) -> List[Dict[str, Any]]:
        '''発売中のレース一覧を取得（オッズ収集対象）'''
        active_races = []
        try:
            stadiums_info = self.boatrace.get_stadiums(d=target_date.date())
            if not stadiums_info:
                return []

            for stadium_name, info in stadiums_info.items():
                if not isinstance(info, dict):
                    continue

                status = info.get("status", "")
                if "発売中" not in status:
                    continue

                stadium_code = STADIUM_MAP.get(stadium_name)
                if not stadium_code:
                    continue

                next_race = info.get("next_race", 1)
                for race_num in range(next_race, 13):
                    active_races.append({
                        "race_date": target_date.date(),
                        "stadium_code": stadium_code,
                        "race_number": race_num,
                    })

        except Exception as e:
            logger.error(f"発売中レース取得中にエラー: {e}", exc_info=True)

        return active_races

    def collect_odds_for_race(self, target_date: datetime, stadium_code: int, race_number: int) -> Dict[str, Any]:
        '''特定レースのオッズを収集'''
        odds_data = {
            "scraped_at": datetime.now(JST),
            "exacta": {},
            "quinella": {},
            "win": {},
            "place_show": {},
        }

        try:
            # 2連単・2連複オッズ
            exacta_quinella = self.boatrace.get_odds_exacta_quinella(
                d=target_date.date(), stadium=stadium_code, race=race_number
            )
            if 'exacta' in exacta_quinella and isinstance(exacta_quinella['exacta'], dict):
                for key, value in exacta_quinella['exacta'].items():
                    if isinstance(value, (int, float)):
                        odds_data["exacta"][key] = float(value)
            if 'quinella' in exacta_quinella and isinstance(exacta_quinella['quinella'], dict):
                for key, value in exacta_quinella['quinella'].items():
                    if isinstance(value, (int, float)):
                        odds_data["quinella"][key] = float(value)

            # 単勝・複勝オッズ
            win_placeshow = self.boatrace.get_odds_win_placeshow(
                d=target_date.date(), stadium=stadium_code, race=race_number
            )
            if 'win' in win_placeshow and isinstance(win_placeshow['win'], dict):
                for key, value in win_placeshow['win'].items():
                    if isinstance(value, (int, float)):
                        odds_data["win"][key] = float(value)
            if 'place_show' in win_placeshow and isinstance(win_placeshow['place_show'], dict):
                for key, value in win_placeshow['place_show'].items():
                    if isinstance(value, list) and len(value) == 2:
                        odds_data["place_show"][key] = {
                            "min": float(value[0]),
                            "max": float(value[1])
                        }

        except Exception as e:
            logger.error(f"オッズ取得エラー (場:{stadium_code}, R:{race_number}): {e}")

        return odds_data

    def save_odds(self, race_id: int, odds_data: Dict[str, Any]):
        '''オッズデータをDBに保存'''
        self.connect_db()
        scraped_at = odds_data["scraped_at"]
        cursor = self.conn.cursor()
        
        try:
            # 2連単
            for combo, value in odds_data.get("exacta", {}).items():
                cursor.execute('''
                    INSERT INTO odds (race_id, scraped_at, odds_type, combination, odds_value, odds_min, odds_max)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    odds_value = VALUES(odds_value),
                    odds_min = VALUES(odds_min),
                    odds_max = VALUES(odds_max)
                ''', (race_id, scraped_at, 'exacta', combo, value, None, None))

            # 2連複
            for combo, value in odds_data.get("quinella", {}).items():
                cursor.execute('''
                    INSERT INTO odds (race_id, scraped_at, odds_type, combination, odds_value, odds_min, odds_max)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    odds_value = VALUES(odds_value),
                    odds_min = VALUES(odds_min),
                    odds_max = VALUES(odds_max)
                ''', (race_id, scraped_at, 'quinella', combo, value, None, None))

            # 単勝
            for combo, value in odds_data.get("win", {}).items():
                cursor.execute('''
                    INSERT INTO odds (race_id, scraped_at, odds_type, combination, odds_value, odds_min, odds_max)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    odds_value = VALUES(odds_value),
                    odds_min = VALUES(odds_min),
                    odds_max = VALUES(odds_max)
                ''', (race_id, scraped_at, 'win', combo, value, None, None))

            # 複勝
            for combo, value in odds_data.get("place_show", {}).items():
                if isinstance(value, dict):
                    cursor.execute('''
                        INSERT INTO odds (race_id, scraped_at, odds_type, combination, odds_value, odds_min, odds_max)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        odds_value = VALUES(odds_value),
                        odds_min = VALUES(odds_min),
                        odds_max = VALUES(odds_max)
                    ''', (race_id, scraped_at, 'place_show', combo, None, value.get("min"), value.get("max")))

            self.conn.commit()
            count = cursor.rowcount
            logger.info(f"race_id={race_id}: オッズを保存")
        except Exception as e:
            logger.error(f"オッズ保存エラー: {e}")
            self.conn.rollback()
        finally:
            cursor.close()

    def get_finished_races(self, target_date: datetime) -> List[Dict[str, Any]]:
        '''終了したレース一覧を取得（結果収集対象）'''
        finished_races = []
        try:
            stadiums_info = self.boatrace.get_stadiums(d=target_date.date())
            if not stadiums_info:
                return []

            for stadium_name, info in stadiums_info.items():
                if not isinstance(info, dict):
                    continue

                stadium_code = STADIUM_MAP.get(stadium_name)
                if not stadium_code:
                    continue

                next_race = info.get("next_race", 1)
                for race_num in range(1, next_race):
                    finished_races.append({
                        "race_date": target_date.date(),
                        "stadium_code": stadium_code,
                        "race_number": race_num,
                    })

        except Exception as e:
            logger.error(f"終了レース取得中にエラー: {e}", exc_info=True)

        return finished_races

    def collect_result_for_race(self, target_date: datetime, stadium_code: int, race_number: int) -> Optional[Dict[str, Any]]:
        '''特定レースの結果を収集'''
        try:
            result = self.boatrace.get_race_result(
                d=target_date.date(), stadium=stadium_code, race=race_number
            )
            if not result:
                return None

            return {
                "result": result.get("result", {}),
                "payoff": result.get("payoff", {}),
            }

        except Exception as e:
            logger.error(f"結果取得エラー (場:{stadium_code}, R:{race_number}): {e}")
            return None

    def save_result(self, race_id: int, result_data: Dict[str, Any]):
        '''レース結果をDBに保存'''
        self.connect_db()

        # 着順情報を抽出
        result_info = result_data.get("result", {})
        places = [None] * 6
        if isinstance(result_info, dict):
            for i in range(1, 7):
                boat_info = result_info.get(str(i), {})
                if isinstance(boat_info, dict):
                    places[i - 1] = boat_info.get("rank")

        cursor = self.conn.cursor()
        try:
            # race_resultsテーブルに保存
            cursor.execute('''
                INSERT INTO race_results (race_id, first_place, second_place, third_place, fourth_place, fifth_place, sixth_place)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                first_place = VALUES(first_place),
                second_place = VALUES(second_place),
                third_place = VALUES(third_place),
                fourth_place = VALUES(fourth_place),
                fifth_place = VALUES(fifth_place),
                sixth_place = VALUES(sixth_place),
                updated_at = CURRENT_TIMESTAMP
            ''', (race_id, *places))
            self.conn.commit()
            logger.info(f"race_id={race_id}: 結果を保存")

            # payoffsテーブルに保存
            payoff_info = result_data.get("payoff", {})
            for bet_type in ['win', 'exacta', 'quinella', 'quinella_place', 'trifecta', 'trio']:
                payoff_data = payoff_info.get(bet_type)
                if isinstance(payoff_data, dict):
                    combo = payoff_data.get("result", "")
                    amount = payoff_data.get("payoff", 0)
                    popularity = payoff_data.get("popularity")
                    # popularityが空文字の場合はNULLに変換
                    if popularity == '' or popularity is None:
                        popularity = None
                    if combo and amount:
                        cursor.execute('''
                            INSERT INTO payoffs (race_id, bet_type, combination, payoff, popularity)
                            VALUES (%s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                            payoff = VALUES(payoff),
                            popularity = VALUES(popularity)
                        ''', (race_id, bet_type, combo, amount, popularity))
            
            self.conn.commit()
            logger.info(f"race_id={race_id}: 払戻金を保存")
        except Exception as e:
            logger.error(f"結果保存エラー: {e}")
            self.conn.rollback()
        finally:
            cursor.close()


def run_daily_collection(database_url: str):
    '''日次収集を実行'''
    collector = BoatraceCollector(database_url)
    today = datetime.now(JST)
    races = collector.get_today_races(today)
    if races:
        collector.save_races(races)
    collector.close_db()


def run_odds_regular_collection(database_url: str):
    '''定期オッズ収集を実行'''
    collector = BoatraceCollector(database_url)
    today = datetime.now(JST)

    # まずレース情報を更新
    races = collector.get_today_races(today)
    race_id_map = {}
    if races:
        race_id_map = collector.save_races(races)

    # 発売中のレースのオッズを収集
    active_races = collector.get_active_races(today)
    logger.info(f"オッズ収集対象: {len(active_races)} レース")

    collected_count = 0
    for race in active_races:
        key = (race['race_date'], race['stadium_code'], race['race_number'])
        race_id = race_id_map.get(key)
        if not race_id:
            # race_idがない場合はDBから取得を試みる
            collector.connect_db()
            cursor = collector.conn.cursor()
            cursor.execute(
                "SELECT id FROM races WHERE race_date = %s AND stadium_code = %s AND race_number = %s",
                (race['race_date'], race['stadium_code'], race['race_number'])
            )
            row = cursor.fetchone()
            if row:
                race_id = row[0]
            cursor.close()

        if race_id:
            odds_data = collector.collect_odds_for_race(today, race['stadium_code'], race['race_number'])
            if odds_data.get("exacta") or odds_data.get("win"):
                collector.save_odds(race_id, odds_data)
                collected_count += 1

    logger.info(f"オッズ収集完了: {collected_count} レース")
    collector.close_db()


def run_result_collection(database_url: str):
    '''結果収集を実行'''
    collector = BoatraceCollector(database_url)
    today = datetime.now(JST)

    # 終了したレースの結果を収集
    finished_races = collector.get_finished_races(today)
    logger.info(f"結果収集対象: {len(finished_races)} レース")

    collected_count = 0
    for race in finished_races:
        # race_idを取得
        collector.connect_db()
        cursor = collector.conn.cursor()
        cursor.execute(
            "SELECT id FROM races WHERE race_date = %s AND stadium_code = %s AND race_number = %s",
            (race['race_date'], race['stadium_code'], race['race_number'])
        )
        row = cursor.fetchone()
        if not row:
            cursor.close()
            continue
        race_id = row[0]

        # 既に結果が保存されているかチェック
        cursor.execute("SELECT id FROM race_results WHERE race_id = %s", (race_id,))
        if cursor.fetchone():
            cursor.close()
            continue  # 既に保存済み
        cursor.close()

        result_data = collector.collect_result_for_race(today, race['stadium_code'], race['race_number'])
        if result_data:
            collector.save_result(race_id, result_data)
            collected_count += 1

    logger.info(f"結果収集完了: {collected_count} レース")
    collector.close_db()

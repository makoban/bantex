競艇データ収集システム - メインコレクター
pyjpboatraceライブラリを使用して公式サイトからデータを取得します。
'''

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
import json

import psycopg2
from psycopg2.extras import execute_values, Json
from pyjpboatrace import PyJPBoatrace
import requests
from bs4 import BeautifulSoup
import re

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


class BoatraceCollector:
    '''競艇データ収集クラス'''

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.boatrace = PyJPBoatrace()
        self.conn = None

    def connect_db(self):
        '''データベースに接続'''
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(self.database_url)
            logger.info("データベースに接続しました")

    def close_db(self):
        '''データベース接続を閉じる'''
        if self.conn and not self.conn.closed:
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
                # infoが辞書型でない場合（例: 'date'キー）、スキップ
                if not isinstance(info, dict):
                    continue

                # statusが発売中でない場合はスキップ
                status = info.get("status", "")
                if "発売中" not in status:
                    continue

                stadium_code = STADIUM_MAP.get(stadium_name)
                if not stadium_code:
                    logger.warning(f"不明な競艇場名です: {stadium_name}")
                    continue

                # 締切時刻を取得
                deadlines = self.get_race_deadlines(target_date, stadium_code)

                # この場は開催中、各レースの情報を取得
                for race_num in range(1, 13):
                    races.append({
                        "race_date": target_date.date(),
                        "stadium_code": stadium_code,
                        "race_number": race_num,
                        "title": info.get("title", ""),
                        "deadline_at": deadlines.get(race_num),
                    })

        except Exception as e:
            logger.error(f"レース情報取得中にエラーが発生しました: {e}", exc_info=True)

        logger.info(f"{target_date.date()} のレース数: {len(races)}")
        return races

    def get_race_deadlines(self, target_date: datetime, stadium_code: int) -> Dict[int, datetime]:
        '''公式サイトから各レースの締切時刻を取得'''
        deadlines = {}
        try:
            url = f'https://www.boatrace.jp/owpc/pc/race/raceindex?jcd={stadium_code:02d}&hd={target_date.strftime("%Y%m%d")}'
            logger.info(f"URL created: {url}")
            response = requests.get(url, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')

            # 各レースの行を探す
            race_rows = soup.select('table tr')
            for row in race_rows:
                cells = row.select('td')
                if len(cells) >= 2:
                    race_text = cells[0].text.strip()
                    time_text = cells[1].text.strip()

                    # レース番号を抽出
                    race_match = re.match(r'(\d+)R', race_text)
                    if race_match:
                        race_num = int(race_match.group(1))
                        # 時刻を抽出
                        time_match = re.match(r'(\d{1,2}):(\d{2})', time_text)
                        if time_match:
                            hour = int(time_match.group(1))
                            minute = int(time_match.group(2))
                            deadline = target_date.replace(
                                hour=hour, minute=minute, second=0, microsecond=0,
                                tzinfo=JST
                            )
                            deadlines[race_num] = deadline

            logger.info(f"場{stadium_code}: {len(deadlines)}件の締切時刻を取得")
        except Exception as e:
            logger.warning(f"締切時刻取得エラー (場:{stadium_code}): {e}")

        return deadlines

    def save_races(self, races: List[Dict[str, Any]]) -> Dict[tuple, int]:
        '''レース情報をDBに保存し、race_idのマッピングを返す'''
        self.connect_db()
        race_id_map = {}
        with self.conn.cursor() as cur:
            # 既存のレースIDを先に取得
            existing_races = {}
            race_keys = [(r['race_date'], r['stadium_code'], r['race_number']) for r in races]
            if not race_keys:
                logger.info("保存対象のレースはありませんでした。")
                return {}

            cur.execute(
                "SELECT id, race_date, stadium_code, race_number FROM races WHERE (race_date, stadium_code, race_number) IN %s",
                (tuple(race_keys),)
            )
            for row in cur.fetchall():
                key = (row[1], row[2], row[3])
                existing_races[key] = row[0]

            # 新規レースと更新レースを分ける
            new_races_to_insert = []
            races_to_update = []
            for race in races:
                key = (race['race_date'], race['stadium_code'], race['race_number'])
                if key in existing_races:
                    race_id_map[key] = existing_races[key]
                    # 締切時刻があれば更新対象に追加
                    if race.get('deadline_at'):
                        races_to_update.append({
                            'id': existing_races[key],
                            'deadline_at': race['deadline_at']
                        })
                else:
                    new_races_to_insert.append(race)

            # 既存レースの締切時刻を更新
            if races_to_update:
                try:
                    for race in races_to_update:
                        cur.execute(
                            "UPDATE races SET deadline_at = %s WHERE id = %s AND deadline_at IS NULL",
                            (race['deadline_at'], race['id'])
                        )
                    self.conn.commit()
                    logger.info(f"{len(races_to_update)} 件のレースの締切時刻を更新しました")
                except Exception as e:
                    logger.error(f"締切時刻の更新中にエラーが発生しました: {e}")
                    self.conn.rollback()

            # 新規レースを一括登録
            if new_races_to_insert:
                insert_query = (
                    "INSERT INTO races (race_date, stadium_code, race_number, title, deadline_at) "
                    "VALUES %s RETURNING id, race_date, stadium_code, race_number"
                )
                values = [
                    (
                        r['race_date'], r['stadium_code'], r['race_number'],
                        r['title'], r['deadline_at']
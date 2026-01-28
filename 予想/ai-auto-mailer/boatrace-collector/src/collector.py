'''
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
        '''指定日の全レース情報を取得（公式サイトから直接取得）'''
        races = []
        date_str = target_date.strftime('%Y%m%d')

        try:
            # 公式サイトから開催場一覧を取得
            url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={date_str}"
            logger.info(f"URL created: {url}")
            response = requests.get(url, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')

            # 開催場のリンクを抽出（jcdパラメータから場コードを取得）
            stadium_codes = set()
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                if 'raceindex' in href and 'jcd=' in href:
                    # jcd=XX を抽出
                    match = re.search(r'jcd=(\d+)', href)
                    if match:
                        stadium_codes.add(int(match.group(1)))

            if not stadium_codes:
                logger.info("開催中のレース情報はありませんでした。")
                return []

            logger.info(f"開催場を検出: {sorted(stadium_codes)}")

            for stadium_code in sorted(stadium_codes):
                # 締切時刻を取得
                deadlines = self.get_race_deadlines(target_date, stadium_code)

                # この場の各レースの情報を取得
                for race_num in range(1, 13):
                    races.append({
                        "race_date": target_date.date(),
                        "stadium_code": stadium_code,
                        "race_number": race_num,
                        "title": "",  # タイトルは別途取得可能だが省略
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
                    ) for r in new_races_to_insert
                ]
                try:
                    inserted_rows = execute_values(cur, insert_query, values, fetch=True)
                    self.conn.commit()
                    for row in inserted_rows:
                        key = (row[1], row[2], row[3])
                        race_id_map[key] = row[0]
                    logger.info(f"{len(inserted_rows)} 件の新規レースを保存しました")
                except Exception as e:
                    logger.error(f"新規レースの保存中にエラーが発生しました: {e}")
                    self.conn.rollback()
            else:
                logger.info("新規レースはありませんでした。")

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

                # next_raceから最終レース(12R)までがオッズ収集対象
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
            "trifecta": {},
            "trio": {},
            "exacta": {},
            "quinella": {},
            "win": {},
            "place_show": {},
        }

        try:
            # 3連単オッズ（データ量削減のため収集を無効化）
            # trifecta = self.boatrace.get_odds_trifecta(
            #     d=target_date.date(), stadium=stadium_code, race=race_number
            # )
            # for key, value in trifecta.items():
            #     if key not in ['update', 'date', 'stadium', 'race'] and isinstance(value, (int, float)):
            #         odds_data["trifecta"][key] = float(value)

            # 3連複オッズ（データ量削減のため収集を無効化）
            # trio = self.boatrace.get_odds_trio(
            #     d=target_date.date(), stadium=stadium_code, race=race_number
            # )
            # for key, value in trio.items():
            #     if key not in ['update', 'date', 'stadium', 'race'] and isinstance(value, (int, float)):
            #         odds_data["trio"][key] = float(value)

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
        records = []

        # 3連単（データ量削減のため収集を無効化）
        # for combo, value in odds_data.get("trifecta", {}).items():
        #     records.append((race_id, scraped_at, 'trifecta', combo, value, None, None))

        # 3連複（データ量削減のため収集を無効化）
        # for combo, value in odds_data.get("trio", {}).items():
        #     records.append((race_id, scraped_at, 'trio', combo, value, None, None))

        # 2連単
        for combo, value in odds_data.get("exacta", {}).items():
            records.append((race_id, scraped_at, 'exacta', combo, value, None, None))

        # 2連複
        for combo, value in odds_data.get("quinella", {}).items():
            records.append((race_id, scraped_at, 'quinella', combo, value, None, None))

        # 単勝
        for combo, value in odds_data.get("win", {}).items():
            records.append((race_id, scraped_at, 'win', combo, value, None, None))

        # 複勝
        for combo, value in odds_data.get("place_show", {}).items():
            if isinstance(value, dict):
                records.append((race_id, scraped_at, 'place_show', combo, None, value.get("min"), value.get("max")))

        if not records:
            return

        with self.conn.cursor() as cur:
            insert_query = '''
                INSERT INTO odds (race_id, scraped_at, odds_type, combination, odds_value, odds_min, odds_max)
                VALUES %s
                ON CONFLICT (race_id, scraped_at, odds_type, combination) DO UPDATE
                SET odds_value = EXCLUDED.odds_value,
                    odds_min = EXCLUDED.odds_min,
                    odds_max = EXCLUDED.odds_max
            '''
            try:
                execute_values(cur, insert_query, records)
                self.conn.commit()
                logger.info(f"race_id={race_id}: {len(records)} 件のオッズを保存")
            except Exception as e:
                logger.error(f"オッズ保存エラー: {e}")
                self.conn.rollback()

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

                # next_raceより前のレースが終了済み
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

    def collect_result_for_race(self, stadium_code: int, race_number: int, target_date: datetime) -> Optional[Dict]:
        '''特定レースの結果を収集（直接スクレイピング版）'''
        try:
            # 公式サイトから直接スクレイピング
            date_str = target_date.strftime('%Y%m%d')
            url = f"https://www.boatrace.jp/owpc/pc/race/raceresult?rno={race_number}&jcd={stadium_code:02d}&hd={date_str}"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            # 「データがありません」チェック
            if 'データがありません' in response.text:
                logger.info(f"結果なし (場:{stadium_code}, R:{race_number}): データがありません")
                return None

            soup = BeautifulSoup(response.text, 'html.parser')

            result_data = {
                "result": {},
                "payoff": {}
            }

            # 着順テーブルを探す（class='is-w495'で7行のテーブル）
            tables = soup.find_all('table')
            result_table = None
            for table in tables:
                table_class = table.get('class', [])
                if 'is-w495' in table_class:
                    rows = table.find_all('tr')
                    if len(rows) == 7:  # ヘッダー + 6艇
                        header = rows[0].find_all(['td', 'th'])
                        if len(header) >= 4 and '着' in header[0].get_text(strip=True):
                            result_table = table
                            break

            if result_table:
                rows = result_table.find_all('tr')
                for row in rows[1:]:  # ヘッダーをスキップ
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 4:
                        first_cell_text = cells[0].get_text(strip=True)
                        # 着順を探す（１、２、３、４、５、６）
                        rank_map = {'１': 1, '２': 2, '３': 3, '４': 4, '５': 5, '６': 6}
                        if first_cell_text in rank_map:
                            rank = rank_map[first_cell_text]
                            waku = cells[1].get_text(strip=True)
                            if waku.isdigit():
                                boat_num = int(waku)

                                # ボートレーサー列から登番を抽出（4桁数字）
                                racer_text = cells[2].get_text(strip=True)
                                racer_no_match = re.match(r'(\d{4})', racer_text)
                                racer_no = racer_no_match.group(1) if racer_no_match else ''

                                # レースタイムを取得
                                race_time = cells[3].get_text(strip=True)
                                # タイムが空の場合は空文字
                                if not race_time or race_time == '-':
                                    race_time = ''

                                result_data["result"][str(boat_num)] = {
                                    "rank": rank,
                                    "racer_no": racer_no,
                                    "race_time": race_time
                                }

            # 払戻金テーブルを探す
            # rowspan対応: 複勝・ワイドは複数行に分かれ、2行目以降は勝式セルがない
            last_bet_type = None  # 前回の勝式を記憶
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:  # 最低2セル（組番、払戻金）があれば処理
                        bet_type_text = cells[0].get_text(strip=True)

                        # 勝式を判定（日本語表記に統一）
                        bet_type = None
                        if '3連単' in bet_type_text:
                            bet_type = '3連単'
                        elif '3連複' in bet_type_text:
                            bet_type = '3連複'
                        elif '2連単' in bet_type_text:
                            bet_type = '2連単'
                        elif '2連複' in bet_type_text:
                            bet_type = '2連複'
                        elif '単勝' in bet_type_text:
                            bet_type = '単勝'
                        elif '複勝' in bet_type_text:
                            bet_type = '複勝'
                        elif '拡連複' in bet_type_text or 'ワイド' in bet_type_text:
                            bet_type = 'ワイド'

                        # 勝式が見つかった場合、記憶して処理
                        if bet_type:
                            last_bet_type = bet_type
                            # 組番と払戻金を取得（セル[1]とセル[2]）
                            if len(cells) >= 3:
                                combination = cells[1].get_text(strip=True).replace('\n', '').replace(' ', '')
                                payout_text = cells[2].get_text(strip=True)
                                popularity = None
                                if len(cells) >= 4:
                                    pop_text = cells[3].get_text(strip=True)
                                    if pop_text.isdigit():
                                        popularity = int(pop_text)
                        # 勝式セルがないがlast_bet_typeが複勝・ワイドの場合、継続行として処理
                        elif last_bet_type in ['複勝', 'ワイド'] and len(cells) >= 2:
                            bet_type = last_bet_type
                            # rowspanの継続行: セル[0]が組番、セル[1]が払戻金
                            combination = cells[0].get_text(strip=True).replace('\n', '').replace(' ', '')
                            payout_text = cells[1].get_text(strip=True)
                            popularity = None
                            if len(cells) >= 3:
                                pop_text = cells[2].get_text(strip=True)
                                if pop_text.isdigit():
                                    popularity = int(pop_text)
                        else:
                            # 勝式が判定できない場合はリセット
                            if not bet_type_text.replace('-', '').replace('=', '').isdigit():
                                last_bet_type = None
                            continue

                        # 払戻金を数値に変換
                        payout_match = re.search(r'[\d,]+', payout_text.replace('¥', '').replace(',', ''))
                        if payout_match:
                            payout = int(payout_match.group().replace(',', ''))

                            result_data["payoff"][bet_type] = {
                                "result": combination,
                                "payoff": payout,
                                "popularity": popularity
                            }
                            # 複勝・ワイドはリストとしても保存（複数組の場合に対応）
                            if bet_type in ['複勝', 'ワイド']:
                                if bet_type + '_list' not in result_data["payoff"]:
                                    result_data["payoff"][bet_type + '_list'] = []
                                result_data["payoff"][bet_type + '_list'].append({
                                    "result": combination,
                                    "payoff": payout,
                                    "popularity": popularity
                                })

            # 結果が取得できたかチェック
            if result_data["result"]:
                logger.info(f"結果取得成功 (場:{stadium_code}, R:{race_number})")
                return result_data

            logger.warning(f"結果パース失敗 (場:{stadium_code}, R:{race_number})")
            return None

        except Exception as e:
            logger.error(f"結果取得エラー (場:{stadium_code}, R:{race_number}): {e}")
            return None

    def save_result(self, race_id: int, result_data: Dict[str, Any], race_date: str = None, stadium_code: int = None, race_number: int = None):
        '''レース結果をDBに保存'''
        self.connect_db()

        # 着順情報を抽出
        # result_infoは {boat_num: {"rank": rank, "racer_no": "1234", "race_time": "1'52\"0"}} の形式
        # placesは [1着の艇番, 2着の艇番, ...] の形式で保存
        result_info = result_data.get("result", {})
        places = [None] * 6
        historical_results = []  # historical_race_results用のデータ

        if isinstance(result_info, dict):
            # 艇番をキー、着順を値として取得し、着順をキーに艇番を値に変換
            for boat_num_str, boat_info in result_info.items():
                if isinstance(boat_info, dict):
                    rank = boat_info.get("rank")
                    if rank and 1 <= rank <= 6:
                        boat_num = int(boat_num_str)
                        places[rank - 1] = boat_num

                        # historical_race_results用のデータを作成
                        if race_date and stadium_code and race_number:
                            historical_results.append({
                                'race_date': race_date,
                                'stadium_code': str(stadium_code).zfill(2),
                                'race_no': str(race_number).zfill(2),
                                'boat_no': boat_num_str,
                                'racer_no': boat_info.get('racer_no', ''),
                                'rank': str(rank),
                                'race_time': boat_info.get('race_time', '')
                            })

        with self.conn.cursor() as cur:
            # race_resultsテーブルに保存
            try:
                cur.execute('''
                    INSERT INTO race_results (race_id, first_place, second_place, third_place, fourth_place, fifth_place, sixth_place)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (race_id) DO UPDATE
                    SET first_place = EXCLUDED.first_place,
                        second_place = EXCLUDED.second_place,
                        third_place = EXCLUDED.third_place,
                        fourth_place = EXCLUDED.fourth_place,
                        fifth_place = EXCLUDED.fifth_place,
                        sixth_place = EXCLUDED.sixth_place,
                        updated_at = CURRENT_TIMESTAMP
                ''', (race_id, *places))
                self.conn.commit()
                logger.info(f"race_id={race_id}: 結果を保存")
            except Exception as e:
                logger.error(f"結果保存エラー: {e}")
                self.conn.rollback()

            # payoffsテーブルに保存
            payoff_info = result_data.get("payoff", {})
            payoff_records = []
            for bet_type in ['単勝', '複勝', '2連単', '2連複', 'ワイド', '3連単', '3連複']:
                # 複勝・ワイドはリストから取得（複数組対応）
                if bet_type in ['複勝', 'ワイド']:
                    payoff_list = payoff_info.get(bet_type + '_list', [])
                    if payoff_list:
                        for item in payoff_list:
                            combo = item.get("result", "")
                            amount = item.get("payoff", 0)
                            popularity = item.get("popularity")
                            if popularity == "" or popularity is None:
                                popularity = None
                            else:
                                try:
                                    popularity = int(popularity)
                                except (ValueError, TypeError):
                                    popularity = None
                            if combo and amount:
                                payoff_records.append((race_id, bet_type, combo, amount, popularity))
                        continue  # リストから取得した場合はスキップ

                payoff_data = payoff_info.get(bet_type)
                if isinstance(payoff_data, dict):
                    combo = payoff_data.get("result", "")
                    amount = payoff_data.get("payoff", 0)
                    popularity = payoff_data.get("popularity")
                    # popularityが空文字の場合はNULLに変換
                    if popularity == "" or popularity is None:
                        popularity = None
                    else:
                        try:
                            popularity = int(popularity)
                        except (ValueError, TypeError):
                            popularity = None
                    if combo and amount:
                        payoff_records.append((race_id, bet_type, combo, amount, popularity))

            if payoff_records:
                try:
                    execute_values(cur, '''
                        INSERT INTO payoffs (race_id, bet_type, combination, payoff, popularity)
                        VALUES %s
                        ON CONFLICT (race_id, bet_type, combination) DO UPDATE
                        SET payoff = EXCLUDED.payoff,
                            popularity = EXCLUDED.popularity
                    ''', payoff_records)
                    self.conn.commit()
                    logger.info(f"race_id={race_id}: {len(payoff_records)} 件の払戻金を保存")
                except Exception as e:
                    logger.error(f"払戻金保存エラー: {e}")
                    self.conn.rollback()

            # historical_race_resultsテーブルにも保存（登番、タイム含む）
            if historical_results:
                try:
                    # テーブルが存在しない場合は作成
                    cur.execute('''
                        CREATE TABLE IF NOT EXISTS historical_race_results (
                            id SERIAL PRIMARY KEY,
                            race_date VARCHAR(8) NOT NULL,
                            stadium_code VARCHAR(2) NOT NULL,
                            race_no VARCHAR(2) NOT NULL,
                            boat_no VARCHAR(1),
                            racer_no VARCHAR(4),
                            rank VARCHAR(2),
                            race_time VARCHAR(10),
                            created_at TIMESTAMP DEFAULT NOW(),
                            UNIQUE(race_date, stadium_code, race_no, boat_no)
                        )
                    ''')

                    for hr in historical_results:
                        cur.execute('''
                            INSERT INTO historical_race_results
                            (race_date, stadium_code, race_no, boat_no, racer_no, rank, race_time)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (race_date, stadium_code, race_no, boat_no) DO UPDATE
                            SET racer_no = EXCLUDED.racer_no,
                                rank = EXCLUDED.rank,
                                race_time = EXCLUDED.race_time
                        ''', (hr['race_date'], hr['stadium_code'], hr['race_no'],
                              hr['boat_no'], hr['racer_no'], hr['rank'], hr['race_time']))

                    self.conn.commit()
                    logger.info(f"race_id={race_id}: {len(historical_results)} 件の詳細結果をhistorical_race_resultsに保存")
                except Exception as e:
                    logger.error(f"historical_race_results保存エラー: {e}")
                    self.conn.rollback()


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
            with collector.conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM races WHERE race_date = %s AND stadium_code = %s AND race_number = %s",
                    (race['race_date'], race['stadium_code'], race['race_number'])
                )
                row = cur.fetchone()
                if row:
                    race_id = row[0]

        if race_id:
            odds_data = collector.collect_odds_for_race(today, race['stadium_code'], race['race_number'])
            # 2連単または単勝オッズが取得できた場合のみ保存（3連は使わない）
            if odds_data.get("exacta") or odds_data.get("win"):
                collector.save_odds(race_id, odds_data)
                collected_count += 1

    logger.info(f"オッズ収集完了: {collected_count} レース")
    collector.close_db()


def run_result_collection(database_url: str, target_date: datetime = None):
    '''結果収集を実行（DBベースで結果未取得のレースを収集）'''
    collector = BoatraceCollector(database_url)

    if target_date is None:
        target_date = datetime.now(JST)

    # DBから結果未取得のレースを取得（締切時刻を過ぎたもの）
    # deadline_atはJSTで保存されているので、現在時刻もJSTで比較
    now_jst = datetime.now(JST)

    # 日付を文字列に変換（PostgreSQLの型変換問題を回避）
    target_date_str = target_date.strftime('%Y-%m-%d')
    logger.info(f"結果収集対象日: {target_date_str}")

    collector.connect_db()
    with collector.conn.cursor() as cur:
        cur.execute('''
            SELECT r.id, r.race_date, r.stadium_code, r.race_number
            FROM races r
            LEFT JOIN race_results rr ON r.id = rr.race_id
            WHERE r.race_date = %s::date
            AND r.deadline_at < %s
            AND (rr.id IS NULL OR rr.first_place IS NULL)
            ORDER BY r.stadium_code, r.race_number
        ''', (target_date_str, now_jst))

        races_to_collect = cur.fetchall()

    logger.info(f"結果収集対象: {len(races_to_collect)} レース")

    collected_count = 0
    for race_id, race_date, stadium_code, race_number in races_to_collect:
        # 結果を取得
        result_data = collector.collect_result_for_race(stadium_code, race_number, target_date)
        if result_data:
            # race_dateをYYYYMMDD形式の文字列に変換
            race_date_str = race_date.strftime('%Y%m%d') if hasattr(race_date, 'strftime') else str(race_date).replace('-', '')
            collector.save_result(race_id, result_data, race_date_str, stadium_code, race_number)
            collected_count += 1

    logger.info(f"結果収集完了: {collected_count} レース")
    collector.close_db()

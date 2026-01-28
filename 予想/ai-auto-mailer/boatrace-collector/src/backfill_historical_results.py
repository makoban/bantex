"""
2026年1月17日以降の欠落データ（登番、タイム）を補正するスクリプト
公式サイトから再スクレイピングしてhistorical_race_resultsテーブルに保存
"""

import os
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from bs4 import BeautifulSoup

# ロギング設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 日本時間
JST = timezone(timedelta(hours=9))


def fetch_race_result(stadium_code: int, race_number: int, race_date: str) -> Dict[str, Any]:
    """
    公式サイトからレース結果を取得
    race_date: YYYYMMDD形式
    """
    url = f'https://www.boatrace.jp/owpc/pc/race/raceresult?rno={race_number}&jcd={stadium_code:02d}&hd={race_date}'
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        result_data = {"result": {}}
        
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
                            if not race_time or race_time == '-':
                                race_time = ''
                            
                            result_data["result"][str(boat_num)] = {
                                "rank": rank,
                                "racer_no": racer_no,
                                "race_time": race_time
                            }
            
            return result_data
        
        return None
    
    except Exception as e:
        logger.error(f"結果取得エラー (場:{stadium_code}, R:{race_number}, 日:{race_date}): {e}")
        return None


def backfill_historical_results(database_url: str, start_date: str = '2026-01-17'):
    """
    指定日以降のレース結果をhistorical_race_resultsに補正
    """
    conn = psycopg2.connect(database_url)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
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
    conn.commit()
    
    # 対象レースを取得（race_resultsに結果があるもの）
    cur.execute('''
        SELECT r.id, r.race_date, r.stadium_code, r.race_number
        FROM races r
        INNER JOIN race_results rr ON r.id = rr.race_id
        WHERE r.race_date >= %s::date
        AND rr.first_place IS NOT NULL
        ORDER BY r.race_date, r.stadium_code, r.race_number
    ''', (start_date,))
    
    races = cur.fetchall()
    logger.info(f"補正対象: {len(races)} レース")
    
    # 既にhistorical_race_resultsにあるレースを確認
    cur.execute('''
        SELECT DISTINCT race_date, stadium_code, race_no
        FROM historical_race_results
        WHERE race_date >= %s
    ''', (start_date.replace('-', ''),))
    
    existing = set()
    for row in cur.fetchall():
        key = (row['race_date'], row['stadium_code'], row['race_no'])
        existing.add(key)
    
    logger.info(f"既存データ: {len(existing)} レース")
    
    # 補正実行
    backfilled_count = 0
    for race in races:
        race_date_str = race['race_date'].strftime('%Y%m%d') if hasattr(race['race_date'], 'strftime') else str(race['race_date']).replace('-', '')
        stadium_code_str = str(race['stadium_code']).zfill(2)
        race_no_str = str(race['race_number']).zfill(2)
        
        key = (race_date_str, stadium_code_str, race_no_str)
        if key in existing:
            continue
        
        # 公式サイトから結果を取得
        result_data = fetch_race_result(race['stadium_code'], race['race_number'], race_date_str)
        
        if result_data and result_data.get('result'):
            for boat_num_str, boat_info in result_data['result'].items():
                try:
                    cur.execute('''
                        INSERT INTO historical_race_results 
                        (race_date, stadium_code, race_no, boat_no, racer_no, rank, race_time)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (race_date, stadium_code, race_no, boat_no) DO UPDATE
                        SET racer_no = EXCLUDED.racer_no,
                            rank = EXCLUDED.rank,
                            race_time = EXCLUDED.race_time
                    ''', (race_date_str, stadium_code_str, race_no_str,
                          boat_num_str, boat_info.get('racer_no', ''),
                          str(boat_info.get('rank', '')), boat_info.get('race_time', '')))
                except Exception as e:
                    logger.error(f"保存エラー: {e}")
                    conn.rollback()
                    continue
            
            conn.commit()
            backfilled_count += 1
            
            if backfilled_count % 50 == 0:
                logger.info(f"進捗: {backfilled_count} レース補正完了")
    
    logger.info(f"補正完了: {backfilled_count} レース")
    
    conn.close()


if __name__ == '__main__':
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL環境変数が設定されていません")
        exit(1)
    
    # 2026年1月17日以降のデータを補正
    backfill_historical_results(database_url, '2026-01-17')

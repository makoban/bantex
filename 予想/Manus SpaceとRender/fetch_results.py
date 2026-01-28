#!/usr/bin/env python3
"""
公式サイトから直接レース結果を取得してDBに保存するスクリプト
pyjpboatraceの日付チェックをバイパスして、直接スクレイピング
"""

import os
import re
import sys
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_values

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# DB接続
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging')

# 場コード
STADIUM_CODES = {
    '01': '桐生', '02': '戸田', '03': 'ボートレース江戸川', '04': '平和島',
    '05': '多摩川', '06': '浜名湖', '07': '蒲郡', '08': '常滑',
    '09': '津', '10': '三国', '11': 'びわこ', '12': '住之江',
    '13': '尼崎', '14': '鳴門', '15': '丸亀', '16': '児島',
    '17': '宮島', '18': '徳山', '19': '下関', '20': '若松',
    '21': '芦屋', '22': '福岡', '23': '唐津', '24': '大村'
}


def get_db_connection():
    """DB接続を取得"""
    return psycopg2.connect(DATABASE_URL)


def fetch_race_result(stadium_code: str, race_number: int, race_date: str) -> dict:
    """
    公式サイトからレース結果を取得
    
    Args:
        stadium_code: 場コード（01-24）
        race_number: レース番号（1-12）
        race_date: 日付（YYYYMMDD形式）
    
    Returns:
        結果辞書 or None
    """
    url = f"https://www.boatrace.jp/owpc/pc/race/raceresult?rno={race_number}&jcd={stadium_code}&hd={race_date}"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 「データがありません」チェック
        if 'データがありません' in response.text:
            return None
        
        result = {
            'stadium_code': stadium_code,
            'race_number': race_number,
            'race_date': race_date,
            'first_place': None,
            'second_place': None,
            'third_place': None,
            'payoffs': []
        }
        
        # 着順テーブルを探す
        # 着順は「着」「枠」「ボートレーサー」「レースタイム」のテーブル
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    # 着順を探す
                    first_cell_text = cells[0].get_text(strip=True)
                    if first_cell_text == '１':
                        # 2番目のセルが枠番
                        waku = cells[1].get_text(strip=True)
                        if waku.isdigit():
                            result['first_place'] = int(waku)
                    elif first_cell_text == '２':
                        waku = cells[1].get_text(strip=True)
                        if waku.isdigit():
                            result['second_place'] = int(waku)
                    elif first_cell_text == '３':
                        waku = cells[1].get_text(strip=True)
                        if waku.isdigit():
                            result['third_place'] = int(waku)
        
        # 払戻金テーブルを探す
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    bet_type_text = cells[0].get_text(strip=True)
                    
                    # 勝式を判定
                    bet_type = None
                    if '3連単' in bet_type_text:
                        bet_type = 'trifecta'
                    elif '3連複' in bet_type_text:
                        bet_type = 'trio'
                    elif '2連単' in bet_type_text:
                        bet_type = 'exacta'
                    elif '2連複' in bet_type_text:
                        bet_type = 'quinella'
                    elif '単勝' in bet_type_text:
                        bet_type = 'win'
                    elif '複勝' in bet_type_text:
                        bet_type = 'place'
                    elif '拡連複' in bet_type_text:
                        bet_type = 'wide'
                    
                    if bet_type:
                        # 組番と払戻金を取得
                        combination = cells[1].get_text(strip=True).replace('\n', '').replace(' ', '')
                        payout_text = cells[2].get_text(strip=True)
                        
                        # 払戻金を数値に変換
                        payout_match = re.search(r'[\d,]+', payout_text.replace('¥', '').replace(',', ''))
                        if payout_match:
                            payout = int(payout_match.group().replace(',', ''))
                            result['payoffs'].append({
                                'bet_type': bet_type,
                                'combination': combination,
                                'payout': payout
                            })
        
        # 結果が取得できたかチェック
        if result['first_place'] and result['second_place'] and result['third_place']:
            return result
        
        return None
        
    except Exception as e:
        logger.error(f"結果取得エラー ({stadium_code} {race_number}R): {e}")
        return None


def save_result_to_db(conn, result: dict):
    """結果をDBに保存"""
    cursor = conn.cursor()
    
    try:
        # race_idを取得
        race_date = f"{result['race_date'][:4]}-{result['race_date'][4:6]}-{result['race_date'][6:8]}"
        cursor.execute("""
            SELECT id FROM races 
            WHERE race_date = %s 
            AND stadium_code = %s 
            AND race_number = %s
        """, (race_date, result['stadium_code'], result['race_number']))
        
        row = cursor.fetchone()
        if not row:
            logger.warning(f"レースが見つかりません: {result['stadium_code']} {result['race_number']}R {race_date}")
            return False
        
        race_id = row[0]
        
        # race_resultsを更新
        cursor.execute("""
            UPDATE race_results 
            SET first_place = %s, second_place = %s, third_place = %s, updated_at = NOW()
            WHERE race_id = %s
        """, (result['first_place'], result['second_place'], result['third_place'], race_id))
        
        if cursor.rowcount == 0:
            # レコードがない場合は挿入
            cursor.execute("""
                INSERT INTO race_results (race_id, first_place, second_place, third_place, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
            """, (race_id, result['first_place'], result['second_place'], result['third_place']))
        
        # 払戻金を保存
        for payoff in result['payoffs']:
            # 既存のpayoffを確認
            cursor.execute("""
                SELECT id FROM payoffs 
                WHERE race_id = %s AND bet_type = %s AND combination = %s
            """, (race_id, payoff['bet_type'], payoff['combination']))
            
            if cursor.fetchone():
                cursor.execute("""
                    UPDATE payoffs 
                    SET payout = %s, updated_at = NOW()
                    WHERE race_id = %s AND bet_type = %s AND combination = %s
                """, (payoff['payout'], race_id, payoff['bet_type'], payoff['combination']))
            else:
                cursor.execute("""
                    INSERT INTO payoffs (race_id, bet_type, combination, payout, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                """, (race_id, payoff['bet_type'], payoff['combination'], payoff['payout']))
        
        conn.commit()
        logger.info(f"結果保存: {result['stadium_code']} {result['race_number']}R - {result['first_place']}-{result['second_place']}-{result['third_place']}")
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"DB保存エラー: {e}")
        return False


def fetch_all_results_for_date(race_date: str):
    """指定日の全レース結果を取得"""
    logger.info(f"=== {race_date} の結果取得開始 ===")
    
    # DBから該当日のレース一覧を取得
    conn = get_db_connection()
    cursor = conn.cursor()
    formatted_date = f"{race_date[:4]}-{race_date[4:6]}-{race_date[6:8]}"
    
    cursor.execute("""
        SELECT DISTINCT stadium_code, race_number 
        FROM races 
        WHERE race_date = %s
        ORDER BY stadium_code, race_number
    """, (formatted_date,))
    
    races = cursor.fetchall()
    conn.close()
    
    logger.info(f"対象レース数: {len(races)}")
    
    success_count = 0
    for stadium_code, race_number in races:
        result = fetch_race_result(stadium_code, race_number, race_date)
        if result:
            # 各レースごとにDB接続を作成
            try:
                conn = get_db_connection()
                if save_result_to_db(conn, result):
                    success_count += 1
                conn.close()
            except Exception as e:
                logger.error(f"DB接続エラー: {e}")
    
    logger.info(f"=== 結果取得完了: {success_count}/{len(races)} レース ===")


def main():
    if len(sys.argv) < 2:
        # デフォルトは今日の日付
        target_date = datetime.now().strftime('%Y%m%d')
    else:
        target_date = sys.argv[1]
    
    fetch_all_results_for_date(target_date)


if __name__ == '__main__':
    main()

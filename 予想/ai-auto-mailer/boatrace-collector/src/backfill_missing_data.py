#!/usr/bin/env python3
"""
不足分のレース結果・払戻金データをスクレイピングで取得してDBに保存するスクリプト
対象: 2026/01/17〜19
"""

import os
import sys
import logging
from datetime import datetime, timedelta
import psycopg2
import requests
from bs4 import BeautifulSoup
import time
import re

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# DB接続情報
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging')

# 競艇場コード（01〜24）
STADIUM_CODES = list(range(1, 25))

def get_db_connection():
    """DB接続を取得"""
    return psycopg2.connect(DATABASE_URL)

def scrape_race_result(stadium_code: int, race_number: int, date_str: str):
    """
    レース結果をスクレイピングで取得
    date_str: YYYYMMDD形式
    """
    url = f"https://www.boatrace.jp/owpc/pc/race/raceresult?rno={race_number}&jcd={stadium_code:02d}&hd={date_str}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 着順を取得
        result = {}
        result_table = soup.select_one('.is-w495')
        if not result_table:
            return None
        
        rows = result_table.select('tbody tr')
        for row in rows:
            rank_elem = row.select_one('.is-fs14')
            boat_elem = row.select_one('.is-fs18')
            if rank_elem and boat_elem:
                rank = rank_elem.text.strip()
                boat_no = boat_elem.text.strip()
                if rank.isdigit() and boat_no.isdigit():
                    result[f'rank_{rank}'] = int(boat_no)
        
        # 払戻金を取得
        payoffs = []
        payout_tables = soup.select('.is-w243')
        for table in payout_tables:
            rows = table.select('tbody tr')
            for row in rows:
                cells = row.select('td')
                if len(cells) >= 3:
                    bet_type_elem = row.select_one('th')
                    if bet_type_elem:
                        bet_type = bet_type_elem.text.strip()
                        combination = cells[0].text.strip().replace('\n', '-').replace(' ', '')
                        payoff_text = cells[1].text.strip().replace(',', '').replace('円', '').replace('¥', '')
                        popularity_text = cells[2].text.strip() if len(cells) > 2 else '0'
                        
                        try:
                            payoff = int(payoff_text) if payoff_text.isdigit() else 0
                            popularity = int(popularity_text) if popularity_text.isdigit() else 0
                            if payoff > 0:
                                payoffs.append({
                                    'bet_type': bet_type,
                                    'combination': combination,
                                    'payoff': payoff,
                                    'popularity': popularity
                                })
                        except ValueError:
                            pass
        
        result['payoffs'] = payoffs
        return result
        
    except Exception as e:
        logger.error(f"スクレイピングエラー: {stadium_code:02d} {race_number}R {date_str} - {e}")
        return None

def save_to_historical_race_results(conn, race_date: str, stadium_code: int, race_number: int, result: dict):
    """historical_race_resultsテーブルに保存"""
    with conn.cursor() as cur:
        for rank in range(1, 7):
            boat_no = result.get(f'rank_{rank}')
            if boat_no:
                try:
                    cur.execute('''
                        INSERT INTO historical_race_results (race_date, stadium_code, race_no, boat_no, rank)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (race_date, stadium_code, race_no, boat_no) DO NOTHING
                    ''', (race_date, f'{stadium_code:02d}', f'{race_number:02d}', str(boat_no), f'{rank:02d}'))
                except Exception as e:
                    logger.error(f"保存エラー (race_results): {e}")
    conn.commit()

def save_to_historical_payoffs(conn, race_date: str, stadium_code: int, race_number: int, payoffs: list):
    """historical_payoffsテーブルに保存"""
    with conn.cursor() as cur:
        for payoff in payoffs:
            try:
                cur.execute('''
                    INSERT INTO historical_payoffs (race_date, stadium_code, race_no, bet_type, combination, payoff, popularity)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                ''', (
                    race_date,
                    f'{stadium_code:02d}',
                    f'{race_number:02d}',
                    payoff['bet_type'],
                    payoff['combination'],
                    payoff['payoff'],
                    payoff.get('popularity', 0)
                ))
            except Exception as e:
                logger.error(f"保存エラー (payoffs): {e}")
    conn.commit()

def backfill_date(conn, target_date: str):
    """指定日のデータを取得・保存"""
    logger.info(f"=== {target_date} のデータ取得開始 ===")
    
    total_races = 0
    success_races = 0
    
    for stadium_code in STADIUM_CODES:
        for race_number in range(1, 13):  # 1R〜12R
            result = scrape_race_result(stadium_code, race_number, target_date)
            total_races += 1
            
            if result and result.get('rank_1'):
                # 着順を保存
                save_to_historical_race_results(conn, target_date, stadium_code, race_number, result)
                
                # 払戻金を保存
                if result.get('payoffs'):
                    save_to_historical_payoffs(conn, target_date, stadium_code, race_number, result['payoffs'])
                
                success_races += 1
                logger.info(f"取得成功: {stadium_code:02d}場 {race_number}R - 着順:{result.get('rank_1')}-{result.get('rank_2')}-{result.get('rank_3')} 払戻金:{len(result.get('payoffs', []))}件")
            
            # サーバー負荷軽減のため少し待機
            time.sleep(0.3)
        
        logger.info(f"  {stadium_code:02d}場 完了")
    
    logger.info(f"=== {target_date} 完了: {success_races}/{total_races} レース ===")
    return success_races

def main():
    """メイン処理"""
    # 不足している日付
    missing_dates = ['20260117', '20260118', '20260119']
    
    logger.info("=== 不足分データ取得開始 ===")
    logger.info(f"対象日: {missing_dates}")
    
    conn = get_db_connection()
    
    try:
        total_success = 0
        for date_str in missing_dates:
            success = backfill_date(conn, date_str)
            total_success += success
        
        logger.info(f"=== 全日程完了: 合計 {total_success} レース ===")
    finally:
        conn.close()

if __name__ == '__main__':
    main()

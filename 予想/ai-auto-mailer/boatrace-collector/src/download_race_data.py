'''
競走成績・番組表データの一括ダウンロードスクリプト
公式サイトから指定期間のLZHファイルをダウンロードし、解凍します。
'''

import os
import requests
import subprocess
import logging
from datetime import datetime, timedelta, timezone
JST = timezone(timedelta(hours=9))
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ダウンロード先ディレクトリ
BASE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
RESULT_DOWNLOAD_DIR = os.path.join(BASE_DIR, 'race_results_lzh')
RESULT_EXTRACTED_DIR = os.path.join(BASE_DIR, 'race_results')
PROGRAM_DOWNLOAD_DIR = os.path.join(BASE_DIR, 'programs_lzh')
PROGRAM_EXTRACTED_DIR = os.path.join(BASE_DIR, 'programs')

# 公式サイトのURL
RESULT_BASE_URL = "https://www1.mbrace.or.jp/od2/K"
PROGRAM_BASE_URL = "https://www1.mbrace.or.jp/od2/B"


def download_file(url, filepath, max_retries=3):
    """
    指定されたURLからファイルをダウンロード
    """
    # 既にダウンロード済みの場合はスキップ
    if os.path.exists(filepath):
        logger.debug(f"既にダウンロード済み: {os.path.basename(filepath)}")
        return filepath
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=60)
            
            if response.status_code == 200:
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                logger.info(f"ダウンロード完了: {os.path.basename(filepath)} ({len(response.content)} bytes)")
                return filepath
            elif response.status_code == 404:
                logger.debug(f"ファイルが存在しません: {url}")
                return None
            else:
                logger.warning(f"ダウンロード失敗: {url} (HTTP {response.status_code})")
                
        except Exception as e:
            logger.warning(f"ダウンロードエラー (試行 {attempt + 1}/{max_retries}): {url} - {e}")
            time.sleep(1)
    
    return None


def extract_lzh(filepath, output_dir):
    """
    LZHファイルを解凍
    """
    if not filepath or not os.path.exists(filepath):
        return None
    
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # lhaコマンドで解凍
        result = subprocess.run(
            ['lha', '-xw=' + output_dir, filepath],
            check=True,
            capture_output=True,
            timeout=30
        )
        logger.debug(f"解凍完了: {os.path.basename(filepath)}")
        return output_dir
    except FileNotFoundError:
        # lhaがない場合はunarを試す
        try:
            subprocess.run(
                ['unar', '-o', output_dir, '-f', filepath],
                check=True,
                capture_output=True,
                timeout=30
            )
            logger.debug(f"解凍完了 (unar): {os.path.basename(filepath)}")
            return output_dir
        except Exception as e:
            logger.error(f"解凍エラー: {os.path.basename(filepath)} - {e}")
            return None
    except Exception as e:
        logger.error(f"解凍エラー: {os.path.basename(filepath)} - {e}")
        return None


def get_date_range(start_date, end_date):
    """
    日付範囲のリストを生成
    """
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def download_race_results(date):
    """
    指定日の競走成績をダウンロード・解凍
    """
    year = date.year
    month = date.month
    day = date.day
    
    # URLとファイルパスを生成
    yyyymm = f"{year:04d}{month:02d}"
    yymm = f"{year % 100:02d}{month:02d}"
    dd = f"{day:02d}"
    
    url = f"{RESULT_BASE_URL}/{yyyymm}/k{yymm}{dd}.lzh"
    filepath = os.path.join(RESULT_DOWNLOAD_DIR, yyyymm, f"k{yymm}{dd}.lzh")
    
    downloaded = download_file(url, filepath)
    if downloaded:
        output_dir = os.path.join(RESULT_EXTRACTED_DIR, yyyymm)
        extract_lzh(downloaded, output_dir)
        return True
    return False


def download_program(date):
    """
    指定日の番組表をダウンロード・解凍
    """
    year = date.year
    month = date.month
    day = date.day
    
    # URLとファイルパスを生成
    yyyymm = f"{year:04d}{month:02d}"
    yymm = f"{year % 100:02d}{month:02d}"
    dd = f"{day:02d}"
    
    url = f"{PROGRAM_BASE_URL}/{yyyymm}/b{yymm}{dd}.lzh"
    filepath = os.path.join(PROGRAM_DOWNLOAD_DIR, yyyymm, f"b{yymm}{dd}.lzh")
    
    downloaded = download_file(url, filepath)
    if downloaded:
        output_dir = os.path.join(PROGRAM_EXTRACTED_DIR, yyyymm)
        extract_lzh(downloaded, output_dir)
        return True
    return False


def download_race_results_range(start_date, end_date, max_workers=5):
    """
    指定期間の競走成績を一括ダウンロード
    """
    dates = get_date_range(start_date, end_date)
    logger.info(f"競走成績ダウンロード開始: {start_date} 〜 {end_date} ({len(dates)} 日間)")
    
    success_count = 0
    fail_count = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_race_results, date): date for date in dates}
        
        for future in as_completed(futures):
            date = futures[future]
            try:
                if future.result():
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.error(f"エラー: {date} - {e}")
                fail_count += 1
    
    logger.info(f"競走成績ダウンロード完了: 成功 {success_count} / 失敗 {fail_count}")
    return success_count, fail_count


def download_programs_range(start_date, end_date, max_workers=5):
    """
    指定期間の番組表を一括ダウンロード
    """
    dates = get_date_range(start_date, end_date)
    logger.info(f"番組表ダウンロード開始: {start_date} 〜 {end_date} ({len(dates)} 日間)")
    
    success_count = 0
    fail_count = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_program, date): date for date in dates}
        
        for future in as_completed(futures):
            date = futures[future]
            try:
                if future.result():
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.error(f"エラー: {date} - {e}")
                fail_count += 1
    
    logger.info(f"番組表ダウンロード完了: 成功 {success_count} / 失敗 {fail_count}")
    return success_count, fail_count


def download_all_historical(data_type='both', start_year=2005, end_date=None):
    """
    全履歴データをダウンロード
    
    Args:
        data_type: 'results', 'programs', or 'both'
        start_year: 開始年（デフォルト: 2005）
        end_date: 終了日（デフォルト: 昨日）
    """
    if end_date is None:
        end_date = datetime.now(JST).date() - timedelta(days=1)
    
    start_date = datetime(start_year, 1, 1).date()
    
    if data_type in ['results', 'both']:
        download_race_results_range(start_date, end_date)
    
    if data_type in ['programs', 'both']:
        download_programs_range(start_date, end_date)


def download_recent(days=7, data_type='both'):
    """
    直近のデータをダウンロード
    
    Args:
        days: 何日分をダウンロードするか
        data_type: 'results', 'programs', or 'both'
    """
    end_date = datetime.now(JST).date() - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)
    
    if data_type in ['results', 'both']:
        download_race_results_range(start_date, end_date)
    
    if data_type in ['programs', 'both']:
        download_programs_range(start_date, end_date)


def download_today_program():
    """
    本日の番組表をダウンロード
    """
    today = datetime.now(JST).date()
    logger.info(f"本日の番組表をダウンロード: {today}")
    return download_program(today)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python download_race_data.py recent [days] [type]  - 直近N日分をダウンロード")
        print("  python download_race_data.py today                  - 本日の番組表をダウンロード")
        print("  python download_race_data.py all [start_year] [type] - 全履歴をダウンロード")
        print("  python download_race_data.py date YYYY-MM-DD [type] - 指定日をダウンロード")
        print("")
        print("type: results, programs, both (デフォルト: both)")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'recent':
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        data_type = sys.argv[3] if len(sys.argv) > 3 else 'both'
        download_recent(days, data_type)
    
    elif command == 'today':
        download_today_program()
    
    elif command == 'all':
        start_year = int(sys.argv[2]) if len(sys.argv) > 2 else 2005
        data_type = sys.argv[3] if len(sys.argv) > 3 else 'both'
        download_all_historical(data_type, start_year)
    
    elif command == 'date':
        if len(sys.argv) < 3:
            print("日付を指定してください: YYYY-MM-DD")
            sys.exit(1)
        date = datetime.strptime(sys.argv[2], '%Y-%m-%d').date()
        data_type = sys.argv[3] if len(sys.argv) > 3 else 'both'
        
        if data_type in ['results', 'both']:
            download_race_results(date)
        if data_type in ['programs', 'both']:
            download_program(date)
    
    else:
        print(f"不明なコマンド: {command}")
        sys.exit(1)

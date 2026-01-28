'''
公式データの一括ダウンロード＆DBインポートスクリプト（並列処理版）
Renderのバッチジョブとして実行することを想定

使用方法:
  python import_historical_data.py download       - データをダウンロード（並列）
  python import_historical_data.py import         - ダウンロード済みデータをDBにインポート
  python import_historical_data.py all            - ダウンロード＆インポート両方実行
  python import_historical_data.py status         - 進捗状況を表示
  python import_historical_data.py import_payoffs - 払戻金データをインポート
'''

import os
import sys
import glob
import logging
import psycopg2
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import subprocess
import time
import re
import struct
import io

# lhafileライブラリ（-lh5-圧縮対応）
try:
    import lhafile
    HAS_LHAFILE = True
except ImportError:
    HAS_LHAFILE = False

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if not HAS_LHAFILE:
    logger.warning("lhafileライブラリがインストールされていません。pip install lhafile を実行してください。")

# データベース接続
DATABASE_URL = os.environ.get('DATABASE_URL')

# ディレクトリ設定
BASE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
RESULT_DOWNLOAD_DIR = os.path.join(BASE_DIR, 'race_results_lzh')
RESULT_EXTRACTED_DIR = os.path.join(BASE_DIR, 'race_results')
PROGRAM_DOWNLOAD_DIR = os.path.join(BASE_DIR, 'programs_lzh')
PROGRAM_EXTRACTED_DIR = os.path.join(BASE_DIR, 'programs')

# 公式サイトのURL
RESULT_BASE_URL = "https://www1.mbrace.or.jp/od2/K"
PROGRAM_BASE_URL = "https://www1.mbrace.or.jp/od2/B"

# 進捗管理テーブル
PROGRESS_TABLE = 'historical_import_progress'

# 1回の実行で処理する最大月数（タイムアウト防止）
# 環境変数で上書き可能。デフォルト48ヶ月（約4年分）に増加
MAX_MONTHS_PER_RUN = int(os.environ.get('MAX_MONTHS_PER_RUN', 48))

# 並列処理のワーカー数
# 環境変数で上書き可能。デフォルト5並列
PARALLEL_WORKERS = int(os.environ.get('PARALLEL_WORKERS', 5))


def get_db_connection():
    """データベース接続を取得"""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL環境変数が設定されていません")
    return psycopg2.connect(DATABASE_URL)


def init_progress_table():
    """進捗管理テーブルを作成"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f'''
                CREATE TABLE IF NOT EXISTS {PROGRESS_TABLE} (
                    id SERIAL PRIMARY KEY,
                    task_type VARCHAR(50) NOT NULL,
                    year_month VARCHAR(6) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    records_count INTEGER DEFAULT 0,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    UNIQUE(task_type, year_month)
                )
            ''')
            conn.commit()
            logger.info("進捗管理テーブルを初期化しました")
    finally:
        conn.close()


def update_progress(task_type, year_month, status, records_count=0, error_message=None):
    """進捗を更新"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if status == 'running':
                cur.execute(f'''
                    INSERT INTO {PROGRESS_TABLE} (task_type, year_month, status, started_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (task_type, year_month) 
                    DO UPDATE SET status = %s, started_at = NOW(), error_message = NULL
                ''', (task_type, year_month, status, status))
            elif status == 'completed':
                cur.execute(f'''
                    INSERT INTO {PROGRESS_TABLE} (task_type, year_month, status, records_count, completed_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (task_type, year_month) 
                    DO UPDATE SET status = %s, records_count = %s, completed_at = NOW()
                ''', (task_type, year_month, status, records_count, status, records_count))
            else:
                cur.execute(f'''
                    INSERT INTO {PROGRESS_TABLE} (task_type, year_month, status, error_message)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (task_type, year_month) 
                    DO UPDATE SET status = %s, error_message = %s
                ''', (task_type, year_month, status, error_message, status, error_message))
            conn.commit()
    finally:
        conn.close()


def get_pending_months(task_type, start_year=2005):
    """未処理の年月リストを取得（新しい順）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f'''
                SELECT year_month FROM {PROGRESS_TABLE}
                WHERE task_type = %s AND status = 'completed'
            ''', (task_type,))
            completed = set(row[0] for row in cur.fetchall())
    finally:
        conn.close()
    
    # 対象年月を生成（新しい順）
    now = datetime.now()
    all_months = []
    for year in range(start_year, now.year + 1):
        for month in range(1, 13):
            if year == now.year and month > now.month:
                continue
            year_month = f"{year}{month:02d}"
            if year_month not in completed:
                all_months.append(year_month)
    
    # 新しい順にソート
    return sorted(all_months, reverse=True)


def download_file(url, filepath, max_retries=3):
    """ファイルをダウンロード（リトライ機能付き）"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                return filepath
            elif response.status_code == 404:
                return None
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            logger.warning(f"ダウンロード失敗 ({url}): {e}")
    return None


def extract_lzh(lzh_path, output_dir):
    """LZHファイルを解凍"""
    os.makedirs(output_dir, exist_ok=True)
    
    if HAS_LHAFILE:
        try:
            with lhafile.LhaFile(lzh_path) as lha:
                for name in lha.namelist():
                    data = lha.read(name)
                    output_path = os.path.join(output_dir, name)
                    with open(output_path, 'wb') as f:
                        f.write(data)
            return True
        except Exception as e:
            logger.warning(f"lhafile解凍失敗 ({lzh_path}): {e}")
    
    # フォールバック: lhaコマンド
    try:
        subprocess.run(['lha', '-xw=' + output_dir, lzh_path], 
                      check=True, capture_output=True)
        return True
    except Exception as e:
        logger.warning(f"lhaコマンド解凍失敗 ({lzh_path}): {e}")
    
    return False


def download_single_day(args):
    """1日分のデータをダウンロード（並列処理用）"""
    year_month, day, data_type = args
    year = int(year_month[:4])
    month = int(year_month[4:6])
    yymm = f"{year % 100:02d}{month:02d}"
    
    if data_type == 'results':
        url = f"{RESULT_BASE_URL}/{year_month}/k{yymm}{day:02d}.lzh"
        filepath = os.path.join(RESULT_DOWNLOAD_DIR, year_month, f"k{yymm}{day:02d}.lzh")
        output_dir = os.path.join(RESULT_EXTRACTED_DIR, year_month)
    else:
        url = f"{PROGRAM_BASE_URL}/{year_month}/b{yymm}{day:02d}.lzh"
        filepath = os.path.join(PROGRAM_DOWNLOAD_DIR, year_month, f"b{yymm}{day:02d}.lzh")
        output_dir = os.path.join(PROGRAM_EXTRACTED_DIR, year_month)
    
    downloaded = download_file(url, filepath)
    if downloaded:
        extract_lzh(downloaded, output_dir)
        return 1
    return 0


def download_month_parallel(year_month, data_type='results'):
    """指定年月のデータを並列ダウンロード"""
    year = int(year_month[:4])
    month = int(year_month[4:6])
    
    # その月の日数を計算
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    days_in_month = (next_month - datetime(year, month, 1)).days
    
    # 並列ダウンロード用のタスクリスト
    tasks = [(year_month, day, data_type) for day in range(1, days_in_month + 1)]
    
    success_count = 0
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        futures = [executor.submit(download_single_day, task) for task in tasks]
        for future in as_completed(futures):
            success_count += future.result()
    
    return success_count


def process_month_download(args):
    """1ヶ月分のダウンロード処理（並列処理用）"""
    year_month, task_type, data_type = args
    try:
        update_progress(task_type, year_month, 'running')
        count = download_month_parallel(year_month, data_type)
        update_progress(task_type, year_month, 'completed', count)
        logger.info(f"{data_type}ダウンロード完了: {year_month} ({count} ファイル)")
        return (year_month, 'success', count)
    except Exception as e:
        update_progress(task_type, year_month, 'failed', error_message=str(e))
        logger.error(f"{data_type}ダウンロード失敗: {year_month} - {e}")
        return (year_month, 'failed', 0)


def run_download_parallel(start_year=2005):
    """ダウンロード処理を並列実行"""
    init_progress_table()
    
    # 競走結果のダウンロード
    pending_results = get_pending_months('download_results', start_year)[:MAX_MONTHS_PER_RUN]
    logger.info(f"競走結果ダウンロード対象: {len(pending_results)} ヶ月（並列数: {PARALLEL_WORKERS}）")
    
    # 月単位で並列処理（各月内も並列）
    tasks = [(ym, 'download_results', 'results') for ym in pending_results]
    
    with ThreadPoolExecutor(max_workers=3) as executor:  # 月単位は3並列
        futures = [executor.submit(process_month_download, task) for task in tasks]
        for future in as_completed(futures):
            result = future.result()
            logger.info(f"処理結果: {result}")
    
    # 番組表のダウンロード
    pending_programs = get_pending_months('download_programs', start_year)[:MAX_MONTHS_PER_RUN]
    logger.info(f"番組表ダウンロード対象: {len(pending_programs)} ヶ月")
    
    tasks = [(ym, 'download_programs', 'programs') for ym in pending_programs]
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_month_download, task) for task in tasks]
        for future in as_completed(futures):
            result = future.result()
            logger.info(f"処理結果: {result}")


# 既存のimport_historical_data.pyから必要な関数をインポート
from import_historical_data import (
    parse_result_file,
    parse_program_file,
    parse_payoffs_from_result_file,
    create_historical_tables,
    create_payoffs_table,
    import_results_to_db,
    import_programs_to_db,
    import_payoffs_to_db,
    run_import,
    run_import_payoffs,
    show_status,
    reset_progress
)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python import_historical_data_parallel.py download       - データを並列ダウンロード")
        print("  python import_historical_data_parallel.py import         - DBにインポート")
        print("  python import_historical_data_parallel.py all            - ダウンロード＆インポート")
        print("  python import_historical_data_parallel.py status         - 進捗状況を表示")
        print("  python import_historical_data_parallel.py import_payoffs - 払戻金データをインポート")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'download':
        run_download_parallel()
    elif command == 'import':
        run_import()
    elif command == 'all':
        run_download_parallel()
        run_import()
        run_import_payoffs()
    elif command == 'status':
        show_status()
    elif command == 'import_payoffs':
        run_import_payoffs()
    elif command == 'reset':
        reset_progress()
    elif command == 'reset_import':
        reset_progress(['import_results', 'import_programs', 'import_payoffs'])
    else:
        print(f"不明なコマンド: {command}")
        sys.exit(1)

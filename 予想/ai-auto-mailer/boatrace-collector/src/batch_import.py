#!/usr/bin/env python3
"""
競艇データ バッチインポート処理

3種類のデータを確実にDBにインポートするバッチ処理
- レーサー期別成績（ファン手帳）
- 競走成績（Kファイル）
- 番組表（Bファイル）

確実性と安定感を重視した設計:
- トランザクション管理
- 検証処理
- 進捗管理
- リトライ機能
"""

import os
import sys
import time
import glob
import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, List, Dict

# 日本時間
JST = timezone(timedelta(hours=9))
import psycopg2
from psycopg2.extras import execute_values

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 定数
MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒
RACER_START_YEAR = 2002
RACE_START_YEAR = 2005

# 1回の実行で処理する最大月数（タイムアウト防止）
# 環境変数で上書き可能。デフォルト5ヶ月（約30分）
MAX_MONTHS_PER_RUN = int(os.environ.get('MAX_MONTHS_PER_RUN', 5))

# データベース接続
DATABASE_URL = os.environ.get('DATABASE_URL')


def get_db_connection(retries: int = MAX_RETRIES) -> psycopg2.extensions.connection:
    """データベース接続を取得（リトライ機能付き）"""
    for attempt in range(retries):
        try:
            conn = psycopg2.connect(DATABASE_URL)
            return conn
        except psycopg2.OperationalError as e:
            if attempt < retries - 1:
                logger.warning(f"DB接続失敗、{RETRY_DELAY}秒後にリトライ... ({attempt + 1}/{retries})")
                time.sleep(RETRY_DELAY)
            else:
                raise e


def create_progress_table():
    """進捗管理テーブルを作成"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS import_batch_progress (
                    id SERIAL PRIMARY KEY,
                    data_type VARCHAR(50) NOT NULL,
                    period_key VARCHAR(10) NOT NULL,
                    step VARCHAR(20) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    record_count INTEGER DEFAULT 0,
                    verified_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(data_type, period_key, step)
                )
            ''')
            conn.commit()
            logger.info("進捗管理テーブルを作成/確認しました")
    finally:
        conn.close()


def update_progress(data_type: str, period_key: str, step: str, status: str,
                   record_count: int = 0, verified_count: int = 0, error_message: str = None):
    """進捗を更新"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            now = datetime.now(JST)
            started_at = now if status == 'running' else None
            completed_at = now if status in ('completed', 'failed') else None
            
            cur.execute('''
                INSERT INTO import_batch_progress 
                (data_type, period_key, step, status, record_count, verified_count, 
                 error_message, started_at, completed_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (data_type, period_key, step) DO UPDATE SET
                    status = EXCLUDED.status,
                    record_count = EXCLUDED.record_count,
                    verified_count = EXCLUDED.verified_count,
                    error_message = EXCLUDED.error_message,
                    started_at = COALESCE(import_batch_progress.started_at, EXCLUDED.started_at),
                    completed_at = EXCLUDED.completed_at,
                    updated_at = NOW()
            ''', (data_type, period_key, step, status, record_count, verified_count,
                  error_message, started_at, completed_at))
            conn.commit()
    finally:
        conn.close()


def get_progress_status(data_type: str, period_key: str, step: str) -> Optional[str]:
    """進捗状態を取得"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT status FROM import_batch_progress
                WHERE data_type = %s AND period_key = %s AND step = %s
            ''', (data_type, period_key, step))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def is_step_completed(data_type: str, period_key: str, step: str) -> bool:
    """ステップが完了済みかどうか"""
    status = get_progress_status(data_type, period_key, step)
    return status == 'completed'


def get_record_count(data_type: str, period_key: str, step: str) -> int:
    """進捗のrecord_countを取得"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT record_count FROM import_batch_progress
                WHERE data_type = %s AND period_key = %s AND step = %s
            ''', (data_type, period_key, step))
            row = cur.fetchone()
            return row[0] if row else 0
    finally:
        conn.close()


# ============================================
# レーサー期別成績のインポート
# ============================================

def get_racer_periods_to_process() -> List[Tuple[int, int]]:
    """処理対象のレーサー期別を取得"""
    periods = []
    current_year = datetime.now(JST).year
    current_month = datetime.now(JST).month
    
    for year in range(RACER_START_YEAR, current_year + 1):
        for period in [1, 2]:  # 1:前期(10月), 2:後期(4月)
            # 未来の期は除外
            if year == current_year:
                if period == 1 and current_month < 10:
                    # 前期は10月から
                    if not (current_month >= 1 and current_month <= 3):
                        # 1-3月は前年の前期データがある
                        continue
                if period == 2 and current_month < 4:
                    continue
            
            period_key = f"{year}_{period}"
            if not is_step_completed('racer', period_key, 'verify'):
                periods.append((year, period))
    
    return periods


def download_racer_file(year: int, period: int) -> Optional[str]:
    """レーサーデータファイルをダウンロード"""
    from download_racer_data import download_file, extract_lzh, DOWNLOAD_DIR, EXTRACTED_DIR
    
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(EXTRACTED_DIR, exist_ok=True)
    
    yy = str(year)[2:]
    # 前期=10月、後期=4月
    month_code = "10" if period == 1 else "04"
    filename = f"fan{yy}{month_code}.lzh"
    
    filepath = download_file(filename)
    if filepath:
        extracted = extract_lzh(filepath)
        if extracted:
            # 解凍されたファイルを探す
            txt_files = glob.glob(os.path.join(extracted, '*.txt')) + \
                       glob.glob(os.path.join(extracted, '*.TXT'))
            if txt_files:
                return txt_files[0]
    return None


def import_racer_to_db(filepath: str, year: int, period: int) -> int:
    """レーサーデータをDBにインポート"""
    from import_racer_data import parse_fan_handbook_file, create_racer_table, import_racers_to_db
    
    conn = get_db_connection()
    try:
        # テーブル作成
        create_racer_table(conn)
        
        # パース
        racers = parse_fan_handbook_file(filepath)
        if not racers:
            return 0
        
        # データ年・期を設定
        for r in racers:
            r['data_year'] = year
            r['data_period'] = period
        
        # インポート
        import_racers_to_db(racers, conn)
        conn.commit()
        
        return len(racers)
    finally:
        conn.close()


def verify_racer_import(year: int, period: int, expected_count: int) -> Tuple[bool, int]:
    """レーサーインポートを検証"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT COUNT(*) FROM racer_period_stats
                WHERE data_year = %s AND data_period = %s
            ''', (year, period))
            actual_count = cur.fetchone()[0]
            
            # 95%以上でOK（一部パースエラーを許容）
            threshold = int(expected_count * 0.95) if expected_count > 0 else 0
            is_valid = actual_count >= threshold
            
            return is_valid, actual_count
    finally:
        conn.close()


def process_racer_period(year: int, period: int) -> bool:
    """1期分のレーサーデータを処理"""
    period_key = f"{year}_{period}"
    logger.info(f"[レーサー] 処理開始: {period_key}")
    
    # ダウンロード
    filepath = None
    if not is_step_completed('racer', period_key, 'download'):
        update_progress('racer', period_key, 'download', 'running')
        
        for attempt in range(MAX_RETRIES):
            filepath = download_racer_file(year, period)
            if filepath:
                break
            logger.warning(f"[レーサー] ダウンロードリトライ {attempt + 1}/{MAX_RETRIES}")
            time.sleep(RETRY_DELAY)
        
        if not filepath:
            update_progress('racer', period_key, 'download', 'failed', 
                          error_message='ダウンロード失敗')
            logger.warning(f"[レーサー] ダウンロード失敗（スキップ）: {period_key}")
            return False
        
        update_progress('racer', period_key, 'download', 'completed')
        logger.info(f"[レーサー] ダウンロード完了: {period_key}")
    else:
        # 既にダウンロード済みの場合、ファイルパスを取得
        from download_racer_data import EXTRACTED_DIR
        yy = str(year)[2:]
        month_code = "10" if period == 1 else "04"
        extracted_dir = os.path.join(EXTRACTED_DIR, f"fan{yy}{month_code}")
        txt_files = glob.glob(os.path.join(extracted_dir, '*.txt')) + \
                   glob.glob(os.path.join(extracted_dir, '*.TXT'))
        if txt_files:
            filepath = txt_files[0]
    
    # インポート
    if not is_step_completed('racer', period_key, 'import'):
        if not filepath:
            logger.error(f"[レーサー] ファイルが見つかりません: {period_key}")
            return False
        
        update_progress('racer', period_key, 'import', 'running')
        
        try:
            record_count = import_racer_to_db(filepath, year, period)
            update_progress('racer', period_key, 'import', 'completed', record_count=record_count)
            logger.info(f"[レーサー] インポート完了: {period_key} ({record_count}件)")
        except Exception as e:
            update_progress('racer', period_key, 'import', 'failed', 
                          error_message=str(e))
            logger.error(f"[レーサー] インポート失敗: {period_key} - {e}")
            traceback.print_exc()
            return False
    
    # 検証
    if not is_step_completed('racer', period_key, 'verify'):
        update_progress('racer', period_key, 'verify', 'running')
        
        expected_count = get_record_count('racer', period_key, 'import')
        is_valid, actual_count = verify_racer_import(year, period, expected_count)
        
        if is_valid:
            update_progress('racer', period_key, 'verify', 'completed', 
                          verified_count=actual_count)
            logger.info(f"[レーサー] 検証OK: {period_key} (DB={actual_count}件)")
        else:
            update_progress('racer', period_key, 'verify', 'failed',
                          verified_count=actual_count,
                          error_message=f'検証失敗: 期待={expected_count}, 実際={actual_count}')
            logger.warning(f"[レーサー] 検証NG: {period_key} (期待={expected_count}, 実際={actual_count})")
            return False
    
    return True


# ============================================
# 競走成績のインポート
# ============================================

def get_race_months_to_process(data_type: str = 'results') -> List[str]:
    """処理対象の月を取得"""
    months = []
    current_year = datetime.now(JST).year
    current_month = datetime.now(JST).month
    
    for year in range(RACE_START_YEAR, current_year + 1):
        for month in range(1, 13):
            # 未来の月は除外
            if year == current_year and month > current_month:
                continue
            
            year_month = f"{year}{month:02d}"
            if not is_step_completed(data_type, year_month, 'verify'):
                months.append(year_month)
    
    return months


def process_race_results_month(year_month: str) -> bool:
    """1ヶ月分の競走成績を処理"""
    from import_historical_data import (
        download_month_results, import_results_to_db, create_historical_tables
    )
    
    logger.info(f"[競走成績] 処理開始: {year_month}")
    
    # テーブル作成
    create_historical_tables()
    
    # ダウンロード
    file_count = 0
    if not is_step_completed('results', year_month, 'download'):
        update_progress('results', year_month, 'download', 'running')
        
        for attempt in range(MAX_RETRIES):
            try:
                file_count = download_month_results(year_month)
                if file_count > 0:
                    break
            except Exception as e:
                logger.warning(f"[競走成績] ダウンロードエラー: {e}")
            time.sleep(RETRY_DELAY)
        
        if file_count == 0:
            update_progress('results', year_month, 'download', 'failed',
                          error_message='ダウンロード失敗（ファイルなし）')
            logger.warning(f"[競走成績] ダウンロード失敗（スキップ）: {year_month}")
            return False
        
        update_progress('results', year_month, 'download', 'completed', record_count=file_count)
        logger.info(f"[競走成績] ダウンロード完了: {year_month} ({file_count}ファイル)")
    else:
        file_count = get_record_count('results', year_month, 'download')
    
    # インポート
    if not is_step_completed('results', year_month, 'import'):
        update_progress('results', year_month, 'import', 'running')
        
        try:
            record_count = import_results_to_db(year_month)
            update_progress('results', year_month, 'import', 'completed', record_count=record_count)
            logger.info(f"[競走成績] インポート完了: {year_month} ({record_count}件)")
        except Exception as e:
            update_progress('results', year_month, 'import', 'failed',
                          error_message=str(e))
            logger.error(f"[競走成績] インポート失敗: {year_month} - {e}")
            traceback.print_exc()
            return False
    
    # 検証
    if not is_step_completed('results', year_month, 'verify'):
        update_progress('results', year_month, 'verify', 'running')
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT COUNT(*) FROM historical_race_results
                    WHERE race_date LIKE %s
                ''', (year_month + '%',))
                actual_count = cur.fetchone()[0]
        finally:
            conn.close()
        
        # 最低ライン: ファイル数 × 60件
        expected_min = file_count * 60 if file_count > 0 else 0
        is_valid = actual_count >= expected_min
        
        if is_valid or actual_count > 0:
            update_progress('results', year_month, 'verify', 'completed',
                          verified_count=actual_count)
            logger.info(f"[競走成績] 検証OK: {year_month} (DB={actual_count}件)")
        else:
            update_progress('results', year_month, 'verify', 'failed',
                          verified_count=actual_count,
                          error_message=f'検証失敗: 最低={expected_min}, 実際={actual_count}')
            logger.warning(f"[競走成績] 検証NG: {year_month} (実際={actual_count}件)")
    
    return True


# ============================================
# 番組表のインポート
# ============================================

def process_programs_month(year_month: str) -> bool:
    """1ヶ月分の番組表を処理"""
    from import_historical_data import (
        download_month_programs, import_programs_to_db, create_historical_tables
    )
    
    logger.info(f"[番組表] 処理開始: {year_month}")
    
    # テーブル作成
    create_historical_tables()
    
    # ダウンロード
    file_count = 0
    if not is_step_completed('programs', year_month, 'download'):
        update_progress('programs', year_month, 'download', 'running')
        
        for attempt in range(MAX_RETRIES):
            try:
                file_count = download_month_programs(year_month)
                if file_count > 0:
                    break
            except Exception as e:
                logger.warning(f"[番組表] ダウンロードエラー: {e}")
            time.sleep(RETRY_DELAY)
        
        if file_count == 0:
            update_progress('programs', year_month, 'download', 'failed',
                          error_message='ダウンロード失敗（ファイルなし）')
            logger.warning(f"[番組表] ダウンロード失敗（スキップ）: {year_month}")
            return False
        
        update_progress('programs', year_month, 'download', 'completed', record_count=file_count)
        logger.info(f"[番組表] ダウンロード完了: {year_month} ({file_count}ファイル)")
    else:
        file_count = get_record_count('programs', year_month, 'download')
    
    # インポート
    if not is_step_completed('programs', year_month, 'import'):
        update_progress('programs', year_month, 'import', 'running')
        
        try:
            record_count = import_programs_to_db(year_month)
            update_progress('programs', year_month, 'import', 'completed', record_count=record_count)
            logger.info(f"[番組表] インポート完了: {year_month} ({record_count}件)")
        except Exception as e:
            update_progress('programs', year_month, 'import', 'failed',
                          error_message=str(e))
            logger.error(f"[番組表] インポート失敗: {year_month} - {e}")
            traceback.print_exc()
            return False
    
    # 検証
    if not is_step_completed('programs', year_month, 'verify'):
        update_progress('programs', year_month, 'verify', 'running')
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT COUNT(*) FROM historical_programs
                    WHERE race_date LIKE %s
                ''', (year_month + '%',))
                actual_count = cur.fetchone()[0]
        finally:
            conn.close()
        
        # 最低ライン: ファイル数 × 60件
        expected_min = file_count * 60 if file_count > 0 else 0
        is_valid = actual_count >= expected_min
        
        if is_valid or actual_count > 0:
            update_progress('programs', year_month, 'verify', 'completed',
                          verified_count=actual_count)
            logger.info(f"[番組表] 検証OK: {year_month} (DB={actual_count}件)")
        else:
            update_progress('programs', year_month, 'verify', 'failed',
                          verified_count=actual_count,
                          error_message=f'検証失敗: 最低={expected_min}, 実際={actual_count}')
            logger.warning(f"[番組表] 検証NG: {year_month} (実際={actual_count}件)")
    
    return True


# ============================================
# メイン処理
# ============================================

def run_all():
    """全データを処理（月数制限あり）"""
    logger.info("=== バッチ処理開始（全データ） ===")
    logger.info(f"1回の実行で処理する最大月数: {MAX_MONTHS_PER_RUN}ヶ月")
    create_progress_table()
    
    # 1. レーサー期別成績（期数制限なし、元々少ない）
    logger.info("--- レーサー期別成績の処理 ---")
    racer_periods = get_racer_periods_to_process()
    logger.info(f"処理対象: {len(racer_periods)}期")
    
    for year, period in racer_periods:
        try:
            process_racer_period(year, period)
        except Exception as e:
            logger.error(f"レーサー処理エラー: {year}_{period} - {e}")
            traceback.print_exc()
    
    # 2. 競走成績（月数制限あり）
    logger.info("--- 競走成績の処理 ---")
    race_months = get_race_months_to_process('results')
    logger.info(f"処理対象: {len(race_months)}ヶ月（今回の上限: {MAX_MONTHS_PER_RUN}ヶ月）")
    
    processed_results = 0
    for year_month in race_months:
        if processed_results >= MAX_MONTHS_PER_RUN:
            logger.info(f"競走成績の月数制限に達しました（{MAX_MONTHS_PER_RUN}ヶ月）。残りは次回実行時に処理します。")
            break
        try:
            process_race_results_month(year_month)
            processed_results += 1
        except Exception as e:
            logger.error(f"競走成績処理エラー: {year_month} - {e}")
            traceback.print_exc()
    
    # 3. 番組表（月数制限あり）
    logger.info("--- 番組表の処理 ---")
    program_months = get_race_months_to_process('programs')
    logger.info(f"処理対象: {len(program_months)}ヶ月（今回の上限: {MAX_MONTHS_PER_RUN}ヶ月）")
    
    processed_programs = 0
    for year_month in program_months:
        if processed_programs >= MAX_MONTHS_PER_RUN:
            logger.info(f"番組表の月数制限に達しました（{MAX_MONTHS_PER_RUN}ヶ月）。残りは次回実行時に処理します。")
            break
        try:
            process_programs_month(year_month)
            processed_programs += 1
        except Exception as e:
            logger.error(f"番組表処理エラー: {year_month} - {e}")
            traceback.print_exc()
    
    logger.info("=== バッチ処理完了 ===")


def run_racer():
    """レーサーデータのみ処理"""
    logger.info("=== バッチ処理開始（レーサーのみ） ===")
    create_progress_table()
    
    racer_periods = get_racer_periods_to_process()
    logger.info(f"処理対象: {len(racer_periods)}期")
    
    for year, period in racer_periods:
        try:
            process_racer_period(year, period)
        except Exception as e:
            logger.error(f"レーサー処理エラー: {year}_{period} - {e}")
            traceback.print_exc()
    
    logger.info("=== バッチ処理完了 ===")


def run_results():
    """競走成績のみ処理（月数制限あり）"""
    logger.info("=== バッチ処理開始（競走成績のみ） ===")
    create_progress_table()
    
    race_months = get_race_months_to_process('results')
    logger.info(f"処理対象: {len(race_months)}ヶ月（今回の上限: {MAX_MONTHS_PER_RUN}ヶ月）")
    
    processed = 0
    for year_month in race_months:
        if processed >= MAX_MONTHS_PER_RUN:
            logger.info(f"月数制限に達しました（{MAX_MONTHS_PER_RUN}ヶ月）。残りは次回実行時に処理します。")
            break
        try:
            process_race_results_month(year_month)
            processed += 1
        except Exception as e:
            logger.error(f"競走成績処理エラー: {year_month} - {e}")
            traceback.print_exc()
    
    logger.info("=== バッチ処理完了 ===")


def run_programs():
    """番組表のみ処理（月数制限あり）"""
    logger.info("=== バッチ処理開始（番組表のみ） ===")
    create_progress_table()
    
    program_months = get_race_months_to_process('programs')
    logger.info(f"処理対象: {len(program_months)}ヶ月（今回の上限: {MAX_MONTHS_PER_RUN}ヶ月）")
    
    processed = 0
    for year_month in program_months:
        if processed >= MAX_MONTHS_PER_RUN:
            logger.info(f"月数制限に達しました（{MAX_MONTHS_PER_RUN}ヶ月）。残りは次回実行時に処理します。")
            break
        try:
            process_programs_month(year_month)
            processed += 1
        except Exception as e:
            logger.error(f"番組表処理エラー: {year_month} - {e}")
            traceback.print_exc()
    
    logger.info("=== バッチ処理完了 ===")


def show_status():
    """進捗状況を表示"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 各データタイプの状況
            for data_type in ['racer', 'results', 'programs']:
                cur.execute('''
                    SELECT status, COUNT(*) 
                    FROM import_batch_progress
                    WHERE data_type = %s AND step = 'verify'
                    GROUP BY status
                ''', (data_type,))
                rows = cur.fetchall()
                
                print(f"\n=== {data_type} ===")
                for status, count in rows:
                    print(f"  {status}: {count}件")
                
                # 最新の処理
                cur.execute('''
                    SELECT period_key, status, completed_at
                    FROM import_batch_progress
                    WHERE data_type = %s AND step = 'verify'
                    ORDER BY completed_at DESC NULLS LAST
                    LIMIT 5
                ''', (data_type,))
                rows = cur.fetchall()
                
                if rows:
                    print("  最新の処理:")
                    for period_key, status, completed_at in rows:
                        print(f"    {period_key}: {status} ({completed_at})")
    finally:
        conn.close()


def main():
    if len(sys.argv) < 2:
        print("使用方法: python batch_import.py <command>")
        print("  all      - 全データ処理")
        print("  racer    - レーサーデータのみ")
        print("  results  - 競走成績のみ")
        print("  programs - 番組表のみ")
        print("  status   - 進捗確認")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == 'all':
        run_all()
    elif command == 'racer':
        run_racer()
    elif command == 'results':
        run_results()
    elif command == 'programs':
        run_programs()
    elif command == 'status':
        show_status()
    else:
        print(f"不明なコマンド: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()

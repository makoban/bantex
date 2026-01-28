'''
公式データの一括ダウンロード＆DBインポートスクリプト
Renderのバッチジョブとして実行することを想定

使用方法:
  python import_historical_data.py download       - データをダウンロード
  python import_historical_data.py import         - ダウンロード済みデータをDBにインポート
  python import_historical_data.py all            - ダウンロード＆インポート両方実行
  python import_historical_data.py status         - 進捗状況を表示
  python import_historical_data.py import_payoffs - 払戻金データをインポート
  python import_historical_data.py payoffs_only   - 払戻金のみをダウンロード＆インポート（不足分のみ）
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
# 環境変数で上書き可能。デフォルト24ヶ月（約2年分）
MAX_MONTHS_PER_RUN = int(os.environ.get('MAX_MONTHS_PER_RUN', 100))

# 並列処理のワーカー数
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
            elif status in ['completed', 'failed']:
                cur.execute(f'''
                    UPDATE {PROGRESS_TABLE} 
                    SET status = %s, completed_at = NOW(), records_count = %s, error_message = %s
                    WHERE task_type = %s AND year_month = %s
                ''', (status, records_count, error_message, task_type, year_month))
            conn.commit()
    finally:
        conn.close()


def get_pending_months(task_type, start_year=2005):
    """未処理の年月リストを取得"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 完了済みの年月を取得
            cur.execute(f'''
                SELECT year_month FROM {PROGRESS_TABLE}
                WHERE task_type = %s AND status = 'completed'
            ''', (task_type,))
            completed = set(row[0] for row in cur.fetchall())
        
        # 全年月リストを生成
        all_months = []
        current = datetime(start_year, 1, 1)
        end = datetime.now()
        while current <= end:
            ym = current.strftime('%Y%m')
            if ym not in completed:
                all_months.append(ym)
            current = (current.replace(day=1) + timedelta(days=32)).replace(day=1)
        
        # 新しい順（本日から過去へ）に並べ替え
        return list(reversed(all_months))
    finally:
        conn.close()


def get_payoffs_missing_months():
    """払戻金が不足している年月リストを取得（DBの実データを直接確認）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 払戻金が存在する年月を取得
            cur.execute('''
                SELECT DISTINCT LEFT(race_date, 6) as year_month
                FROM historical_payoffs
            ''')
            existing_payoff_months = set(row[0] for row in cur.fetchall())
            
            # 競走結果が存在する年月を取得
            cur.execute('''
                SELECT DISTINCT LEFT(race_date, 6) as year_month
                FROM historical_race_results
            ''')
            all_result_months = set(row[0] for row in cur.fetchall())
        
        # 競走結果はあるが払戻金がない年月を特定
        missing_months = all_result_months - existing_payoff_months
        logger.info(f"払戻金不足月: {len(missing_months)} ヶ月（競走結果: {len(all_result_months)} ヶ月, 払戻金: {len(existing_payoff_months)} ヶ月）")
        return sorted(list(missing_months), reverse=True)
    finally:
        conn.close()


def download_file(url, filepath, max_retries=3):
    """ファイルをダウンロード"""
    if os.path.exists(filepath):
        return filepath
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=60)
            if response.status_code == 200:
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                return filepath
            elif response.status_code == 404:
                return None
        except Exception as e:
            logger.warning(f"ダウンロードエラー (試行 {attempt + 1}/{max_retries}): {url} - {e}")
            time.sleep(2)
    return None


def extract_lzh(filepath, output_dir):
    """LZHファイルを解凍（Python純正実装）"""
    if not filepath or not os.path.exists(filepath):
        return None
    
    os.makedirs(output_dir, exist_ok=True)
    
    # まず外部コマンドを試す
    try:
        subprocess.run(['lha', '-xw=' + output_dir, filepath],
                      check=True, capture_output=True, timeout=30)
        return output_dir
    except FileNotFoundError:
        pass
    except Exception:
        pass
    
    try:
        subprocess.run(['unar', '-o', output_dir, '-f', filepath],
                      check=True, capture_output=True, timeout=30)
        return output_dir
    except FileNotFoundError:
        pass
    except Exception:
        pass
    
    # 外部コマンドがない場合、Pythonで解凍を試みる
    try:
        return extract_lzh_python(filepath, output_dir)
    except Exception as e:
        logger.error(f"解凍エラー: {filepath} - {e}")
        return None


def extract_lzh_python(filepath, output_dir):
    """PythonでLZHファイルを解凍（lhafileライブラリ使用、-lh0-/-lh5-/-lh6-/-lh7-対応）"""
    
    # 出力ディレクトリを作成
    os.makedirs(output_dir, exist_ok=True)
    
    # lhafileライブラリが利用可能な場合はそれを使用
    if HAS_LHAFILE:
        try:
            lzh = lhafile.Lhafile(filepath)
            extracted_count = 0
            for info in lzh.infolist():
                # ファイル名を取得
                filename = info.filename
                basename = os.path.basename(filename.replace('\\', '/'))
                if not basename:
                    continue
                
                # ファイルを解凍して保存
                try:
                    file_data = lzh.read(info.filename)
                    output_path = os.path.join(output_dir, basename)
                    with open(output_path, 'wb') as out_f:
                        out_f.write(file_data)
                    extracted_count += 1
                except Exception as e:
                    logger.warning(f"ファイル解凍エラー: {basename} - {e}")
            
            # LhaFileオブジェクトにはclose()メソッドがないため、明示的なクローズは不要
            if extracted_count > 0:
                return output_dir
            return None
        except Exception as e:
            logger.warning(f"lhafile解凍エラー: {filepath} - {e}")
            # フォールバックとして手動パースを試みる
    
    # lhafileが使えない場合、手動パースを試みる（-lh0-のみ対応）
    with open(filepath, 'rb') as f:
        data = f.read()
    
    pos = 0
    extracted_count = 0
    
    while pos < len(data):
        # ヘッダサイズを読み取り
        if pos + 21 > len(data):
            break
        
        header_size = data[pos]
        if header_size == 0:
            break
        
        # チェックサム
        checksum = data[pos + 1]
        
        # 圧縮方式（-lh0-, -lh5-等）
        method = data[pos + 2:pos + 7].decode('ascii', errors='ignore')
        
        # 圧縮後サイズ、元サイズ
        compressed_size = struct.unpack('<I', data[pos + 7:pos + 11])[0]
        original_size = struct.unpack('<I', data[pos + 11:pos + 15])[0]
        
        # ファイル名長
        name_length = data[pos + 21]
        filename = data[pos + 22:pos + 22 + name_length].decode('shift_jis', errors='ignore')
        
        # ヘッダー全体のサイズ
        total_header_size = header_size + 2
        
        # データ部分の開始位置
        data_start = pos + total_header_size
        data_end = data_start + compressed_size
        
        if data_end > len(data):
            break
        
        # -lh0-は無圧縮なのでそのまま保存
        if method == '-lh0-':
            file_data = data[data_start:data_end]
            
            # ファイル名からディレクトリ部分を除去
            basename = os.path.basename(filename.replace('\\', '/'))
            if basename:
                output_path = os.path.join(output_dir, basename)
                with open(output_path, 'wb') as out_f:
                    out_f.write(file_data)
                extracted_count += 1
        else:
            # -lh5-等の圧縮形式はlhafileがないと対応できない
            logger.warning(f"未対応の圧縮形式（lhafileが必要）: {method} - {filename}")
        
        pos = data_end
    
    if extracted_count > 0:
        return output_dir
    return None



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


def download_month_results(year_month):
    """指定年月のレース結果を並列ダウンロード"""
    year = int(year_month[:4])
    month = int(year_month[4:6])
    
    # その月の日数を計算
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    days_in_month = (next_month - datetime(year, month, 1)).days
    
    # 並列ダウンロード
    tasks = [(year_month, day, 'results') for day in range(1, days_in_month + 1)]
    
    success_count = 0
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        futures = [executor.submit(download_single_day, task) for task in tasks]
        for future in as_completed(futures):
            success_count += future.result()
    
    return success_count


def download_month_programs(year_month):
    """指定年月の番組表を並列ダウンロード"""
    year = int(year_month[:4])
    month = int(year_month[4:6])
    
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    days_in_month = (next_month - datetime(year, month, 1)).days
    
    # 並列ダウンロード
    tasks = [(year_month, day, 'programs') for day in range(1, days_in_month + 1)]
    
    success_count = 0
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        futures = [executor.submit(download_single_day, task) for task in tasks]
        for future in as_completed(futures):
            success_count += future.result()
    
    return success_count


def parse_result_file(filepath):
    """
    レース結果ファイル（Kファイル）をパース
    
    Kファイルのフォーマット:
    - テキストファイル（Shift-JIS）
    - 場コード: "24KBGN" 形式（先頭2桁が場コード）
    - レース番号: "   1R       予　選" 形式
    - 着順データ: "01  3 2778 河　内　正　一　 21   15  6.68   2    0.08     1.49.3"
    """
    results = []
    
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
        
        # Shift-JISでデコード
        text = content.decode('shift_jis', errors='ignore')
        lines = text.replace('\r', '').split('\n')
        
        # ファイル名から日付を取得 (K050101.TXT -> 20050101)
        basename = os.path.basename(filepath).upper()
        race_date = None
        if basename.startswith('K') and len(basename) >= 7:
            date_part = basename[1:7]  # 050101
            try:
                year = int(date_part[:2])
                year = 2000 + year if year < 50 else 1900 + year
                month = date_part[2:4]
                day = date_part[4:6]
                race_date = f"{year}{month}{day}"
            except ValueError:
                pass
        
        if not race_date:
            logger.warning(f"ファイル名から日付を取得できません: {filepath}")
            return results
        
        # 状態変数
        current_stadium = None
        current_race_no = None
        
        # 着順データ行のパターン
        # 形式: "01  3 2778 河　内　正　一　 21   15  6.68   2    0.08     1.49.3"
        # または "F   6 4248 岡　本　　　大　 14   48  6.49   5   F0.02      .  ."
        result_pattern = re.compile(
            r'^\s*(\d{2}|[FKLSE失転落沈妨欠])\s+'  # 着順
            r'(\d)\s+'                              # 艇番
            r'(\d{4})\s+'                           # 登番
            r'(.+?)\s+'                             # 選手名
            r'(\d+)\s+'                             # モーター
            r'(\d+)\s+'                             # ボート
            r'([\d.]+)\s+'                          # 展示タイム
            r'(\d)\s+'                              # 進入コース
            r'([F]?[\d.]+)\s+'                      # スタートタイミング
            r'([\d.]+|\.?\s*\.?\s*)$'               # レースタイム
        )
        
        # レース番号行のパターン（"   1R       予　選" 形式）
        race_pattern = re.compile(r'^\s*(\d{1,2})R\s+')
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            
            # 場コードの検出 (24KBGN形式)
            if 'KBGN' in line:
                match = re.search(r'(\d{2})KBGN', line)
                if match:
                    current_stadium = match.group(1)
                continue
            
            # レース番号の検出
            race_match = race_pattern.match(stripped)
            if race_match:
                current_race_no = race_match.group(1).zfill(2)
                continue
            
            # 着順データの検出
            if current_stadium and current_race_no:
                result_match = result_pattern.match(stripped)
                if result_match:
                    rank = result_match.group(1)
                    boat_no = result_match.group(2)
                    racer_no = result_match.group(3)
                    race_time = result_match.group(10).strip()
                    
                    # レースタイムが空の場合は ". ." を空文字に
                    if race_time in ['. .', '.  .', '']:
                        race_time = ''
                    
                    results.append({
                        'race_date': race_date,
                        'stadium_code': current_stadium,
                        'race_no': current_race_no,
                        'boat_no': boat_no,
                        'racer_no': racer_no,
                        'rank': rank,
                        'race_time': race_time
                    })
    
    except Exception as e:
        logger.error(f"ファイルパースエラー: {filepath} - {e}")
    
    return results


def parse_payoffs_from_result_file(filepath):
    """
    レース結果ファイル（Kファイル）から払戻金データをパース
    
    払戻金フォーマット:
    - 単勝     1          100
    - 複勝     1          100  2          110
    - ２連単   1-2        430  人気     2
    - ２連複   1-2        330  人気     2
    - 拡連複   1-2        180  人気     2 （ワイド、最大3組）
    - ３連単   1-2-4     1400  人気     5
    - ３連複   1-2-4      820  人気     4
    """
    payoffs = []
    
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
        
        # Shift-JISでデコード
        text = content.decode('shift_jis', errors='ignore')
        lines = text.replace('\r', '').split('\n')
        
        # ファイル名から日付を取得 (K050101.TXT -> 20050101)
        basename = os.path.basename(filepath).upper()
        race_date = None
        if basename.startswith('K') and len(basename) >= 7:
            date_part = basename[1:7]  # 050101
            try:
                year = int(date_part[:2])
                year = 2000 + year if year < 50 else 1900 + year
                month = date_part[2:4]
                day = date_part[4:6]
                race_date = f"{year}{month}{day}"
            except ValueError:
                pass
        
        if not race_date:
            logger.warning(f"ファイル名から日付を取得できません: {filepath}")
            return payoffs
        
        # 状態変数
        current_stadium = None
        current_race_no = None
        in_payoff_section = False
        
        # レース番号行のパターン（"   1R       予　選" 形式）
        race_pattern = re.compile(r'^\s*(\d{1,2})R\s+')
        
        for line in lines:
            stripped = line.strip()
            
            # 場コードの検出 (24KBGN形式)
            if 'KBGN' in line:
                match = re.search(r'(\d{2})KBGN', line)
                if match:
                    current_stadium = match.group(1)
                continue
            
            # レース番号の検出
            race_match = race_pattern.match(stripped)
            if race_match:
                current_race_no = race_match.group(1).zfill(2)
                in_payoff_section = False
                continue
            
            if not current_stadium or not current_race_no:
                continue
            
            # 払戻金セクションの検出（「単勝」で始まる行）
            if stripped.startswith('単勝'):
                in_payoff_section = True
            
            if not in_payoff_section:
                continue
            
            # 単勝のパース: "単勝     1          100"
            if stripped.startswith('単勝'):
                # 複数の単勝がある場合（同着など）
                matches = re.findall(r'(\d)\s+(\d+)', stripped)
                for m in matches:
                    boat_no, amount = m
                    payoffs.append({
                        'race_date': race_date,
                        'stadium_code': current_stadium,
                        'race_no': current_race_no,
                        'bet_type': 'tansho',
                        'combination': boat_no,
                        'payout': int(amount),
                        'popularity': None
                    })
            
            # 複勝のパース: "複勝     1          100  2          110"
            elif stripped.startswith('複勝'):
                matches = re.findall(r'(\d)\s+(\d+)', stripped)
                for m in matches:
                    boat_no, amount = m
                    payoffs.append({
                        'race_date': race_date,
                        'stadium_code': current_stadium,
                        'race_no': current_race_no,
                        'bet_type': 'fukusho',
                        'combination': boat_no,
                        'payout': int(amount),
                        'popularity': None
                    })
            
            # ２連単のパース: "２連単   1-2        430  人気     2"
            elif stripped.startswith('２連単'):
                match = re.search(r'(\d-\d)\s+(\d+)\s+人気\s+(\d+)', stripped)
                if match:
                    payoffs.append({
                        'race_date': race_date,
                        'stadium_code': current_stadium,
                        'race_no': current_race_no,
                        'bet_type': 'nirentan',
                        'combination': match.group(1),
                        'payout': int(match.group(2)),
                        'popularity': int(match.group(3))
                    })
            
            # ２連複のパース: "２連複   1-2        330  人気     2"
            elif stripped.startswith('２連複'):
                match = re.search(r'(\d-\d)\s+(\d+)\s+人気\s+(\d+)', stripped)
                if match:
                    payoffs.append({
                        'race_date': race_date,
                        'stadium_code': current_stadium,
                        'race_no': current_race_no,
                        'bet_type': 'nirenpuku',
                        'combination': match.group(1),
                        'payout': int(match.group(2)),
                        'popularity': int(match.group(3))
                    })
            
            # 拡連複（ワイド）のパース: "拡連複   1-2        180  人気     2"
            # 複数行にわたる場合あり（最大3組）
            elif stripped.startswith('拡連複') or (in_payoff_section and re.match(r'^\s+\d-\d\s+\d+\s+人気', stripped)):
                matches = re.findall(r'(\d-\d)\s+(\d+)\s+人気\s+(\d+)', stripped)
                for m in matches:
                    payoffs.append({
                        'race_date': race_date,
                        'stadium_code': current_stadium,
                        'race_no': current_race_no,
                        'bet_type': 'wide',
                        'combination': m[0],
                        'payout': int(m[1]),
                        'popularity': int(m[2])
                    })
            
            # ３連単のパース: "３連単   1-2-4     1400  人気     5"
            elif stripped.startswith('３連単'):
                match = re.search(r'(\d-\d-\d)\s+(\d+)\s+人気\s+(\d+)', stripped)
                if match:
                    payoffs.append({
                        'race_date': race_date,
                        'stadium_code': current_stadium,
                        'race_no': current_race_no,
                        'bet_type': 'sanrentan',
                        'combination': match.group(1),
                        'payout': int(match.group(2)),
                        'popularity': int(match.group(3))
                    })
            
            # ３連複のパース: "３連複   1-2-4      820  人気     4"
            elif stripped.startswith('３連複'):
                match = re.search(r'(\d-\d-\d)\s+(\d+)\s+人気\s+(\d+)', stripped)
                if match:
                    payoffs.append({
                        'race_date': race_date,
                        'stadium_code': current_stadium,
                        'race_no': current_race_no,
                        'bet_type': 'sanrenpuku',
                        'combination': match.group(1),
                        'payout': int(match.group(2)),
                        'popularity': int(match.group(3))
                    })
                # 払戻金セクション終了
                in_payoff_section = False
    
    except Exception as e:
        logger.error(f"払戻金パースエラー: {filepath} - {e}")
    
    return payoffs


def parse_program_file(filepath):
    """番組表ファイルをパース"""
    programs = []
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
        
        # Shift_JISでデコードし、\rを削除
        text = content.decode('shift_jis', errors='ignore').replace('\r', '')
        lines = text.strip().split('\n')
        
        current_stadium = None
        current_race_date = None
        current_race_no = None
        current_deadline = None
        
        # ファイル名から日付を取得 (B260103.TXT -> 20260103)
        basename = os.path.basename(filepath)
        if basename.upper().startswith('B') and len(basename) >= 7:
            date_part = basename[1:7]  # 260103
            year_prefix = '20' if int(date_part[:2]) < 50 else '19'
            current_race_date = f"{year_prefix}{date_part}"
        
        for line in lines:
            # 場コードの検出 (BBGN行) - strip前に検出
            if 'BBGN' in line:
                stadium_match = re.search(r'(\d{2})BBGN', line)
                if stadium_match:
                    current_stadium = stadium_match.group(1)
                continue
            
            line = line.strip()
            if not line:
                continue
            
            # レース番号と締切時刻の検出
            # 形式: "　１Ｒ  予選　　　　          Ｈ１８００ｍ  電話投票締切予定１７：４１"
            # 全角数字と半角数字両方に対応
            race_match = re.search(r'[　\s]*([\d０-９]{1,2})[ＲR].*締切予定([\d０-９]{1,2})[：:]([\d０-９]{2})', line)
            if race_match:
                # 全角数字を半角に変換
                race_no_str = race_match.group(1).translate(str.maketrans('０１２３４５６７８９', '0123456789'))
                current_race_no = race_no_str.zfill(2)
                hour = race_match.group(2).translate(str.maketrans('０１２３４５６７８９', '0123456789'))
                minute = race_match.group(3).translate(str.maketrans('０１２３４５６７８９', '0123456789'))
                current_deadline = f"{hour}:{minute}"
                continue
            
            # 選手データ行の検出
            # 形式: "1 4112大久保信45佐賀52B1 5.43 36.14 5.09 25.00 39 33.08 11 29.92"
            # 選手名は4～8文字（全角スペース含む）
            racer_match = re.match(
                r'^([1-6])\s+(\d{4})'
                r'(.{2,8}?)'
                r'(\d{2})'
                r'(.{2,4}?)'
                r'(\d{2})'
                r'([AB][12])\s+'
                r'([\d.]+)\s+'
                r'([\d.]+)\s+'
                r'([\d.]+)\s+'
                r'([\d.]+)\s+'
                r'(\d+)\s+'
                r'([\d.]+)\s+'
                r'(\d+)\s+'
                r'([\d.]+)',
                line
            )
            if racer_match and current_stadium and current_race_date and current_race_no:
                try:
                    programs.append({
                        'race_date': current_race_date,
                        'stadium_code': current_stadium,
                        'race_no': current_race_no,
                        'boat_no': racer_match.group(1),
                        'racer_no': racer_match.group(2),
                        'racer_name': racer_match.group(3).strip().replace('　', ''),
                        'age': int(racer_match.group(4)),
                        'branch': racer_match.group(5).strip().replace('　', ''),
                        'weight': int(racer_match.group(6)),
                        'rank': racer_match.group(7),
                        'national_win_rate': float(racer_match.group(8)),
                        'national_2nd_rate': float(racer_match.group(9)),
                        'local_win_rate': float(racer_match.group(10)),
                        'local_2nd_rate': float(racer_match.group(11)),
                        'motor_no': int(racer_match.group(12)),
                        'motor_2nd_rate': float(racer_match.group(13)),
                        'boat_no_assigned': int(racer_match.group(14)),
                        'boat_2nd_rate': float(racer_match.group(15)),
                        'deadline_time': current_deadline
                    })
                except (ValueError, IndexError) as e:
                    continue
    except Exception as e:
        logger.error(f"番組表パースエラー: {filepath} - {e}")
    
    return programs


def import_programs_to_db(year_month):
    """番組表をDBにインポート"""
    extracted_dir = os.path.join(PROGRAM_EXTRACTED_DIR, year_month)
    if not os.path.exists(extracted_dir):
        return 0
    
    conn = get_db_connection()
    total_count = 0
    
    try:
        with conn.cursor() as cur:
            for filename in os.listdir(extracted_dir):
                if not filename.upper().endswith('.TXT'):
                    continue
                
                filepath = os.path.join(extracted_dir, filename)
                programs = parse_program_file(filepath)
                
                for prog in programs:
                    try:
                        cur.execute('''
                            INSERT INTO historical_programs 
                            (race_date, stadium_code, race_no, boat_no, racer_no, racer_name,
                             age, branch, weight, rank, national_win_rate, national_2nd_rate,
                             local_win_rate, local_2nd_rate, motor_no, motor_2nd_rate,
                             boat_no_assigned, boat_2nd_rate, deadline_time)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (race_date, stadium_code, race_no, boat_no) DO UPDATE SET
                                racer_no = EXCLUDED.racer_no,
                                racer_name = EXCLUDED.racer_name,
                                age = EXCLUDED.age,
                                branch = EXCLUDED.branch,
                                weight = EXCLUDED.weight,
                                rank = EXCLUDED.rank,
                                national_win_rate = EXCLUDED.national_win_rate,
                                national_2nd_rate = EXCLUDED.national_2nd_rate,
                                local_win_rate = EXCLUDED.local_win_rate,
                                local_2nd_rate = EXCLUDED.local_2nd_rate,
                                motor_no = EXCLUDED.motor_no,
                                motor_2nd_rate = EXCLUDED.motor_2nd_rate,
                                boat_no_assigned = EXCLUDED.boat_no_assigned,
                                boat_2nd_rate = EXCLUDED.boat_2nd_rate,
                                deadline_time = EXCLUDED.deadline_time
                        ''', (
                            prog['race_date'], prog['stadium_code'], prog['race_no'],
                            prog['boat_no'], prog['racer_no'], prog['racer_name'],
                            prog['age'], prog['branch'], prog['weight'], prog['rank'],
                            prog['national_win_rate'], prog['national_2nd_rate'],
                            prog['local_win_rate'], prog['local_2nd_rate'],
                            prog['motor_no'], prog['motor_2nd_rate'],
                            prog['boat_no_assigned'], prog['boat_2nd_rate'],
                            prog['deadline_time']
                        ))
                        total_count += 1
                    except Exception as e:
                        continue
                
                conn.commit()
    finally:
        conn.close()
    
    return total_count


def import_results_to_db(year_month):
    """レース結果と払戻金をDBにインポート"""
    extracted_dir = os.path.join(RESULT_EXTRACTED_DIR, year_month)
    if not os.path.exists(extracted_dir):
        return 0
    
    conn = get_db_connection()
    total_count = 0
    payoff_count = 0
    
    try:
        # K*.TXTファイルを検索
        pattern = os.path.join(extracted_dir, 'K*.TXT')
        files = glob.glob(pattern, recursive=True)
        
        if not files:
            # 小文字も試す
            pattern = os.path.join(extracted_dir, 'k*.txt')
            files = glob.glob(pattern, recursive=True)
        
        for filepath in files:
            results = parse_result_file(filepath)
            
            with conn.cursor() as cur:
                for r in results:
                    try:
                        # historical_race_resultsテーブルに挿入
                        cur.execute('''
                            INSERT INTO historical_race_results 
                            (race_date, stadium_code, race_no, boat_no, racer_no, rank, race_time)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT DO NOTHING
                        ''', (
                            r['race_date'], r['stadium_code'], r['race_no'],
                            r['boat_no'], r['racer_no'], r['rank'], r['race_time']
                        ))
                        total_count += 1
                    except Exception as e:
                        continue
            
            # 払戻金もインポート
            payoffs = parse_payoffs_from_result_file(filepath)
            with conn.cursor() as cur:
                for p in payoffs:
                    try:
                        cur.execute('''
                            INSERT INTO historical_payoffs 
                            (race_date, stadium_code, race_no, bet_type, combination, payout, popularity)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (race_date, stadium_code, race_no, bet_type, combination) 
                            DO UPDATE SET payout = EXCLUDED.payout, popularity = EXCLUDED.popularity
                        ''', (
                            p['race_date'], p['stadium_code'], p['race_no'],
                            p['bet_type'], p['combination'], p['payout'], p.get('popularity')
                        ))
                        payoff_count += 1
                    except Exception as e:
                        continue
            
            conn.commit()
        
        if payoff_count > 0:
            logger.info(f"払戻金インポート: {payoff_count} 件")
    finally:
        conn.close()
    
    return total_count


def create_historical_tables():
    """履歴データ用テーブルを作成"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # レース結果テーブル
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
            
            # インデックス作成
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_hist_results_date 
                ON historical_race_results(race_date)
            ''')
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_hist_results_racer 
                ON historical_race_results(racer_no)
            ''')
            
            # 番組表（出走表）テーブル
            cur.execute('''
                CREATE TABLE IF NOT EXISTS historical_programs (
                    id SERIAL PRIMARY KEY,
                    race_date VARCHAR(8) NOT NULL,
                    stadium_code VARCHAR(2) NOT NULL,
                    race_no VARCHAR(2) NOT NULL,
                    boat_no VARCHAR(1) NOT NULL,
                    racer_no VARCHAR(4),
                    racer_name VARCHAR(20),
                    age INTEGER,
                    branch VARCHAR(10),
                    weight INTEGER,
                    rank VARCHAR(2),
                    national_win_rate DECIMAL(5,2),
                    national_2nd_rate DECIMAL(5,2),
                    local_win_rate DECIMAL(5,2),
                    local_2nd_rate DECIMAL(5,2),
                    motor_no INTEGER,
                    motor_2nd_rate DECIMAL(5,2),
                    boat_no_assigned INTEGER,
                    boat_2nd_rate DECIMAL(5,2),
                    deadline_time VARCHAR(10),
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(race_date, stadium_code, race_no, boat_no)
                )
            ''')
            
            # 番組表インデックス
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_hist_programs_date 
                ON historical_programs(race_date)
            ''')
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_hist_programs_racer 
                ON historical_programs(racer_no)
            ''')
            
            conn.commit()
            logger.info("履歴データ用テーブルを作成しました")
    finally:
        conn.close()


def create_payoffs_table():
    """払戻金テーブルを作成"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS historical_payoffs (
                    id SERIAL PRIMARY KEY,
                    race_date VARCHAR(8) NOT NULL,
                    stadium_code VARCHAR(2) NOT NULL,
                    race_no VARCHAR(2) NOT NULL,
                    bet_type VARCHAR(20) NOT NULL,
                    combination VARCHAR(10) NOT NULL,
                    payout INTEGER NOT NULL,
                    popularity INTEGER,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(race_date, stadium_code, race_no, bet_type, combination)
                )
            ''')
            
            # インデックス作成
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_hist_payoffs_date 
                ON historical_payoffs(race_date)
            ''')
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_hist_payoffs_bet_type 
                ON historical_payoffs(bet_type)
            ''')
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_hist_payoffs_race 
                ON historical_payoffs(race_date, stadium_code, race_no)
            ''')
            
            conn.commit()
            logger.info("払戻金テーブルを作成しました")
    finally:
        conn.close()


def import_payoffs_to_db(year_month):
    """払戻金データをDBにインポート"""
    extracted_dir = os.path.join(RESULT_EXTRACTED_DIR, year_month)
    if not os.path.exists(extracted_dir):
        logger.warning(f"ディレクトリが存在しません: {extracted_dir}")
        return 0
    
    conn = get_db_connection()
    total_count = 0
    
    try:
        # K*.TXTファイルを検索
        pattern = os.path.join(extracted_dir, 'K*.TXT')
        files = glob.glob(pattern, recursive=True)
        
        if not files:
            # 小文字も試す
            pattern = os.path.join(extracted_dir, 'k*.txt')
            files = glob.glob(pattern, recursive=True)
        
        logger.info(f"処理対象ファイル数: {len(files)}")
        
        for filepath in files:
            payoffs = parse_payoffs_from_result_file(filepath)
            
            with conn.cursor() as cur:
                for p in payoffs:
                    try:
                        cur.execute('''
                            INSERT INTO historical_payoffs 
                            (race_date, stadium_code, race_no, bet_type, combination, payout, popularity)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (race_date, stadium_code, race_no, bet_type, combination) 
                            DO UPDATE SET payout = EXCLUDED.payout, popularity = EXCLUDED.popularity
                        ''', (
                            p['race_date'], p['stadium_code'], p['race_no'],
                            p['bet_type'], p['combination'], p['payout'], p['popularity']
                        ))
                        total_count += 1
                    except Exception as e:
                        logger.warning(f"払戻金インポートエラー: {e}")
                        continue
            
            conn.commit()
    finally:
        conn.close()
    
    return total_count


def run_download(start_year=2005):
    """ダウンロード処理を実行（月数制限あり）"""
    init_progress_table()
    
    processed_count = 0
    
    # 競走結果のダウンロード
    pending = get_pending_months('download_results', start_year)
    logger.info(f"競走結果ダウンロード対象: {len(pending)} ヶ月（今回の上限: {MAX_MONTHS_PER_RUN} ヶ月）")
    
    for year_month in pending:
        # 月数制限チェック
        if processed_count >= MAX_MONTHS_PER_RUN:
            logger.info(f"月数制限に達しました（{MAX_MONTHS_PER_RUN}ヶ月）。残りは次回実行時に処理します。")
            break
        
        logger.info(f"競走結果ダウンロード開始: {year_month}")
        update_progress('download_results', year_month, 'running')
        
        try:
            count = download_month_results(year_month)
            update_progress('download_results', year_month, 'completed', count)
            logger.info(f"競走結果ダウンロード完了: {year_month} ({count} ファイル)")
            processed_count += 1
        except Exception as e:
            update_progress('download_results', year_month, 'failed', error_message=str(e))
            logger.error(f"競走結果ダウンロード失敗: {year_month} - {e}")
    
    # 番組表のダウンロード（競走結果と同じ月数制限を共有）
    pending_programs = get_pending_months('download_programs', start_year)
    logger.info(f"番組表ダウンロード対象: {len(pending_programs)} ヶ月")
    
    program_processed = 0
    for year_month in pending_programs:
        # 番組表も同じ月数制限を適用
        if program_processed >= MAX_MONTHS_PER_RUN:
            logger.info(f"番組表の月数制限に達しました（{MAX_MONTHS_PER_RUN}ヶ月）。残りは次回実行時に処理します。")
            break
        
        logger.info(f"番組表ダウンロード開始: {year_month}")
        update_progress('download_programs', year_month, 'running')
        
        try:
            count = download_month_programs(year_month)
            update_progress('download_programs', year_month, 'completed', count)
            logger.info(f"番組表ダウンロード完了: {year_month} ({count} ファイル)")
            program_processed += 1
        except Exception as e:
            update_progress('download_programs', year_month, 'failed', error_message=str(e))
            logger.error(f"番組表ダウンロード失敗: {year_month} - {e}")


def run_import():
    """インポート処理を実行（月数制限あり）"""
    init_progress_table()
    create_historical_tables()
    create_payoffs_table()  # 払戻金テーブルも作成
    
    processed_count = 0
    
    # === 競走結果のインポート ===
    downloaded_dirs = []
    if os.path.exists(RESULT_EXTRACTED_DIR):
        downloaded_dirs = [d for d in os.listdir(RESULT_EXTRACTED_DIR) 
                         if os.path.isdir(os.path.join(RESULT_EXTRACTED_DIR, d))]
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f'''
                SELECT year_month FROM {PROGRESS_TABLE}
                WHERE task_type = 'import_results' AND status = 'completed'
            ''')
            imported = set(row[0] for row in cur.fetchall())
    finally:
        conn.close()
    
    # 新しい順（最新データを優先）
    pending = [ym for ym in sorted(downloaded_dirs, reverse=True) if ym not in imported]
    logger.info(f"競走結果インポート対象: {len(pending)} ヶ月（今回の上限: {MAX_MONTHS_PER_RUN} ヶ月）")
    
    for year_month in pending:
        # 月数制限チェック
        if processed_count >= MAX_MONTHS_PER_RUN:
            logger.info(f"月数制限に達しました（{MAX_MONTHS_PER_RUN}ヶ月）。残りは次回実行時に処理します。")
            break
        
        logger.info(f"競走結果インポート開始: {year_month}")
        update_progress('import_results', year_month, 'running')
        
        try:
            count = import_results_to_db(year_month)
            update_progress('import_results', year_month, 'completed', count)
            logger.info(f"競走結果インポート完了: {year_month} ({count} レコード)")
            processed_count += 1
        except Exception as e:
            update_progress('import_results', year_month, 'failed', error_message=str(e))
            logger.error(f"競走結果インポート失敗: {year_month} - {e}")
    
    # === 番組表のインポート ===
    program_dirs = []
    if os.path.exists(PROGRAM_EXTRACTED_DIR):
        program_dirs = [d for d in os.listdir(PROGRAM_EXTRACTED_DIR) 
                       if os.path.isdir(os.path.join(PROGRAM_EXTRACTED_DIR, d))]
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f'''
                SELECT year_month FROM {PROGRESS_TABLE}
                WHERE task_type = 'import_programs' AND status = 'completed'
            ''')
            imported_programs = set(row[0] for row in cur.fetchall())
    finally:
        conn.close()
    
    # 新しい順（最新データを優先）
    pending_programs = [ym for ym in sorted(program_dirs, reverse=True) if ym not in imported_programs]
    logger.info(f"番組表インポート対象: {len(pending_programs)} ヶ月")
    
    program_processed = 0
    for year_month in pending_programs:
        # 番組表も同じ月数制限を適用
        if program_processed >= MAX_MONTHS_PER_RUN:
            logger.info(f"番組表の月数制限に達しました（{MAX_MONTHS_PER_RUN}ヶ月）。残りは次回実行時に処理します。")
            break
        
        logger.info(f"番組表インポート開始: {year_month}")
        update_progress('import_programs', year_month, 'running')
        
        try:
            count = import_programs_to_db(year_month)
            update_progress('import_programs', year_month, 'completed', count)
            logger.info(f"番組表インポート完了: {year_month} ({count} レコード)")
            program_processed += 1
        except Exception as e:
            update_progress('import_programs', year_month, 'failed', error_message=str(e))
            logger.error(f"番組表インポート失敗: {year_month} - {e}")


def run_import_payoffs():
    """払戻金インポート処理を実行（月数制限あり）"""
    init_progress_table()
    create_payoffs_table()
    
    processed_count = 0
    
    # 解凍済みディレクトリを取得
    downloaded_dirs = []
    if os.path.exists(RESULT_EXTRACTED_DIR):
        downloaded_dirs = [d for d in os.listdir(RESULT_EXTRACTED_DIR) 
                         if os.path.isdir(os.path.join(RESULT_EXTRACTED_DIR, d))]
    
    # 完了済みの年月を取得
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f'''
                SELECT year_month FROM {PROGRESS_TABLE}
                WHERE task_type = 'import_payoffs' AND status = 'completed'
            ''')
            imported = set(row[0] for row in cur.fetchall())
    finally:
        conn.close()
    
    # 未処理の年月を新しい順にソート（最新データを優先）
    pending = [ym for ym in sorted(downloaded_dirs, reverse=True) if ym not in imported]
    logger.info(f"払戻金インポート対象: {len(pending)} ヶ月（今回の上限: {MAX_MONTHS_PER_RUN} ヶ月）")
    
    for year_month in pending:
        # 月数制限チェック
        if processed_count >= MAX_MONTHS_PER_RUN:
            logger.info(f"月数制限に達しました（{MAX_MONTHS_PER_RUN}ヶ月）。残りは次回実行時に処理します。")
            break
        
        logger.info(f"払戻金インポート開始: {year_month}")
        update_progress('import_payoffs', year_month, 'running')
        
        try:
            count = import_payoffs_to_db(year_month)
            update_progress('import_payoffs', year_month, 'completed', count)
            logger.info(f"払戻金インポート完了: {year_month} ({count} レコード)")
            processed_count += 1
        except Exception as e:
            update_progress('import_payoffs', year_month, 'failed', error_message=str(e))
            logger.error(f"払戻金インポート失敗: {year_month} - {e}")


def run_payoffs_only():
    """払戻金のみをダウンロード＆インポート（不足分のみ）
    
    DBの実データを確認して、競走結果はあるが払戻金がない年月のみを処理する。
    番組表・競走結果のダウンロード・インポートはスキップする。
    """
    init_progress_table()
    create_payoffs_table()
    
    # 払戻金が不足している年月を取得
    missing_months = get_payoffs_missing_months()
    
    if not missing_months:
        logger.info("払戻金データは全て揃っています。処理不要です。")
        return
    
    logger.info(f"=== 払戻金のみダウンロード＆インポート開始 ===")
    logger.info(f"対象: {len(missing_months)} ヶ月（今回の上限: {MAX_MONTHS_PER_RUN} ヶ月）")
    
    processed_count = 0
    
    for year_month in missing_months:
        # 月数制限チェック
        if processed_count >= MAX_MONTHS_PER_RUN:
            logger.info(f"月数制限に達しました（{MAX_MONTHS_PER_RUN}ヶ月）。残りは次回実行時に処理します。")
            break
        
        logger.info(f"\n--- {year_month} 処理開始 ---")
        update_progress('payoffs_only', year_month, 'running')
        
        try:
            # 1. Kファイル（競走結果）のみダウンロード
            logger.info(f"  Kファイルダウンロード中: {year_month}")
            download_count = download_month_results(year_month)
            logger.info(f"  ダウンロード完了: {download_count} ファイル")
            
            # 2. 払戻金のみをDBにインポート
            logger.info(f"  払戻金インポート中: {year_month}")
            payoff_count = import_payoffs_to_db(year_month)
            
            update_progress('payoffs_only', year_month, 'completed', payoff_count)
            logger.info(f"払戻金処理完了: {year_month} ({payoff_count} レコード)")
            processed_count += 1
            
        except Exception as e:
            update_progress('payoffs_only', year_month, 'failed', error_message=str(e))
            logger.error(f"払戻金処理失敗: {year_month} - {e}")
    
    logger.info(f"\n=== 処理完了 ===")
    logger.info(f"処理月数: {processed_count} ヶ月")
    logger.info(f"残り月数: {len(missing_months) - processed_count} ヶ月")


def reset_progress(task_types=None):
    """進捗をリセット（再インポート用）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if task_types:
                for task_type in task_types:
                    cur.execute(f'DELETE FROM {PROGRESS_TABLE} WHERE task_type = %s', (task_type,))
                    logger.info(f"進捗をリセットしました: {task_type}")
            else:
                cur.execute(f'DELETE FROM {PROGRESS_TABLE}')
                logger.info("全ての進捗をリセットしました")
            conn.commit()
    finally:
        conn.close()


def show_status():
    """進捗状況を表示"""
    init_progress_table()
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # ダウンロード進捗
            cur.execute(f'''
                SELECT status, COUNT(*) 
                FROM {PROGRESS_TABLE}
                WHERE task_type = 'download_results'
                GROUP BY status
            ''')
            download_status = dict(cur.fetchall())
            
            # インポート進捗
            cur.execute(f'''
                SELECT status, COUNT(*), SUM(records_count)
                FROM {PROGRESS_TABLE}
                WHERE task_type = 'import_results'
                GROUP BY status
            ''')
            import_status = {row[0]: {'count': row[1], 'records': row[2] or 0} 
                           for row in cur.fetchall()}
            
            # 払戻金インポート進捗
            cur.execute(f'''
                SELECT status, COUNT(*), SUM(records_count)
                FROM {PROGRESS_TABLE}
                WHERE task_type = 'import_payoffs'
                GROUP BY status
            ''')
            payoffs_status = {row[0]: {'count': row[1], 'records': row[2] or 0} 
                            for row in cur.fetchall()}
            
            # 履歴データ件数
            cur.execute('SELECT COUNT(*) FROM historical_race_results')
            total_records = cur.fetchone()[0]
            
            # 払戻金データ件数
            try:
                cur.execute('SELECT COUNT(*) FROM historical_payoffs')
                total_payoffs = cur.fetchone()[0]
            except:
                total_payoffs = 0
        
        print("\n=== 公式データインポート進捗 ===\n")
        print("【ダウンロード】")
        print(f"  完了: {download_status.get('completed', 0)} ヶ月")
        print(f"  実行中: {download_status.get('running', 0)} ヶ月")
        print(f"  失敗: {download_status.get('failed', 0)} ヶ月")
        
        print("\n【DBインポート（着順）】")
        completed = import_status.get('completed', {'count': 0, 'records': 0})
        print(f"  完了: {completed['count']} ヶ月 ({completed['records']} レコード)")
        running = import_status.get('running', {'count': 0})
        print(f"  実行中: {running['count']} ヶ月")
        failed = import_status.get('failed', {'count': 0})
        print(f"  失敗: {failed['count']} ヶ月")
        
        print("\n【DBインポート（払戻金）】")
        completed_payoffs = payoffs_status.get('completed', {'count': 0, 'records': 0})
        print(f"  完了: {completed_payoffs['count']} ヶ月 ({completed_payoffs['records']} レコード)")
        running_payoffs = payoffs_status.get('running', {'count': 0})
        print(f"  実行中: {running_payoffs['count']} ヶ月")
        failed_payoffs = payoffs_status.get('failed', {'count': 0})
        print(f"  失敗: {failed_payoffs['count']} ヶ月")
        
        print(f"\n【DB総レコード数】")
        print(f"  historical_race_results: {total_records:,} 件")
        print(f"  historical_payoffs: {total_payoffs:,} 件")
        
    finally:
        conn.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python import_historical_data.py download       - データをダウンロード")
        print("  python import_historical_data.py import         - DBにインポート")
        print("  python import_historical_data.py all            - ダウンロード＆インポート")
        print("  python import_historical_data.py status         - 進捗状況を表示")
        print("  python import_historical_data.py import_payoffs - 払戻金データをインポート")
        print("  python import_historical_data.py payoffs_only   - 払戻金のみをダウンロード＆インポート（不足分のみ）")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'download':
        run_download()
    elif command == 'import':
        run_import()
    elif command == 'all':
        run_download()
        run_import()
        run_import_payoffs()  # 払戻金インポートも実行
    elif command == 'status':
        show_status()
    elif command == 'import_payoffs':
        run_import_payoffs()
    elif command == 'payoffs_only':
        run_payoffs_only()
    elif command == 'reset':
        reset_progress()
    elif command == 'reset_import':
        reset_progress(['import_results', 'import_programs', 'import_payoffs'])
    elif command == 'reset_results':
        reset_progress(['import_results'])
    else:
        print(f"不明なコマンド: {command}")
        sys.exit(1)

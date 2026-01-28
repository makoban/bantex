"""
LZHファイルからの結果取得バッチ処理

毎日6:00 JSTに実行され、前日の結果をLZHファイルから取得して
データベースに保存・検証します。
"""

import os
import sys
import logging
import requests
import psycopg2
import re
import lhafile
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 日本時間
JST = timezone(timedelta(hours=9))

# ダウンロード先ディレクトリ
BASE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
RESULT_DOWNLOAD_DIR = os.path.join(BASE_DIR, 'race_results_lzh')
RESULT_EXTRACTED_DIR = os.path.join(BASE_DIR, 'race_results')

# 公式サイトのURL
RESULT_BASE_URL = "https://www1.mbrace.or.jp/od2/K"


def download_file(url: str, filepath: str, max_retries: int = 3) -> Optional[str]:
    """
    指定されたURLからファイルをダウンロード
    """
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
                logger.info(f"ファイルが存在しません: {url}")
                return None
            else:
                logger.warning(f"ダウンロード失敗: {url} (HTTP {response.status_code})")

        except Exception as e:
            logger.warning(f"ダウンロードエラー (試行 {attempt + 1}/{max_retries}): {url} - {e}")

    return None


def extract_lzh(filepath: str, output_dir: str) -> Optional[str]:
    """
    LZHファイルを解凍（Pythonライブラリを使用）
    """
    if not filepath or not os.path.exists(filepath):
        return None

    os.makedirs(output_dir, exist_ok=True)

    try:
        # lhafileライブラリで解凍（コンテキストマネージャ非対応）
        lha = lhafile.Lhafile(filepath)
        extracted_count = 0

        for info in lha.infolist():
            # ファイル名を取得
            filename = info.filename
            # パスの区切り文字を正規化
            if '\\' in filename:
                filename = filename.replace('\\', '/')
            # ディレクトリ部分を除去してファイル名のみ取得
            basename = os.path.basename(filename)
            if not basename:
                continue

            # ファイルを解凍
            try:
                output_path = os.path.join(output_dir, basename)
                with open(output_path, 'wb') as f:
                    f.write(lha.read(info.filename))
                extracted_count += 1
                logger.debug(f"解凍: {basename}")
            except Exception as e:
                logger.warning(f"ファイル解凍エラー: {basename} - {e}")

        if extracted_count > 0:
            logger.info(f"解凍完了: {os.path.basename(filepath)} ({extracted_count}ファイル)")
            return output_dir
        else:
            logger.warning(f"解凍ファイルなし: {os.path.basename(filepath)}")
            return None

    except Exception as e:
        logger.error(f"解凍エラー: {os.path.basename(filepath)} - {e}")
        return None


def download_race_results_for_date(target_date: datetime) -> Optional[str]:
    """
    指定日の競走成績LZHファイルをダウンロード・解凍

    Returns:
        解凍先ディレクトリのパス、失敗時はNone
    """
    year = target_date.year
    month = target_date.month
    day = target_date.day

    # URLとファイルパスを生成
    yyyymm = f"{year:04d}{month:02d}"
    yymm = f"{year % 100:02d}{month:02d}"
    dd = f"{day:02d}"

    url = f"{RESULT_BASE_URL}/{yyyymm}/k{yymm}{dd}.lzh"
    filepath = os.path.join(RESULT_DOWNLOAD_DIR, yyyymm, f"k{yymm}{dd}.lzh")

    logger.info(f"LZHファイルダウンロード: {url}")

    downloaded = download_file(url, filepath)
    if downloaded:
        output_dir = os.path.join(RESULT_EXTRACTED_DIR, yyyymm)
        extracted = extract_lzh(downloaded, output_dir)
        return extracted

    return None


def parse_result_file(filepath: str) -> List[Dict]:
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

        # ファイル名から日付を取得 (K260123.TXT -> 20260123)
        basename = os.path.basename(filepath).upper()
        race_date = None
        if basename.startswith('K') and len(basename) >= 7:
            date_part = basename[1:7]  # 260123
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
        result_pattern = re.compile(
            r'^\s*(\d{2}|[FKLSE失転落沈妨欠])\s+'  # 着順 (1)
            r'(\d)\s+'                              # 艇番 (2)
            r'(\d{4})\s+'                           # 登番 (3)
            r'(.+?)\s+'                             # 選手名 (4)
            r'(\d+)\s+'                             # モーター (5)
            r'(\d+)\s+'                             # ボート (6)
            r'([\d.]+)\s+'                          # 展示タイム (7)
            r'(\d)\s+'                              # 進入コース (8)
            r'([F]?[\d.]+)\s+'                      # スタートタイミング (9)
            r'([\d.]+|\.?\s*\.?\s*)$'               # レースタイム (10)
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
                    rank_str = result_match.group(1)
                    boat_no = result_match.group(2)
                    racer_no = result_match.group(3)
                    exhibition_time_str = result_match.group(7).strip()

                    # 着順を数値に変換（失格等は99）
                    try:
                        rank = int(rank_str)
                    except ValueError:
                        rank = 99  # 失格、転覆等

                    exhibition_time = None
                    try:
                        exhibition_time = float(exhibition_time_str)
                    except ValueError:
                        pass

                    results.append({
                        'race_date': race_date,
                        'stadium_code': current_stadium,
                        'race_no': current_race_no,
                        'boat_no': boat_no,
                        'rank': f"{rank:02d}",
                        'racer_no': racer_no,
                        'exhibition_time': exhibition_time
                    })

        logger.info(f"パース完了: {filepath} -> {len(results)}件")

    except Exception as e:
        logger.error(f"ファイルパースエラー: {filepath} - {e}")

    return results


def save_results_to_db(results: List[Dict], database_url: str) -> int:
    """
    パースした結果をデータベースに保存

    Returns:
        保存した件数
    """
    if not results:
        return 0

    saved_count = 0

    try:
        conn = psycopg2.connect(database_url)

        with conn.cursor() as cur:
            for result in results:
                try:
                    cur.execute("""
                        INSERT INTO historical_race_results
                        (race_date, stadium_code, race_no, boat_no, rank, exhibition_time)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (race_date, stadium_code, race_no, boat_no) DO UPDATE SET
                            rank = EXCLUDED.rank,
                            exhibition_time = EXCLUDED.exhibition_time
                    """, (
                        result['race_date'],
                        result['stadium_code'],
                        result['race_no'],
                        result['boat_no'],
                        result['rank'],
                        result.get('exhibition_time')
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.warning(f"保存エラー: {result} - {e}")

            conn.commit()

        conn.close()
        logger.info(f"データベースに保存: {saved_count}件")

    except Exception as e:
        logger.error(f"データベース接続エラー: {e}")

    return saved_count


def verify_results(target_date: datetime, database_url: str) -> Dict:
    """
    スクレイピング結果とLZH結果を比較・検証

    Returns:
        検証結果の辞書
    """
    date_str = target_date.strftime('%Y%m%d')

    verification = {
        'date': date_str,
        'scraping_count': 0,
        'lzh_count': 0,
        'match_count': 0,
        'mismatch_count': 0,
        'missing_in_scraping': 0,
        'missing_in_lzh': 0
    }

    try:
        conn = psycopg2.connect(database_url)

        with conn.cursor() as cur:
            # スクレイピング結果（race_results）のカウント
            cur.execute("""
                SELECT COUNT(*) FROM race_results rr
                JOIN races r ON rr.race_id = r.id
                WHERE r.race_date = %s::date
            """, (target_date.strftime('%Y-%m-%d'),))
            verification['scraping_count'] = cur.fetchone()[0]

            # LZH結果（historical_race_results）のカウント
            cur.execute("""
                SELECT COUNT(*) FROM historical_race_results
                WHERE race_date = %s
            """, (date_str,))
            verification['lzh_count'] = cur.fetchone()[0]

        conn.close()

        logger.info(f"検証結果: スクレイピング={verification['scraping_count']}件, LZH={verification['lzh_count']}件")

    except Exception as e:
        logger.error(f"検証エラー: {e}")

    return verification


def process_single_date(target_date: datetime, database_url: str) -> Dict:
    """
    単一日付の処理

    Args:
        target_date: 対象日
        database_url: データベースURL

    Returns:
        処理結果の辞書
    """
    logger.info(f"対象日: {target_date.strftime('%Y-%m-%d')}")

    # LZHファイルをダウンロード・解凍
    extracted_dir = download_race_results_for_date(target_date)

    if not extracted_dir:
        logger.warning(f"LZHファイルのダウンロードに失敗: {target_date.strftime('%Y-%m-%d')}")
        return {'date': target_date.strftime('%Y-%m-%d'), 'saved_count': 0, 'status': 'download_failed'}

    # 解凍されたファイルを探す
    yymm = f"{target_date.year % 100:02d}{target_date.month:02d}"
    dd = f"{target_date.day:02d}"
    result_filename = f"K{yymm}{dd}.TXT"
    result_filepath = os.path.join(extracted_dir, result_filename)

    # 大文字小文字の違いを考慮
    if not os.path.exists(result_filepath):
        result_filepath = os.path.join(extracted_dir, result_filename.lower())

    if not os.path.exists(result_filepath):
        # ディレクトリ内のファイルを探す
        for f in os.listdir(extracted_dir):
            if f.upper() == result_filename:
                result_filepath = os.path.join(extracted_dir, f)
                break

    if not os.path.exists(result_filepath):
        logger.warning(f"結果ファイルが見つかりません: {result_filename}")
        return {'date': target_date.strftime('%Y-%m-%d'), 'saved_count': 0, 'status': 'file_not_found'}

    # ファイルをパース
    results = parse_result_file(result_filepath)

    if not results:
        logger.warning(f"パース結果が空です: {target_date.strftime('%Y-%m-%d')}")
        return {'date': target_date.strftime('%Y-%m-%d'), 'saved_count': 0, 'status': 'parse_empty'}

    # データベースに保存
    saved_count = save_results_to_db(results, database_url)

    logger.info(f"完了: {target_date.strftime('%Y-%m-%d')} -> {saved_count}件保存")

    return {
        'date': target_date.strftime('%Y-%m-%d'),
        'saved_count': saved_count,
        'status': 'success'
    }


def run_morning_batch(database_url: str = None):
    """
    早朝バッチ処理のメイン関数
    前日の結果をLZHファイルから取得してデータベースに保存
    """
    logger.info("=== LZH結果取得バッチ処理開始 ===")

    if not database_url:
        database_url = os.environ.get('DATABASE_URL')

    if not database_url:
        logger.error("DATABASE_URLが設定されていません")
        return

    # 前日の日付を取得
    now_jst = datetime.now(JST)
    yesterday = now_jst - timedelta(days=1)

    result = process_single_date(yesterday, database_url)

    # 検証
    if result.get('status') == 'success':
        verification = verify_results(yesterday, database_url)
        result['verification'] = verification

    logger.info(f"=== LZH結果取得バッチ処理完了: {result.get('saved_count', 0)}件保存 ===")

    return result


def run_date_range_batch(start_date_str: str, end_date_str: str, database_url: str = None):
    """
    日付範囲を指定してLZHファイルを取得

    Args:
        start_date_str: 開始日 (YYYYMMDD形式)
        end_date_str: 終了日 (YYYYMMDD形式)
        database_url: データベースURL

    Returns:
        処理結果のリスト
    """
    logger.info(f"=== LZH結果取得バッチ処理開始（範囲指定） ===")
    logger.info(f"対象期間: {start_date_str} 〜 {end_date_str}")

    if not database_url:
        database_url = os.environ.get('DATABASE_URL')

    if not database_url:
        logger.error("DATABASE_URLが設定されていません")
        return []

    # 日付をパース
    try:
        start_date = datetime.strptime(start_date_str, '%Y%m%d')
        end_date = datetime.strptime(end_date_str, '%Y%m%d')
    except ValueError as e:
        logger.error(f"日付形式エラー: {e}（YYYYMMDD形式で指定してください）")
        return []

    if start_date > end_date:
        logger.error("開始日が終了日より後です")
        return []

    results = []
    total_saved = 0
    current_date = start_date

    while current_date <= end_date:
        result = process_single_date(current_date, database_url)
        results.append(result)
        total_saved += result.get('saved_count', 0)
        current_date += timedelta(days=1)

    # サマリー
    success_count = len([r for r in results if r.get('status') == 'success'])
    failed_count = len(results) - success_count

    logger.info(f"=== LZH結果取得バッチ処理完了 ===")
    logger.info(f"合計: {len(results)}日分処理、成功: {success_count}日、失敗: {failed_count}日、保存: {total_saved}件")

    return results


def check_lzh_exists(target_date: datetime) -> bool:
    """
    指定日のLZHファイルが既にダウンロード済みかチェック

    Args:
        target_date: 対象日

    Returns:
        True: ファイルが存在する
        False: ファイルが存在しない
    """
    year = target_date.year
    month = target_date.month
    day = target_date.day

    yyyymm = f"{year:04d}{month:02d}"
    yymm = f"{year % 100:02d}{month:02d}"
    dd = f"{day:02d}"

    filepath = os.path.join(RESULT_DOWNLOAD_DIR, yyyymm, f"k{yymm}{dd}.lzh")
    return os.path.exists(filepath)


def run_backfill_batch(database_url: str = None, max_days: int = 365):
    """
    LZHファイルの存在チェックで過去に遡り、欠損分を自動取得

    動作:
    1. 前日から1日ずつ過去に遡る
    2. LZHファイルが既にダウンロード済みの日が見つかったら停止
    3. その間の日付だけをダウンロード

    Args:
        database_url: データベースURL
        max_days: 最大遡る日数（デフォルト365日）

    Returns:
        処理結果のリスト
    """
    logger.info("=== LZHバックフィル処理開始 ===")

    if not database_url:
        database_url = os.environ.get('DATABASE_URL')

    if not database_url:
        logger.error("DATABASE_URLが設定されていません")
        return []

    now_jst = datetime.now(JST)
    yesterday = now_jst - timedelta(days=1)

    # 欠損日を特定
    missing_dates = []
    current_date = yesterday

    for _ in range(max_days):
        if check_lzh_exists(current_date):
            logger.info(f"LZHファイル発見: {current_date.strftime('%Y-%m-%d')} - ここで停止")
            break
        missing_dates.append(current_date)
        current_date -= timedelta(days=1)

    if not missing_dates:
        logger.info("欠損日なし - 処理不要")
        return []

    # 古い順に並べ替え（古い日から処理）
    missing_dates.reverse()

    logger.info(f"欠損日: {len(missing_dates)}日分")
    logger.info(f"範囲: {missing_dates[0].strftime('%Y-%m-%d')} 〜 {missing_dates[-1].strftime('%Y-%m-%d')}")

    # 各日を処理
    results = []
    total_saved = 0

    for target_date in missing_dates:
        result = process_single_date(target_date, database_url)
        results.append(result)
        total_saved += result.get('saved_count', 0)

    # サマリー
    success_count = len([r for r in results if r.get('status') == 'success'])
    failed_count = len(results) - success_count

    logger.info(f"=== LZHバックフィル処理完了 ===")
    logger.info(f"合計: {len(results)}日分処理、成功: {success_count}日、失敗: {failed_count}日、保存: {total_saved}件")

    return results


if __name__ == '__main__':
    # 直接実行時のテスト
    run_morning_batch()

'''
レーサー期別成績データの一括ダウンロードスクリプト
公式サイトから2002年〜2026年のLZHファイルをダウンロードし、解凍します。

Render環境対応: lhafileライブラリを使用（システムコマンド不要）
'''

import os
import requests
import logging
from datetime import datetime, timezone, timedelta
JST = timezone(timedelta(hours=9))

# lhafileライブラリをインポート（純粋Python実装）
try:
    import lhafile
    LHAFILE_AVAILABLE = True
except ImportError:
    LHAFILE_AVAILABLE = False
    logging.warning("lhafileライブラリがインストールされていません。pip install lhafile を実行してください。")

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ダウンロード先ディレクトリ
DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'racer_kibetsu')
EXTRACTED_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'racer_kibetsu_extracted')

# 公式サイトのURL
BASE_URL = "https://www.boatrace.jp/static_extra/pc_static/download/data/kibetsu"


def get_file_list():
    """
    ダウンロード対象のファイルリストを生成
    2002年〜2026年の前期・後期データ
    """
    files = []
    current_year = datetime.now(JST).year
    current_month = datetime.now(JST).month
    
    for year in range(2002, current_year + 1):
        # 年度の下2桁
        yy = str(year)[2:]
        
        # 前期（10月〜3月）: fan{YY}10.lzh
        # 後期（4月〜9月）: fan{YY}04.lzh
        
        # 前期ファイル（前年10月〜当年3月のデータ）
        # ファイル名の年は「期が始まる年」の下2桁
        # 例: fan2510.lzh = 2025年10月〜2026年3月のデータ
        
        if year <= current_year:
            # 前期（YY10）
            files.append(f"fan{yy}10.lzh")
            
            # 後期（YY04）- 現在の年で、まだ後期が始まっていない場合はスキップ
            if year < current_year or (year == current_year and current_month >= 4):
                files.append(f"fan{yy}04.lzh")
    
    return files


def download_file(filename):
    """
    指定されたファイルをダウンロード
    """
    url = f"{BASE_URL}/{filename}"
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    
    # 既にダウンロード済みの場合はスキップ
    if os.path.exists(filepath):
        logger.info(f"既にダウンロード済み: {filename}")
        return filepath
    
    try:
        logger.info(f"ダウンロード中: {url}")
        response = requests.get(url, timeout=60)
        
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(response.content)
            logger.info(f"ダウンロード完了: {filename} ({len(response.content)} bytes)")
            return filepath
        elif response.status_code == 404:
            logger.warning(f"ファイルが存在しません: {filename}")
            return None
        else:
            logger.error(f"ダウンロード失敗: {filename} (HTTP {response.status_code})")
            return None
            
    except Exception as e:
        logger.error(f"ダウンロードエラー: {filename} - {e}")
        return None


def extract_lzh(filepath):
    """
    LZHファイルを解凍（lhafileライブラリを使用）
    
    Render環境対応: システムコマンド（lha/7z/unar）に依存せず、
    純粋Pythonのlhafileライブラリを使用
    
    注意: LhaFileオブジェクトはcontext managerをサポートしていないため、
    with文を使用せずに直接操作する
    """
    if not filepath or not os.path.exists(filepath):
        return None
    
    filename = os.path.basename(filepath)
    output_dir = os.path.join(EXTRACTED_DIR, filename.replace('.lzh', ''))
    
    # 既に解凍済みの場合はスキップ
    if os.path.exists(output_dir) and os.listdir(output_dir):
        logger.info(f"既に解凍済み: {filename}")
        return output_dir
    
    os.makedirs(output_dir, exist_ok=True)
    
    # lhafileライブラリを使用して解凍
    if LHAFILE_AVAILABLE:
        try:
            # LhaFileはcontext managerをサポートしていないため、with文を使用しない
            lzh = lhafile.Lhafile(filepath)
            try:
                for info in lzh.infolist():
                    # ファイル名を取得（パスセパレータを正規化）
                    member_name = info.filename.replace('\\', '/').split('/')[-1]
                    if not member_name:
                        continue
                    
                    # ファイルを解凍
                    output_path = os.path.join(output_dir, member_name)
                    with open(output_path, 'wb') as f:
                        f.write(lzh.read(info.filename))
                    logger.debug(f"解凍: {member_name}")
            finally:
                # LhaFileにはclose()メソッドがないため、何もしない
                pass
            
            logger.info(f"解凍完了 (lhafile): {filename}")
            return output_dir
            
        except Exception as e:
            logger.error(f"lhafile解凍エラー: {filename} - {e}")
            # フォールバック: システムコマンドを試す
            return _extract_lzh_system_command(filepath, output_dir, filename)
    else:
        # lhafileが利用できない場合はシステムコマンドを試す
        return _extract_lzh_system_command(filepath, output_dir, filename)


def _extract_lzh_system_command(filepath, output_dir, filename):
    """
    システムコマンドを使用してLZHファイルを解凍（フォールバック用）
    """
    import subprocess
    
    try:
        # lhaコマンドで解凍（Linuxの場合）
        try:
            subprocess.run(
                ['lha', '-xw=' + output_dir, filepath],
                check=True,
                capture_output=True
            )
            logger.info(f"解凍完了 (lha): {filename}")
            return output_dir
        except FileNotFoundError:
            # lhaがない場合は7zを試す
            try:
                subprocess.run(
                    ['7z', 'x', '-o' + output_dir, filepath, '-y'],
                    check=True,
                    capture_output=True
                )
                logger.info(f"解凍完了 (7z): {filename}")
                return output_dir
            except FileNotFoundError:
                # unarを試す
                try:
                    subprocess.run(
                        ['unar', '-o', output_dir, filepath],
                        check=True,
                        capture_output=True
                    )
                    logger.info(f"解凍完了 (unar): {filename}")
                    return output_dir
                except FileNotFoundError:
                    logger.error(f"解凍ツールが見つかりません: lha, 7z, unar のいずれかをインストールしてください")
                    return None
                
    except subprocess.CalledProcessError as e:
        logger.error(f"解凍エラー: {filename} - {e}")
        return None
    except Exception as e:
        logger.error(f"解凍エラー: {filename} - {e}")
        return None


def download_all():
    """
    全てのレーサー期別成績データをダウンロード・解凍
    """
    # ディレクトリ作成
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(EXTRACTED_DIR, exist_ok=True)
    
    files = get_file_list()
    logger.info(f"ダウンロード対象: {len(files)} ファイル")
    
    success_count = 0
    fail_count = 0
    
    for filename in files:
        filepath = download_file(filename)
        if filepath:
            extracted = extract_lzh(filepath)
            if extracted:
                success_count += 1
            else:
                fail_count += 1
        else:
            fail_count += 1
    
    logger.info(f"完了: 成功 {success_count} / 失敗 {fail_count}")
    return success_count, fail_count


def download_latest():
    """
    最新のレーサー期別成績データのみダウンロード
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(EXTRACTED_DIR, exist_ok=True)
    
    current_year = datetime.now(JST).year
    current_month = datetime.now(JST).month
    yy = str(current_year)[2:]
    
    # 現在の期に応じてファイルを選択
    if current_month >= 10:
        # 10月以降は前期データ
        filename = f"fan{yy}10.lzh"
    elif current_month >= 4:
        # 4月〜9月は後期データ
        filename = f"fan{yy}04.lzh"
    else:
        # 1月〜3月は前年の前期データ
        prev_yy = str(current_year - 1)[2:]
        filename = f"fan{prev_yy}10.lzh"
    
    logger.info(f"最新データをダウンロード: {filename}")
    filepath = download_file(filename)
    if filepath:
        extracted = extract_lzh(filepath)
        if extracted:
            logger.info(f"最新データの解凍完了: {extracted}")
            return extracted
    
    return None


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='レーサー期別成績データのダウンロード')
    parser.add_argument('--all', action='store_true', help='全データをダウンロード')
    parser.add_argument('--latest', action='store_true', help='最新データのみダウンロード')
    
    args = parser.parse_args()
    
    if args.all:
        download_all()
    elif args.latest:
        download_latest()
    else:
        # デフォルトは最新データのみ
        download_latest()

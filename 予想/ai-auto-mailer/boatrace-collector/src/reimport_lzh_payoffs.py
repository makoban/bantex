# -*- coding: utf-8 -*-
"""
LZH一括再インポートスクリプト（ローカル実行用）

20年前から前日までのLZHデータをダウンロードしてDBに保存します。
複勝2組・ワイド3組が正しく保存されるようになっています（Ver1.56修正済み）。

使用方法:
1. DATABASE_URLを環境変数に設定するか、.envファイルに記載
2. python reimport_lzh_payoffs.py --start 200601 --end 202601

注意:
- 20年分のデータは数時間かかります
- 既存データは上書きされます（ON CONFLICT DO UPDATE）
"""
import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv

# 同じディレクトリのモジュールをインポート
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from import_historical_data import (
    download_month_results,
    import_results_to_db,
    create_historical_tables,
    create_payoffs_table,
    logger
)

def main():
    parser = argparse.ArgumentParser(description='LZHデータを一括再インポート')
    parser.add_argument('--start', type=str, default='200601', help='開始年月 (YYYYMM)')
    parser.add_argument('--end', type=str, default=None, help='終了年月 (YYYYMM)、省略時は前月')
    parser.add_argument('--skip-download', action='store_true', help='ダウンロードをスキップ（既存ファイルを使用）')
    args = parser.parse_args()

    # .envファイルを読み込み
    load_dotenv()

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("エラー: DATABASE_URLが設定されていません")
        print("環境変数に設定するか、.envファイルにDATABASE_URL=...を記載してください")
        sys.exit(1)

    # 終了年月のデフォルト（前月）
    if args.end is None:
        now = datetime.now()
        if now.month == 1:
            args.end = f"{now.year - 1}12"
        else:
            args.end = f"{now.year}{now.month - 1:02d}"

    print(f"=== LZH一括再インポート ===")
    print(f"期間: {args.start} - {args.end}")
    print(f"DATABASE_URL: {database_url[:50]}...")
    print()

    # テーブル作成
    print("テーブルを作成/確認中...")
    create_historical_tables()
    create_payoffs_table()

    # 年月リストを生成
    year_months = []
    start_year = int(args.start[:4])
    start_month = int(args.start[4:6])
    end_year = int(args.end[:4])
    end_month = int(args.end[4:6])

    year = start_year
    month = start_month
    while year < end_year or (year == end_year and month <= end_month):
        year_months.append(f"{year}{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1

    print(f"処理対象: {len(year_months)}ヶ月")
    print()

    # 各月を処理
    total_results = 0
    for i, year_month in enumerate(year_months):
        print(f"[{i+1}/{len(year_months)}] {year_month}...")

        # ダウンロード
        if not args.skip_download:
            try:
                download_count = download_month_results(year_month)
                print(f"  ダウンロード: {download_count}ファイル")
            except Exception as e:
                print(f"  ダウンロードエラー: {e}")
                continue

        # DBにインポート
        try:
            result_count = import_results_to_db(year_month)
            total_results += result_count
            print(f"  インポート: {result_count}件")
        except Exception as e:
            print(f"  インポートエラー: {e}")
            continue

    print()
    print(f"=== 完了 ===")
    print(f"合計インポート: {total_results}件")

if __name__ == '__main__':
    main()

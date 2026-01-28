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
    elif command == 'reset':
        reset_progress()
    elif command == 'reset_import':
        reset_progress(['import_results', 'import_programs', 'import_payoffs'])
    elif command == 'reset_results':
        reset_progress(['import_results'])
    else:
        print(f"不明なコマンド: {command}")
        sys.exit(1)

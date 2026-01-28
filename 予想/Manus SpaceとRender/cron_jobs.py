        
        logger.info("=== 結果収集ジョブ完了 ===")
    except Exception as e:
        logger.error(f"結果収集ジョブ失敗: {e}")
        sys.exit(1)


def update_manus_virtual_bets(boatrace_db_url: str):
    """
    Manus Space DBのvirtualBetsを更新
    
    - confirmedステータスで結果未確定のレースを取得
    - 外部DBから結果を取得
    - 的中/不的中を判定してvirtualBetsを更新
    - 資金（virtualFunds）も更新
    """
    manus_db_url = os.environ.get('MANUS_DATABASE_URL')
    if not manus_db_url:
        logger.debug("MANUS_DATABASE_URL未設定、仮想購入結果更新をスキップ")
        return
    
    logger.info("=== Manus Space DB 仮想購入結果更新開始 ===")
    
    try:
        import pymysql
        from pymysql.cursors import DictCursor
        import psycopg2
        from psycopg2.extras import DictCursor as PgDictCursor
        import json
        import re
        
        # MySQL URL解析
        def parse_mysql_url(url: str) -> dict:
            pattern = r'mysql://([^:]+):([^@]+)@([^:/]+):?(\d+)?/([^?]+)(?:\?(.*))?'
            match = re.match(pattern, url)
            if not match:
                raise ValueError(f"Invalid MySQL URL: {url}")
            
            user, password, host, port, database, params = match.groups()
            
            config = {
                'host': host,
                'user': user,
                'password': password,
                'database': database,
                'port': int(port) if port else 4000,
                'charset': 'utf8mb4',
                'cursorclass': DictCursor,
            }
            
            if params and 'ssl' in params.lower():
                config['ssl'] = {'ssl': {}}
            
            return config
        
        # Manus Space DBに接続
        manus_config = parse_mysql_url(manus_db_url)
        manus_config['ssl'] = {'ssl': {}}
        manus_conn = pymysql.connect(**manus_config)
        
        # 外部DBに接続
        pg_conn = psycopg2.connect(boatrace_db_url)
        
        try:
            # confirmedステータスで結果未確定のレースを取得
            with manus_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM virtualBets 
                    WHERE status = 'confirmed'
                    AND resultConfirmedAt IS NULL
                """)
                confirmed_bets = cursor.fetchall()
            
            if not confirmed_bets:
                logger.info("結果待ちの購入がありません")
                return
            
            logger.info(f"結果確認対象: {len(confirmed_bets)}件")
            
            for bet in confirmed_bets:
                try:
                    process_single_bet_result(bet, manus_conn, pg_conn)
                except Exception as e:
                    logger.error(f"結果処理エラー: bet_id={bet['id']}, error={e}")
        
        finally:
            manus_conn.close()
            pg_conn.close()
        
        logger.info("=== Manus Space DB 仮想購入結果更新完了 ===")
        
    except ImportError as e:
        logger.error(f"必要なモジュールがインストールされていません: {e}")
    except Exception as e:
        logger.error(f"Manus Space DB更新エラー: {e}")


def process_single_bet_result(bet: dict, manus_conn, pg_conn):
    """単一の購入結果を処理"""
    from psycopg2.extras import DictCursor as PgDictCursor
    import json
    
    bet_id = bet['id']
    strategy_type = bet['strategyType']
    race_date = bet['raceDate'].strftime('%Y%m%d') if hasattr(bet['raceDate'], 'strftime') else str(bet['raceDate']).replace('-', '')
    stadium_code = bet['stadiumCode']
    race_number = bet['raceNumber']
    combination = bet['combination']
    bet_type = bet['betType']
    bet_amount = float(bet['betAmount'])
    
    logger.info(f"結果確認: {stadium_code} {race_number}R {combination}")
    
    # 外部DBから結果を取得
    with pg_conn.cursor(cursor_factory=PgDictCursor) as cursor:
        # historical_race_resultsから結果を取得
        cursor.execute("""
            SELECT 
                hrr.stadium_code,
                hrr.race_no::integer as race_number,
                hrr.race_date,
                MAX(CASE WHEN hrr.rank IN ('1', '01') THEN hrr.boat_no::integer END) as rank1,
                MAX(CASE WHEN hrr.rank IN ('2', '02') THEN hrr.boat_no::integer END) as rank2,
                MAX(CASE WHEN hrr.rank IN ('3', '03') THEN hrr.boat_no::integer END) as rank3
            FROM historical_race_results hrr
            WHERE hrr.stadium_code = %s 
              AND hrr.race_no = %s
              AND hrr.race_date = %s
            GROUP BY hrr.stadium_code, hrr.race_no, hrr.race_date
        """, (stadium_code, str(race_number).zfill(2), race_date))
        result = cursor.fetchone()
        
        if not result:
            # race_resultsテーブルからも試す
            cursor.execute("""
                SELECT 
                    rr.first_place as rank1,
                    rr.second_place as rank2,
                    rr.third_place as rank3
                FROM race_results rr
                JOIN races r ON rr.race_id = r.id
                WHERE r.stadium_code = %s 
                  AND r.race_number = %s
                  AND r.race_date = %s
            """, (int(stadium_code), race_number, race_date.replace('/', '-') if '/' in race_date else f"{race_date[:4]}-{race_date[4:6]}-{race_date[6:8]}"))
            result = cursor.fetchone()
        
        if not result or not result['rank1']:
            logger.info(f"レース結果未確定: {stadium_code} {race_number}R")
            return
        
        # 的中判定
        actual_result = str(result['rank1'])
        is_hit = False
        payoff = 0
        
        if bet_type == 'win':
            # 単勝の場合
            is_hit = (combination == actual_result)
            if is_hit:
                # 払戻金を取得
                cursor.execute("""
                    SELECT payoff FROM payoffs p
                    JOIN races r ON p.race_id = r.id
                    WHERE r.stadium_code = %s 
                      AND r.race_number = %s
                      AND r.race_date = %s
                      AND p.bet_type = 'win'
                """, (int(stadium_code), race_number, f"{race_date[:4]}-{race_date[4:6]}-{race_date[6:8]}"))
                payoff_row = cursor.fetchone()
                if payoff_row:
                    payoff = float(payoff_row['payoff'])
        
        elif bet_type == 'quinella':
            # 2連複の場合
            result_combo = f"{min(result['rank1'], result['rank2'])}-{max(result['rank1'], result['rank2'])}"
            actual_result = result_combo
            is_hit = (combination == result_combo)
            if is_hit:
                cursor.execute("""
                    SELECT payoff FROM payoffs p
                    JOIN races r ON p.race_id = r.id
                    WHERE r.stadium_code = %s 
                      AND r.race_number = %s
                      AND r.race_date = %s
                      AND p.bet_type = 'quinella'
                      AND p.combination = %s
                """, (int(stadium_code), race_number, f"{race_date[:4]}-{race_date[4:6]}-{race_date[6:8]}", combination))
                payoff_row = cursor.fetchone()
                if payoff_row:
                    payoff = float(payoff_row['payoff'])
        
        elif bet_type == 'exacta':
            # 2連単の場合
            result_combo = f"{result['rank1']}-{result['rank2']}"
            actual_result = result_combo
            is_hit = (combination == result_combo)
            if is_hit:
                cursor.execute("""
                    SELECT payoff FROM payoffs p
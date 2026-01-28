"""
expire_overdue_bets関数の修正版
"""

def expire_overdue_bets(self):
    """
    締切が過ぎたpending状態の購入予定をskippedに更新
    """
    logger.info("=== 期限切れ購入予定の処理開始 ===")
    
    conn = self.get_manus_connection()
    if not conn:
        return 0
    
    boatrace_conn = self.get_boatrace_connection()
    if not boatrace_conn:
        logger.error("競艇データDBに接続できません")
        return 0
    
    try:
        with conn.cursor() as cursor:
            # pendingの購入予定を取得
            cursor.execute("""
                SELECT id, raceDate, stadiumCode, raceNumber 
                FROM virtualBets 
                WHERE status = 'pending'
            """)
            pending_bets = cursor.fetchall()
            
            if not pending_bets:
                logger.info("期限切れの購入予定はありません")
                boatrace_conn.close()
                return 0
            
            logger.info(f"pending件数: {len(pending_bets)}件")
            
            # 競艇データDBから締切時間を取得して期限切れを判定
            expired_bets = []
            # aware datetime(JST)で統一して比較
            now_jst = datetime.now(JST)
            
            with boatrace_conn.cursor() as boatrace_cursor:
                for bet in pending_bets:
                    boatrace_cursor.execute("""
                        SELECT deadline_at 
                        FROM races 
                        WHERE race_date = %s 
                        AND stadium_code = %s 
                        AND race_number = %s
                    """, (bet['raceDate'], int(bet['stadiumCode']), bet['raceNumber']))
                    race = boatrace_cursor.fetchone()
                    
                    if race and race['deadline_at']:
                        deadline = race['deadline_at']
                        # deadlineがnaiveの場合はJSTとして扱う
                        if deadline.tzinfo is None:
                            deadline = deadline.replace(tzinfo=JST)
                        
                        if now_jst > deadline:
                            bet['scheduledDeadline'] = deadline
                            expired_bets.append(bet)
            
            boatrace_conn.close()
            
            if expired_bets:
                logger.info(f"期限切れで無効化対象: {len(expired_bets)}件")
                
                # updatedAtを文字列形式に変換（TiDB対応）
                now_str = datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')
                
                import json
                for bet in expired_bets:
                    # reasonに見送り理由を設定
                    reason = {'skipReason': '締切超過（購入判断未実行）', 'decision': 'skipped'}
                    reason_json = json.dumps(reason, ensure_ascii=False)
                    
                    # statusをskippedに更新
                    cursor.execute("""
                        UPDATE virtualBets 
                        SET status = 'skipped',
                            reason = %s,
                            updatedAt = %s
                        WHERE id = %s
                    """, (reason_json, now_str, bet['id']))
                    
                    logger.info(f"  - bet_id={bet['id']}, {bet['stadiumCode']} {bet['raceNumber']}R, 締切={bet['scheduledDeadline']}")
                    logger.info(f"    -> skippedに更新完了（締切超過）")
                
                conn.commit()
            else:
                logger.info("期限切れの購入予定はありません")
            
            return len(expired_bets)
            
    except Exception as e:
        logger.error(f"期限切れ処理エラー: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()

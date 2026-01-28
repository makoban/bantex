"""
仮想購入シミュレーションモジュール

PostgreSQL（kokotomo-db-staging）と連携して、締切1分前に購入判断を行い、
結果確定後に的中/不的中を更新する。

※ Manus Space DBは使用しない。全てPostgreSQLに一本化。

対応戦略:
- 11r12r_win: 11R・12R単勝戦略
- bias_1_3: 1-3穴バイアス戦略
- bias_1_3_2nd: 3穴2nd戦略（当地勝率4.5-6.0、特定競艇場×R）
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor

# ログ設定
logger = logging.getLogger(__name__)

# 日本時間
JST = timezone(timedelta(hours=9))

# 戦略設定
STRATEGIES = {
    '11r12r_win': {
        'name': '11R・12R単勝戦略',
        'target_races': [11, 12],
        'bet_type': 'win',
        'min_odds': 1.5,
        'max_odds': 10.0,
        'bet_amount': 1000,
        'min_expected_value': 1.0,  # 期待値1.0以上で購入
    },
    'bias_1_3': {
        'name': '1-3穴バイアス戦略（論文準拠）',
        'target_stadium': '24',  # 大村競艇場のみ（論文の対象場）
        'target_races': 'all',
        'bet_type': 'auto',  # 2連単/2連複の高い方を自動選択（論文の条件）
        'combination': '1-3',
        'min_odds': 1.0,  # オッズ制限なし（論文に従う）
        'max_odds': 999.0,  # オッズ制限なし（論文に従う）
        'bet_amount': 1000,
        'min_local_win_rate': 6.5,  # 1号艇の当地勝率下限（論文の条件）
    },
    'bias_1_3_2nd': {
        'name': '3穴2nd戦略',
        'target_races': {
            # 回収率110%超えの競艇場×R番号
            '05': [2, 4, 6, 11],  # 多摩川
            '11': [2, 4, 5, 9],   # 琵琶湖
            '13': [1, 4, 6],      # 尼崎
            '18': [3, 6, 10],     # 徳山
            '24': [4],            # 大村
        },
        'bet_type': 'auto',  # 2連単/2連複の高い方を自動選択
        'combination': '1-3',
        'min_odds': 3.0,
        'max_odds': 100.0,
        'bet_amount': 1000,
        'min_local_win_rate': 4.5,  # 1号艇の当地勝率4.5%以上
        'max_local_win_rate': 6.0,  # 1号艇の当地勝率6.0%未満
    }
}


class VirtualBettingManager:
    """仮想購入管理クラス（PostgreSQL専用）"""
    
    def __init__(self, db_url: str = None):
        """
        Args:
            db_url: PostgreSQLのURL
        """
        self.db_url = db_url or os.environ.get('DATABASE_URL')
        
        if not self.db_url:
            logger.warning("DATABASE_URL環境変数が設定されていません")
    
    def get_db_connection(self):
        """PostgreSQLへの接続を取得"""
        if not self.db_url:
            logger.error("DATABASE_URL環境変数が設定されていません")
            return None
        
        try:
            conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
            return conn
        except Exception as e:
            logger.error(f"DB接続エラー: {e}")
            return None
    
    def get_pending_bets(self, strategy_type: str, race_date: str, 
                         stadium_code: str, race_number: int) -> List[Dict]:
        """
        指定レースの購入予定（pending）を取得
        
        Args:
            strategy_type: 戦略タイプ
            race_date: レース日（YYYY-MM-DD）
            stadium_code: 競艇場コード
            race_number: レース番号
        
        Returns:
            購入予定のリスト
        """
        conn = self.get_db_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM virtual_bets 
                    WHERE strategy_type = %s 
                    AND race_date = %s 
                    AND stadium_code = %s 
                    AND race_number = %s 
                    AND status = 'pending'
                """, (strategy_type, race_date, stadium_code, race_number))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"購入予定取得エラー: {e}")
            return []
        finally:
            conn.close()
    
    def get_all_pending_bets_near_deadline(self, minutes_to_deadline: int = 1) -> List[Dict]:
        """
        締切N分前の全ての購入予定を取得
        
        Args:
            minutes_to_deadline: 締切までの分数
        
        Returns:
            購入予定のリスト
        """
        conn = self.get_db_connection()
        if not conn:
            return []
        
        try:
            # 現在時刻（UTC）
            now_utc = datetime.now(timezone.utc)
            # 締切N分前〜N+1分前のレースを対象
            deadline_start = now_utc + timedelta(minutes=minutes_to_deadline - 1)
            deadline_end = now_utc + timedelta(minutes=minutes_to_deadline + 1)
            
            logger.info(f"締切時間範囲: {deadline_start.astimezone(JST).strftime('%Y-%m-%d %H:%M:%S')} 〜 {deadline_end.astimezone(JST).strftime('%Y-%m-%d %H:%M:%S')} (JST)")
            
            with conn.cursor() as cursor:
                # racesテーブルと結合して締切時間を取得
                # 型の不一致を解消: virtual_bets.stadium_code(varchar) vs races.stadium_code(smallint)
                cursor.execute("""
                    SELECT vb.*, r.deadline_at as scheduled_deadline
                    FROM virtual_bets vb
                    JOIN races r ON vb.race_date = r.race_date 
                        AND vb.stadium_code::smallint = r.stadium_code 
                        AND vb.race_number::smallint = r.race_number
                    WHERE vb.status = 'pending'
                    AND r.deadline_at BETWEEN %s AND %s
                """, (deadline_start, deadline_end))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"購入予定取得エラー: {e}")
            return []
        finally:
            conn.close()
    
    def confirm_bet(self, bet_id: int, final_odds: float, reason: dict = None):
        """
        購入を確定する
        
        Args:
            bet_id: 購入ID
            final_odds: 最終オッズ
            reason: 購入理由（更新用）
        """
        conn = self.get_db_connection()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cursor:
                now = datetime.now(timezone.utc)
                
                reason_json = json.dumps(reason, ensure_ascii=False) if reason else None
                
                cursor.execute("""
                    UPDATE virtual_bets 
                    SET status = 'confirmed',
                        odds = %s,
                        reason = %s,
                        decision_time = %s,
                        executed_at = %s,
                        updated_at = %s
                    WHERE id = %s
                """, (final_odds, reason_json, now, now, now, bet_id))
                
                conn.commit()
                logger.info(f"購入確定: bet_id={bet_id}, odds={final_odds}")
                return True
        except Exception as e:
            logger.error(f"購入確定エラー: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def skip_bet(self, bet_id: int, skip_reason: str):
        """
        購入を見送る
        
        Args:
            bet_id: 購入ID
            skip_reason: 見送り理由
        """
        conn = self.get_db_connection()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cursor:
                now = datetime.now(timezone.utc)
                
                # 現在の理由を取得
                cursor.execute("SELECT reason FROM virtual_bets WHERE id = %s", (bet_id,))
                row = cursor.fetchone()
                
                reason = {}
                if row and row.get('reason'):
                    try:
                        if isinstance(row['reason'], str):
                            reason = json.loads(row['reason'])
                        elif isinstance(row['reason'], dict):
                            reason = row['reason']
                    except:
                        pass
                
                reason['skipReason'] = skip_reason
                reason['decision'] = 'skipped'
                
                cursor.execute("""
                    UPDATE virtual_bets 
                    SET status = 'skipped',
                        reason = %s,
                        decision_time = %s,
                        updated_at = %s
                    WHERE id = %s
                """, (json.dumps(reason, ensure_ascii=False), now, now, bet_id))
                
                conn.commit()
                logger.info(f"購入見送り: bet_id={bet_id}, reason={skip_reason}")
                return True
        except Exception as e:
            logger.error(f"購入見送りエラー: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def update_result(self, bet_id: int, actual_result: str, payoff: float, 
                      is_hit: bool, return_amount: float, profit: float):
        """
        結果を更新する
        
        Args:
            bet_id: 購入ID
            actual_result: 実際の結果（"1", "1-3"など）
            payoff: 払戻金（100円あたり）
            is_hit: 的中したかどうか
            return_amount: 回収額
            profit: 損益
        """
        conn = self.get_db_connection()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cursor:
                now = datetime.now(timezone.utc)
                status = 'won' if is_hit else 'lost'
                
                cursor.execute("""
                    UPDATE virtual_bets 
                    SET status = %s,
                        actual_result = %s,
                        payoff = %s,
                        return_amount = %s,
                        profit = %s,
                        result_confirmed_at = %s,
                        updated_at = %s
                    WHERE id = %s
                """, (status, actual_result, payoff, return_amount, profit, now, now, bet_id))
                
                conn.commit()
                logger.info(f"結果更新: bet_id={bet_id}, status={status}, profit={profit}")
                return True
        except Exception as e:
            logger.error(f"結果更新エラー: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def update_fund(self, strategy_type: str, profit: float, is_hit: bool):
        """
        資金を更新する
        
        Args:
            strategy_type: 戦略タイプ
            profit: 損益
            is_hit: 的中したかどうか
        """
        conn = self.get_db_connection()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cursor:
                now = datetime.now(timezone.utc)
                
                # 現在の資金を取得
                cursor.execute("""
                    SELECT * FROM virtual_funds 
                    WHERE strategy_type = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (strategy_type,))
                fund = cursor.fetchone()
                
                if fund:
                    new_balance = float(fund['current_balance']) + profit
                    total_bets = fund['total_bets'] + 1
                    total_wins = fund['total_wins'] + (1 if is_hit else 0)
                    total_profit = float(fund['total_profit']) + profit
                    
                    cursor.execute("""
                        UPDATE virtual_funds 
                        SET current_balance = %s,
                            total_bets = %s,
                            total_wins = %s,
                            total_profit = %s,
                            updated_at = %s
                        WHERE id = %s
                    """, (new_balance, total_bets, total_wins, total_profit, now, fund['id']))
                else:
                    # 初期資金を作成
                    initial_balance = 100000
                    new_balance = initial_balance + profit
                    
                    cursor.execute("""
                        INSERT INTO virtual_funds 
                        (strategy_type, initial_balance, current_balance, total_bets, total_wins, total_profit, created_at, updated_at)
                        VALUES (%s, %s, %s, 1, %s, %s, %s, %s)
                    """, (strategy_type, initial_balance, new_balance, 1 if is_hit else 0, profit, now, now))
                
                conn.commit()
                logger.info(f"資金更新: strategy={strategy_type}, balance={new_balance}")
                return True
        except Exception as e:
            logger.error(f"資金更新エラー: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_latest_odds(self, race_date: str, stadium_code: str, race_number: int, 
                        odds_type: str, combination: str) -> Optional[float]:
        """
        最新オッズを取得（odds_historyテーブルから）
        
        Args:
            race_date: レース日（YYYYMMDD）
            stadium_code: 競艇場コード
            race_number: レース番号
            odds_type: オッズタイプ（win, 2f, 2t等）
            combination: 買い目（"1", "1=3"等）
        
        Returns:
            オッズ（取得できない場合はNone）
        """
        conn = self.get_db_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor() as cursor:
                # race_dateをYYYY-MM-DD形式に変換
                if len(race_date) == 8:
                    race_date_formatted = f"{race_date[:4]}-{race_date[4:6]}-{race_date[6:8]}"
                else:
                    race_date_formatted = race_date
                
                # オッズタイプはodds_historyではそのまま保存されている
                # win -> win, 2f -> 2f, 2t -> 2t
                db_odds_type = odds_type
                
                # 組み合わせを正規化
                # 単勝: "1" -> "1"
                # 2連複: "1=3" -> "1-3" (odds_historyでは1-3形式で保存)
                normalized_combination = combination.replace('=', '-')
                
                # odds_historyテーブルから最新オッズを取得
                # stadium_codeは文字列（'01', '02'等）で保存されている
                cursor.execute("""
                    SELECT odds_value FROM odds_history
                    WHERE race_date = %s 
                    AND stadium_code = %s 
                    AND race_number = %s
                    AND odds_type = %s
                    AND combination = %s
                    ORDER BY scraped_at DESC
                    LIMIT 1
                """, (race_date_formatted, stadium_code, race_number, db_odds_type, normalized_combination))
                row = cursor.fetchone()
                
                if row and row.get('odds_value'):
                    return float(row['odds_value'])
                
                # 見つからない場合、stadium_codeを2桁にパディングして再試行
                if len(str(stadium_code)) == 1:
                    padded_code = f"0{stadium_code}"
                else:
                    padded_code = str(stadium_code).zfill(2)
                
                cursor.execute("""
                    SELECT odds_value FROM odds_history
                    WHERE race_date = %s 
                    AND stadium_code = %s 
                    AND race_number = %s
                    AND odds_type = %s
                    AND combination = %s
                    ORDER BY scraped_at DESC
                    LIMIT 1
                """, (race_date_formatted, padded_code, race_number, db_odds_type, normalized_combination))
                row = cursor.fetchone()
                
                if row and row.get('odds_value'):
                    return float(row['odds_value'])
                
                return None
        except Exception as e:
            logger.error(f"オッズ取得エラー: {e}")
            return None
        finally:
            conn.close()
    
    def expire_overdue_bets(self):
        """
        締切が過ぎた購入予定を見送り（skipped）に更新する
        """
        logger.info("=== 期限切れ購入予定の処理開始 ===")
        
        conn = self.get_db_connection()
        if not conn:
            return 0
        
        try:
            now_utc = datetime.now(timezone.utc)
            
            with conn.cursor() as cursor:
                # 締切が過ぎたpendingの購入予定を取得
                # 型の不一致を解消: virtual_bets.stadium_code(varchar) vs races.stadium_code(smallint)
                cursor.execute("""
                    SELECT vb.id, vb.stadium_code, vb.race_number, vb.reason, r.deadline_at
                    FROM virtual_bets vb
                    JOIN races r ON vb.race_date = r.race_date 
                        AND vb.stadium_code::smallint = r.stadium_code 
                        AND vb.race_number::smallint = r.race_number
                    WHERE vb.status = 'pending'
                    AND r.deadline_at < %s
                """, (now_utc,))
                expired_bets = cursor.fetchall()
                
                if not expired_bets:
                    logger.info("期限切れの購入予定はありません")
                    return 0
                
                logger.info(f"期限切れで無効化対象: {len(expired_bets)}件")
                
                for bet in expired_bets:
                    # 既存のreasonを取得してskipReasonを追加
                    reason = {}
                    if bet.get('reason'):
                        try:
                            if isinstance(bet['reason'], str):
                                reason = json.loads(bet['reason'])
                            elif isinstance(bet['reason'], dict):
                                reason = bet['reason']
                        except:
                            pass
                    
                    reason['skipReason'] = '締切超過（購入判断未実行）'
                    reason['decision'] = 'skipped'
                    
                    cursor.execute("""
                        UPDATE virtual_bets 
                        SET status = 'skipped',
                            reason = %s,
                            updated_at = %s
                        WHERE id = %s
                    """, (json.dumps(reason, ensure_ascii=False), now_utc, bet['id']))
                    
                    logger.info(f"  - bet_id={bet['id']}, {bet['stadium_code']} {bet['race_number']}R, 締切={bet['deadline_at']}")
                    logger.info(f"    -> skippedに更新完了（締切超過）")
                
                conn.commit()
                return len(expired_bets)
                
        except Exception as e:
            logger.error(f"期限切れ処理エラー: {e}")
            if conn:
                conn.rollback()
            return 0
        finally:
            conn.close()
    
    def process_deadline_bets(self):
        """
        締切1分前の購入予定を処理する
        
        - pendingステータスのレースを取得
        - 最新オッズを確認
        - 条件を満たせばconfirmed、満たさなければskipped
        """
        logger.info("=== 締切1分前の購入判断処理開始 ===")
        
        # 締切1分前の購入予定を取得
        pending_bets = self.get_all_pending_bets_near_deadline(minutes_to_deadline=1)
        
        if not pending_bets:
            logger.info("処理対象の購入予定がありません")
            return
        
        logger.info(f"処理対象: {len(pending_bets)}件")
        
        for bet in pending_bets:
            try:
                self._process_single_bet(bet)
            except Exception as e:
                logger.error(f"購入処理エラー: bet_id={bet['id']}, error={e}")
    
    def _process_single_bet(self, bet: Dict):
        """単一の購入予定を処理"""
        bet_id = bet['id']
        strategy_type = bet['strategy_type']
        race_date = bet['race_date'].strftime('%Y%m%d') if hasattr(bet['race_date'], 'strftime') else str(bet['race_date']).replace('-', '')
        stadium_code = bet['stadium_code']
        race_number = bet['race_number']
        combination = bet['combination']
        bet_type = bet['bet_type']
        
        logger.info(f"処理中: {stadium_code} {race_number}R {combination} ({strategy_type})")
        
        # オッズタイプを変換
        odds_type_map = {'win': 'win', 'quinella': '2f', 'exacta': '2t'}
        odds_type = odds_type_map.get(bet_type, 'win')
        
        # 最新オッズを取得
        final_odds = self.get_latest_odds(race_date, stadium_code, race_number, odds_type, combination)
        
        if final_odds is None:
            logger.warning(f"オッズ取得失敗: {stadium_code} {race_number}R {combination}")
            self.skip_bet(bet_id, "オッズ取得失敗")
            return
        
        # 戦略設定を取得
        strategy = STRATEGIES.get(strategy_type, {})
        min_odds = strategy.get('min_odds', 1.5)
        max_odds = strategy.get('max_odds', 10.0)
        
        # 購入判断
        reason = {}
        if bet.get('reason'):
            try:
                if isinstance(bet['reason'], str):
                    reason = json.loads(bet['reason'])
                elif isinstance(bet['reason'], dict):
                    reason = bet['reason']
            except:
                pass
        
        reason['finalOdds'] = final_odds
        
        if final_odds < min_odds:
            reason['decision'] = 'skipped'
            reason['skipReason'] = f'オッズが低すぎる ({final_odds} < {min_odds})'
            self.skip_bet(bet_id, reason['skipReason'])
        elif final_odds > max_odds:
            reason['decision'] = 'skipped'
            reason['skipReason'] = f'オッズが高すぎる ({final_odds} > {max_odds})'
            self.skip_bet(bet_id, reason['skipReason'])
        else:
            # 期待値計算（単勝戦略の場合）
            if strategy_type == '11r12r_win':
                # 1号艇の勝率を仮定（実際は過去データから計算）
                estimated_win_rate = 0.5  # 50%と仮定
                expected_value = final_odds * estimated_win_rate
                reason['expectedValue'] = expected_value
                
                if expected_value < strategy.get('min_expected_value', 1.0):
                    reason['decision'] = 'skipped'
                    reason['skipReason'] = f'期待値が低い ({expected_value:.2f} < 1.0)'
                    self.skip_bet(bet_id, reason['skipReason'])
                    return
            
            reason['decision'] = 'confirmed'
            self.confirm_bet(bet_id, final_odds, reason)
    
    def process_results(self):
        """
        確定済みレースの結果を更新する
        
        - confirmedステータスのレースを取得
        - 結果を確認
        - won/lostに更新し、資金を反映
        """
        logger.info("=== 結果更新処理開始 ===")
        
        conn = self.get_db_connection()
        if not conn:
            return
        
        try:
            with conn.cursor() as cursor:
                # 確定済みで結果未確定のレースを取得
                cursor.execute("""
                    SELECT * FROM virtual_bets 
                    WHERE status = 'confirmed'
                    AND result_confirmed_at IS NULL
                """)
                confirmed_bets = cursor.fetchall()
        finally:
            conn.close()
        
        if not confirmed_bets:
            logger.info("結果待ちの購入がありません")
            return
        
        logger.info(f"結果確認対象: {len(confirmed_bets)}件")
        
        for bet in confirmed_bets:
            try:
                self._process_single_result(bet)
            except Exception as e:
                logger.error(f"結果処理エラー: bet_id={bet['id']}, error={e}")
    
    def _process_single_result(self, bet: Dict):
        """単一の結果を処理"""
        bet_id = bet['id']
        strategy_type = bet['strategy_type']
        race_date = bet['race_date'].strftime('%Y%m%d') if hasattr(bet['race_date'], 'strftime') else str(bet['race_date']).replace('-', '')
        stadium_code = bet['stadium_code']
        race_number = bet['race_number']
        combination = bet['combination']
        bet_type = bet['bet_type']
        bet_amount = float(bet['bet_amount'])
        
        logger.info(f"結果確認: {stadium_code} {race_number}R {combination}")
        
        conn = self.get_db_connection()
        if not conn:
            return
        
        try:
            with conn.cursor() as cursor:
                # race_dateをYYYY-MM-DD形式に変換
                if len(race_date) == 8:
                    race_date_formatted = f"{race_date[:4]}-{race_date[4:6]}-{race_date[6:8]}"
                else:
                    race_date_formatted = race_date
                
                cursor.execute("""
                    SELECT * FROM races 
                    WHERE race_date = %s 
                    AND stadium_code = %s 
                    AND race_number = %s
                """, (race_date_formatted, stadium_code, race_number))
                race = cursor.fetchone()
                
                if not race:
                    logger.info(f"レース結果未確定: {stadium_code} {race_number}R")
                    return
                
                # 結果が確定しているか確認
                if not race.get('result_1st'):
                    logger.info(f"レース結果未確定: {stadium_code} {race_number}R")
                    return
                
                # 的中判定
                actual_result = str(race['result_1st'])
                is_hit = False
                payoff = 0
                
                if bet_type == 'win':
                    # 単勝の場合
                    is_hit = (combination == actual_result)
                    if is_hit:
                        # 払戻金を取得
                        cursor.execute("""
                            SELECT payoff FROM payoffs 
                            WHERE race_date = %s 
                            AND stadium_code = %s 
                            AND race_number = %s
                            AND bet_type = 'win'
                        """, (race_date_formatted, stadium_code, race_number))
                        payoff_row = cursor.fetchone()
                        if payoff_row:
                            payoff = float(payoff_row['payoff'])
                
                elif bet_type == 'quinella':
                    # 2連複の場合
                    result_combo = f"{min(race['result_1st'], race['result_2nd'])}-{max(race['result_1st'], race['result_2nd'])}"
                    actual_result = result_combo
                    # 組み合わせを正規化
                    normalized_combination = combination.replace('=', '-')
                    is_hit = (normalized_combination == result_combo)
                    if is_hit:
                        cursor.execute("""
                            SELECT payoff FROM payoffs 
                            WHERE race_date = %s 
                            AND stadium_code = %s 
                            AND race_number = %s
                            AND bet_type = 'quinella'
                            AND combination = %s
                        """, (race_date_formatted, stadium_code, race_number, normalized_combination))
                        payoff_row = cursor.fetchone()
                        if payoff_row:
                            payoff = float(payoff_row['payoff'])
                
                elif bet_type == 'exacta':
                    # 2連単の場合
                    result_combo = f"{race['result_1st']}-{race['result_2nd']}"
                    actual_result = result_combo
                    is_hit = (combination == result_combo)
                    if is_hit:
                        cursor.execute("""
                            SELECT payoff FROM payoffs 
                            WHERE race_date = %s 
                            AND stadium_code = %s 
                            AND race_number = %s
                            AND bet_type = 'exacta'
                            AND combination = %s
                        """, (race_date_formatted, stadium_code, race_number, combination))
                        payoff_row = cursor.fetchone()
                        if payoff_row:
                            payoff = float(payoff_row['payoff'])
                
                # 回収額と損益を計算
                return_amount = (payoff / 100 * bet_amount) if is_hit else 0
                profit = return_amount - bet_amount
                
                # 結果を更新
                self.update_result(bet_id, actual_result, payoff, is_hit, return_amount, profit)
                
                # 資金を更新
                self.update_fund(strategy_type, profit, is_hit)
                
        except Exception as e:
            logger.error(f"結果取得エラー: {e}")
        finally:
            conn.close()


def process_virtual_betting():
    """
    仮想購入処理のエントリーポイント
    odds_worker.pyから呼び出される
    """
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        logger.debug("DATABASE_URL未設定、仮想購入処理をスキップ")
        return
    
    manager = VirtualBettingManager()
    
    # まず、期限切れの購入予定を処理
    manager.expire_overdue_bets()
    
    # 締切1分前の購入判断
    manager.process_deadline_bets()
    
    # 結果更新
    manager.process_results()


if __name__ == '__main__':
    # テスト実行
    logging.basicConfig(level=logging.INFO)
    process_virtual_betting()

"""
仮想購入システム

予想に基づいて仮想的な購入を行い、結果を追跡するシステム
"""

import json
import logging
import os
import random
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, time, timedelta, timezone

from typing import Dict, List, Optional, Tuple, Any
import psycopg2
from psycopg2.extras import RealDictCursor

# ロガー設定
logger = logging.getLogger(__name__)

# タイムゾーン設定
JST = timezone(timedelta(hours=9))

# 戦略設定
STRATEGIES = {
    'bias_1_3_2nd': {
        'name': '3穴2nd戦略',
        'combination': '1-3',
        'bet_type': 'auto',
        'base_amount': 1000,
        'min_local_win_rate': 4.5,
        'max_local_win_rate': 6.0,
        'min_odds': 3.0,  # 仕様書通り
        'max_odds': 100.0,  # 仕様書通り
        # 検証レポート準拠の15パターン（ROI 106.6%達成条件）
        'target_conditions': [
            ('07', 4),   # 蒲郡 4R
            ('07', 5),   # 蒲郡 5R
            ('03', 4),   # 江戸川 4R
            ('04', 4),   # 平和島 4R
            ('09', 4),   # 津 4R
            ('10', 4),   # 三国 4R
            ('11', 4),   # 琵琶湖 4R
            ('12', 5),   # 住之江 5R
            ('14', 4),   # 鳴門 4R
            ('15', 4),   # 丸亀 4R
            ('18', 4),   # 徳山 4R
            ('19', 4),   # 下関 4R
            ('20', 4),   # 若松 4R
            ('21', 4),   # 芦屋 4R
            ('23', 4),   # 唐津 4R
        ],
        # 朝にpendingとして登録（オッズ条件は締切前に判断）
        'register_at_batch': True,
    },
    'win_10x_1_3': {
        'name': '１単勝10倍以上１－３',
        'combination': '1-3',
        'bet_type': 'exacta',  # 2連単固定
        'base_amount': 1000,
        # 条件: 1号艇の単勝オッズが10倍以上
        'min_win_odds': 10.0,
        # 朝登録なし（締切3分前に直接チェック）
        'register_at_batch': False,
    }
}




class VirtualBettingManager:
    """仮想購入管理クラス"""

    def __init__(self, db_url: str = None):
        """
        初期化

        Args:
            db_url: PostgreSQL接続URL
        """
        self.db_url = db_url or os.environ.get('DATABASE_URL')
        if not self.db_url:
            raise ValueError("DATABASE_URL is required")


    def register_daily_bets(self):
        """本日分の日次ベット登録"""
        logger.info("=== 日次購入予定登録開始 ===")

        # 本日のレース情報をDBから取得
        conn = self.get_db_connection()
        if not conn:
            return 0

        registered_count = 0
        try:
            # aware datetime(JST)で比較
            now = datetime.now(JST)
            today_date = now.date()

            with conn.cursor() as cursor:
                # 本日のレースを取得
                cursor.execute("""
                    SELECT r.id, r.race_date, r.stadium_code, r.race_number, r.deadline_at
                    FROM races r
                    WHERE r.race_date = %s
                    ORDER BY r.stadium_code, r.race_number
                """, (today_date,))
                races = cursor.fetchall()

                if not races:
                    logger.warning("本日のレース情報がありません")
                    return 0

                # 既存のベットを確認（重複登録防止）
                cursor.execute("""
                    SELECT stadium_code, race_number, strategy_type
                    FROM virtual_bets
                    WHERE race_date = %s
                """, (today_date,))
                existing = set((str(row['stadium_code']), row['race_number'], row['strategy_type']) for row in cursor.fetchall())

                # 番組表から1号艇の勝率を一括取得
                race_date_str = today_date.strftime('%Y%m%d')
                cursor.execute("""
                    SELECT stadium_code, race_no, local_win_rate
                    FROM historical_programs
                    WHERE race_date = %s AND boat_no = '1'
                """, (race_date_str,))
                win_rates = {(row['stadium_code'], row['race_no']): float(row['local_win_rate'])
                             for row in cursor.fetchall() if row['local_win_rate'] is not None}
                logger.info(f"番組表から{len(win_rates)}件の勝率データを取得")

                for race in races:
                    stadium_code = f"{race['stadium_code']:02d}"
                    race_number = race['race_number']

                    for strategy_key, strategy in STRATEGIES.items():
                        # 事前登録不要の戦略はスキップ（締切直前に直接チェック）
                        if not strategy.get('register_at_batch', True):
                            continue

                        is_target = False

                        # 戦略ごとの対象レース判定
                        if strategy_key == 'bias_1_3_2nd':
                            # 条件: 対象の競艇場×レース番号かチェック（15パターン）
                            # オッズ条件は締切3分前に判断
                            target_conditions = strategy.get('target_conditions', [])
                            if target_conditions:
                                if (stadium_code, race_number) not in target_conditions:
                                    continue
                            is_target = True

                        elif strategy_key == 'win_10x_1_3':
                            # register_at_batch=Falseなので朝登録しない
                            # 締切3分前に直接チェックして購入判断
                            continue

                        else:
                            # 未定義の戦略はスキップ
                            continue

                        if not is_target:
                            continue

                        # 既に登録済みかチェック
                        if (stadium_code, race_number, strategy_key) in existing:
                            continue

                        # 登録処理
                        self.create_bet(
                            race_date=today_date,
                            stadium_code=stadium_code,
                            race_number=race_number,
                            strategy_type=strategy_key,
                            combination=strategy.get('combination', '1-3'),
                            bet_type=strategy.get('bet_type', 'auto'),
                            amount=strategy.get('base_amount', 1000),
                            reason={'strategy_name': strategy['name'], 'registered_at': now.isoformat()}
                        )
                        registered_count += 1

            conn.commit()
            logger.info(f"日次ベット登録完了: {registered_count}件")
            return registered_count

        except Exception as e:
            logger.error(f"日次ベット登録エラー: {e}")
            return 0
        finally:
            conn.close()

    def get_db_connection(self):
        """データベース接続を取得"""
        try:
            conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
            return conn
        except Exception as e:
            logger.error(f"DB接続エラー: {e}")
            return None

    def create_bet(self, race_date: str, stadium_code: str, race_number: int,
                   strategy_type: str, combination: str, bet_type: str,
                   amount: int = 1000, reason: dict = None) -> Optional[int]:
        """
        仮想購入を作成

        Args:
            race_date: レース日（YYYY-MM-DD）
            stadium_code: 競艇場コード
            race_number: レース番号
            strategy_type: 戦略タイプ
            combination: 買い目
            bet_type: 購入タイプ（win, quinella, exacta等）
            amount: 購入金額
            reason: 購入理由（JSON）

        Returns:
            作成されたbet_id
        """
        conn = self.get_db_connection()
        if not conn:
            return None

        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO virtual_bets (
                        race_date, stadium_code, race_number, strategy_type,
                        combination, bet_type, amount, status, reason, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)
                    RETURNING id
                """, (
                    race_date, stadium_code, race_number, strategy_type,
                    combination, bet_type, amount,
                    json.dumps(reason) if reason else None,
                    datetime.now(JST)  # aware datetime(JST)で保存
                ))
                bet_id = cursor.fetchone()['id']
                conn.commit()
                return bet_id
        except Exception as e:
            logger.error(f"購入作成エラー: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def confirm_bet(self, bet_id: int, final_odds: float, reason: dict = None):
        """
        購入を確定

        Args:
            bet_id: 購入ID
            final_odds: 確定オッズ
            reason: 確定理由（JSON）
        """
        conn = self.get_db_connection()
        if not conn:
            return

        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE virtual_bets
                    SET status = 'confirmed',
                        final_odds = %s,
                        reason = %s,
                        confirmed_at = %s,
                        updated_at = %s
                    WHERE id = %s
                """, (
                    final_odds,
                    json.dumps(reason, ensure_ascii=False) if reason else None,
                    datetime.now(JST),  # aware datetime(JST)で保存
                    datetime.now(JST),  # aware datetime(JST)で保存
                    bet_id
                ))
                conn.commit()
                logger.info(f"購入確定: bet_id={bet_id}, odds={final_odds}")
        except Exception as e:
            logger.error(f"購入確定エラー: {e}")
            conn.rollback()
        finally:
            conn.close()

    def skip_bet(self, bet_id: int, reason: str):
        """
        購入を見送り

        Args:
            bet_id: 購入ID
            reason: 見送り理由
        """
        conn = self.get_db_connection()
        if not conn:
            return

        try:
            with conn.cursor() as cursor:
                # 既存のreasonを取得
                cursor.execute("SELECT reason FROM virtual_bets WHERE id = %s", (bet_id,))
                row = cursor.fetchone()
                existing_reason = {}
                if row and row.get('reason'):
                    try:
                        if isinstance(row['reason'], str):
                            existing_reason = json.loads(row['reason'])
                        elif isinstance(row['reason'], dict):
                            existing_reason = row['reason']
                    except:
                        pass

                existing_reason['skipReason'] = reason
                existing_reason['decision'] = 'skipped'

                cursor.execute("""
                    UPDATE virtual_bets
                    SET status = 'skipped',
                        reason = %s,
                        updated_at = %s
                    WHERE id = %s
                """, (
                    json.dumps(existing_reason, ensure_ascii=False),
                    datetime.now(JST),  # aware datetime(JST)で保存
                    bet_id
                ))
                conn.commit()
                logger.info(f"購入見送り: bet_id={bet_id}, reason={reason}")
        except Exception as e:
            logger.error(f"購入見送りエラー: {e}")
            conn.rollback()
        finally:
            conn.close()

    def update_result(self, bet_id: int, is_won: bool, payout: int = 0):
        """
        結果を更新

        Args:
            bet_id: 購入ID
            is_won: 的中したか
            payout: 払戻金
        """
        conn = self.get_db_connection()
        if not conn:
            return

        try:
            with conn.cursor() as cursor:
                status = 'won' if is_won else 'lost'
                cursor.execute("""
                    UPDATE virtual_bets
                    SET status = %s,
                        payout = %s,
                        result_confirmed_at = %s,
                        updated_at = %s
                    WHERE id = %s
                """, (
                    status,
                    payout,
                    datetime.now(JST),  # aware datetime(JST)で保存
                    datetime.now(JST),  # aware datetime(JST)で保存
                    bet_id
                ))
                conn.commit()
                logger.info(f"結果更新: bet_id={bet_id}, status={status}, payout={payout}")
        except Exception as e:
            logger.error(f"結果更新エラー: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_pending_bets(self, race_date: str = None) -> List[Dict]:
        """
        保留中の購入を取得

        Args:
            race_date: レース日（指定しない場合は全て）

        Returns:
            保留中の購入リスト
        """
        conn = self.get_db_connection()
        if not conn:
            return []

        try:
            with conn.cursor() as cursor:
                if race_date:
                    cursor.execute("""
                        SELECT * FROM virtual_bets
                        WHERE status = 'pending' AND race_date = %s
                        ORDER BY race_number
                    """, (race_date,))
                else:
                    cursor.execute("""
                        SELECT * FROM virtual_bets
                        WHERE status = 'pending'
                        ORDER BY race_date, race_number
                    """)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"保留中購入取得エラー: {e}")
            return []
        finally:
            conn.close()

    def get_all_pending_bets_near_deadline(self, minutes_to_deadline: int = 2) -> List[Dict]:
        """
        締切間近の保留中購入を取得

        修正（2026/01/24）:
        - デフォルトを2分前に拡大（締切超過問題対策）
        - 10秒間隔で実行されるため、2分前から処理開始で確実に購入判断を実行

        Args:
            minutes_to_deadline: 締切までの分数（デフォルト2分）

        Returns:
            締切間近の保留中購入リスト
        """
        conn = self.get_db_connection()
        if not conn:
            return []

        try:
            with conn.cursor() as cursor:
                # 現在時刻から締切までの時間で絞り込み
                # racesテーブルのdeadline_atを使用
                # aware datetime(JST)で統一して比較
                JST = timezone(timedelta(hours=9))
                now_jst = datetime.now(JST)
                deadline_threshold = now_jst + timedelta(minutes=minutes_to_deadline)

                # デバッグログ
                logger.info(f"[DEBUG] now_jst={now_jst}, deadline_threshold={deadline_threshold}")

                # 型の不一致を解消: virtual_bets."stadiumCode"(varchar) vs races.stadium_code(smallint)
                # virtual_betsテーブルはキャメルケースのカラム名を使用
                # 締切2分前〜現在時刻の間のレースを取得
                cursor.execute("""
                    SELECT vb.*, r.deadline_at
                    FROM virtual_bets vb
                    JOIN races r ON vb.race_date::date = r.race_date
                        AND CAST(vb.stadium_code AS smallint) = r.stadium_code
                        AND vb.race_number = CAST(r.race_number AS integer)
                    WHERE vb.status = 'pending'
                    AND r.deadline_at <= %s
                    AND r.deadline_at > %s
                    ORDER BY r.deadline_at
                """, (deadline_threshold, now_jst))
                results = cursor.fetchall()

                # DBから取得したdeadline_atをJSTに変換
                for result in results:
                    if result.get('deadline_at') and result['deadline_at'].tzinfo is not None:
                        result['deadline_at'] = result['deadline_at'].astimezone(JST)

                if results:
                    logger.info(f"締切間近の購入予定: {len(results)}件（締切{minutes_to_deadline}分以内）")
                else:
                    # デバッグ: pendingの購入予定を確認
                    cursor.execute("""
                        SELECT vb.id, vb.race_date, vb.stadium_code, vb.race_number,
                               vb.status, r.deadline_at
                        FROM virtual_bets vb
                        JOIN races r ON vb.race_date::date = r.race_date
                            AND CAST(vb.stadium_code AS smallint) = r.stadium_code
                            AND vb.race_number = CAST(r.race_number AS integer)
                        WHERE vb.status = 'pending'
                        ORDER BY r.deadline_at
                        LIMIT 5
                    """)
                    pending_bets = cursor.fetchall()
                    if pending_bets:
                        for bet in pending_bets:
                            deadline_jst = bet['deadline_at']
                            if deadline_jst and deadline_jst.tzinfo is not None:
                                deadline_jst = deadline_jst.astimezone(JST)
                            logger.info(f"[DEBUG] pending bet: id={bet['id']}, deadline_at={deadline_jst}, type={type(bet['deadline_at'])}")
                    else:
                        logger.info("[DEBUG] pendingの購入予定がありません")
                return results
        except Exception as e:
            logger.error(f"締切間近購入取得エラー: {e}")
            return []
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

                if row and row.get('odds_value') is not None:
                    odds_val = float(row['odds_value'])
                    # 0.0は発売前または投票が少ない状態なので、有効なオッズとして扱わない
                    if odds_val > 0:
                        return odds_val

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

                if row and row.get('odds_value') is not None:
                    odds_val = float(row['odds_value'])
                    if odds_val > 0:
                        return odds_val

                return None
        except Exception as e:
            logger.error(f"オッズ取得エラー: {e}")
            return None
        finally:
            conn.close()

    def fetch_odds_from_website(self, race_date: str, stadium_code: str, race_number: int,
                                  odds_type: str, combination: str) -> Optional[float]:
        """
        競艇公式サイトから直接オッズを取得する（DBにない場合のフォールバック）

        Args:
            race_date: レース日（YYYYMMDD形式）
            stadium_code: 競艇場コード
            race_number: レース番号
            odds_type: オッズタイプ（win, 2f, 2t等）
            combination: 買い目（"1", "1-3"等）

        Returns:
            オッズ（取得できない場合はNone）
        """
        try:
            # race_dateをYYYYMMDD形式に統一
            if '-' in race_date:
                race_date = race_date.replace('-', '')

            # stadium_codeを2桁にパディング
            padded_code = str(stadium_code).zfill(2)

            BASE_URL = "https://www.boatrace.jp/owpc/pc/race"

            if odds_type in ['2t', '2f']:
                # 2連単・2連複オッズページ
                url = f"{BASE_URL}/odds2tf?rno={race_number}&jcd={padded_code}&hd={race_date}"
            elif odds_type == 'win':
                # 単勝・複勝オッズページ
                url = f"{BASE_URL}/oddstf?rno={race_number}&jcd={padded_code}&hd={race_date}"
            else:
                logger.warning(f"未対応のオッズタイプ: {odds_type}")
                return None

            logger.info(f"Webサイトからオッズ取得: {url}")

            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                logger.warning(f"オッズページ取得失敗: status={response.status_code}")
                return None

            soup = BeautifulSoup(response.text, 'html.parser')

            # 組み合わせを正規化
            normalized_combination = combination.replace('=', '-')

            if odds_type in ['2t', '2f']:
                return self._parse_2tf_odds(soup, odds_type, normalized_combination)
            elif odds_type == 'win':
                return self._parse_win_odds(soup, normalized_combination)

            return None

        except Exception as e:
            logger.error(f"Webサイトからのオッズ取得エラー: {e}")
            return None

    def _parse_2tf_odds(self, soup: BeautifulSoup, odds_type: str, combination: str) -> Optional[float]:
        """
        2連単・2連複オッズをパース

        Args:
            soup: BeautifulSoupオブジェクト
            odds_type: '2t'（2連単）または'2f'（2連複）
            combination: 買い目（"1-3"形式）

        Returns:
            オッズ値
        """
        try:
            # 組み合わせを分解
            parts = combination.split('-')
            if len(parts) != 2:
                return None

            first_boat = int(parts[0])
            second_boat = int(parts[1])

            # テーブルを取得
            tables = soup.find_all('table')

            # 2連単は2番目のテーブル、2連複は1番目のテーブル
            target_table_idx = 1 if odds_type == '2t' else 0

            for table_idx, table in enumerate(tables):
                rows = table.find_all('tr')
                if len(rows) < 2:
                    continue

                first_row = rows[0]
                first_cells = first_row.find_all(['th', 'td'])
                if not first_cells:
                    continue

                has_boat_color = any('is-boatColor' in ' '.join(c.get('class', [])) for c in first_cells)
                if not has_boat_color:
                    continue

                # このテーブルがターゲットかチェック
                current_odds_type = '2t' if table_idx == 1 else '2f'
                if current_odds_type != odds_type:
                    continue

                # 1着の艇番を取得
                first_place_boats = []
                for i, cell in enumerate(first_cells):
                    if i % 2 == 0:
                        text = cell.get_text(strip=True)
                        if text.isdigit():
                            first_place_boats.append(int(text))

                # 行を走査して該当する組み合わせを探す
                for row in rows[1:]:
                    cells = row.find_all('td')
                    if not cells:
                        continue

                    for pair_idx in range(0, len(cells), 2):
                        if pair_idx + 1 >= len(cells):
                            break

                        boat_cell = cells[pair_idx]
                        odds_cell = cells[pair_idx + 1]

                        boat_text = boat_cell.get_text(strip=True)
                        if not boat_text.isdigit():
                            continue

                        row_boat = int(boat_text)
                        col_idx = pair_idx // 2

                        if col_idx < len(first_place_boats):
                            col_boat = first_place_boats[col_idx]

                            # 組み合わせが一致するかチェック
                            if col_boat == first_boat and row_boat == second_boat:
                                odds_text = odds_cell.get_text(strip=True)
                                odds_val = self._parse_odds_text(odds_text)
                                if odds_val and odds_val > 0:
                                    logger.info(f"  -> Webから取得成功: {combination} = {odds_val}")
                                    return odds_val

            return None

        except Exception as e:
            logger.error(f"2連オッズパースエラー: {e}")
            return None

    def _parse_win_odds(self, soup: BeautifulSoup, combination: str) -> Optional[float]:
        """
        単勝オッズをパース

        Args:
            soup: BeautifulSoupオブジェクト
            combination: 艇番（"1"等）

        Returns:
            オッズ値
        """
        try:
            target_boat = int(combination)

            # 単勝オッズテーブルを探す
            tables = soup.find_all('table')

            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    if len(cells) >= 2:
                        boat_cell = cells[0]
                        odds_cell = cells[1]

                        boat_text = boat_cell.get_text(strip=True)
                        if boat_text.isdigit() and int(boat_text) == target_boat:
                            odds_text = odds_cell.get_text(strip=True)
                            odds_val = self._parse_odds_text(odds_text)
                            if odds_val and odds_val > 0:
                                logger.info(f"  -> Webから取得成功: 単勝{combination} = {odds_val}")
                                return odds_val

            return None

        except Exception as e:
            logger.error(f"単勝オッズパースエラー: {e}")
            return None

    def _parse_odds_text(self, text: str) -> Optional[float]:
        """オッズ文字列をパース"""
        try:
            cleaned = re.sub(r'[^\d.]', '', text)
            if cleaned:
                return float(cleaned)
        except:
            pass
        return None

    def get_odds_with_fallback(self, race_date: str, stadium_code: str, race_number: int,
                                odds_type: str, combination: str) -> Optional[float]:
        """
        オッズを取得（DBになければWebサイトから直接取得）

        Args:
            race_date: レース日
            stadium_code: 競艇場コード
            race_number: レース番号
            odds_type: オッズタイプ
            combination: 買い目

        Returns:
            オッズ値
        """
        # まずDBから取得を試みる
        odds = self.get_latest_odds(race_date, stadium_code, race_number, odds_type, combination)

        if odds is not None:
            return odds

        # DBにない場合はWebサイトから直接取得
        logger.info(f"DBにオッズがないため、Webサイトから直接取得: {stadium_code} {race_number}R {odds_type} {combination}")
        return self.fetch_odds_from_website(race_date, stadium_code, race_number, odds_type, combination)

    def expire_overdue_bets(self):
        """
        締切が過ぎた購入予定を見送り（skipped）に更新する

        修正（2026/01/24）:
        - 締切後30秒の猶予を設ける（購入判断処理が完了するまでの時間を確保）
        """
        logger.info("=== 期限切れ購入予定の処理開始 ===")

        conn = self.get_db_connection()
        if not conn:
            return 0

        try:
            # aware datetime(JST)で統一して比較
            JST = timezone(timedelta(hours=9))
            now_jst = datetime.now(JST)

            # 締切後30秒の猶予を設ける（購入判断処理が完了するまでの時間を確保）
            grace_period = timedelta(seconds=30)
            threshold_time = now_jst - grace_period

            with conn.cursor() as cursor:
                # 締切が過ぎたpendingの購入予定を取得
                # 型の不一致を解消: virtual_bets.stadium_code(varchar) vs races.stadium_code(smallint)
                # 締切後30秒経過したものだけを対象とする
                cursor.execute("""
                    SELECT vb.id, vb.stadium_code, vb.race_number, vb.reason, r.deadline_at
                    FROM virtual_bets vb
                    JOIN races r ON vb.race_date::date = r.race_date
                        AND CAST(vb.stadium_code AS smallint) = r.stadium_code
                        AND vb.race_number = CAST(r.race_number AS integer)
                    WHERE vb.status = 'pending'
                    AND r.deadline_at < %s
                """, (threshold_time,))
                expired_bets = cursor.fetchall()

                if not expired_bets:
                    logger.info("期限切れの購入予定はありません")
                    return 0

                logger.info(f"期限切れの購入予定: {len(expired_bets)}件")

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
                    """, (json.dumps(reason, ensure_ascii=False), now_jst, bet['id']))

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

    def get_boat1_local_win_rate(self, race_date: str, stadium_code: str, race_number: int) -> Optional[float]:
        """
        1号艇の当地勝率を取得

        Args:
            race_date: レース日
            stadium_code: 競艇場コード
            race_number: レース番号

        Returns:
            当地勝率（取得できない場合はNone）
        """
        conn = self.get_db_connection()
        if not conn:
            return None

        try:
            # race_dateフォーマット調整
            if len(race_date) == 8:
                date_str = race_date  # DBはYYYYMMDD形式で保存
                date_val = datetime.strptime(race_date, '%Y%m%d').date()
            else:
                # ハイフン付きの場合はハイフンなしに変換
                date_str = race_date.replace('-', '')
                date_val = race_date if isinstance(race_date, date) else datetime.strptime(race_date, '%Y-%m-%d').date()

            with conn.cursor() as cursor:
                # historical_programsテーブルから取得
                # 文字列比較のためにパディング
                s_code = f"{int(stadium_code):02d}"
                r_num = f"{int(race_number):02d}"

                cursor.execute("""
                    SELECT local_win_rate
                    FROM historical_programs
                    WHERE race_date = %s
                    AND stadium_code = %s
                    AND race_no = %s
                    AND boat_no = '1'
                    LIMIT 1
                """, (date_str, s_code, r_num))

                row = cursor.fetchone()
                if row and row['local_win_rate']:
                    return float(row['local_win_rate'])

                # historical_programsになければ公式サイトからスクレイピング
                try:
                    url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={race_number}&jcd={s_code}&hd={race_date}"
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        # 1号艇の当地勝率を取得（tableの1行目）
                        tbody = soup.select_one('table.is-w748 tbody')
                        if tbody:
                            rows = tbody.find_all('tr')
                            if rows:
                                # 1号艇は最初の行
                                first_row = rows[0]
                                # 当地勝率は特定のtd位置にある
                                tds = first_row.find_all('td')
                                for td in tds:
                                    text = td.get_text(strip=True)
                                    # 勝率は「X.XX」形式（1桁.2桁）
                                    if re.match(r'^\d\.\d{2}$', text):
                                        return float(text)
                except Exception as scrape_err:
                    logger.warning(f"スクレイピングフォールバック失敗: {scrape_err}")

                return None

        except Exception as e:
            logger.error(f"勝率取得エラー: {e}")
            return None
        finally:
            conn.close()

    def process_deadline_bets(self):
        """
        締切1分前の購入予定を処理する

        - pendingステータスのレースを取得
        - 最新オッズを確認
        - 条件を満たせばconfirmed、満たさなければskipped
        - win_10x_1_3戦略は事前登録なしで直接チェック
        """
        logger.info("=== 締切1分前の購入判断処理開始 ===")

        # 締切2分前の購入予定を取得（通常戦略）
        # v9.2: 処理高速化により2分前に戻し
        pending_bets = self.get_all_pending_bets_near_deadline(minutes_to_deadline=2)

        if pending_bets:
            logger.info(f"処理対象（pending）: {len(pending_bets)}件")
            for bet in pending_bets:
                try:
                    self._process_single_bet(bet)
                except Exception as e:
                    logger.error(f"購入処理エラー: bet_id={bet['id']}, error={e}")

        # 両戦略とも締切3分前のレースを直接チェック
        self._process_bias_1_3_strategy()
        self._process_win_10x_strategy()

    def _process_bias_1_3_strategy(self):
        """
        bias_1_3_2nd戦略: 締切3分前のレースを直接チェックして購入判断
        15パターン（会場×レース）に該当し、オッズ条件を満たせば購入
        """
        strategy = STRATEGIES.get('bias_1_3_2nd')
        if not strategy:
            return

        now = datetime.now(JST)
        today_date = now.date()
        target_conditions = set(strategy.get('target_conditions', []))
        min_odds = strategy.get('min_odds', 3.0)
        max_odds = strategy.get('max_odds', 100.0)

        logger.info(f"=== bias_1_3_2nd戦略: 直接チェック開始 ===")

        # JST時刻をパラメータとして渡す（DBはUTCのため）
        # v9.2: 処理高速化により2分前に戻し
        now_jst = now
        deadline_threshold = now_jst + timedelta(minutes=2)

        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 締切3分以内のレースを取得（15パターンに該当するもののみ）
                cursor.execute("""
                    SELECT r.id, r.race_date, r.stadium_code, r.race_number, r.deadline_at
                    FROM races r
                    WHERE r.race_date = %s
                    AND r.deadline_at IS NOT NULL
                    AND r.deadline_at > %s
                    AND r.deadline_at <= %s
                    AND NOT EXISTS (
                        SELECT 1 FROM virtual_bets vb
                        WHERE vb.race_date = r.race_date
                        AND vb.stadium_code = LPAD(r.stadium_code::text, 2, '0')
                        AND vb.race_number = r.race_number
                        AND vb.strategy_type = 'bias_1_3_2nd'
                    )
                    ORDER BY r.deadline_at
                """, (today_date, now_jst, deadline_threshold))
                races = cursor.fetchall()

                if not races:
                    logger.info("bias_1_3_2nd: 締切3分以内の未処理レースなし")
                    return

                # 15パターンにフィルタリング
                target_races = []
                for race in races:
                    stadium_code = f"{race['stadium_code']:02d}"
                    race_number = race['race_number']
                    if (stadium_code, race_number) in target_conditions:
                        target_races.append(race)

                if not target_races:
                    logger.info("bias_1_3_2nd: 15パターン該当レースなし")
                    return

                logger.info(f"bias_1_3_2nd: {len(target_races)}レースをチェック（15パターン該当）")

                for race in target_races:
                    race_date = race['race_date']
                    stadium_code = f"{race['stadium_code']:02d}"
                    race_number = race['race_number']
                    race_date_str = race_date.strftime('%Y%m%d') if hasattr(race_date, 'strftime') else str(race_date).replace('-', '')

                    # 2連単1-3と2連複1=3のオッズを取得
                    exacta_odds = self.get_odds_with_fallback(race_date_str, stadium_code, race_number, '2t', '1-3')
                    quinella_odds = self.get_odds_with_fallback(race_date_str, stadium_code, race_number, '2f', '1=3')

                    if exacta_odds is None and quinella_odds is None:
                        logger.info(f"  {stadium_code} {race_number}R: オッズ取得失敗 → スキップ")
                        continue

                    # 高い方を選択
                    if exacta_odds is None:
                        selected_odds = quinella_odds
                        bet_type = 'quinella'
                    elif quinella_odds is None:
                        selected_odds = exacta_odds
                        bet_type = 'exacta'
                    elif exacta_odds >= quinella_odds:
                        selected_odds = exacta_odds
                        bet_type = 'exacta'
                    else:
                        selected_odds = quinella_odds
                        bet_type = 'quinella'

                    # オッズ範囲チェック
                    if selected_odds < min_odds or selected_odds > max_odds:
                        logger.info(f"  {stadium_code} {race_number}R: オッズ{selected_odds:.1f}倍 範囲外 → スキップ")
                        continue

                    # 条件クリア！購入確定
                    logger.info(f"  {stadium_code} {race_number}R: {bet_type} {selected_odds:.1f}倍 → 購入！")

                    # 購入レコードを作成（confirmed状態で）
                    cursor.execute("""
                        INSERT INTO virtual_bets (
                            race_date, stadium_code, race_number, strategy_type,
                            bet_type, combination, amount, odds, status,
                            created_at, updated_at, reason
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        race_date, stadium_code, race_number, 'bias_1_3_2nd',
                        bet_type, '1-3', strategy.get('base_amount', 1000),
                        selected_odds, 'confirmed',
                        now, now,
                        json.dumps({'selected_bet_type': bet_type, 'confirmed_at': now.isoformat()})
                    ))

                conn.commit()
                logger.info("bias_1_3_2nd戦略: チェック完了")

        except Exception as e:
            logger.error(f"bias_1_3_2nd戦略エラー: {e}")
            conn.rollback()

    def _process_win_10x_strategy(self):
        """
        win_10x_1_3戦略: 締切3分前のレースを直接チェックして購入判断
        事前登録なしで、条件を満たせば直接confirmed購入を作成
        """
        strategy = STRATEGIES.get('win_10x_1_3')
        if not strategy:
            return

        now = datetime.now(JST)
        today_date = now.date()
        min_win_odds = strategy.get('min_win_odds', 10.0)

        logger.info(f"=== win_10x_1_3戦略: 直接チェック開始 ===")

        # JST時刻をパラメータとして渡す（DBはUTCのため）
        # v9.2: 処理高速化により2分前に戻し
        now_jst = now
        deadline_threshold = now_jst + timedelta(minutes=2)

        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 締切3分以内のレースを取得（まだwin_10x_1_3で購入していないもの）
                cursor.execute("""
                    SELECT r.id, r.race_date, r.stadium_code, r.race_number, r.deadline_at
                    FROM races r
                    WHERE r.race_date = %s
                    AND r.deadline_at IS NOT NULL
                    AND r.deadline_at > %s
                    AND r.deadline_at <= %s
                    AND NOT EXISTS (
                        SELECT 1 FROM virtual_bets vb
                        WHERE vb.race_date = r.race_date
                        AND vb.stadium_code = LPAD(r.stadium_code::text, 2, '0')
                        AND vb.race_number = r.race_number
                        AND vb.strategy_type = 'win_10x_1_3'
                    )
                    ORDER BY r.deadline_at
                """, (today_date, now_jst, deadline_threshold))
                races = cursor.fetchall()

                if not races:
                    logger.info("win_10x_1_3: 締切3分以内の未処理レースなし")
                    return

                logger.info(f"win_10x_1_3: {len(races)}レースをチェック")

                for race in races:
                    race_date = race['race_date']
                    stadium_code = f"{race['stadium_code']:02d}"
                    race_number = race['race_number']
                    race_date_str = race_date.strftime('%Y%m%d') if hasattr(race_date, 'strftime') else str(race_date).replace('-', '')

                    # 1号艇単勝オッズを取得
                    win_odds = self.get_odds_with_fallback(race_date_str, stadium_code, race_number, 'win', '1')

                    if win_odds is None:
                        logger.info(f"  {stadium_code} {race_number}R: 単勝オッズ取得失敗 → スキップ")
                        continue

                    if win_odds < min_win_odds:
                        logger.info(f"  {stadium_code} {race_number}R: 単勝{win_odds:.1f}倍 < {min_win_odds} → スキップ")
                        continue

                    # 条件クリア！2連単1-3で購入確定
                    logger.info(f"  {stadium_code} {race_number}R: 単勝{win_odds:.1f}倍 >= {min_win_odds} → 購入！")

                    # 2連単1-3のオッズを取得
                    exacta_odds = self.get_odds_with_fallback(race_date_str, stadium_code, race_number, '2t', '1-3')
                    if exacta_odds is None:
                        exacta_odds = 0  # オッズ取得失敗でも購入

                    # 直接購入レコードを作成（confirmed状態で）
                    cursor.execute("""
                        INSERT INTO virtual_bets (
                            race_date, stadium_code, race_number, strategy_type,
                            bet_type, combination, amount, odds, status,
                            created_at, updated_at, reason
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        race_date, stadium_code, race_number, 'win_10x_1_3',
                        'exacta', '1-3', strategy.get('base_amount', 1000),
                        exacta_odds, 'confirmed',
                        now, now,
                        json.dumps({'win_odds': win_odds, 'confirmed_at': now.isoformat()})
                    ))

                conn.commit()
                logger.info("win_10x_1_3戦略: チェック完了")

        except Exception as e:
            logger.error(f"win_10x_1_3戦略エラー: {e}")
            conn.rollback()

    def _process_single_bet(self, bet: Dict):
        """単一の購入予定を処理"""
        bet_id = bet['id']
        strategy_type = bet['strategy_type']
        # virtual_betsテーブルはキャメルケースのカラム名を使用
        race_date = bet['race_date'].strftime('%Y%m%d') if hasattr(bet['race_date'], 'strftime') else str(bet['race_date']).replace('-', '')
        stadium_code = bet['stadium_code']
        race_number = bet['race_number']
        combination = bet['combination']
        bet_type = bet['bet_type']

        logger.info(f"処理中: {stadium_code} {race_number}R {combination} ({strategy_type})")

        if strategy_type == 'bias_1_3_2nd':
            # 1号艇の当地勝率チェック
            local_win_rate = self.get_boat1_local_win_rate(race_date, stadium_code, race_number)

            if local_win_rate is None:
                self.skip_bet(bet_id, "当地勝率取得失敗")
                return

            strategy_config = STRATEGIES.get(strategy_type, {})
            # デフォルト値は復元ロジックに基づく
            min_rate = strategy_config.get('min_local_win_rate', 4.5)
            max_rate = strategy_config.get('max_local_win_rate', 6.0)

            if not (min_rate <= local_win_rate < max_rate):
                self.skip_bet(bet_id, f"当地勝率範囲外: {local_win_rate} (基準: {min_rate}-{max_rate})")
                return

        elif strategy_type == 'win_10x_1_3':
            # 1号艇の単勝オッズを取得してチェック
            win_odds = self.get_odds_with_fallback(race_date, stadium_code, race_number, 'win', '1')

            if win_odds is None:
                self.skip_bet(bet_id, "1号艇単勝オッズ取得失敗")
                return

            strategy_config = STRATEGIES.get(strategy_type, {})
            min_win_odds = strategy_config.get('min_win_odds', 10.0)

            if win_odds < min_win_odds:
                self.skip_bet(bet_id, f"1号艇単勝オッズ不足: {win_odds} < {min_win_odds}")
                return

            logger.info(f"  1号艇単勝オッズ条件クリア: {win_odds} >= {min_win_odds}")

        # bet_type='auto'の場合は2連単/2連複の両方を取得して高い方を選択
        # DBになければWebサイトから直接取得するフォールバック機能を使用
        if bet_type == 'auto':
            odds_2t = self.get_odds_with_fallback(race_date, stadium_code, race_number, '2t', combination)
            odds_2f = self.get_odds_with_fallback(race_date, stadium_code, race_number, '2f', combination)

            logger.info(f"  auto判定: 2連単={odds_2t}, 2連複={odds_2f}")

            if odds_2t is None and odds_2f is None:
                logger.warning(f"オッズ取得失敗: {stadium_code} {race_number}R {combination} (2連単/2連複両方なし)")
                self.skip_bet(bet_id, "オッズ取得失敗")
                return

            # 高い方を選択（Noneの場合は0として比較）
            odds_2t_val = float(odds_2t) if odds_2t is not None else 0
            odds_2f_val = float(odds_2f) if odds_2f is not None else 0

            if odds_2t_val >= odds_2f_val:
                final_odds = odds_2t
                actual_bet_type = 'exacta'  # 2連単
                logger.info(f"  -> 2連単を選択: {final_odds}")
            else:
                final_odds = odds_2f
                actual_bet_type = 'quinella'  # 2連複
                logger.info(f"  -> 2連複を選択: {final_odds}")
        else:
            # 通常のオッズタイプ変換
            odds_type_map = {'win': 'win', 'quinella': '2f', 'exacta': '2t'}
            odds_type = odds_type_map.get(bet_type, 'win')

            # 最新オッズを取得（DBになければWebサイトから直接取得）
            final_odds = self.get_odds_with_fallback(race_date, stadium_code, race_number, odds_type, combination)
            actual_bet_type = bet_type

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
        race_date = bet['race_date'].strftime('%Y-%m-%d') if hasattr(bet['race_date'], 'strftime') else str(bet['race_date'])
        stadium_code = bet['stadium_code']
        race_number = bet['race_number']
        combination = bet['combination']
        bet_type = bet['bet_type']
        amount = float(bet.get('amount', 1000))
        final_odds = float(bet.get('final_odds', 0) or 0)

        logger.info(f"結果確認: {stadium_code} {race_number}R {combination}")

        # レース結果を取得
        result = self._get_race_result(race_date, stadium_code, race_number)

        if not result:
            logger.info(f"  結果未確定")
            return

        # 的中判定
        is_won = self._check_win(combination, bet_type, result)

        if is_won:
            # 払戻金を計算
            payout = int(amount * final_odds)
            logger.info(f"  的中！ 払戻金: {payout}円")
        else:
            payout = 0
            logger.info(f"  不的中")

        self.update_result(bet_id, is_won, payout)

    def _get_race_result(self, race_date: str, stadium_code: str, race_number: int) -> Optional[Dict]:
        """レース結果を取得（racesテーブル経由でrace_idを取得してからrace_resultsを検索）"""
        conn = self.get_db_connection()
        if not conn:
            return None

        try:
            with conn.cursor() as cursor:
                # まずracesテーブルからrace_idを取得
                cursor.execute("""
                    SELECT id FROM races
                    WHERE race_date = %s::date
                    AND stadium_code = %s
                    AND race_number = %s
                """, (race_date, stadium_code, race_number))
                race_row = cursor.fetchone()

                if not race_row:
                    logger.debug(f"レースが見つかりません: {race_date} {stadium_code} {race_number}R")
                    return None

                race_id = race_row['id']

                # race_resultsテーブルから結果を取得
                cursor.execute("""
                    SELECT * FROM race_results
                    WHERE race_id = %s
                """, (race_id,))
                return cursor.fetchone()
        except Exception as e:
            logger.error(f"結果取得エラー: {e}")
            return None
        finally:
            conn.close()

    def _check_win(self, combination: str, bet_type: str, result: Dict) -> bool:
        """的中判定"""
        if not result:
            return False

        # 結果の着順を取得
        first = str(result.get('first_place', ''))
        second = str(result.get('second_place', ''))
        third = str(result.get('third_place', ''))

        if bet_type == 'win':
            # 単勝: 1着が一致
            return combination == first
        elif bet_type == 'quinella':
            # 2連複: 1-2着の組み合わせ（順不同）
            combo_set = set(combination.replace('=', '-').split('-'))
            result_set = {first, second}
            return combo_set == result_set
        elif bet_type == 'exacta':
            # 2連単: 1-2着の順番が一致
            combo_parts = combination.replace('=', '-').split('-')
            return combo_parts[0] == first and combo_parts[1] == second

        return False

    def get_summary(self, race_date: str = None) -> Dict:
        """
        購入サマリーを取得

        Args:
            race_date: レース日（指定しない場合は全期間）

        Returns:
            サマリー情報
        """
        conn = self.get_db_connection()
        if not conn:
            return {}

        try:
            with conn.cursor() as cursor:
                if race_date:
                    cursor.execute("""
                        SELECT
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                            SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed,
                            SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) as won,
                            SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END) as lost,
                            SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped,
                            SUM(CASE WHEN status IN ('confirmed', 'won', 'lost') THEN amount ELSE 0 END) as total_bet,
                            SUM(CASE WHEN status = 'won' THEN payout ELSE 0 END) as total_payout
                        FROM virtual_bets
                        WHERE race_date = %s
                    """, (race_date,))
                else:
                    cursor.execute("""
                        SELECT
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                            SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed,
                            SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) as won,
                            SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END) as lost,
                            SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped,
                            SUM(CASE WHEN status IN ('confirmed', 'won', 'lost') THEN amount ELSE 0 END) as total_bet,
                            SUM(CASE WHEN status = 'won' THEN payout ELSE 0 END) as total_payout
                        FROM virtual_bets
                    """)

                row = cursor.fetchone()

                total_bet = row['total_bet'] or 0
                total_payout = row['total_payout'] or 0

                return {
                    'total': row['total'] or 0,
                    'pending': row['pending'] or 0,
                    'confirmed': row['confirmed'] or 0,
                    'won': row['won'] or 0,
                    'lost': row['lost'] or 0,
                    'skipped': row['skipped'] or 0,
                    'total_bet': total_bet,
                    'total_payout': total_payout,
                    'profit': total_payout - total_bet,
                    'roi': (total_payout / total_bet * 100) if total_bet > 0 else 0
                }
        except Exception as e:
            logger.error(f"サマリー取得エラー: {e}")
            return {}
        finally:
            conn.close()


# モジュールレベルの関数（odds_worker.pyから呼び出される）
def process_virtual_betting():
    """
    仮想購入処理のエントリポイント
    odds_worker.pyから30秒ごとに呼び出される

    処理内容:
    1. 締切1分前のレースの購入判断を実行
    2. 締切超過のレースを見送りに更新
    3. 確定済みレースの結果を更新
    """
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.warning("DATABASE_URL環境変数が設定されていません")
        return

    try:
        manager = VirtualBettingManager(database_url)

        # 締切1分前のレースの購入判断を実行
        manager.process_deadline_bets()

        # 締切超過のレースを見送りに更新
        expired_count = manager.expire_overdue_bets()
        if expired_count > 0:
            logger.info(f"締切超過で見送りにしたレース: {expired_count}件")

        # 確定済みレースの結果を更新
        manager.process_results()

    except Exception as e:
        logger.error(f"仮想購入処理エラー: {e}")
        import traceback
        traceback.print_exc()

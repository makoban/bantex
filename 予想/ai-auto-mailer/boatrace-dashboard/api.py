"""
競艇予想ダッシュボード API
PostgreSQL（kokotomo-db-staging）のみを使用
"""

import os
import json
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional, Dict, Any
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="競艇予想ダッシュボード API")

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# データベース接続
DATABASE_URL = os.environ.get("DATABASE_URL")

# タイムゾーン設定
JST = timezone(timedelta(hours=9))

def get_adjusted_date() -> date:
    """現在の日付を返す（JST）"""
    now_jst = datetime.now(JST)
    return date(now_jst.year, now_jst.month, now_jst.day)


def get_db_connection():
    """データベース接続を取得"""
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def decimal_to_float(obj):
    """Decimalをfloatに変換"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(item) for item in obj]
    return obj


# ==================== レスポンスモデル ====================

class StadiumInfo(BaseModel):
    stadium_code: int
    name: str


class RaceInfo(BaseModel):
    id: int
    race_date: str
    stadium_code: int
    stadium_name: str
    race_number: int
    title: Optional[str]
    deadline_at: Optional[str]
    is_canceled: bool


class RaceResult(BaseModel):
    race_id: int
    first_place: Optional[int]
    second_place: Optional[int]
    third_place: Optional[int]
    race_status: Optional[str]


class VirtualBet(BaseModel):
    id: int
    strategy_type: str
    race_date: str
    stadium_code: str
    race_number: int
    bet_type: str
    combination: str
    bet_amount: int
    odds: Optional[float]
    status: str
    reason: Optional[Dict[str, Any]]
    actual_result: Optional[str]
    payoff: Optional[int]
    return_amount: Optional[int]
    profit: Optional[int]
    created_at: str


class VirtualFund(BaseModel):
    id: int
    strategy_type: str
    initial_fund: float
    current_fund: float
    total_profit: float
    total_bets: int
    total_hits: int
    hit_rate: float
    return_rate: float
    is_active: bool


class DashboardStats(BaseModel):
    # 本日の統計
    total_races_today: int
    completed_races: int
    pending_bets: int
    confirmed_bets: int
    won_bets: int
    lost_bets: int
    skipped_bets: int
    today_profit: float
    today_bet_count: int
    today_hit_count: int
    today_hit_rate: float
    today_return_rate: float
    # 累計の統計
    total_profit: float
    total_bet_count: int
    total_hit_count: int
    total_won_count: int  # 累計的中数
    total_lost_count: int  # 累計不的中数
    total_bet_amount: float  # 累計投資額
    hit_rate: float
    return_rate: float


# ==================== APIエンドポイント ====================

@app.get("/api/health")
def health_check():
    """ヘルスチェック"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/stadiums", response_model=List[StadiumInfo])
def get_stadiums():
    """競艇場一覧を取得"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT stadium_code, name FROM stadiums ORDER BY stadium_code")
            rows = cur.fetchall()
            return [StadiumInfo(**row) for row in rows]
    finally:
        conn.close()


@app.get("/api/races/today", response_model=List[RaceInfo])
def get_today_races():
    """今日のレース一覧を取得"""
    today = get_adjusted_date()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.id, r.race_date, r.stadium_code, s.name as stadium_name,
                       r.race_number, r.title, r.deadline_at, r.is_canceled
                FROM races r
                JOIN stadiums s ON r.stadium_code = s.stadium_code
                WHERE r.race_date = %s
                ORDER BY r.deadline_at
            """, (today,))
            rows = cur.fetchall()
            return [RaceInfo(
                id=row['id'],
                race_date=str(row['race_date']),
                stadium_code=row['stadium_code'],
                stadium_name=row['stadium_name'],
                race_number=row['race_number'],
                title=row['title'],
                deadline_at=row['deadline_at'].isoformat() if row['deadline_at'] else None,
                is_canceled=row['is_canceled'] or False
            ) for row in rows]
    finally:
        conn.close()


@app.get("/api/races/today/with-odds")
def get_today_races_with_odds():
    """今日のレース一覧（単勝・2連複オッズ付き）を取得"""
    today = get_adjusted_date()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 今日のレース一覧を取得
            cur.execute("""
                SELECT r.id, r.race_date, r.stadium_code, s.name as stadium_name,
                       r.race_number, r.title, r.deadline_at, r.is_canceled
                FROM races r
                JOIN stadiums s ON r.stadium_code = s.stadium_code
                WHERE r.race_date = %s
                ORDER BY r.stadium_code, r.race_number
            """, (today,))
            races = cur.fetchall()

            # レース結果を取得
            cur.execute("""
                SELECT rr.race_id, rr.first_place, rr.second_place, rr.third_place, rr.race_status
                FROM race_results rr
                JOIN races r ON rr.race_id = r.id
                WHERE r.race_date = %s
            """, (today,))
            results_map = {row['race_id']: row for row in cur.fetchall()}

            # 払戻金を取得
            cur.execute("""
                SELECT p.race_id, p.bet_type, p.combination, p.payoff
                FROM payoffs p
                JOIN races r ON p.race_id = r.id
                WHERE r.race_date = %s
            """, (today,))

            # bet_type名を正規化するマッピング
            bet_type_normalize = {
                '単勝': 'win', 'win': 'win',
                '複勝': 'place', 'place': 'place',
                '2連単': 'exacta', '２連単': 'exacta', 'exacta': 'exacta',
                '2連複': 'quinella', '２連複': 'quinella', 'quinella': 'quinella',
                'ワイド': 'wide', '拡連複': 'wide', 'wide': 'wide',
                '3連単': 'trifecta', '３連単': 'trifecta', 'trifecta': 'trifecta',
                '3連複': 'trio', '３連複': 'trio', 'trio': 'trio'
            }

            payoffs_map = {}
            for row in cur.fetchall():
                race_id = row['race_id']
                if race_id not in payoffs_map:
                    payoffs_map[race_id] = {}
                # bet_typeを正規化
                bet_type = bet_type_normalize.get(row['bet_type'], row['bet_type'])
                if bet_type not in payoffs_map[race_id]:
                    payoffs_map[race_id][bet_type] = []
                payoffs_map[race_id][bet_type].append({
                    'combination': row['combination'],
                    'payoff': row['payoff']
                })

            # 最新オッズを取得（単勝と2連複）
            cur.execute("""
                WITH latest_odds AS (
                    SELECT race_date, stadium_code, race_number, odds_type, combination, odds_value,
                           ROW_NUMBER() OVER (
                               PARTITION BY race_date, stadium_code, race_number, odds_type, combination
                               ORDER BY scraped_at DESC
                           ) as rn
                    FROM odds_history
                    WHERE race_date = %s AND odds_type IN ('win', '2f')
                )
                SELECT race_date, stadium_code, race_number, odds_type, combination, odds_value
                FROM latest_odds
                WHERE rn = 1
            """, (today,))

            odds_map = {}
            for row in cur.fetchall():
                key = (row['stadium_code'], row['race_number'])
                if key not in odds_map:
                    odds_map[key] = {'win': {}, '2f': {}}
                odds_type = row['odds_type']
                odds_map[key][odds_type][row['combination']] = float(row['odds_value']) if row['odds_value'] else None

            # レース情報を組み立て
            result = []
            for race in races:
                race_id = race['id']
                stadium_code = str(race['stadium_code']).zfill(2)
                race_number = race['race_number']
                key = (stadium_code, race_number)

                odds_data = odds_map.get(key, {'win': {}, '2f': {}})
                race_result = results_map.get(race_id)
                payoffs = payoffs_map.get(race_id, {})

                # レース状態を判定（現在時刻ベース）
                # aware datetime(JST)で統一して比較
                now = datetime.now(JST)
                deadline = race['deadline_at']
                # deadlineがnaiveの場合はJSTとして扱う
                if deadline and deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=JST)
                status = 'upcoming'

                if race['is_canceled']:
                    status = 'canceled'
                elif race_result and race_result.get('first_place'):
                    # 結果が入っていれば確定
                    status = 'finished'
                elif deadline and deadline.tzinfo is not None:
                    # 締切時刻から判定（deadlineはawareに変換済み）
                    minutes_since_deadline = (now - deadline).total_seconds() / 60
                    if minutes_since_deadline > 10:
                        # 締切から10分以上経過 → 確定（結果待ち）
                        status = 'finished'
                    elif minutes_since_deadline > 0:
                        # 締切後10分以内 → レース中
                        status = 'in_progress'
                    # それ以外は発売中(upcoming)

                result.append({
                    'id': race_id,
                    'race_date': str(race['race_date']),
                    'stadium_code': race['stadium_code'],
                    'stadium_name': race['stadium_name'],
                    'race_number': race_number,
                    'title': race['title'],
                    'deadline_at': race['deadline_at'].isoformat() if race['deadline_at'] else None,
                    'status': status,
                    'result': {
                        'first': race_result['first_place'] if race_result else None,
                        'second': race_result['second_place'] if race_result else None,
                        'third': race_result['third_place'] if race_result else None,
                    } if race_result else None,
                    'odds': {
                        'win': odds_data.get('win', {}),
                        'quinella': odds_data.get('2f', {})  # 2連複
                    },
                    'payoffs': {
                        'win': payoffs.get('win', []),
                        'place': payoffs.get('place', []),  # 複勝（2組）
                        'quinella': payoffs.get('quinella', []),
                        'wide': payoffs.get('wide', []),  # ワイド（3組）
                    }
                })

            return result
    finally:
        conn.close()


@app.get("/api/races/{race_date}", response_model=List[RaceInfo])
def get_races_by_date(race_date: str):
    """指定日のレース一覧を取得"""
    try:
        target_date = datetime.strptime(race_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.id, r.race_date, r.stadium_code, s.name as stadium_name,
                       r.race_number, r.title, r.deadline_at, r.is_canceled
                FROM races r
                JOIN stadiums s ON r.stadium_code = s.stadium_code
                WHERE r.race_date = %s
                ORDER BY r.deadline_at
            """, (target_date,))
            rows = cur.fetchall()
            return [RaceInfo(
                id=row['id'],
                race_date=str(row['race_date']),
                stadium_code=row['stadium_code'],
                stadium_name=row['stadium_name'],
                race_number=row['race_number'],
                title=row['title'],
                deadline_at=row['deadline_at'].isoformat() if row['deadline_at'] else None,
                is_canceled=row['is_canceled'] or False
            ) for row in rows]
    finally:
        conn.close()


@app.get("/api/results/{race_id}")
def get_race_result(race_id: int):
    """レース結果を取得"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rr.*, r.race_date, r.stadium_code, s.name as stadium_name, r.race_number
                FROM race_results rr
                JOIN races r ON rr.race_id = r.id
                JOIN stadiums s ON r.stadium_code = s.stadium_code
                WHERE rr.race_id = %s
            """, (race_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Result not found")

            # 払戻金情報も取得
            cur.execute("""
                SELECT bet_type, combination, payoff, popularity
                FROM payoffs
                WHERE race_id = %s
                ORDER BY bet_type, popularity
            """, (race_id,))
            payoffs = cur.fetchall()

            return {
                "race_id": row['race_id'],
                "race_date": str(row['race_date']),
                "stadium_code": row['stadium_code'],
                "stadium_name": row['stadium_name'],
                "race_number": row['race_number'],
                "first_place": row['first_place'],
                "second_place": row['second_place'],
                "third_place": row['third_place'],
                "fourth_place": row['fourth_place'],
                "fifth_place": row['fifth_place'],
                "sixth_place": row['sixth_place'],
                "race_status": row['race_status'],
                "payoffs": [dict(p) for p in payoffs]
            }
    finally:
        conn.close()


@app.get("/api/bets", response_model=List[VirtualBet])
def get_virtual_bets(
    status: Optional[str] = None,
    race_date: Optional[str] = None,
    strategy_type: Optional[str] = None,
    limit: int = Query(default=100, le=500)
):
    """仮想購入一覧を取得"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            query = "SELECT * FROM virtual_bets WHERE 1=1"
            params = []

            if status:
                query += " AND status = %s"
                params.append(status)
            if race_date:
                query += " AND race_date = %s"
                params.append(race_date)
            if strategy_type:
                query += " AND strategy_type = %s"
                params.append(strategy_type)

            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            rows = cur.fetchall()

            return [VirtualBet(
                id=row['id'],
                strategy_type=row['strategy_type'],
                race_date=str(row['race_date']),
                stadium_code=row['stadium_code'],
                race_number=row['race_number'],
                bet_type=row['bet_type'],
                combination=row['combination'],
                bet_amount=row['bet_amount'],
                odds=float(row['odds']) if row['odds'] else None,
                status=row['status'],
                reason=row['reason'],
                actual_result=row['actual_result'],
                payoff=row['payoff'],
                return_amount=row['return_amount'],
                profit=row['profit'],
                created_at=row['created_at'].isoformat() if row['created_at'] else None
            ) for row in rows]
    finally:
        conn.close()


@app.get("/api/funds", response_model=List[VirtualFund])
def get_virtual_funds():
    """仮想資金一覧を取得（v1.4: 全戦略を表示）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # v1.4: 全戦略を表示
            cur.execute("SELECT * FROM virtual_funds WHERE is_active = true ORDER BY strategy_type")
            rows = cur.fetchall()
            return [VirtualFund(
                id=row['id'],
                strategy_type=row['strategy_type'],
                initial_fund=float(row['initial_fund']),
                current_fund=float(row['current_fund']),
                total_profit=float(row['total_profit']),
                total_bets=row['total_bets'],
                total_hits=row['total_hits'],
                hit_rate=float(row['hit_rate']),
                return_rate=float(row['return_rate']),
                is_active=row['is_active']
            ) for row in rows]
    finally:
        conn.close()


@app.get("/api/stats/dashboard", response_model=DashboardStats)
def get_dashboard_stats():
    """ダッシュボード統計を取得"""
    today = get_adjusted_date()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 今日のレース数
            cur.execute("SELECT COUNT(*) as cnt FROM races WHERE race_date = %s", (today,))
            total_races_today = cur.fetchone()['cnt']

            # 完了したレース数
            cur.execute("""
                SELECT COUNT(*) as cnt FROM races r
                JOIN race_results rr ON r.id = rr.race_id
                WHERE r.race_date = %s
            """, (today,))
            completed_races = cur.fetchone()['cnt']

            # 今日の購入状況
            cur.execute("""
                SELECT status, COUNT(*) as cnt, COALESCE(SUM(profit), 0) as profit
                FROM virtual_bets
                WHERE race_date = %s
                GROUP BY status
            """, (today,))
            status_counts = {row['status']: {'count': row['cnt'], 'profit': float(row['profit'])} for row in cur.fetchall()}

            pending_bets = status_counts.get('pending', {}).get('count', 0)
            confirmed_bets = status_counts.get('confirmed', {}).get('count', 0)
            won_bets = status_counts.get('won', {}).get('count', 0)
            lost_bets = status_counts.get('lost', {}).get('count', 0)
            skipped_bets = status_counts.get('skipped', {}).get('count', 0)

            today_profit = sum(s.get('profit', 0) for s in status_counts.values())

            # 今日の詳細統計
            cur.execute("""
                SELECT
                    COUNT(CASE WHEN status IN ('won', 'lost') THEN 1 END) as today_bet_count,
                    COUNT(CASE WHEN status = 'won' THEN 1 END) as today_hit_count,
                    COALESCE(SUM(CASE WHEN status IN ('won', 'lost') THEN bet_amount ELSE 0 END), 0) as today_bet_amount,
                    COALESCE(SUM(CASE WHEN status IN ('won', 'lost') THEN return_amount ELSE 0 END), 0) as today_return_amount
                FROM virtual_bets
                WHERE race_date = %s
            """, (today,))
            today_stats = cur.fetchone()
            today_bet_count = today_stats['today_bet_count']
            today_hit_count = today_stats['today_hit_count']
            today_hit_rate = (today_hit_count / today_bet_count * 100) if today_bet_count > 0 else 0
            today_bet_amount = float(today_stats['today_bet_amount'])
            today_return_amount = float(today_stats['today_return_amount'])
            today_return_rate = (today_return_amount / today_bet_amount * 100) if today_bet_amount > 0 else 0

            # 全体統計（累計）
            cur.execute("""
                SELECT
                    COALESCE(SUM(CASE WHEN status IN ('won', 'lost') THEN profit ELSE 0 END), 0) as total_profit,
                    COUNT(CASE WHEN status IN ('won', 'lost') THEN 1 END) as total_bets,
                    COUNT(CASE WHEN status = 'won' THEN 1 END) as total_hits,
                    COUNT(CASE WHEN status = 'lost' THEN 1 END) as total_lost,
                    COALESCE(SUM(CASE WHEN status IN ('won', 'lost') THEN bet_amount ELSE 0 END), 0) as total_bet_amount,
                    COALESCE(SUM(CASE WHEN status IN ('won', 'lost') THEN return_amount ELSE 0 END), 0) as total_return_amount
                FROM virtual_bets
            """)
            totals = cur.fetchone()

            total_profit = float(totals['total_profit'])
            total_bet_count = totals['total_bets']
            total_hit_count = totals['total_hits']
            total_won_count = totals['total_hits']  # 累計的中数
            total_lost_count = totals['total_lost']  # 累計不的中数
            hit_rate = (total_hit_count / total_bet_count * 100) if total_bet_count > 0 else 0
            total_bet_amount = float(totals['total_bet_amount'])
            total_return_amount = float(totals['total_return_amount'])
            return_rate = (total_return_amount / total_bet_amount * 100) if total_bet_amount > 0 else 0

            return DashboardStats(
                total_races_today=total_races_today,
                completed_races=completed_races,
                pending_bets=pending_bets,
                confirmed_bets=confirmed_bets,
                won_bets=won_bets,
                lost_bets=lost_bets,
                skipped_bets=skipped_bets,
                today_profit=today_profit,
                today_bet_count=today_bet_count,
                today_hit_count=today_hit_count,
                today_hit_rate=today_hit_rate,
                today_return_rate=today_return_rate,
                total_profit=total_profit,
                total_bet_count=total_bet_count,
                total_hit_count=total_hit_count,
                total_won_count=total_won_count,
                total_lost_count=total_lost_count,
                total_bet_amount=total_bet_amount,
                hit_rate=hit_rate,
                return_rate=return_rate
            )
    finally:
        conn.close()


@app.get("/api/odds/latest/{race_date}/{stadium_code}/{race_number}")
def get_latest_odds(race_date: str, stadium_code: str, race_number: int):
    """最新のオッズを取得"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT odds_type, combination, odds_value, odds_min, odds_max, scraped_at
                FROM odds_history
                WHERE race_date = %s AND stadium_code = %s AND race_number = %s
                AND scraped_at = (
                    SELECT MAX(scraped_at) FROM odds_history
                    WHERE race_date = %s AND stadium_code = %s AND race_number = %s
                )
                ORDER BY odds_type, combination
            """, (race_date, stadium_code, race_number, race_date, stadium_code, race_number))
            rows = cur.fetchall()

            result = {}
            for row in rows:
                odds_type = row['odds_type']
                if odds_type not in result:
                    result[odds_type] = {}
                result[odds_type][row['combination']] = {
                    'value': float(row['odds_value']) if row['odds_value'] else None,
                    'min': float(row['odds_min']) if row['odds_min'] else None,
                    'max': float(row['odds_max']) if row['odds_max'] else None,
                    'scraped_at': row['scraped_at'].isoformat() if row['scraped_at'] else None
                }

            return result
    finally:
        conn.close()


@app.get("/api/bets/with-results")
def get_bets_with_results(
    race_date: Optional[str] = None,
    include_skipped: bool = True,
    limit: int = Query(default=100, le=500)
):
    """購入結果と見送りレースの結果を取得"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT
                    vb.*,
                    s.name as stadium_name,
                    r.id as race_id,
                    r.deadline_at as scheduled_deadline,
                    rr.first_place,
                    rr.second_place,
                    rr.third_place,
                    rr.race_status
                FROM virtual_bets vb
                LEFT JOIN stadiums s ON vb.stadium_code::int = s.stadium_code
                LEFT JOIN races r ON vb.race_date = r.race_date
                    AND vb.stadium_code::int = r.stadium_code
                    AND vb.race_number = r.race_number
                LEFT JOIN race_results rr ON r.id = rr.race_id
                WHERE 1=1
            """
            params = []

            if race_date:
                query += " AND vb.race_date = %s"
                params.append(race_date)

            if not include_skipped:
                query += " AND vb.status != 'skipped'"

            query += " ORDER BY vb.race_date DESC, r.deadline_at DESC LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            rows = cur.fetchall()

            # レースIDを収集して払戻金を一括取得
            race_ids = [row['race_id'] for row in rows if row.get('race_id')]
            payoffs_map = {}
            if race_ids:
                cur.execute("""
                    SELECT race_id, bet_type, combination, payoff
                    FROM payoffs
                    WHERE race_id = ANY(%s)
                """, (race_ids,))
                # bet_typeの日本語→英語マッピング
                bet_type_map = {
                    '2連複': 'quinella',
                    '2連単': 'exacta',
                    '単勝': 'win',
                    '複勝': 'place',
                    '3連単': 'trifecta',
                    '3連複': 'trio',
                    'ワイド': 'wide',
                }
                for p in cur.fetchall():
                    # 日本語のbet_typeを英語に変換してキーを作成
                    bt = p['bet_type']
                    bt_en = bet_type_map.get(bt, bt)
                    key = (p['race_id'], bt_en, p['combination'])
                    payoffs_map[key] = p['payoff']
                    # 元の日本語でもアクセスできるようにする
                    key_jp = (p['race_id'], bt, p['combination'])
                    payoffs_map[key_jp] = p['payoff']

            results = []
            for row in rows:
                actual_result_str = None
                if row['first_place'] and row['second_place'] and row['third_place']:
                    actual_result_str = f"{row['first_place']}-{row['second_place']}-{row['third_place']}"

                # 締切を過ぎたらステータスを自動更新（先に判定）
                display_status = row['status']
                display_reason = row['reason']
                if row['status'] == 'pending' and row['scheduled_deadline']:
                    # aware datetime(JST)で統一して比較
                    now = datetime.now(JST)
                    deadline = row['scheduled_deadline']
                    # deadlineがnaiveの場合はJSTとして扱う
                    if deadline.tzinfo is None:
                        deadline = deadline.replace(tzinfo=JST)
                    if now > deadline:
                        # 締切を過ぎたら「見送り」として表示
                        display_status = 'skipped'
                        # reasonにskipReasonを追加
                        if display_reason is None:
                            display_reason = {}
                        elif isinstance(display_reason, str):
                            try:
                                display_reason = json.loads(display_reason)
                            except:
                                display_reason = {}
                        if 'skipReason' not in display_reason:
                            display_reason = dict(display_reason)
                            display_reason['skipReason'] = '締切超過（購入判断未実行）'
                            display_reason['decision'] = 'skipped'

                # 見送りレース（DB上skippedまたは表示上skipped）で結果を計算
                would_have_hit = None
                would_have_payoff = None
                # display_status == 'skipped'に変更（pending+締切超過も対象）
                if display_status == 'skipped' and actual_result_str and row.get('race_id'):
                    # 的中判定
                    bet_type = row['bet_type']
                    combination = row['combination']

                    # auto の場合は2連複・2連単の両方をチェック（買い目1-3の場合）
                    if bet_type == 'auto':
                        # 2連複でチェック
                        actual_pair = set([str(row['first_place']), str(row['second_place'])])
                        bet_pair = set(combination.replace('-', '=').split('='))
                        if actual_pair == bet_pair:
                            would_have_hit = True
                            # 2連複の払戻金を取得（組合せを正規化）
                            pair_list = sorted([str(row['first_place']), str(row['second_place'])])
                            payoff_comb = f"{pair_list[0]}={pair_list[1]}"
                            would_have_payoff = payoffs_map.get((row['race_id'], 'quinella', payoff_comb))
                            if not would_have_payoff:
                                payoff_comb2 = f"{pair_list[0]}-{pair_list[1]}"
                                would_have_payoff = payoffs_map.get((row['race_id'], 'quinella', payoff_comb2))
                            # 2連単の払戻金も試す（高い方を表示したいが、とりあえず2連複を優先）
                            if not would_have_payoff:
                                actual_exacta = f"{row['first_place']}-{row['second_place']}"
                                if actual_exacta == combination:
                                    would_have_payoff = payoffs_map.get((row['race_id'], 'exacta', actual_exacta))
                        else:
                            would_have_hit = False
                    elif bet_type == 'win':
                        would_have_hit = str(row['first_place']) == combination
                        if would_have_hit:
                            # 単勝の払戻金を取得
                            would_have_payoff = payoffs_map.get((row['race_id'], 'win', str(row['first_place'])))
                    elif bet_type == 'quinella':
                        # 2連複: 順不同
                        actual_pair = set([str(row['first_place']), str(row['second_place'])])
                        bet_pair = set(combination.replace('-', '=').split('='))
                        would_have_hit = actual_pair == bet_pair
                        if would_have_hit:
                            # 2連複の払戻金を取得（組合せを正規化）
                            pair_list = sorted([str(row['first_place']), str(row['second_place'])])
                            payoff_comb = f"{pair_list[0]}={pair_list[1]}"
                            would_have_payoff = payoffs_map.get((row['race_id'], 'quinella', payoff_comb))
                            if not would_have_payoff:
                                # 別の形式も試す
                                payoff_comb2 = f"{pair_list[0]}-{pair_list[1]}"
                                would_have_payoff = payoffs_map.get((row['race_id'], 'quinella', payoff_comb2))
                    elif bet_type == 'exacta':
                        # 2連単: 順番通り
                        actual_exacta = f"{row['first_place']}-{row['second_place']}"
                        would_have_hit = actual_exacta == combination
                        if would_have_hit:
                            would_have_payoff = payoffs_map.get((row['race_id'], 'exacta', actual_exacta))

                # v1.58: confirmed/won/lostレースでも払戻金と損益を計算
                calc_payoff = row['payoff']
                calc_return_amount = row['return_amount']
                calc_profit = row['profit']

                if display_status in ('confirmed', 'won', 'lost') and actual_result_str and row.get('race_id') and row['bet_amount']:
                    bet_type = row['bet_type']
                    combination = row['combination']
                    bet_amount = row['bet_amount']

                    # 的中判定と払戻金取得
                    is_hit = False
                    actual_payoff = None

                    if bet_type == 'auto':
                        # autoの場合は2連複/2連単で判定
                        actual_pair = set([str(row['first_place']), str(row['second_place'])])
                        bet_pair = set(combination.replace('-', '=').split('='))
                        if actual_pair == bet_pair:
                            is_hit = True
                            # 2連複の払戻金を取得
                            pair_list = sorted([str(row['first_place']), str(row['second_place'])])
                            payoff_comb = f"{pair_list[0]}={pair_list[1]}"
                            actual_payoff = payoffs_map.get((row['race_id'], 'quinella', payoff_comb))
                            if not actual_payoff:
                                payoff_comb2 = f"{pair_list[0]}-{pair_list[1]}"
                                actual_payoff = payoffs_map.get((row['race_id'], 'quinella', payoff_comb2))
                            # 2連単も試す
                            if not actual_payoff:
                                actual_exacta = f"{row['first_place']}-{row['second_place']}"
                                actual_payoff = payoffs_map.get((row['race_id'], 'exacta', actual_exacta))
                    elif bet_type == 'quinella':
                        actual_pair = set([str(row['first_place']), str(row['second_place'])])
                        bet_pair = set(combination.replace('-', '=').split('='))
                        is_hit = actual_pair == bet_pair
                        if is_hit:
                            pair_list = sorted([str(row['first_place']), str(row['second_place'])])
                            payoff_comb = f"{pair_list[0]}={pair_list[1]}"
                            actual_payoff = payoffs_map.get((row['race_id'], 'quinella', payoff_comb))
                            if not actual_payoff:
                                payoff_comb2 = f"{pair_list[0]}-{pair_list[1]}"
                                actual_payoff = payoffs_map.get((row['race_id'], 'quinella', payoff_comb2))
                    elif bet_type == 'exacta':
                        actual_exacta = f"{row['first_place']}-{row['second_place']}"
                        is_hit = actual_exacta == combination
                        if is_hit:
                            actual_payoff = payoffs_map.get((row['race_id'], 'exacta', actual_exacta))
                    elif bet_type == 'win':
                        is_hit = str(row['first_place']) == combination
                        if is_hit:
                            actual_payoff = payoffs_map.get((row['race_id'], 'win', str(row['first_place'])))

                    # 払戻金と損益を計算
                    if actual_payoff:
                        calc_payoff = actual_payoff
                        # 払戻金は100円単位なので、購入金額に応じて計算
                        calc_return_amount = int((actual_payoff / 100) * bet_amount)
                        calc_profit = calc_return_amount - bet_amount
                    elif is_hit is False:
                        # 不的中の場合
                        calc_payoff = 0
                        calc_return_amount = 0
                        calc_profit = -bet_amount

                results.append({
                    "id": row['id'],
                    "strategy_type": row['strategy_type'],
                    "race_date": str(row['race_date']),
                    "stadium_code": row['stadium_code'],
                    "stadium_name": row['stadium_name'],
                    "race_number": row['race_number'],
                    "bet_type": row['bet_type'],
                    "combination": row['combination'],
                    "bet_amount": row['bet_amount'],
                    "odds": float(row['odds']) if row['odds'] else None,
                    "status": display_status,
                    "reason": display_reason,
                    "actual_result": row['actual_result'] or actual_result_str,
                    "payoff": calc_payoff,
                    "return_amount": calc_return_amount,
                    "profit": calc_profit,
                    "race_status": row['race_status'],
                    "would_have_hit": would_have_hit,
                    "would_have_payoff": would_have_payoff,
                    "scheduled_deadline": row['scheduled_deadline'].isoformat() if row['scheduled_deadline'] else None,
                    "created_at": row['created_at'].isoformat() if row['created_at'] else None
                })

            return results
    finally:
        conn.close()


# ==================== 過去レースAPI ====================

@app.get("/api/historical/races/{race_date}")
def get_historical_races(race_date: str):
    """
    過去のレース一覧を取得（historical_race_resultsテーブルから）
    日付形式: YYYY-MM-DD
    """
    try:
        target_date = datetime.strptime(race_date, "%Y-%m-%d").date()
        target_date_str = target_date.strftime("%Y%m%d")  # DBは YYYYMMDD形式
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 過去レース結果を取得（着順データ）
            cur.execute("""
                SELECT DISTINCT
                    race_date,
                    stadium_code,
                    race_no,
                    MAX(CASE WHEN rank = '01' THEN boat_no END) as first_place,
                    MAX(CASE WHEN rank = '02' THEN boat_no END) as second_place,
                    MAX(CASE WHEN rank = '03' THEN boat_no END) as third_place
                FROM historical_race_results
                WHERE race_date = %s
                GROUP BY race_date, stadium_code, race_no
                ORDER BY stadium_code, race_no
            """, (target_date_str,))
            races = cur.fetchall()

            # 競艇場名を取得
            cur.execute("SELECT stadium_code, name FROM stadiums")
            stadiums_map = {str(row['stadium_code']).zfill(2): row['name'] for row in cur.fetchall()}

            result = []
            for race in races:
                stadium_code = race['stadium_code']
                stadium_name = stadiums_map.get(stadium_code, f"場{stadium_code}")

                result.append({
                    'race_date': race['race_date'],
                    'stadium_code': stadium_code,
                    'stadium_name': stadium_name,
                    'race_no': race['race_no'],
                    'result': {
                        'first': race['first_place'],
                        'second': race['second_place'],
                        'third': race['third_place']
                    } if race['first_place'] else None
                })

            return result
    finally:
        conn.close()


@app.get("/api/historical/race/{race_date}/{stadium_code}/{race_no}")
def get_historical_race_detail(race_date: str, stadium_code: str, race_no: str):
    """
    過去レースの詳細を取得（着順、払戻金、選手情報）
    """
    try:
        target_date = datetime.strptime(race_date, "%Y-%m-%d").date()
        target_date_str = target_date.strftime("%Y%m%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 着順データを取得
            cur.execute("""
                SELECT boat_no, racer_no, rank, race_time
                FROM historical_race_results
                WHERE race_date = %s AND stadium_code = %s AND race_no = %s
                ORDER BY
                    CASE WHEN rank ~ '^[0-9]+$' THEN rank::int ELSE 99 END,
                    boat_no
            """, (target_date_str, stadium_code, race_no.zfill(2)))
            results = cur.fetchall()

            # 払戻金データを取得（historical_payoffsから）
            cur.execute("""
                SELECT bet_type, combination, payout, popularity
                FROM historical_payoffs
                WHERE race_date = %s AND stadium_code = %s AND race_no = %s
                ORDER BY
                    CASE bet_type
                        WHEN 'tansho' THEN 1
                        WHEN 'fukusho' THEN 2
                        WHEN 'nirentan' THEN 3
                        WHEN 'nirenpuku' THEN 4
                        WHEN 'wide' THEN 5
                        WHEN 'sanrentan' THEN 6
                        WHEN 'sanrenpuku' THEN 7
                        ELSE 8
                    END,
                    popularity
            """, (target_date_str, stadium_code, race_no.zfill(2)))
            payoffs = cur.fetchall()

            # LZHからのデータがない場合（当日分等）はpayoffsテーブルからフォールバック
            if not payoffs:
                # racesテーブルからrace_idを取得
                cur.execute("""
                    SELECT id FROM races
                    WHERE race_date = %s AND stadium_code = %s AND race_number = %s
                """, (target_date, int(stadium_code), int(race_no)))
                race_row = cur.fetchone()
                if race_row:
                    race_id = race_row['id']
                    # payoffsテーブルから取得（bet_type名を変換）
                    cur.execute("""
                        SELECT bet_type, combination, payoff as payout, NULL as popularity
                        FROM payoffs
                        WHERE race_id = %s
                        ORDER BY
                            CASE bet_type
                                WHEN 'win' THEN 1
                                WHEN 'place' THEN 2
                                WHEN 'exacta' THEN 3
                                WHEN 'quinella' THEN 4
                                WHEN 'wide' THEN 5
                                WHEN 'trifecta' THEN 6
                                WHEN 'trio' THEN 7
                                ELSE 8
                            END
                    """, (race_id,))
                    payoffs_raw = cur.fetchall()
                    # bet_type名をhistorical_payoffs形式に変換
                    # payoffsテーブルは日本語名で保存されている
                    bet_type_map = {
                        # 英語名
                        'win': 'tansho',
                        'place': 'fukusho',
                        'exacta': 'nirentan',
                        'quinella': 'nirenpuku',
                        'wide': 'wide',
                        'trifecta': 'sanrentan',
                        'trio': 'sanrenpuku',
                        # 日本語名
                        '単勝': 'tansho',
                        '複勝': 'fukusho',
                        '2連単': 'nirentan',
                        '2連複': 'nirenpuku',
                        'ワイド': 'wide',
                        '3連単': 'sanrentan',
                        '3連複': 'sanrenpuku',
                    }
                    payoffs = []
                    for p in payoffs_raw:
                        payoffs.append({
                            'bet_type': bet_type_map.get(p['bet_type'], p['bet_type']),
                            'combination': p['combination'],
                            'payout': p['payout'],
                            'popularity': p['popularity']
                        })

            # 番組表データを取得（選手情報）
            cur.execute("""
                SELECT boat_no, racer_no, racer_name, age, branch, weight, rank,
                       national_win_rate, national_2nd_rate, local_win_rate, local_2nd_rate,
                       motor_no, motor_2nd_rate, boat_no_assigned, boat_2nd_rate
                FROM historical_programs
                WHERE race_date = %s AND stadium_code = %s AND race_no = %s
                ORDER BY boat_no
            """, (target_date_str, stadium_code, race_no.zfill(2)))
            programs = cur.fetchall()

            # 競艇場名を取得
            cur.execute("SELECT name FROM stadiums WHERE stadium_code = %s", (int(stadium_code),))
            stadium_row = cur.fetchone()
            stadium_name = stadium_row['name'] if stadium_row else f"場{stadium_code}"

            # 払戻金を種類別に整理
            payoffs_by_type = {}
            bet_type_names = {
                'tansho': '単勝',
                'fukusho': '複勝',
                'nirentan': '2連単',
                'nirenpuku': '2連複',
                'wide': 'ワイド',
                'sanrentan': '3連単',
                'sanrenpuku': '3連複'
            }
            for p in payoffs:
                bet_type = p['bet_type']
                if bet_type not in payoffs_by_type:
                    payoffs_by_type[bet_type] = {
                        'name': bet_type_names.get(bet_type, bet_type),
                        'items': []
                    }
                payoffs_by_type[bet_type]['items'].append({
                    'combination': p['combination'],
                    'payout': p['payout'],
                    'popularity': p['popularity']
                })

            return {
                'race_date': race_date,
                'stadium_code': stadium_code,
                'stadium_name': stadium_name,
                'race_no': race_no,
                'results': [{
                    'boat_no': r['boat_no'],
                    'racer_no': r['racer_no'],
                    'rank': r['rank'],
                    'race_time': r['race_time']
                } for r in results],
                'payoffs': payoffs_by_type,
                'programs': [decimal_to_float(dict(p)) for p in programs]
            }
    finally:
        conn.close()


@app.get("/api/historical/dates")
def get_available_dates(limit: int = Query(default=30, le=365)):
    """
    データが存在する日付一覧を取得（最新から指定件数）
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT race_date
                FROM historical_race_results
                ORDER BY race_date DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()

            # YYYYMMDD形式をYYYY-MM-DD形式に変換
            dates = []
            for row in rows:
                date_str = row['race_date']
                if len(date_str) == 8:
                    formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    dates.append(formatted)

            return dates
    finally:
        conn.close()


# ==================== 管理API ====================

@app.post("/api/admin/update-skip-reasons")
def update_skip_reasons():
    """
    skipReasonが設定されていない見送りレースに一括で理由を設定
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # skipReasonが設定されていない見送りレースを取得
            cur.execute("""
                SELECT id, reason FROM virtual_bets
                WHERE status = 'skipped'
            """)
            skipped_bets = cur.fetchall()

            updated_count = 0
            for bet in skipped_bets:
                reason = {}
                if bet['reason']:
                    try:
                        if isinstance(bet['reason'], str):
                            reason = json.loads(bet['reason'])
                        elif isinstance(bet['reason'], dict):
                            reason = bet['reason']
                    except:
                        pass

                # skipReasonが設定されていない場合のみ更新
                if 'skipReason' not in reason:
                    reason['skipReason'] = '締切超過（購入判断未実行）'
                    reason['decision'] = 'skipped'

                    cur.execute("""
                        UPDATE virtual_bets
                        SET reason = %s
                        WHERE id = %s
                    """, (json.dumps(reason, ensure_ascii=False), bet['id']))
                    updated_count += 1

            conn.commit()
            return {"message": f"更新完了: {updated_count}件"}
    finally:
        conn.close()


# ==================== 見送り分析・周期別統計API ====================

@app.get("/api/stats/skipped-analysis")
def get_skipped_analysis(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    strategy_type: Optional[str] = None
):
    """
    見送りレースの詳細分析を取得
    - 見送り件数
    - 見送り理由の分布
    - 仮想勝率・回収率
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 基本条件
            conditions = ["vb.status = 'skipped'"]
            params = []

            if start_date:
                conditions.append("vb.race_date >= %s")
                params.append(start_date)
            if end_date:
                conditions.append("vb.race_date <= %s")
                params.append(end_date)
            if strategy_type:
                conditions.append("vb.strategy_type = %s")
                params.append(strategy_type)

            where_clause = " AND ".join(conditions)

            # 見送りレースの基本統計
            cur.execute(f"""
                SELECT
                    COUNT(*) as total_skipped,
                    COUNT(DISTINCT vb.race_date) as days_count
                FROM virtual_bets vb
                WHERE {where_clause}
            """, params)
            basic_stats = cur.fetchone()

            # 見送り理由の分布
            cur.execute(f"""
                SELECT
                    COALESCE(reason->>'skipReason', '理由不明') as skip_reason,
                    COUNT(*) as count
                FROM virtual_bets vb
                WHERE {where_clause}
                GROUP BY reason->>'skipReason'
                ORDER BY count DESC
            """, params)
            reason_distribution = [dict(row) for row in cur.fetchall()]

            # 戦略別の見送り統計
            cur.execute(f"""
                SELECT
                    vb.strategy_type,
                    COUNT(*) as skipped_count
                FROM virtual_bets vb
                WHERE {where_clause}
                GROUP BY vb.strategy_type
                ORDER BY skipped_count DESC
            """, params)
            by_strategy = [dict(row) for row in cur.fetchall()]

            # 見送りレースの仮想的中率・回収率を計算
            cur.execute(f"""
                SELECT
                    vb.*,
                    r.id as race_id,
                    rr.first_place,
                    rr.second_place,
                    rr.third_place
                FROM virtual_bets vb
                LEFT JOIN races r ON vb.race_date = r.race_date
                    AND vb.stadium_code::smallint = r.stadium_code
                    AND vb.race_number = r.race_number
                LEFT JOIN race_results rr ON r.id = rr.race_id
                WHERE {where_clause}
            """, params)
            skipped_bets = cur.fetchall()

            # レースIDを収集して払戻金を一括取得
            race_ids = [row['race_id'] for row in skipped_bets if row.get('race_id')]
            payoffs_map = {}
            if race_ids:
                cur.execute("""
                    SELECT race_id, bet_type, combination, payoff
                    FROM payoffs
                    WHERE race_id = ANY(%s)
                """, (race_ids,))
                # bet_typeの日本語→英語マッピング
                bet_type_map = {
                    '2連複': 'quinella',
                    '2連単': 'exacta',
                    '単勝': 'win',
                    '複勝': 'place',
                    '3連単': 'trifecta',
                    '3連複': 'trio',
                    'ワイド': 'wide',
                }
                for p in cur.fetchall():
                    bt = p['bet_type']
                    bt_en = bet_type_map.get(bt, bt)
                    key = (p['race_id'], bt_en, p['combination'])
                    payoffs_map[key] = p['payoff']

            # 仮想的中・払戻金を計算
            total_would_have_bet = 0
            total_would_have_hit = 0
            total_would_have_payoff = 0

            for row in skipped_bets:
                if not row['first_place'] or not row['second_place']:
                    continue

                bet_amount = row['bet_amount'] or 1000  # デフォルト1000円
                total_would_have_bet += bet_amount

                bet_type = row['bet_type']
                combination = row['combination']
                would_have_hit = False
                payoff = 0

                if bet_type == 'win':
                    would_have_hit = str(row['first_place']) == combination
                    if would_have_hit:
                        payoff = payoffs_map.get((row['race_id'], 'win', str(row['first_place'])), 0) or 0
                elif bet_type in ('quinella', 'auto'):
                    # autoの場合も2連複で判定
                    actual_pair = set([str(row['first_place']), str(row['second_place'])])
                    bet_pair = set(combination.replace('-', '=').split('='))
                    would_have_hit = actual_pair == bet_pair
                    if would_have_hit:
                        pair_list = sorted([str(row['first_place']), str(row['second_place'])])
                        payoff_comb = f"{pair_list[0]}={pair_list[1]}"
                        payoff = payoffs_map.get((row['race_id'], 'quinella', payoff_comb), 0) or 0
                        if not payoff:
                            payoff_comb2 = f"{pair_list[0]}-{pair_list[1]}"
                            payoff = payoffs_map.get((row['race_id'], 'quinella', payoff_comb2), 0) or 0
                        # 2連単も試す
                        if not payoff:
                            actual_exacta = f"{row['first_place']}-{row['second_place']}"
                            payoff = payoffs_map.get((row['race_id'], 'exacta', actual_exacta), 0) or 0
                elif bet_type == 'exacta':
                    actual_exacta = f"{row['first_place']}-{row['second_place']}"
                    would_have_hit = actual_exacta == combination
                    if would_have_hit:
                        payoff = payoffs_map.get((row['race_id'], 'exacta', actual_exacta), 0) or 0

                if would_have_hit:
                    total_would_have_hit += 1
                    # 払戻金は100円単位なので、bet_amountベースに換算
                    return_amount = int((payoff / 100) * bet_amount) if payoff else 0
                    total_would_have_payoff += return_amount

            # 結果が確定しているレース数
            total_with_result = sum(1 for row in skipped_bets if row['first_place'] and row['second_place'])

            virtual_hit_rate = (total_would_have_hit / total_with_result * 100) if total_with_result > 0 else 0
            virtual_return_rate = (total_would_have_payoff / total_would_have_bet * 100) if total_would_have_bet > 0 else 0
            virtual_profit = total_would_have_payoff - total_would_have_bet

            return {
                "total_skipped": basic_stats['total_skipped'],
                "days_count": basic_stats['days_count'],
                "reason_distribution": reason_distribution,
                "by_strategy": by_strategy,
                "virtual_stats": {
                    "total_with_result": total_with_result,
                    "total_would_have_hit": total_would_have_hit,
                    "total_would_have_bet": total_would_have_bet,
                    "total_would_have_payoff": total_would_have_payoff,
                    "virtual_hit_rate": round(virtual_hit_rate, 2),
                    "virtual_return_rate": round(virtual_return_rate, 2),
                    "virtual_profit": virtual_profit
                }
            }
    finally:
        conn.close()


@app.get("/api/stats/period-summary")
def get_period_summary(
    period: str = Query(default="daily", regex="^(daily|weekly|monthly)$"),
    limit: int = Query(default=30, le=365)
):
    """
    周期別のサマリーを取得（日別/週別/月別）
    購入レースと見送りレースの両方を含む
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if period == "daily":
                date_trunc = "day"
                date_format = "race_date"
            elif period == "weekly":
                date_trunc = "week"
                date_format = "DATE_TRUNC('week', race_date)::date"
            else:  # monthly
                date_trunc = "month"
                date_format = "DATE_TRUNC('month', race_date)::date"

            # 購入レースの統計
            cur.execute(f"""
                SELECT
                    {date_format} as period_date,
                    COUNT(*) as total_bets,
                    COUNT(CASE WHEN status = 'won' THEN 1 END) as hits,
                    COUNT(CASE WHEN status = 'lost' THEN 1 END) as losses,
                    COUNT(CASE WHEN status = 'skipped' THEN 1 END) as skipped,
                    COALESCE(SUM(CASE WHEN status IN ('won', 'lost') THEN bet_amount END), 0) as total_bet_amount,
                    COALESCE(SUM(CASE WHEN status IN ('won', 'lost') THEN return_amount END), 0) as total_return_amount,
                    COALESCE(SUM(CASE WHEN status IN ('won', 'lost') THEN profit END), 0) as total_profit
                FROM virtual_bets
                GROUP BY {date_format}
                ORDER BY period_date DESC
                LIMIT %s
            """, (limit,))
            period_stats = cur.fetchall()

            results = []
            for row in period_stats:
                total_decided = row['hits'] + row['losses']
                hit_rate = (row['hits'] / total_decided * 100) if total_decided > 0 else 0
                return_rate = (float(row['total_return_amount']) / float(row['total_bet_amount']) * 100) if row['total_bet_amount'] > 0 else 0

                results.append({
                    "period_date": str(row['period_date']),
                    "total_bets": row['total_bets'],
                    "hits": row['hits'],
                    "losses": row['losses'],
                    "skipped": row['skipped'],
                    "total_bet_amount": float(row['total_bet_amount']),
                    "total_return_amount": float(row['total_return_amount']),
                    "total_profit": float(row['total_profit']),
                    "hit_rate": round(hit_rate, 2),
                    "return_rate": round(return_rate, 2)
                })

            return results
    finally:
        conn.close()


@app.get("/api/stats/strategy-comparison")
def get_strategy_comparison(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    戦略別の比較統計を取得
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            conditions = ["1=1"]
            params = []

            if start_date:
                conditions.append("race_date >= %s")
                params.append(start_date)
            if end_date:
                conditions.append("race_date <= %s")
                params.append(end_date)

            where_clause = " AND ".join(conditions)

            cur.execute(f"""
                SELECT
                    strategy_type,
                    COUNT(*) as total_bets,
                    COUNT(CASE WHEN status = 'won' THEN 1 END) as hits,
                    COUNT(CASE WHEN status = 'lost' THEN 1 END) as losses,
                    COUNT(CASE WHEN status = 'skipped' THEN 1 END) as skipped,
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                    COALESCE(SUM(CASE WHEN status IN ('won', 'lost') THEN bet_amount END), 0) as total_bet_amount,
                    COALESCE(SUM(CASE WHEN status IN ('won', 'lost') THEN return_amount END), 0) as total_return_amount,
                    COALESCE(SUM(CASE WHEN status IN ('won', 'lost') THEN profit END), 0) as total_profit
                FROM virtual_bets
                WHERE {where_clause}
                GROUP BY strategy_type
                ORDER BY strategy_type
            """, params)
            strategy_stats = cur.fetchall()

            results = []
            for row in strategy_stats:
                total_decided = row['hits'] + row['losses']
                hit_rate = (row['hits'] / total_decided * 100) if total_decided > 0 else 0
                return_rate = (float(row['total_return_amount']) / float(row['total_bet_amount']) * 100) if row['total_bet_amount'] > 0 else 0

                results.append({
                    "strategy_type": row['strategy_type'],
                    "total_bets": row['total_bets'],
                    "hits": row['hits'],
                    "losses": row['losses'],
                    "skipped": row['skipped'],
                    "pending": row['pending'],
                    "total_bet_amount": float(row['total_bet_amount']),
                    "total_return_amount": float(row['total_return_amount']),
                    "total_profit": float(row['total_profit']),
                    "hit_rate": round(hit_rate, 2),
                    "return_rate": round(return_rate, 2)
                })

            return results
    finally:
        conn.close()


@app.get("/api/stats/skipped-virtual-results")
def get_skipped_virtual_results(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    strategy_type: Optional[str] = None,
    limit: int = Query(default=100, le=500)
):
    """
    見送りレースの仮想結果一覧を取得
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            conditions = ["vb.status = 'skipped'"]
            params = []

            if start_date:
                conditions.append("vb.race_date >= %s")
                params.append(start_date)
            if end_date:
                conditions.append("vb.race_date <= %s")
                params.append(end_date)
            if strategy_type:
                conditions.append("vb.strategy_type = %s")
                params.append(strategy_type)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            cur.execute(f"""
                SELECT
                    vb.*,
                    s.name as stadium_name,
                    r.id as race_id,
                    rr.first_place,
                    rr.second_place,
                    rr.third_place
                FROM virtual_bets vb
                LEFT JOIN stadiums s ON vb.stadium_code::int = s.stadium_code
                LEFT JOIN races r ON vb.race_date = r.race_date
                    AND vb.stadium_code::smallint = r.stadium_code
                    AND vb.race_number = r.race_number
                LEFT JOIN race_results rr ON r.id = rr.race_id
                WHERE {where_clause}
                ORDER BY vb.race_date DESC, vb.created_at DESC
                LIMIT %s
            """, params)
            skipped_bets = cur.fetchall()

            # レースIDを収集して払戻金を一括取得
            race_ids = [row['race_id'] for row in skipped_bets if row.get('race_id')]
            payoffs_map = {}
            if race_ids:
                cur.execute("""
                    SELECT race_id, bet_type, combination, payoff
                    FROM payoffs
                    WHERE race_id = ANY(%s)
                """, (race_ids,))
                # bet_typeの日本語→英語マッピング
                bet_type_map = {
                    '2連複': 'quinella',
                    '2連単': 'exacta',
                    '単勝': 'win',
                    '複勝': 'place',
                }
                for p in cur.fetchall():
                    bt = p['bet_type']
                    bt_en = bet_type_map.get(bt, bt)
                    key = (p['race_id'], bt_en, p['combination'])
                    payoffs_map[key] = p['payoff']

            results = []
            for row in skipped_bets:
                actual_result_str = None
                if row['first_place'] and row['second_place'] and row['third_place']:
                    actual_result_str = f"{row['first_place']}-{row['second_place']}-{row['third_place']}"

                # 仮想的中判定
                would_have_hit = None
                would_have_payoff = None
                would_have_profit = None  # 仮想損益を追加

                if actual_result_str and row.get('race_id'):
                    bet_type = row['bet_type']
                    combination = row['combination']
                    bet_amount = row['bet_amount'] or 1000  # デフォルト1000円

                    if bet_type == 'win':
                        would_have_hit = str(row['first_place']) == combination
                        if would_have_hit:
                            would_have_payoff = payoffs_map.get((row['race_id'], 'win', str(row['first_place'])))
                    elif bet_type in ('quinella', 'auto'):
                        # autoの場合も2連複で判定
                        actual_pair = set([str(row['first_place']), str(row['second_place'])])
                        bet_pair = set(combination.replace('-', '=').split('='))
                        would_have_hit = actual_pair == bet_pair
                        if would_have_hit:
                            pair_list = sorted([str(row['first_place']), str(row['second_place'])])
                            payoff_comb = f"{pair_list[0]}={pair_list[1]}"
                            would_have_payoff = payoffs_map.get((row['race_id'], 'quinella', payoff_comb))
                            if not would_have_payoff:
                                payoff_comb2 = f"{pair_list[0]}-{pair_list[1]}"
                                would_have_payoff = payoffs_map.get((row['race_id'], 'quinella', payoff_comb2))
                    elif bet_type == 'exacta':
                        actual_exacta = f"{row['first_place']}-{row['second_place']}"
                        would_have_hit = actual_exacta == combination
                        if would_have_hit:
                            would_have_payoff = payoffs_map.get((row['race_id'], 'exacta', actual_exacta))

                    # 仮想損益を計算（1000円ベース）
                    if would_have_hit is not None:
                        if would_have_hit and would_have_payoff:
                            # 払戻金は100円単位なので、1000円投資で計算
                            return_amount = int((would_have_payoff / 100) * bet_amount)
                            would_have_profit = return_amount - bet_amount
                        else:
                            would_have_profit = -bet_amount  # 不的中の場合

                skip_reason = None
                if row['reason']:
                    try:
                        if isinstance(row['reason'], str):
                            reason_dict = json.loads(row['reason'])
                        else:
                            reason_dict = row['reason']
                        skip_reason = reason_dict.get('skipReason')
                    except:
                        pass

                results.append({
                    "id": row['id'],
                    "strategy_type": row['strategy_type'],
                    "race_date": str(row['race_date']),
                    "stadium_code": row['stadium_code'],
                    "stadium_name": row['stadium_name'],
                    "race_number": row['race_number'],
                    "bet_type": row['bet_type'],
                    "combination": row['combination'],
                    "bet_amount": row['bet_amount'] or 1000,
                    "odds": float(row['odds']) if row['odds'] else None,
                    "skip_reason": skip_reason,
                    "actual_result": actual_result_str,
                    "would_have_hit": would_have_hit,
                    "would_have_payoff": would_have_payoff,
                    "virtual_profit": would_have_profit
                })

            return results
    finally:
        conn.close()


@app.get("/api/debug/odds-history")
async def debug_odds_history(
    race_date: str = Query(None, description="レース日 (YYYY-MM-DD)"),
    stadium_code: str = Query(None, description="競艇場コード"),
    race_number: int = Query(None, description="レース番号"),
    combination: str = Query(None, description="買い目")
):
    """
    odds_historyテーブルのデバッグ用API
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # テーブルのサンプルデータを取得
            if race_date and stadium_code and race_number:
                # 特定レースのオッズを検索
                cursor.execute("""
                    SELECT race_date, stadium_code, race_number, odds_type, combination,
                           odds_value, scraped_at
                    FROM odds_history
                    WHERE race_date = %s
                    AND (stadium_code = %s OR stadium_code = %s)
                    AND race_number = %s
                    ORDER BY scraped_at DESC
                    LIMIT 50
                """, (race_date, stadium_code, stadium_code.zfill(2), race_number))
            else:
                # 最新のオッズデータを取得
                cursor.execute("""
                    SELECT race_date, stadium_code, race_number, odds_type, combination,
                           odds_value, scraped_at
                    FROM odds_history
                    ORDER BY scraped_at DESC
                    LIMIT 50
                """)

            rows = cursor.fetchall()

            # stadium_codeの分布を確認
            cursor.execute("""
                SELECT stadium_code, COUNT(*) as count
                FROM odds_history
                WHERE race_date = %s
                GROUP BY stadium_code
                ORDER BY count DESC
                LIMIT 30
            """, (race_date or get_adjusted_date().isoformat(),))
            stadium_distribution = cursor.fetchall()

            # odds_typeの分布を確認
            cursor.execute("""
                SELECT odds_type, COUNT(*) as count
                FROM odds_history
                WHERE race_date = %s
                GROUP BY odds_type
                ORDER BY count DESC
            """, (race_date or get_adjusted_date().isoformat(),))
            type_distribution = cursor.fetchall()

            return {
                "sample_data": [decimal_to_float(dict(row)) for row in rows],
                "stadium_code_distribution": [dict(row) for row in stadium_distribution],
                "odds_type_distribution": [dict(row) for row in type_distribution],
                "query_params": {
                    "race_date": race_date,
                    "stadium_code": stadium_code,
                    "race_number": race_number,
                    "combination": combination
                }
            }
    finally:
        conn.close()


# ==================== データ補正API ====================

@app.post("/api/admin/backfill-historical-results")
def backfill_historical_results(
    start_date: str = Query(default="2026-01-17", description="開始日 (YYYY-MM-DD)"),
    end_date: str = Query(default=None, description="終了日 (YYYY-MM-DD)、省略時は今日")
):
    """
    2026年1月17日以降の欠落データ（登番、タイム）を補正
    公式サイトから再スクレイピングしてhistorical_race_resultsテーブルに保存
    """
    import requests
    from bs4 import BeautifulSoup
    import re
    import time

    # 終了日が指定されていない場合は今日
    if not end_date:
        end_date = get_adjusted_date().isoformat()

    # 日付をパース
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    conn = get_db_connection()
    total_processed = 0
    total_inserted = 0
    errors = []

    try:
        with conn.cursor() as cur:
            # 競艇場コードを取得
            cur.execute("SELECT stadium_code FROM stadiums")
            stadium_codes = [str(row['stadium_code']).zfill(2) for row in cur.fetchall()]

            current_date = start
            while current_date <= end:
                date_str = current_date.strftime("%Y%m%d")

                for stadium_code in stadium_codes:
                    for race_no in range(1, 13):
                        # 既存データをチェック
                        cur.execute("""
                            SELECT COUNT(*) as cnt FROM historical_race_results
                            WHERE race_date = %s AND stadium_code = %s AND race_no = %s
                        """, (date_str, stadium_code, str(race_no).zfill(2)))
                        if cur.fetchone()['cnt'] > 0:
                            continue  # 既存データがあればスキップ

                        # 公式サイトから結果を取得
                        url = f"https://www.boatrace.jp/owpc/pc/race/raceresult?rno={race_no}&jcd={stadium_code}&hd={date_str}"
                        try:
                            resp = requests.get(url, timeout=10)
                            if resp.status_code != 200:
                                continue

                            soup = BeautifulSoup(resp.text, 'html.parser')

                            # 着順テーブルを探す
                            result_table = soup.find('table', class_='is-w495')
                            if not result_table:
                                continue

                            tbody = result_table.find('tbody')
                            if not tbody:
                                continue

                            rows = tbody.find_all('tr')
                            for row in rows:
                                cells = row.find_all('td')
                                if len(cells) < 4:
                                    continue

                                # 着順
                                rank = cells[0].get_text(strip=True)

                                # 艇番
                                boat_no_elem = cells[1].find('span')
                                boat_no = boat_no_elem.get_text(strip=True) if boat_no_elem else ''

                                # 登番（4桁数字）
                                racer_text = cells[2].get_text(strip=True)
                                racer_no_match = re.match(r'(\d{4})', racer_text)
                                racer_no = racer_no_match.group(1) if racer_no_match else ''

                                # タイム
                                race_time = cells[3].get_text(strip=True)

                                if boat_no and rank:
                                    cur.execute("""
                                        INSERT INTO historical_race_results
                                        (race_date, stadium_code, race_no, boat_no, racer_no, rank, race_time)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                                        ON CONFLICT (race_date, stadium_code, race_no, boat_no) DO UPDATE
                                        SET racer_no = EXCLUDED.racer_no, race_time = EXCLUDED.race_time
                                    """, (date_str, stadium_code, str(race_no).zfill(2), boat_no, racer_no, rank, race_time))
                                    total_inserted += 1

                            total_processed += 1
                            time.sleep(0.1)  # レート制限

                        except Exception as e:
                            errors.append(f"{date_str}/{stadium_code}/{race_no}: {str(e)}")
                            continue

                conn.commit()
                current_date += timedelta(days=1)

            return {
                "message": "補正完了",
                "start_date": start_date,
                "end_date": end_date,
                "total_races_processed": total_processed,
                "total_records_inserted": total_inserted,
                "errors": errors[:10]  # 最初の10件のエラーのみ
            }
    finally:
        conn.close()


@app.post("/api/admin/reset-today-overdue-bets")
def reset_today_overdue_bets():
    """
    今日の締切超過の購入予定をリセット（削除）
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        today = datetime.now(JST).strftime('%Y-%m-%d')

        # 今日の締切超過（見送り）レコードを削除
        # reasonはJSONB型なので、::textでキャストしてからLIKEを使用
        cur.execute("""
            DELETE FROM virtual_bets
            WHERE race_date = %s
            AND status = 'skipped'
            AND reason::text LIKE '%%締切超過%%'
        """, (today,))

        deleted = cur.rowcount
        conn.commit()

        return {
            "success": True,
            "deleted_count": deleted,
            "message": f"今日({today})の締切超過レコードを{deleted}件削除しました"
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/admin/register-today-bets")
def register_today_bets():
    """
    今日の購入予定を再登録
    """
    try:
        from auto_betting import register_daily_bets
        result = register_daily_bets()
        return {
            "success": True,
            "message": "今日の購入予定を登録しました",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/migrate-to-timestamptz")
def migrate_to_timestamptz():
    """
    DBのTIMESTAMPカラムをTIMESTAMP WITH TIME ZONEに変更
    既存データはJSTとして変換
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            migration_results = []

            # 1. racesテーブルのdeadline_at
            try:
                cur.execute("""
                    ALTER TABLE races
                    ALTER COLUMN deadline_at TYPE TIMESTAMP WITH TIME ZONE
                    USING deadline_at AT TIME ZONE 'Asia/Tokyo'
                """)
                migration_results.append({"table": "races", "column": "deadline_at", "status": "success"})
            except Exception as e:
                migration_results.append({"table": "races", "column": "deadline_at", "status": "error", "error": str(e)})

            # 2. virtual_betsテーブルのscheduled_deadline
            try:
                cur.execute("""
                    ALTER TABLE virtual_bets
                    ALTER COLUMN scheduled_deadline TYPE TIMESTAMP WITH TIME ZONE
                    USING scheduled_deadline AT TIME ZONE 'Asia/Tokyo'
                """)
                migration_results.append({"table": "virtual_bets", "column": "scheduled_deadline", "status": "success"})
            except Exception as e:
                migration_results.append({"table": "virtual_bets", "column": "scheduled_deadline", "status": "error", "error": str(e)})

            # 3. virtual_betsテーブルのcreated_at
            try:
                cur.execute("""
                    ALTER TABLE virtual_bets
                    ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE
                    USING created_at AT TIME ZONE 'Asia/Tokyo'
                """)
                migration_results.append({"table": "virtual_bets", "column": "created_at", "status": "success"})
            except Exception as e:
                migration_results.append({"table": "virtual_bets", "column": "created_at", "status": "error", "error": str(e)})

            # 4. virtual_betsテーブルのupdated_at
            try:
                cur.execute("""
                    ALTER TABLE virtual_bets
                    ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE
                    USING updated_at AT TIME ZONE 'Asia/Tokyo'
                """)
                migration_results.append({"table": "virtual_bets", "column": "updated_at", "status": "success"})
            except Exception as e:
                migration_results.append({"table": "virtual_bets", "column": "updated_at", "status": "error", "error": str(e)})

            # 5. virtual_betsテーブルのconfirmed_at
            try:
                cur.execute("""
                    ALTER TABLE virtual_bets
                    ALTER COLUMN confirmed_at TYPE TIMESTAMP WITH TIME ZONE
                    USING confirmed_at AT TIME ZONE 'Asia/Tokyo'
                """)
                migration_results.append({"table": "virtual_bets", "column": "confirmed_at", "status": "success"})
            except Exception as e:
                migration_results.append({"table": "virtual_bets", "column": "confirmed_at", "status": "error", "error": str(e)})

            # 6. virtual_betsテーブルのresult_confirmed_at
            try:
                cur.execute("""
                    ALTER TABLE virtual_bets
                    ALTER COLUMN result_confirmed_at TYPE TIMESTAMP WITH TIME ZONE
                    USING result_confirmed_at AT TIME ZONE 'Asia/Tokyo'
                """)
                migration_results.append({"table": "virtual_bets", "column": "result_confirmed_at", "status": "success"})
            except Exception as e:
                migration_results.append({"table": "virtual_bets", "column": "result_confirmed_at", "status": "error", "error": str(e)})

            # 7. racesテーブルのcreated_at
            try:
                cur.execute("""
                    ALTER TABLE races
                    ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE
                    USING created_at AT TIME ZONE 'Asia/Tokyo'
                """)
                migration_results.append({"table": "races", "column": "created_at", "status": "success"})
            except Exception as e:
                migration_results.append({"table": "races", "column": "created_at", "status": "error", "error": str(e)})

            conn.commit()

            success_count = sum(1 for r in migration_results if r['status'] == 'success')
            error_count = sum(1 for r in migration_results if r['status'] == 'error')

            return {
                "success": error_count == 0,
                "message": f"マイグレーション完了: 成功 {success_count}件, エラー {error_count}件",
                "results": migration_results
            }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/admin/revert-timezone-fix")
def revert_timezone_fix():
    """
    DBのタイムゾーンデータを修正（9時間減算）
    前回の+9時間修正が間違いだったため、元に戻す
    """
    conn = get_db_connection()
    fix_results = []

    try:
        with conn.cursor() as cur:
            # 1. virtual_betsのscheduled_deadlineを9時間減算
            try:
                cur.execute("""
                    UPDATE virtual_bets
                    SET scheduled_deadline = scheduled_deadline - INTERVAL '9 hours'
                    WHERE scheduled_deadline IS NOT NULL
                """)
                affected = cur.rowcount
                fix_results.append({"table": "virtual_bets", "column": "scheduled_deadline", "status": "success", "affected_rows": affected})
            except Exception as e:
                fix_results.append({"table": "virtual_bets", "column": "scheduled_deadline", "status": "error", "error": str(e)})

            # 2. racesのdeadline_atを9時間減算
            try:
                cur.execute("""
                    UPDATE races
                    SET deadline_at = deadline_at - INTERVAL '9 hours'
                    WHERE deadline_at IS NOT NULL
                """)
                affected = cur.rowcount
                fix_results.append({"table": "races", "column": "deadline_at", "status": "success", "affected_rows": affected})
            except Exception as e:
                fix_results.append({"table": "races", "column": "deadline_at", "status": "error", "error": str(e)})

            conn.commit()

            success_count = sum(1 for r in fix_results if r['status'] == 'success')
            error_count = sum(1 for r in fix_results if r['status'] == 'error')

            return {
                "success": error_count == 0,
                "message": f"タイムゾーンデータ修正完了（-9時間）: 成功 {success_count}件, エラー {error_count}件",
                "results": fix_results
            }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/admin/fix-timezone-data")
def fix_timezone_data():
    """
    DBのタイムゾーンデータを修正（9時間加算）
    マイグレーション時にJSTデータがUTCとして解釈されたため、
    9時間加算して正しいJSTに戻す
    """
    conn = get_db_connection()
    fix_results = []

    try:
        with conn.cursor() as cur:
            # 1. virtual_betsのscheduled_deadlineを9時間加算
            try:
                cur.execute("""
                    UPDATE virtual_bets
                    SET scheduled_deadline = scheduled_deadline + INTERVAL '9 hours'
                    WHERE scheduled_deadline IS NOT NULL
                """)
                affected = cur.rowcount
                fix_results.append({"table": "virtual_bets", "column": "scheduled_deadline", "status": "success", "affected_rows": affected})
            except Exception as e:
                fix_results.append({"table": "virtual_bets", "column": "scheduled_deadline", "status": "error", "error": str(e)})

            # 2. racesのdeadline_atを9時間加算
            try:
                cur.execute("""
                    UPDATE races
                    SET deadline_at = deadline_at + INTERVAL '9 hours'
                    WHERE deadline_at IS NOT NULL
                """)
                affected = cur.rowcount
                fix_results.append({"table": "races", "column": "deadline_at", "status": "success", "affected_rows": affected})
            except Exception as e:
                fix_results.append({"table": "races", "column": "deadline_at", "status": "error", "error": str(e)})

            conn.commit()

            success_count = sum(1 for r in fix_results if r['status'] == 'success')
            error_count = sum(1 for r in fix_results if r['status'] == 'error')

            return {
                "success": error_count == 0,
                "message": f"タイムゾーンデータ修正完了: 成功 {success_count}件, エラー {error_count}件",
                "results": fix_results
            }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# 静的ファイル配信（フロントエンド）
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

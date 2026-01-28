"""
本日の購入予定を新しい単勝戦略（関東4場戦略）に更新するスクリプト
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta

# 日本時間
JST = timezone(timedelta(hours=9))

# データベースURL
DATABASE_URL = "postgresql://kokotomo_staging_user:lTgXbLpIUJMJhGG6XzCwBGZGBKdRFbNM@dpg-d0lqe43uibrs73fmgrl0-a.oregon-postgres.render.com/kokotomo_staging"

# 新しい戦略設定
NEW_STRATEGY = {
    'tansho_kanto': {
        'name': '関東4場単勝戦略',
        'target_stadiums': ['01', '02', '04', '05'],  # 桐生、戸田、平和島、多摩川
        'target_races_by_stadium': {
            '01': [1, 2, 3, 4],           # 桐生: 1-4R
            '02': [1, 2, 3, 4, 6, 8],     # 戸田: 1-4,6,8R
            '04': [1, 2, 3, 4, 6, 7, 8],  # 平和島: 1-4,6-8R
            '05': [2, 3, 4, 5, 6, 7],     # 多摩川: 2-7R
        },
        'bet_type': 'win',
        'min_odds': 1.0,
        'max_odds': 999.0,
        'bet_amount': 1000,
    }
}

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode='require')

def update_today_bets():
    """本日の購入予定を更新"""
    today = datetime.now(JST).date()
    print(f"=== 本日({today})の購入予定を更新 ===")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. 旧戦略(11r12r_win)のpending購入予定を確認
            cur.execute("""
                SELECT * FROM virtual_bets 
                WHERE race_date = %s AND strategy_type = '11r12r_win' AND status = 'pending'
            """, (today,))
            old_bets = cur.fetchall()
            print(f"旧戦略(11r12r_win)のpending: {len(old_bets)}件")
            
            # 2. 旧戦略のpending購入予定を削除
            if old_bets:
                cur.execute("""
                    DELETE FROM virtual_bets 
                    WHERE race_date = %s AND strategy_type = '11r12r_win' AND status = 'pending'
                """, (today,))
                print(f"旧戦略のpending購入予定を削除: {cur.rowcount}件")
            
            # 3. 今日のレース一覧を取得
            cur.execute("""
                SELECT r.id, r.race_date, r.stadium_code, r.race_number, r.deadline_at, s.name as stadium_name
                FROM races r
                JOIN stadiums s ON r.stadium_code = s.stadium_code
                WHERE r.race_date = %s AND r.is_canceled = FALSE
                ORDER BY r.deadline_at
            """, (today,))
            races = cur.fetchall()
            print(f"今日のレース数: {len(races)}")
            
            # 4. 新戦略の購入予定を登録
            config = NEW_STRATEGY['tansho_kanto']
            target_stadiums = config['target_stadiums']
            target_races_by_stadium = config['target_races_by_stadium']
            
            # 既存の購入予定を取得
            cur.execute("""
                SELECT strategy_type, stadium_code, race_number
                FROM virtual_bets
                WHERE race_date = %s
            """, (today,))
            existing = set((r['strategy_type'], r['stadium_code'], r['race_number']) for r in cur.fetchall())
            
            insert_count = 0
            now_str = datetime.now(JST).isoformat()
            
            for race in races:
                race_number = race['race_number']
                stadium_code = str(race['stadium_code']).zfill(2)
                deadline_at = race['deadline_at']
                
                # 対象場かチェック
                if stadium_code not in target_stadiums:
                    continue
                
                # 対象Rかチェック
                target_races = target_races_by_stadium.get(stadium_code, [])
                if race_number not in target_races:
                    continue
                
                # 既存チェック
                if ('tansho_kanto', stadium_code, race_number) in existing:
                    continue
                
                # 締切が過ぎていないかチェック
                if deadline_at:
                    deadline_utc = deadline_at if deadline_at.tzinfo else deadline_at.replace(tzinfo=timezone.utc)
                    if deadline_utc < datetime.now(timezone.utc):
                        print(f"  スキップ（締切済）: {stadium_code} {race_number}R")
                        continue
                
                # 購入予定を登録
                cur.execute("""
                    INSERT INTO virtual_bets (
                        strategy_type, race_date, stadium_code, race_number,
                        bet_type, combination, bet_amount, scheduled_deadline, reason
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    'tansho_kanto',
                    today,
                    stadium_code,
                    race_number,
                    'win',
                    '1',
                    config['bet_amount'],
                    deadline_at,
                    f'{{"strategy": "{config["name"]}", "registered_at": "{now_str}"}}'
                ))
                insert_count += 1
                print(f"  登録: {stadium_code} {race_number}R ({race['stadium_name']})")
            
            conn.commit()
            print(f"\n新戦略(tansho_kanto)の購入予定を登録: {insert_count}件")
            
            # 5. 最終確認
            cur.execute("""
                SELECT strategy_type, COUNT(*) as count
                FROM virtual_bets
                WHERE race_date = %s AND status = 'pending'
                GROUP BY strategy_type
            """, (today,))
            summary = cur.fetchall()
            print("\n=== 本日の購入予定サマリー ===")
            for row in summary:
                print(f"  {row['strategy_type']}: {row['count']}件")
            
    except Exception as e:
        print(f"エラー: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    update_today_bets()

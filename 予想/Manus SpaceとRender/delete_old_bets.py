"""
旧戦略（11r12r_win）の購入予定を削除するスクリプト
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
import time

# 日本時間
JST = timezone(timedelta(hours=9))

# データベースURL
DATABASE_URL = "postgresql://kokotomo_staging_user:lTgXbLpIUJMJhGG6XzCwBGZGBKdRFbNM@dpg-d0lqe43uibrs73fmgrl0-a.oregon-postgres.render.com/kokotomo_staging"

def get_db_connection(retries=3):
    for i in range(retries):
        try:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode='require', connect_timeout=30)
            return conn
        except Exception as e:
            print(f"接続試行 {i+1}/{retries} 失敗: {e}")
            if i < retries - 1:
                time.sleep(5)
    return None

def delete_old_bets():
    """旧戦略の購入予定を削除"""
    today = datetime.now(JST).date()
    print(f"=== 本日({today})の旧戦略購入予定を削除 ===")
    
    conn = get_db_connection()
    if not conn:
        print("DB接続に失敗しました")
        return
    
    try:
        with conn.cursor() as cur:
            # 1. 旧戦略(11r12r_win)の購入予定を確認
            cur.execute("""
                SELECT id, stadium_code, race_number, status, scheduled_deadline
                FROM virtual_bets 
                WHERE race_date = %s AND strategy_type = '11r12r_win'
                ORDER BY scheduled_deadline
            """, (today,))
            old_bets = cur.fetchall()
            print(f"旧戦略(11r12r_win)の購入予定: {len(old_bets)}件")
            
            for bet in old_bets:
                print(f"  - ID:{bet['id']} {bet['stadium_code']} {bet['race_number']}R status={bet['status']}")
            
            if not old_bets:
                print("削除対象がありません")
                return
            
            # 2. 削除確認
            print(f"\n{len(old_bets)}件を削除します...")
            
            # 3. 削除実行
            cur.execute("""
                DELETE FROM virtual_bets 
                WHERE race_date = %s AND strategy_type = '11r12r_win'
            """, (today,))
            deleted_count = cur.rowcount
            
            conn.commit()
            print(f"削除完了: {deleted_count}件")
            
            # 4. 削除後の確認
            cur.execute("""
                SELECT strategy_type, status, COUNT(*) as count
                FROM virtual_bets
                WHERE race_date = %s
                GROUP BY strategy_type, status
                ORDER BY strategy_type, status
            """, (today,))
            summary = cur.fetchall()
            print("\n=== 削除後の購入予定サマリー ===")
            for row in summary:
                print(f"  {row['strategy_type']} ({row['status']}): {row['count']}件")
            
    except Exception as e:
        print(f"エラー: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    delete_old_bets()

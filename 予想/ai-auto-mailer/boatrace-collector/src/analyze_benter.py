import os
import psycopg2
from datetime import datetime
import sys

# DB接続
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def debug_data():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            print("\n=== データ確認: 20260101 ===")
            cur.execute("""
                SELECT race_date, stadium_code, race_no, boat_no, rank, exhibition_time
                FROM historical_race_results
                WHERE race_date='20260101'
                AND stadium_code='01' -- 桐生など
                LIMIT 10
            """)
            rows = cur.fetchall()
            if not rows:
                print("データなし")
            for row in rows:
                print(row)

            print("\n=== 展示タイムがNULLの件数 ===")
            cur.execute("""
                SELECT COUNT(*) FROM historical_race_results
                WHERE race_date >= '20260101' AND exhibition_time IS NULL
            """)
            null_count = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*) FROM historical_race_results
                WHERE race_date >= '20260101'
            """)
            total_count = cur.fetchone()[0]

            print(f"NULL: {null_count} / {total_count}")

    finally:
        conn.close()

if __name__ == "__main__":
    debug_data()

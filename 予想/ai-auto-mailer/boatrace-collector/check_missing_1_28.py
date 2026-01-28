import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def check():
    conn = psycopg2.connect(DATABASE_URL)
    today = datetime.now(JST).strftime('%Y%m%d')
    print(f"Target Date: {today}")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 1/28の琵琶湖(11)の1号艇のデータを取得
        cur.execute("""
            SELECT race_no, boat_no, local_win_rate
            FROM historical_programs
            WHERE race_date = %s AND stadium_code = '11' AND boat_no = '1'
            ORDER BY race_no
        """, (today,))

        rows = cur.fetchall()
        print(f"Biwako (11) boat 1 entries: {len(rows)}")
        for row in rows:
            print(f"Race {row['race_no']} boat {row['boat_no']}: local_win_rate={row['local_win_rate']}")

        # 他の場も確認
        cur.execute("""
            SELECT stadium_code, COUNT(*)
            FROM historical_programs
            WHERE race_date = %s
            GROUP BY stadium_code
        """, (today,))
        print("\nStadium counts:")
        for row in cur.fetchall():
            print(f"Stadium {row['stadium_code']}: {row['count']} entries")

    conn.close()

if __name__ == "__main__":
    check()

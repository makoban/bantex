import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    database_url = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"
    if not database_url:
        print("DATABASE_URL not found")
        return

    conn = psycopg2.connect(database_url)

    target_date = '20260127'
    stadium_code = '09' # 津 (String)

    print(f"Checking data for Stadium {stadium_code} on {target_date}...")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if records exist
        cur.execute("""
            SELECT count(*) as count
            FROM historical_programs
            WHERE race_date = %s AND stadium_code = %s
        """, (target_date, stadium_code))
        count = cur.fetchone()['count']
        print(f"Total records: {count}")

        if count > 0:
            # Check for NULL win rates
            cur.execute("""
                SELECT count(*) as null_count
                FROM historical_programs
                WHERE race_date = %s
                AND stadium_code = %s
                AND local_win_rate IS NULL
            """, (target_date, stadium_code))
            null_count = cur.fetchone()['null_count']
            print(f"Records with NULL local_win_rate: {null_count}")

            # Show sample
            cur.execute("""
                SELECT race_no, boat_no, racer_name, local_win_rate
                FROM historical_programs
                WHERE race_date = %s AND stadium_code = %s
                ORDER BY race_no, boat_no
                LIMIT 5
            """, (target_date, stadium_code))
            print("\nSample Data:")
            for row in cur.fetchall():
                print(row)

    conn.close()

if __name__ == "__main__":
    main()

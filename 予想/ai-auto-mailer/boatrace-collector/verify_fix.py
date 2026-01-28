import psycopg2
from psycopg2.extras import RealDictCursor
import os

def main():
    database_url = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

    conn = psycopg2.connect(database_url)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    query = """
        SELECT COUNT(*) as valid_count
        FROM historical_programs
        WHERE race_date = '2026-01-27'
          AND stadium_code = '18'
          AND local_win_rate IS NOT NULL
    """
    cur.execute(query)
    result = cur.fetchone()
    valid_count = result['valid_count']

    print(f"Valid records for Stadium 18 (2026-01-27): {valid_count}")

    if valid_count > 0:
        print("SUCCESS: Data is being updated!")
    else:
        print("WAITING: No valid data yet.")

    conn.close()

if __name__ == "__main__":
    main()

import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(level=logging.INFO)

def main():
    database_url = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"
    conn = psycopg2.connect(database_url)

    # Check virtual_bets data sample
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        print("\n--- Virtual Bets Sample (Lost bets) ---")
        cur.execute("""
            SELECT id, status, bet_amount, return_amount, profit
            FROM virtual_bets
            WHERE status = 'lost'
            ORDER BY created_at DESC
            LIMIT 5
        """)
        for row in cur.fetchall():
            print(f"ID: {row['id']}, Status: {row['status']}, Profit: {row['profit']} (Type: {type(row['profit'])})")

        print("\n--- Column Types ---")
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'virtual_bets' AND column_name = 'profit'
        """)
        for row in cur.fetchall():
             print(f"Column: {row['column_name']}, Type: {row['data_type']}")

    conn.close()

if __name__ == "__main__":
    main()

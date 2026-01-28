import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from cron_jobs import fetch_today_programs

def main():
    # Hardcoded from check_payoffs.py
    database_url = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

    print("Running fetch_today_programs manually...")
    fetch_today_programs(database_url)
    print("Done.")

if __name__ == "__main__":
    main()

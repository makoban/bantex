import sys
import os
import requests
from bs4 import BeautifulSoup
import re
import psycopg2
from datetime import datetime, timezone, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# JST
JST = timezone(timedelta(hours=9))

def fix_tokuyama():
    # Hardcoded DB URL
    database_url = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

    stadium_code = 18 # Tokuyama

    now = datetime.now(JST)
    today = now.strftime('%Y%m%d')
    # Or force 20260127 if needed
    # today = '20260127'

    logger.info(f"Target Date: {today}, Stadium: {stadium_code}")

    conn = psycopg2.connect(database_url)
    conn.autocommit = True

    total_saved = 0

    try:
        for race_no in range(1, 13):
            logger.info(f"Fetching Race {race_no}...")
            url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={race_no}&jcd={stadium_code}&hd={today}"

            try:
                response = requests.get(url, timeout=10)
                if response.status_code != 200:
                    logger.warning(f"Status {response.status_code}")
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')
                tbodies = soup.find_all('tbody')

                if len(tbodies) < 7:
                    logger.warning("Not enough tbodies")
                    continue

                saved_count_race = 0
                for boat_idx, tbody in enumerate(tbodies[1:7], start=1):
                    rows = tbody.find_all('tr')
                    if not rows: continue

                    first_row = rows[0]
                    tds = first_row.find_all('td')
                    if len(tds) < 5: continue

                    boat_no = str(boat_idx)

                    # Racer Info
                    racer_no = None
                    racer_link = None
                    for td in tds[1:4]:
                        link = td.find('a')
                        if link:
                            href = link.get('href', '')
                            match = re.search(r'toban=(\d{4})', href)
                            if match:
                                racer_no = match.group(1)
                                racer_link = link
                                break

                    racer_name = racer_link.get_text(strip=True)[:10] if racer_link else None

                    # Rates
                    rate_text = ''
                    for td in tds[4:]:
                        rate_text += td.get_text(strip=True)

                    rates = re.findall(r'\d\.\d{2}', rate_text)

                    national_win_rate = float(rates[0]) if len(rates) > 0 else None
                    national_2nd_rate = float(rates[1]) if len(rates) > 1 else None
                    local_win_rate = float(rates[2]) if len(rates) > 2 else None
                    local_2nd_rate = float(rates[3]) if len(rates) > 3 else None

                    # Check if valid
                    if local_win_rate is None:
                        logger.warning(f"Race {race_no} Boat {boat_no}: Local Win Rate is None! Rates found: {rates}")

                    # Update DB
                    with conn.cursor() as cursor:
                         cursor.execute("""
                            INSERT INTO historical_programs
                            (race_date, stadium_code, race_no, boat_no, racer_no, racer_name,
                             national_win_rate, national_2nd_rate, local_win_rate, local_2nd_rate)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (race_date, stadium_code, race_no, boat_no)
                            DO UPDATE SET
                                racer_no = EXCLUDED.racer_no,
                                racer_name = EXCLUDED.racer_name,
                                national_win_rate = EXCLUDED.national_win_rate,
                                national_2nd_rate = EXCLUDED.national_2nd_rate,
                                local_win_rate = EXCLUDED.local_win_rate,
                                local_2nd_rate = EXCLUDED.local_2nd_rate
                        """, (
                            today, f"{stadium_code:02d}", f"{race_no:02d}", boat_no,
                            racer_no, racer_name,
                            national_win_rate, national_2nd_rate,
                            local_win_rate, local_2nd_rate
                        ))
                    saved_count_race += 1
                    total_saved += 1

                logger.info(f"Race {race_no}: Updated {saved_count_race} entries")

            except Exception as e:
                logger.error(f"Error race {race_no}: {e}")

    finally:
        conn.close()

    logger.info(f"Total entries updated: {total_saved}")

if __name__ == "__main__":
    fix_tokuyama()

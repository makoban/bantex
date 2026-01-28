import requests
from bs4 import BeautifulSoup
import re

def debug_scraping():
    stadium_code = 18 # Tokuyama
    race_no = 1
    today = '20260127'

    url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={race_no}&jcd={stadium_code}&hd={today}"
    print(f"URL: {url}")

    response = requests.get(url, timeout=15)
    if response.status_code != 200:
        print(f"Error: Status code {response.status_code}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    tbodies = soup.find_all('tbody')
    print(f"Found {len(tbodies)} tbodies")

    if len(tbodies) < 7:
        print("Not enough tbodies")
        return

    for boat_idx, tbody in enumerate(tbodies[1:7], start=1):
        print(f"\n--- Boat {boat_idx} ---")
        rows = tbody.find_all('tr')
        if not rows:
            continue

        first_row = rows[0]
        tds = first_row.find_all('td')
        print(f"Found {len(tds)} tds")

        # Check racer info
        racer_no = None
        for td in tds[1:4]:
            link = td.find('a')
            if link:
                href = link.get('href', '')
                match = re.search(r'toban=(\d{4})', href)
                if match:
                    racer_no = match.group(1)
                    print(f"Racer: {racer_no}")
                    break

        # Check rates
        rate_text = ''
        for i, td in enumerate(tds[4:]):
            text = td.get_text(strip=True)
            print(f"TD[{4+i}]: {text}")
            rate_text += text

        rates = re.findall(r'\d\.\d{2}', rate_text)
        print(f"Extracted rates: {rates}")

        national_win_rate = float(rates[0]) if len(rates) > 0 else None
        local_win_rate = float(rates[2]) if len(rates) > 2 else None

        print(f"National Win: {national_win_rate}")
        print(f"Local Win: {local_win_rate}")

if __name__ == "__main__":
    debug_scraping()

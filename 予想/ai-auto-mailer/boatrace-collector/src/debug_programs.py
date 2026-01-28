# -*- coding: utf-8 -*-
"""勝率抽出テスト"""
import requests
import re
from bs4 import BeautifulSoup

url = "https://www.boatrace.jp/owpc/pc/race/racelist?rno=4&jcd=05&hd=20260126"
print(f"URL: {url}")

response = requests.get(url, timeout=30)
soup = BeautifulSoup(response.text, 'html.parser')

# tbody[1]〜[6]が1〜6号艇
tbodies = soup.find_all('tbody')
print(f"tbody数: {len(tbodies)}")

for i, tbody in enumerate(tbodies[1:7], start=1):  # tbody[1]〜[6]
    rows = tbody.find_all('tr')
    if not rows:
        continue

    first_row = rows[0]
    tds = first_row.find_all('td')

    if len(tds) < 5:
        continue

    boat_no = tds[0].get_text(strip=True)

    # 登番を取得（リンクから）
    racer_link = tds[2].find('a')
    racer_no = None
    if racer_link:
        href = racer_link.get('href', '')
        match = re.search(r'toban=(\d{4})', href)
        if match:
            racer_no = match.group(1)

    # 勝率は複数のtdに分かれている or 結合されている
    # パターン: X.XX形式の数値を抽出
    rate_text = ''
    for td in tds[4:]:
        rate_text += td.get_text(strip=True)

    # X.XX形式（1桁.2桁）を全て抽出
    rates = re.findall(r'\d\.\d{2}', rate_text)

    # 通常順序: 全国勝率, 全国2連, 当地勝率, 当地2連
    national_win = rates[0] if len(rates) > 0 else None
    national_2nd = rates[1] if len(rates) > 1 else None
    local_win = rates[2] if len(rates) > 2 else None
    local_2nd = rates[3] if len(rates) > 3 else None

    print(f"{boat_no}号艇: 登番={racer_no}, 全国勝率={national_win}, 当地勝率={local_win}")

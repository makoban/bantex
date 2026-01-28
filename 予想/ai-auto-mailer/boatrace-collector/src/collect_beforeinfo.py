'''
直前情報・水面状況の収集スクリプト
展示タイム、チルト、部品交換、スタート展示、水面気象情報を取得します。
'''

import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
import logging
import psycopg2
from psycopg2.extras import execute_values

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 場コード一覧
STADIUM_CODES = {
    '01': '桐生', '02': '戸田', '03': '江戸川', '04': '平和島', '05': '多摩川',
    '06': '浜名湖', '07': '蒲郡', '08': '常滑', '09': '津', '10': '三国',
    '11': '琵琶湖', '12': '住之江', '13': '尼崎', '14': '鳴門', '15': '丸亀',
    '16': '児島', '17': '宮島', '18': '徳山', '19': '下関', '20': '若松',
    '21': '芦屋', '22': '福岡', '23': '唐津', '24': '大村'
}


def get_db_connection():
    """データベース接続を取得"""
    return psycopg2.connect(os.environ.get('DATABASE_URL'))


def create_tables(conn):
    """テーブルを作成"""
    with conn.cursor() as cur:
        # 直前情報テーブル
        cur.execute('''
            CREATE TABLE IF NOT EXISTS boatrace_beforeinfo (
                id SERIAL PRIMARY KEY,
                race_date DATE NOT NULL,
                stadium_code VARCHAR(2) NOT NULL,
                race_number INTEGER NOT NULL,
                waku INTEGER NOT NULL,
                racer_no VARCHAR(4),
                racer_name VARCHAR(20),
                weight DECIMAL(4,1),
                exhibition_time DECIMAL(4,2),
                tilt DECIMAL(3,1),
                propeller VARCHAR(10),
                parts_exchange TEXT,
                start_exhibition_course INTEGER,
                start_exhibition_st DECIMAL(4,2),
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(race_date, stadium_code, race_number, waku)
            )
        ''')
        
        # 水面気象情報テーブル
        cur.execute('''
            CREATE TABLE IF NOT EXISTS boatrace_weather (
                id SERIAL PRIMARY KEY,
                race_date DATE NOT NULL,
                stadium_code VARCHAR(2) NOT NULL,
                race_number INTEGER NOT NULL,
                temperature DECIMAL(4,1),
                weather VARCHAR(10),
                wind_direction VARCHAR(10),
                wind_speed INTEGER,
                water_temperature DECIMAL(4,1),
                wave_height INTEGER,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(race_date, stadium_code, race_number)
            )
        ''')
        
        # インデックス作成
        cur.execute('CREATE INDEX IF NOT EXISTS idx_beforeinfo_date ON boatrace_beforeinfo(race_date)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_beforeinfo_stadium ON boatrace_beforeinfo(stadium_code)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_weather_date ON boatrace_weather(race_date)')
        
        conn.commit()
        logger.info("テーブルを作成しました")


def parse_beforeinfo(html: str, race_date: date, stadium_code: str, race_number: int) -> tuple:
    """
    直前情報ページをパース
    
    Returns:
        (beforeinfo_list, weather_dict)
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    beforeinfo_list = []
    weather_dict = {}
    
    # 選手情報テーブルをパース
    table = soup.find('table', class_='is-w748')
    if table:
        rows = table.find_all('tr')
        current_waku = 0
        
        for row in rows:
            cells = row.find_all('td')
            if not cells:
                continue
            
            # 枠番を含む行を探す
            first_cell = cells[0].get_text(strip=True)
            if first_cell.isdigit() and 1 <= int(first_cell) <= 6:
                current_waku = int(first_cell)
                
                # 選手名
                racer_link = row.find('a')
                racer_name = racer_link.get_text(strip=True) if racer_link else ''
                
                # 登番を抽出（リンクから）
                racer_no = ''
                if racer_link and racer_link.get('href'):
                    match = re.search(r'toban=(\d+)', racer_link.get('href', ''))
                    if match:
                        racer_no = match.group(1)
                
                # 各セルの値を取得
                cell_texts = [c.get_text(strip=True) for c in cells]
                
                # 固定位置からデータを取得
                # ['1', '', '乙津　康志', '52.0kg', '6.78', '-0.5', '', '', 'R', '']
                weight = None
                exhibition_time = None
                tilt = None
                
                # 体重（4番目）
                if len(cell_texts) > 3 and 'kg' in cell_texts[3]:
                    try:
                        weight = float(cell_texts[3].replace('kg', ''))
                    except:
                        pass
                
                # 展示タイム（5番目）
                if len(cell_texts) > 4:
                    try:
                        exhibition_time = float(cell_texts[4])
                    except:
                        pass
                
                # チルト（6番目）
                if len(cell_texts) > 5:
                    try:
                        tilt = float(cell_texts[5])
                    except:
                        pass
                
                beforeinfo_list.append({
                    'race_date': race_date,
                    'stadium_code': stadium_code,
                    'race_number': race_number,
                    'waku': current_waku,
                    'racer_no': racer_no,
                    'racer_name': racer_name.replace('\u3000', ' '),
                    'weight': weight,
                    'exhibition_time': exhibition_time,
                    'tilt': tilt,
                    'propeller': '',
                    'parts_exchange': '',
                    'start_exhibition_course': None,
                    'start_exhibition_st': None
                })
    
    # スタート展示をパース
    st_tables = soup.find_all('table')
    for t in st_tables:
        if 'スタート展示' in t.get_text():
            rows = t.find_all('tr')
            for row in rows:
                text = row.get_text(strip=True)
                # "1.07" のようなパターンを探す
                match = re.match(r'^(\d)\.(\d{2})$', text)
                if match:
                    course = int(match.group(1))
                    st = float(f"0.{match.group(2)}")
                    
                    # 対応する選手を更新
                    for info in beforeinfo_list:
                        if info['waku'] == course:
                            info['start_exhibition_course'] = course
                            info['start_exhibition_st'] = st
                            break
            break
    
    # 水面気象情報をパース
    weather = soup.find('div', class_='weather1')
    if weather:
        weather_dict = {
            'race_date': race_date,
            'stadium_code': stadium_code,
            'race_number': race_number,
            'temperature': None,
            'weather': '',
            'wind_direction': '',
            'wind_speed': None,
            'water_temperature': None,
            'wave_height': None
        }
        
        # 気温
        temp_elem = weather.find('span', class_='weather1_bodyUnitLabelData')
        if temp_elem:
            match = re.search(r'([\d.]+)', temp_elem.get_text())
            if match:
                weather_dict['temperature'] = float(match.group(1))
        
        # 各項目を取得
        items = weather.find_all('div', class_='weather1_bodyUnitLabel')
        for item in items:
            title = item.find('span', class_='weather1_bodyUnitLabelTitle')
            data = item.find('span', class_='weather1_bodyUnitLabelData')
            if title and data:
                title_text = title.get_text(strip=True)
                data_text = data.get_text(strip=True)
                
                if '気温' in title_text:
                    match = re.search(r'([\d.]+)', data_text)
                    if match:
                        weather_dict['temperature'] = float(match.group(1))
                elif '風速' in title_text:
                    match = re.search(r'(\d+)', data_text)
                    if match:
                        weather_dict['wind_speed'] = int(match.group(1))
                elif '水温' in title_text:
                    match = re.search(r'([\d.]+)', data_text)
                    if match:
                        weather_dict['water_temperature'] = float(match.group(1))
                elif '波高' in title_text:
                    match = re.search(r'(\d+)', data_text)
                    if match:
                        weather_dict['wave_height'] = int(match.group(1))
        
        # 天候（画像から判定）
        weather_img = weather.find('img')
        if weather_img:
            alt = weather_img.get('alt', '')
            weather_dict['weather'] = alt
        
        # 風向（画像から判定）
        wind_img = weather.find('p', class_='weather1_bodyUnitImage')
        if wind_img:
            img = wind_img.find('img')
            if img:
                src = img.get('src', '')
                # 風向を画像ファイル名から判定
                if 'icon_wind' in src:
                    weather_dict['wind_direction'] = '不明'  # 画像から判定が必要
    
    return beforeinfo_list, weather_dict


def fetch_beforeinfo(race_date: date, stadium_code: str, race_number: int) -> tuple:
    """
    直前情報を取得
    
    Returns:
        (beforeinfo_list, weather_dict)
    """
    url = f"https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno={race_number}&jcd={stadium_code}&hd={race_date.strftime('%Y%m%d')}"
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return parse_beforeinfo(response.text, race_date, stadium_code, race_number)
    except Exception as e:
        logger.error(f"取得エラー: {url} - {e}")
    
    return [], {}


def save_to_db(conn, beforeinfo_list: list, weather_dict: dict):
    """データベースに保存"""
    with conn.cursor() as cur:
        # 直前情報を保存
        if beforeinfo_list:
            values = [(
                b['race_date'], b['stadium_code'], b['race_number'], b['waku'],
                b['racer_no'], b['racer_name'], b['weight'],
                b['exhibition_time'], b['tilt'], b['propeller'],
                b['parts_exchange'], b['start_exhibition_course'],
                b['start_exhibition_st']
            ) for b in beforeinfo_list]
            
            execute_values(cur, '''
                INSERT INTO boatrace_beforeinfo (
                    race_date, stadium_code, race_number, waku,
                    racer_no, racer_name, weight,
                    exhibition_time, tilt, propeller,
                    parts_exchange, start_exhibition_course,
                    start_exhibition_st
                ) VALUES %s
                ON CONFLICT (race_date, stadium_code, race_number, waku) DO UPDATE SET
                    exhibition_time = EXCLUDED.exhibition_time,
                    tilt = EXCLUDED.tilt,
                    start_exhibition_st = EXCLUDED.start_exhibition_st,
                    scraped_at = CURRENT_TIMESTAMP
            ''', values)
        
        # 水面気象情報を保存
        if weather_dict:
            cur.execute('''
                INSERT INTO boatrace_weather (
                    race_date, stadium_code, race_number,
                    temperature, weather, wind_direction,
                    wind_speed, water_temperature, wave_height
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (race_date, stadium_code, race_number) DO UPDATE SET
                    temperature = EXCLUDED.temperature,
                    weather = EXCLUDED.weather,
                    wind_speed = EXCLUDED.wind_speed,
                    water_temperature = EXCLUDED.water_temperature,
                    wave_height = EXCLUDED.wave_height,
                    scraped_at = CURRENT_TIMESTAMP
            ''', (
                weather_dict['race_date'], weather_dict['stadium_code'],
                weather_dict['race_number'], weather_dict['temperature'],
                weather_dict['weather'], weather_dict['wind_direction'],
                weather_dict['wind_speed'], weather_dict['water_temperature'],
                weather_dict['wave_height']
            ))
        
        conn.commit()


def collect_beforeinfo_for_race(race_date: date, stadium_code: str, race_number: int, conn=None):
    """
    指定レースの直前情報を収集してDBに保存
    """
    beforeinfo_list, weather_dict = fetch_beforeinfo(race_date, stadium_code, race_number)
    
    if beforeinfo_list:
        logger.info(f"取得成功: {STADIUM_CODES.get(stadium_code, stadium_code)} {race_number}R - {len(beforeinfo_list)}名")
        
        if conn:
            save_to_db(conn, beforeinfo_list, weather_dict)
            logger.info(f"DB保存完了")
    else:
        logger.warning(f"データなし: {STADIUM_CODES.get(stadium_code, stadium_code)} {race_number}R")
    
    return beforeinfo_list, weather_dict


def collect_all_beforeinfo(race_date: date = None):
    """
    指定日の全レースの直前情報を収集
    """
    if race_date is None:
        race_date = date.today()
    
    conn = get_db_connection()
    create_tables(conn)
    
    total_count = 0
    
    for stadium_code in STADIUM_CODES.keys():
        for race_number in range(1, 13):
            beforeinfo_list, _ = collect_beforeinfo_for_race(
                race_date, stadium_code, race_number, conn
            )
            total_count += len(beforeinfo_list)
    
    conn.close()
    logger.info(f"全収集完了: {total_count}件")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python collect_beforeinfo.py test              - テスト（桐生1R）")
        print("  python collect_beforeinfo.py all [YYYYMMDD]    - 全レース収集")
        print("  python collect_beforeinfo.py <JJ> <R> [YYYYMMDD] - 指定レース収集")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'test':
        # テスト
        race_date = date.today()
        beforeinfo, weather = fetch_beforeinfo(race_date, '01', 1)
        
        print("\n=== 直前情報 ===")
        for b in beforeinfo:
            print(f"{b['waku']}枠: {b['racer_name']} - 展示{b['exhibition_time']} チルト{b['tilt']} ST展示{b['start_exhibition_st']}")
        
        print("\n=== 水面気象情報 ===")
        print(f"気温: {weather.get('temperature')}℃")
        print(f"風速: {weather.get('wind_speed')}m")
        print(f"水温: {weather.get('water_temperature')}℃")
        print(f"波高: {weather.get('wave_height')}cm")
    
    elif command == 'all':
        race_date = datetime.strptime(sys.argv[2], '%Y%m%d').date() if len(sys.argv) > 2 else date.today()
        collect_all_beforeinfo(race_date)
    
    else:
        stadium_code = sys.argv[1]
        race_number = int(sys.argv[2])
        race_date = datetime.strptime(sys.argv[3], '%Y%m%d').date() if len(sys.argv) > 3 else date.today()
        
        conn = get_db_connection()
        create_tables(conn)
        collect_beforeinfo_for_race(race_date, stadium_code, race_number, conn)
        conn.close()

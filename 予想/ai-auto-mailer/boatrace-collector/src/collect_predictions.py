#!/usr/bin/env python3
"""
WEB予想サイトの予想情報収集スクリプト

対応サイト:
- 競艇日和（ボートレース日和）
- 公式記者予想

仕様:
- 各レースの出走表データを取得
- 予想に役立つ統計情報を収集
- 結果と照合して的中履歴を記録
"""

import requests
from bs4 import BeautifulSoup
import re
import os
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta
import time
import json

# 場コード
STADIUM_CODES = {
    1: "桐生", 2: "戸田", 3: "江戸川", 4: "平和島", 5: "多摩川", 6: "浜名湖",
    7: "蒲郡", 8: "常滑", 9: "津", 10: "三国", 11: "びわこ", 12: "住之江",
    13: "尼崎", 14: "鳴門", 15: "丸亀", 16: "児島", 17: "宮島", 18: "徳山",
    19: "下関", 20: "若松", 21: "芦屋", 22: "福岡", 23: "唐津", 24: "大村"
}

class KyoteiBiyoriCollector:
    """競艇日和からデータを収集するクラス"""
    
    BASE_URL = "https://kyoteibiyori.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_race_list(self, place_no: int, date: str) -> list:
        """レース一覧を取得"""
        url = f"{self.BASE_URL}/race_ichiran.php?place_no={place_no}&race_no=1&hiduke={date}"
        try:
            resp = self.session.get(url, timeout=30)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            races = []
            for i in range(1, 13):
                race_td = soup.find('td', {'id': f'race{i}'})
                if race_td:
                    races.append(i)
            return races
        except Exception as e:
            print(f"Error getting race list: {e}")
            return []
    
    def get_race_data(self, place_no: int, race_no: int, date: str) -> dict:
        """出走表データを取得"""
        url = f"{self.BASE_URL}/race_shusso.php?place_no={place_no}&race_no={race_no}&hiduke={date}&slider=0"
        try:
            resp = self.session.get(url, timeout=30)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            race_data = {
                'place_no': place_no,
                'place_name': STADIUM_CODES.get(place_no, ''),
                'race_no': race_no,
                'date': date,
                'racers': [],
                'scraped_at': datetime.now(JST).isoformat()
            }
            
            # 選手データを取得
            for waku in range(1, 7):
                racer = self._parse_racer_data(soup, waku)
                if racer:
                    race_data['racers'].append(racer)
            
            return race_data
        except Exception as e:
            print(f"Error getting race data: {e}")
            return None
    
    def _parse_racer_data(self, soup: BeautifulSoup, waku: int) -> dict:
        """選手データをパース"""
        try:
            # 選手名を取得（複数の方法を試す）
            racer_data = {'waku': waku}
            
            # テーブルから選手情報を取得
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 7:
                        # 基本情報行を探す
                        first_cell_text = cells[0].get_text(strip=True)
                        if '基本情報' in first_cell_text or '号艇' in first_cell_text:
                            continue
                        
                        # 選手名の行を探す
                        for i, cell in enumerate(cells):
                            cell_id = cell.get('id', '')
                            if cell_id and cell_id.isdigit() and len(cell_id) == 4:
                                # 登録番号を見つけた
                                racer_data['racer_no'] = cell_id
                                racer_data['name'] = cell.get_text(strip=True)
            
            return racer_data if 'racer_no' in racer_data else None
        except Exception as e:
            print(f"Error parsing racer data: {e}")
            return None
    
    def get_gachigachi_races(self, escape_rate: int = 70, miss_rate: int = 50) -> list:
        """ガチガチレース（堅いレース）を検索"""
        # 競艇日和のガチガチレース検索機能を利用
        url = f"{self.BASE_URL}/search_gachi.php?nigerate={escape_rate}&nogashirate={miss_rate}"
        try:
            resp = self.session.get(url, timeout=30)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            races = []
            # 検索結果をパース
            result_divs = soup.find_all('div', class_='race-result')
            for div in result_divs:
                race_info = self._parse_search_result(div)
                if race_info:
                    races.append(race_info)
            
            return races
        except Exception as e:
            print(f"Error searching gachigachi races: {e}")
            return []
    
    def get_ana_races(self, escape_rate: int = 40, sashi_makuri_rate: int = 30) -> list:
        """穴レース（荒れそうなレース）を検索"""
        url = f"{self.BASE_URL}/search_ana.php?nigerate={escape_rate}&sashimakurirate={sashi_makuri_rate}"
        try:
            resp = self.session.get(url, timeout=30)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            races = []
            result_divs = soup.find_all('div', class_='race-result')
            for div in result_divs:
                race_info = self._parse_search_result(div)
                if race_info:
                    races.append(race_info)
            
            return races
        except Exception as e:
            print(f"Error searching ana races: {e}")
            return []
    
    def get_stadium_rankings(self) -> dict:
        """場状況ランキングを取得"""
        url = self.BASE_URL
        try:
            resp = self.session.get(url, timeout=30)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            rankings = {
                'katai': [],      # 固い場
                'arete': [],      # 荒れている場
                'in_nige': [],    # イン逃げ率
                'manbune': []     # 万舟率
            }
            
            # ランキングテーブルをパース
            tables = soup.find_all('table')
            for table in tables:
                header = table.find('th')
                if header:
                    header_text = header.get_text(strip=True)
                    if '固い場' in header_text:
                        rankings['katai'] = self._parse_ranking_table(table)
                    elif '荒れている' in header_text:
                        rankings['arete'] = self._parse_ranking_table(table)
                    elif 'イン逃' in header_text:
                        rankings['in_nige'] = self._parse_ranking_table(table)
                    elif '万舟' in header_text:
                        rankings['manbune'] = self._parse_ranking_table(table)
            
            return rankings
        except Exception as e:
            print(f"Error getting stadium rankings: {e}")
            return {}
    
    def _parse_ranking_table(self, table) -> list:
        """ランキングテーブルをパース"""
        rankings = []
        rows = table.find_all('tr')[1:]  # ヘッダーをスキップ
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 4:
                rank_text = cells[0].get_text(strip=True)
                # ヘッダー行（「順」など）をスキップ
                if not rank_text.isdigit():
                    continue
                rankings.append({
                    'rank': int(rank_text),
                    'stadium': cells[1].get_text(strip=True),
                    'value': cells[2].get_text(strip=True),
                    'status': cells[3].get_text(strip=True)
                })
        return rankings
    
    def _parse_search_result(self, div) -> dict:
        """検索結果をパース"""
        try:
            links = div.find_all('a')
            for link in links:
                href = link.get('href', '')
                if 'race_shusso.php' in href:
                    # URLからパラメータを抽出
                    params = {}
                    for param in href.split('?')[1].split('&'):
                        key, value = param.split('=')
                        params[key] = value
                    return params
            return None
        except:
            return None


class OfficialPredictionCollector:
    """公式コンピューター予想を収集するクラス"""
    
    BASE_URL = "https://www.boatrace.jp"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_computer_prediction(self, stadium_code: str, race_no: int, date: str) -> dict:
        """コンピューター予想を取得"""
        url = f"{self.BASE_URL}/owpc/pc/race/pcexpect?rno={race_no}&jcd={stadium_code}&hd={date}"
        try:
            resp = self.session.get(url, timeout=30)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            prediction = {
                'stadium_code': stadium_code,
                'race_no': race_no,
                'date': date,
                'focus_2rentan': [],    # 2連単予想
                'focus_2renpuku': [],   # 2連複予想
                'focus_3rentan': [],    # 3連単予想
                'confidence_level': 0,  # 自信度 (1-5)
                'entry_prediction': [], # 進入予想
                'scraped_at': datetime.now(JST).isoformat()
            }
            
            # 予想フォーカスを取得
            number_sets = soup.find_all('div', class_='numberSet2_unit')
            for i, unit in enumerate(number_sets):
                rows = unit.find_all('div', class_='numberSet2_row')
                for row in rows:
                    numbers = row.find_all('span', class_='numberSet2_number')
                    if len(numbers) == 2:
                        # 2連予想
                        n1 = numbers[0].get_text(strip=True)
                        n2 = numbers[1].get_text(strip=True)
                        # =は2連複、-は2連単
                        row_text = row.get_text(strip=True)
                        if '=' in row_text:
                            prediction['focus_2renpuku'].append(f"{n1}={n2}")
                        else:
                            prediction['focus_2rentan'].append(f"{n1}-{n2}")
                    elif len(numbers) == 3:
                        # 3連予想
                        n1 = numbers[0].get_text(strip=True)
                        n2 = numbers[1].get_text(strip=True)
                        n3 = numbers[2].get_text(strip=True)
                        row_text = row.get_text(strip=True)
                        if '=' in row_text:
                            prediction['focus_3rentan'].append(f"{n1}={n2}-{n3}")
                        else:
                            prediction['focus_3rentan'].append(f"{n1}-{n2}-{n3}")
            
            # 自信度を取得
            confidence_elem = soup.find('p', class_=lambda x: x and 'state2_lv' in x)
            if confidence_elem:
                classes = confidence_elem.get('class', [])
                for cls in classes:
                    if cls.startswith('is-lv'):
                        try:
                            prediction['confidence_level'] = int(cls.replace('is-lv', ''))
                        except:
                            pass
            
            # 進入予想を取得
            boat_elem = soup.find('ul', class_='boat1_boats')
            if boat_elem:
                boats = boat_elem.find_all('li')
                for boat in boats:
                    img = boat.find('img')
                    if img and 'alt' in img.attrs:
                        prediction['entry_prediction'].append(img['alt'])
            
            return prediction
        except Exception as e:
            print(f"Error getting computer prediction: {e}")
            return None
    
    def get_all_races_prediction(self, stadium_code: str, date: str) -> list:
        """全レースのコンピューター予想を取得"""
        predictions = []
        for race_no in range(1, 13):
            pred = self.get_computer_prediction(stadium_code, race_no, date)
            if pred:
                predictions.append(pred)
            time.sleep(0.5)  # サーバー負荷軽減
        return predictions


class PredictionDatabase:
    """予想データをデータベースに保存するクラス"""
    
    def __init__(self):
        self.db_url = os.environ.get('DATABASE_URL')
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable is not set")
    
    def get_connection(self):
        """データベース接続を取得"""
        return psycopg2.connect(self.db_url)
    
    def create_tables(self):
        """テーブルを作成"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        # 予想情報テーブル
        cur.execute("""
            CREATE TABLE IF NOT EXISTS web_predictions (
                id SERIAL PRIMARY KEY,
                source VARCHAR(50) NOT NULL,
                race_date DATE NOT NULL,
                stadium_code VARCHAR(2) NOT NULL,
                race_no INTEGER NOT NULL,
                prediction_type VARCHAR(50),
                prediction_data JSONB,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source, race_date, stadium_code, race_no, prediction_type)
            )
        """)
        
        # 的中履歴テーブル
        cur.execute("""
            CREATE TABLE IF NOT EXISTS prediction_results (
                id SERIAL PRIMARY KEY,
                prediction_id INTEGER REFERENCES web_predictions(id),
                race_date DATE NOT NULL,
                stadium_code VARCHAR(2) NOT NULL,
                race_no INTEGER NOT NULL,
                predicted_combination VARCHAR(20),
                actual_result VARCHAR(20),
                is_hit BOOLEAN,
                odds_value DECIMAL(10, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 場状況履歴テーブル
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stadium_rankings_history (
                id SERIAL PRIMARY KEY,
                ranking_date DATE NOT NULL,
                ranking_type VARCHAR(20) NOT NULL,
                rank INTEGER NOT NULL,
                stadium_name VARCHAR(20) NOT NULL,
                value VARCHAR(50),
                status VARCHAR(50),
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ranking_date, ranking_type, rank)
            )
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        print("Tables created successfully")
    
    def save_prediction(self, source: str, race_date: str, stadium_code: str, 
                       race_no: int, prediction_type: str, prediction_data: dict):
        """予想データを保存"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO web_predictions 
            (source, race_date, stadium_code, race_no, prediction_type, prediction_data)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (source, race_date, stadium_code, race_no, prediction_type)
            DO UPDATE SET prediction_data = EXCLUDED.prediction_data,
                         scraped_at = CURRENT_TIMESTAMP
        """, (source, race_date, stadium_code, race_no, prediction_type, 
              json.dumps(prediction_data, ensure_ascii=False)))
        
        conn.commit()
        cur.close()
        conn.close()
    
    def save_stadium_rankings(self, rankings: dict, date: str):
        """場状況ランキングを保存"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        for ranking_type, items in rankings.items():
            for item in items:
                cur.execute("""
                    INSERT INTO stadium_rankings_history 
                    (ranking_date, ranking_type, rank, stadium_name, value, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ranking_date, ranking_type, rank)
                    DO UPDATE SET stadium_name = EXCLUDED.stadium_name,
                                 value = EXCLUDED.value,
                                 status = EXCLUDED.status,
                                 scraped_at = CURRENT_TIMESTAMP
                """, (date, ranking_type, item.get('rank', 0), 
                      item.get('stadium', ''), item.get('value', ''), 
                      item.get('status', '')))
        
        conn.commit()
        cur.close()
        conn.close()
    
    def check_prediction_result(self, prediction_id: int, actual_result: str, odds_value: float = None):
        """予想結果を確認して記録"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        # 予想データを取得
        cur.execute("""
            SELECT race_date, stadium_code, race_no, prediction_data
            FROM web_predictions WHERE id = %s
        """, (prediction_id,))
        
        row = cur.fetchone()
        if row:
            race_date, stadium_code, race_no, prediction_data = row
            predicted = prediction_data.get('predicted_combination', '')
            is_hit = predicted == actual_result
            
            cur.execute("""
                INSERT INTO prediction_results 
                (prediction_id, race_date, stadium_code, race_no, 
                 predicted_combination, actual_result, is_hit, odds_value)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (prediction_id, race_date, stadium_code, race_no,
                  predicted, actual_result, is_hit, odds_value))
            
            conn.commit()
        
        cur.close()
        conn.close()
    
    def check_all_predictions_for_race(self, race_date: str, stadium_code: str, race_no: int, 
                                       result_2rentan: str, result_2renpuku: str,
                                       odds_2rentan: float = None, odds_2renpuku: float = None):
        """特定レースの全予想を結果と照合"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        # 該当レースの予想を取得
        cur.execute("""
            SELECT id, source, prediction_type, prediction_data
            FROM web_predictions 
            WHERE race_date = %s AND stadium_code = %s AND race_no = %s
        """, (race_date, stadium_code, race_no))
        
        rows = cur.fetchall()
        results = []
        
        for row in rows:
            pred_id, source, pred_type, pred_data = row
            
            # 2連単予想の確認
            focus_2rentan = pred_data.get('focus_2rentan', [])
            for pred in focus_2rentan:
                is_hit = pred == result_2rentan
                cur.execute("""
                    INSERT INTO prediction_results 
                    (prediction_id, race_date, stadium_code, race_no, 
                     predicted_combination, actual_result, is_hit, odds_value)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (pred_id, race_date, stadium_code, race_no,
                      pred, result_2rentan, is_hit, odds_2rentan if is_hit else None))
                results.append({
                    'source': source,
                    'type': '2連単',
                    'predicted': pred,
                    'actual': result_2rentan,
                    'is_hit': is_hit
                })
            
            # 2連複予想の確認
            focus_2renpuku = pred_data.get('focus_2renpuku', [])
            for pred in focus_2renpuku:
                # 2連複は順序不問なので正規化して比較
                pred_normalized = '='.join(sorted(pred.split('=')))
                result_normalized = '='.join(sorted(result_2renpuku.split('=')))
                is_hit = pred_normalized == result_normalized
                cur.execute("""
                    INSERT INTO prediction_results 
                    (prediction_id, race_date, stadium_code, race_no, 
                     predicted_combination, actual_result, is_hit, odds_value)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (pred_id, race_date, stadium_code, race_no,
                      pred, result_2renpuku, is_hit, odds_2renpuku if is_hit else None))
                results.append({
                    'source': source,
                    'type': '2連複',
                    'predicted': pred,
                    'actual': result_2renpuku,
                    'is_hit': is_hit
                })
        
        conn.commit()
        cur.close()
        conn.close()
        return results
    
    def get_prediction_stats(self, source: str = None, days: int = 30) -> dict:
        """予想的中統計を取得"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        query = """
            SELECT 
                wp.source,
                COUNT(*) as total_predictions,
                SUM(CASE WHEN pr.is_hit THEN 1 ELSE 0 END) as hits,
                ROUND(SUM(CASE WHEN pr.is_hit THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as hit_rate,
                SUM(CASE WHEN pr.is_hit THEN pr.odds_value ELSE 0 END) as total_return
            FROM prediction_results pr
            JOIN web_predictions wp ON pr.prediction_id = wp.id
            WHERE pr.race_date >= CURRENT_DATE - INTERVAL '%s days'
        """
        
        if source:
            query += " AND wp.source = %s"
            query += " GROUP BY wp.source"
            cur.execute(query, (days, source))
        else:
            query += " GROUP BY wp.source"
            cur.execute(query, (days,))
        
        rows = cur.fetchall()
        stats = {}
        for row in rows:
            stats[row[0]] = {
                'total_predictions': row[1],
                'hits': row[2],
                'hit_rate': float(row[3]) if row[3] else 0,
                'total_return': float(row[4]) if row[4] else 0
            }
        
        cur.close()
        conn.close()
        return stats


def collect_today_data():
    """本日のデータを収集"""
    today = datetime.now(JST).strftime('%Y%m%d')
    
    # 競艇日和から収集
    kyotei = KyoteiBiyoriCollector()
    db = PredictionDatabase()
    
    # テーブル作成
    db.create_tables()
    
    # 場状況ランキングを取得・保存
    print("Collecting stadium rankings...")
    rankings = kyotei.get_stadium_rankings()
    if rankings:
        db.save_stadium_rankings(rankings, today)
        print(f"Saved rankings: {len(rankings)} types")
    
    # 各場のレースデータを収集
    for place_no in range(1, 25):
        print(f"Checking {STADIUM_CODES.get(place_no, place_no)}...")
        races = kyotei.get_race_list(place_no, today)
        
        if not races:
            continue
        
        print(f"  Found {len(races)} races")
        for race_no in races:
            race_data = kyotei.get_race_data(place_no, race_no, today)
            if race_data:
                db.save_prediction(
                    source='kyoteibiyori',
                    race_date=today,
                    stadium_code=str(place_no).zfill(2),
                    race_no=race_no,
                    prediction_type='race_data',
                    prediction_data=race_data
                )
            time.sleep(0.5)  # サーバー負荷軽減
    
    print("Collection completed")


def test_collection():
    """テスト収集"""
    today = datetime.now(JST).strftime('%Y%m%d')
    
    kyotei = KyoteiBiyoriCollector()
    
    # 場状況ランキングをテスト
    print("Testing stadium rankings...")
    rankings = kyotei.get_stadium_rankings()
    print(f"Rankings: {json.dumps(rankings, ensure_ascii=False, indent=2)}")
    
    # 桐生1Rのデータをテスト
    print("\nTesting race data (桐生 1R)...")
    race_data = kyotei.get_race_data(1, 1, today)
    print(f"Race data: {json.dumps(race_data, ensure_ascii=False, indent=2)}")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'test':
            test_collection()
        elif sys.argv[1] == 'collect':
            collect_today_data()
        else:
            print("Usage: python collect_predictions.py [test|collect]")
    else:
        test_collection()

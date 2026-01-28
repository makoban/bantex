'''
競走成績・番組表パーサー

データ形式:
- 競走成績 (k*.txt): レース結果、着順、払戻金
- 番組表 (b*.txt): 出走表、選手情報、モーター/ボート情報
'''

import os
import re
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 競艇場コード
STADIUM_CODES = {
    '桐生': '01', '戸田': '02', '江戸川': '03', '平和島': '04', '多摩川': '05',
    '浜名湖': '06', '蒲郡': '07', '常滑': '08', '津': '09', '三国': '10',
    'びわこ': '11', '琵琶湖': '11', '住之江': '12', '尼崎': '13', '鳴門': '14', '丸亀': '15',
    '児島': '16', '宮島': '17', '徳山': '18', '下関': '19', '若松': '20',
    '芦屋': '21', '福岡': '22', '唐津': '23', '大村': '24'
}

# 逆引き
STADIUM_NAMES = {v: k for k, v in STADIUM_CODES.items()}


class RaceResultParser:
    """競走成績パーサー"""
    
    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.environ.get('DATABASE_URL')
    
    def get_db_connection(self):
        """データベース接続を取得"""
        return psycopg2.connect(self.db_url)
    
    def create_tables(self, conn):
        """テーブルを作成"""
        with conn.cursor() as cur:
            # レース結果テーブル
            cur.execute('''
                CREATE TABLE IF NOT EXISTS boatrace_results (
                    id SERIAL PRIMARY KEY,
                    race_date DATE NOT NULL,
                    stadium_code VARCHAR(2) NOT NULL,
                    race_number INTEGER NOT NULL,
                    race_grade VARCHAR(20),
                    weather VARCHAR(10),
                    wind_direction VARCHAR(10),
                    wind_speed INTEGER,
                    wave_height INTEGER,
                    course_length INTEGER DEFAULT 1800,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(race_date, stadium_code, race_number)
                )
            ''')
            
            # 着順テーブル
            cur.execute('''
                CREATE TABLE IF NOT EXISTS boatrace_entries (
                    id SERIAL PRIMARY KEY,
                    race_date DATE NOT NULL,
                    stadium_code VARCHAR(2) NOT NULL,
                    race_number INTEGER NOT NULL,
                    boat_number INTEGER NOT NULL,
                    racer_no INTEGER NOT NULL,
                    racer_name VARCHAR(20),
                    motor_no INTEGER,
                    boat_no INTEGER,
                    exhibition_time DECIMAL(5,2),
                    start_course INTEGER,
                    start_timing DECIMAL(4,2),
                    race_time VARCHAR(10),
                    finish_order INTEGER,
                    decision_type VARCHAR(10),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(race_date, stadium_code, race_number, boat_number)
                )
            ''')
            
            # 払戻金テーブル
            cur.execute('''
                CREATE TABLE IF NOT EXISTS boatrace_payoffs (
                    id SERIAL PRIMARY KEY,
                    race_date DATE NOT NULL,
                    stadium_code VARCHAR(2) NOT NULL,
                    race_number INTEGER NOT NULL,
                    bet_type VARCHAR(10) NOT NULL,
                    combination VARCHAR(20) NOT NULL,
                    payout INTEGER NOT NULL,
                    popularity INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(race_date, stadium_code, race_number, bet_type, combination)
                )
            ''')
            
            # 番組表テーブル
            cur.execute('''
                CREATE TABLE IF NOT EXISTS boatrace_programs (
                    id SERIAL PRIMARY KEY,
                    race_date DATE NOT NULL,
                    stadium_code VARCHAR(2) NOT NULL,
                    race_number INTEGER NOT NULL,
                    boat_number INTEGER NOT NULL,
                    racer_no INTEGER NOT NULL,
                    racer_name VARCHAR(20),
                    age INTEGER,
                    branch VARCHAR(10),
                    weight INTEGER,
                    grade VARCHAR(5),
                    national_win_rate DECIMAL(4,2),
                    national_2rate DECIMAL(5,2),
                    local_win_rate DECIMAL(4,2),
                    local_2rate DECIMAL(5,2),
                    motor_no INTEGER,
                    motor_2rate DECIMAL(5,2),
                    boat_no INTEGER,
                    boat_2rate DECIMAL(5,2),
                    exhibition_order INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(race_date, stadium_code, race_number, boat_number)
                )
            ''')
            
            # インデックス作成
            cur.execute('CREATE INDEX IF NOT EXISTS idx_boatrace_results_date ON boatrace_results(race_date)')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_boatrace_entries_racer ON boatrace_entries(racer_no)')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_boatrace_payoffs_date ON boatrace_payoffs(race_date)')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_boatrace_programs_date ON boatrace_programs(race_date)')
            
            conn.commit()
            logger.info("テーブルを作成/確認しました")
    
    def parse_race_result_file(self, filepath: str) -> Dict:
        """競走成績ファイルをパース"""
        results = {
            'races': [],
            'entries': [],
            'payoffs': []
        }
        
        try:
            with open(filepath, 'rb') as f:
                content = f.read().decode('shift_jis', errors='replace')
        except Exception as e:
            logger.error(f"ファイル読み込みエラー: {filepath} - {e}")
            return results
        
        lines = content.split('\n')
        
        current_stadium = None
        current_date = None
        current_race = None
        race_info = {}
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 場名と日付を検出
            if '［成績］' in line:
                # 例: "大　村［成績］      1/ 3      ミッドナイトボートレ  第 1日"
                match = re.search(r'(.+?)［成績］\s+(\d+)/\s*(\d+)', line)
                if match:
                    stadium_name = match.group(1).replace('　', '').replace(' ', '').strip()
                    month = int(match.group(2))
                    day = int(match.group(3))
                    
                    # 年を推定（ファイル名から）
                    filename = os.path.basename(filepath)
                    year_match = re.search(r'k(\d{2})(\d{2})(\d{2})', filename)
                    if year_match:
                        year = 2000 + int(year_match.group(1))
                        current_date = date(year, month, day)
                    
                    current_stadium = STADIUM_CODES.get(stadium_name)
                    if not current_stadium:
                        logger.debug(f"場名が見つかりません: '{stadium_name}'")
                        # KBGN行から場コードを取得するフォールバック
                        # 前の行をチェック
                        if i > 0:
                            prev_line = lines[i-1]
                            kbgn_match = re.search(r'(\d{2})KBGN', prev_line)
                            if kbgn_match:
                                current_stadium = kbgn_match.group(1)
            
            # 払戻金行を検出
            if '[払戻金]' in line:
                i += 1
                while i < len(lines) and lines[i].strip():
                    payoff_line = lines[i]
                    # 例: "1R  1-3-5    2170    1-3-5    1060    1-3     290    1-3     250"
                    match = re.match(r'\s*(\d+)R\s+(.+)', payoff_line)
                    if match:
                        race_num = int(match.group(1))
                        payoff_data = match.group(2)
                        
                        # 払戻金をパース
                        payoffs = self._parse_payoff_line(payoff_data, current_date, current_stadium, race_num)
                        results['payoffs'].extend(payoffs)
                    i += 1
                continue
            
            # レース情報行を検出
            race_match = re.match(r'\s*(\d+)R\s+(\S+)\s+.*H(\d+)m\s+(\S+)\s+風\s+(\S+)\s+(\d+)m\s+波\s+(\d+)cm', line)
            if race_match:
                current_race = int(race_match.group(1))
                race_grade = race_match.group(2)
                course_length = int(race_match.group(3))
                weather = race_match.group(4)
                wind_direction = race_match.group(5)
                wind_speed = int(race_match.group(6))
                wave_height = int(race_match.group(7))
                
                race_info = {
                    'race_date': current_date,
                    'stadium_code': current_stadium,
                    'race_number': current_race,
                    'race_grade': race_grade,
                    'weather': weather,
                    'wind_direction': wind_direction,
                    'wind_speed': wind_speed,
                    'wave_height': wave_height,
                    'course_length': course_length
                }
                results['races'].append(race_info)
            
            # 着順行を検出
            # 例: "  01  1 4112 大久保　　信一郎 39   11  6.76   1    0.26     1.49.0"
            entry_match = re.match(r'\s*(\d{2})\s+(\d)\s+(\d{4})\s+(.+?)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+(\d)\s+([\d.]+)\s+([\d.]+|\. +\.)', line)
            if entry_match and current_race and current_stadium:
                finish_order = int(entry_match.group(1))
                boat_number = int(entry_match.group(2))
                racer_no = int(entry_match.group(3))
                racer_name = entry_match.group(4).replace('　', ' ').strip()
                motor_no = int(entry_match.group(5))
                boat_no = int(entry_match.group(6))
                exhibition_time = float(entry_match.group(7))
                start_course = int(entry_match.group(8))
                start_timing = float(entry_match.group(9))
                race_time = entry_match.group(10)
                
                # 決まり手を検出（行末）
                decision_type = None
                if '逃げ' in line:
                    decision_type = '逃げ'
                elif '差し' in line:
                    decision_type = '差し'
                elif 'まくり' in line:
                    decision_type = 'まくり'
                elif 'まくり差し' in line:
                    decision_type = 'まくり差し'
                elif '抜き' in line:
                    decision_type = '抜き'
                elif '恵まれ' in line:
                    decision_type = '恵まれ'
                
                entry = {
                    'race_date': current_date,
                    'stadium_code': current_stadium,
                    'race_number': current_race,
                    'boat_number': boat_number,
                    'racer_no': racer_no,
                    'racer_name': racer_name,
                    'motor_no': motor_no,
                    'boat_no': boat_no,
                    'exhibition_time': exhibition_time,
                    'start_course': start_course,
                    'start_timing': start_timing,
                    'race_time': race_time if race_time != '.  .' else None,
                    'finish_order': finish_order,
                    'decision_type': decision_type
                }
                results['entries'].append(entry)
            
            i += 1
        
        return results
    
    def _parse_payoff_line(self, data: str, race_date, stadium_code, race_number) -> List[Dict]:
        """払戻金行をパース"""
        payoffs = []
        
        # 3連単、3連複、2連単、2連複の順で並んでいる
        # 例: "1-3-5    2170    1-3-5    1060    1-3     290    1-3     250"
        patterns = [
            (r'(\d-\d-\d)\s+(\d+)', '3t'),  # 3連単
            (r'(\d-\d-\d)\s+(\d+)', '3f'),  # 3連複
            (r'(\d-\d)\s+(\d+)', '2t'),     # 2連単
            (r'(\d-\d)\s+(\d+)', '2f'),     # 2連複
        ]
        
        # 単純なパターンマッチング
        matches = re.findall(r'(\d-\d(?:-\d)?)\s+(\d+)', data)
        
        bet_types = ['3t', '3f', '2t', '2f']
        for i, (combination, payout) in enumerate(matches):
            if i < len(bet_types):
                payoffs.append({
                    'race_date': race_date,
                    'stadium_code': stadium_code,
                    'race_number': race_number,
                    'bet_type': bet_types[i],
                    'combination': combination,
                    'payout': int(payout),
                    'popularity': None
                })
        
        return payoffs
    
    def parse_program_file(self, filepath: str) -> List[Dict]:
        """番組表ファイルをパース"""
        programs = []
        
        try:
            with open(filepath, 'rb') as f:
                content = f.read().decode('shift_jis', errors='replace')
        except Exception as e:
            logger.error(f"ファイル読み込みエラー: {filepath} - {e}")
            return programs
        
        lines = content.split('\n')
        
        current_stadium = None
        current_date = None
        current_race = None
        
        # ファイル名から日付を取得
        filename = os.path.basename(filepath)
        date_match = re.search(r'b(\d{2})(\d{2})(\d{2})', filename)
        if date_match:
            year = 2000 + int(date_match.group(1))
            month = int(date_match.group(2))
            day = int(date_match.group(3))
            current_date = date(year, month, day)
        
        for i, line in enumerate(lines):
            # BBGN行から場コードを取得
            bbgn_match = re.search(r'(\d{2})BBGN', line)
            if bbgn_match:
                current_stadium = bbgn_match.group(1)
            
            # レース番号を検出（全角数字対応）
            race_match = re.match(r'[　\s]*[１２３４５６７８９０\d]+Ｒ', line)
            if race_match:
                # 全角数字を半角に変換
                race_str = race_match.group(0).strip()
                race_num_str = ''
                for c in race_str:
                    if c in '０１２３４５６７８９':
                        race_num_str += str('０１２３４５６７８９'.index(c))
                    elif c.isdigit():
                        race_num_str += c
                if race_num_str:
                    current_race = int(race_num_str)
            
            # 選手データ行を検出
            # 例: "1 4112大久保信45佐賀52B1 5.43 36.14 5.09 25.00 39 33.08 11 29.92              7"
            entry_match = re.match(
                r'(\d)\s+(\d{4})(.{2,8}?)(\d{2})(.{2})(\d{2})([AB]\d)\s+'
                r'([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+'
                r'(\d+)\s+([\d.]+)\s+(\d+)\s+([\d.]+)',
                line
            )
            if entry_match and current_race and current_stadium:
                boat_number = int(entry_match.group(1))
                racer_no = int(entry_match.group(2))
                racer_name = entry_match.group(3)
                age = int(entry_match.group(4))
                branch = entry_match.group(5)
                weight = int(entry_match.group(6))
                grade = entry_match.group(7)
                national_win_rate = float(entry_match.group(8))
                national_2rate = float(entry_match.group(9))
                local_win_rate = float(entry_match.group(10))
                local_2rate = float(entry_match.group(11))
                motor_no = int(entry_match.group(12))
                motor_2rate = float(entry_match.group(13))
                boat_no = int(entry_match.group(14))
                boat_2rate = float(entry_match.group(15))
                
                # 展示順位（行末の数字）
                exhibition_match = re.search(r'(\d+)\s*$', line)
                exhibition_order = int(exhibition_match.group(1)) if exhibition_match else None
                
                programs.append({
                    'race_date': current_date,
                    'stadium_code': current_stadium,
                    'race_number': current_race,
                    'boat_number': boat_number,
                    'racer_no': racer_no,
                    'racer_name': racer_name,
                    'age': age,
                    'branch': branch,
                    'weight': weight,
                    'grade': grade,
                    'national_win_rate': national_win_rate,
                    'national_2rate': national_2rate,
                    'local_win_rate': local_win_rate,
                    'local_2rate': local_2rate,
                    'motor_no': motor_no,
                    'motor_2rate': motor_2rate,
                    'boat_no': boat_no,
                    'boat_2rate': boat_2rate,
                    'exhibition_order': exhibition_order
                })
        
        return programs
    
    def save_race_results(self, conn, results: Dict):
        """レース結果をデータベースに保存"""
        with conn.cursor() as cur:
            # レース情報
            if results['races']:
                for race in results['races']:
                    if race['race_date'] and race['stadium_code']:
                        cur.execute('''
                            INSERT INTO boatrace_results (
                                race_date, stadium_code, race_number, race_grade,
                                weather, wind_direction, wind_speed, wave_height, course_length
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (race_date, stadium_code, race_number) DO UPDATE SET
                                race_grade = EXCLUDED.race_grade,
                                weather = EXCLUDED.weather,
                                wind_direction = EXCLUDED.wind_direction,
                                wind_speed = EXCLUDED.wind_speed,
                                wave_height = EXCLUDED.wave_height
                        ''', (
                            race['race_date'], race['stadium_code'], race['race_number'],
                            race['race_grade'], race['weather'], race['wind_direction'],
                            race['wind_speed'], race['wave_height'], race['course_length']
                        ))
            
            # 着順
            if results['entries']:
                for entry in results['entries']:
                    if entry['race_date'] and entry['stadium_code']:
                        cur.execute('''
                            INSERT INTO boatrace_entries (
                                race_date, stadium_code, race_number, boat_number,
                                racer_no, racer_name, motor_no, boat_no,
                                exhibition_time, start_course, start_timing,
                                race_time, finish_order, decision_type
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (race_date, stadium_code, race_number, boat_number) DO UPDATE SET
                                finish_order = EXCLUDED.finish_order,
                                race_time = EXCLUDED.race_time,
                                decision_type = EXCLUDED.decision_type
                        ''', (
                            entry['race_date'], entry['stadium_code'], entry['race_number'],
                            entry['boat_number'], entry['racer_no'], entry['racer_name'],
                            entry['motor_no'], entry['boat_no'], entry['exhibition_time'],
                            entry['start_course'], entry['start_timing'], entry['race_time'],
                            entry['finish_order'], entry['decision_type']
                        ))
            
            # 払戻金
            if results['payoffs']:
                for payoff in results['payoffs']:
                    if payoff['race_date'] and payoff['stadium_code']:
                        cur.execute('''
                            INSERT INTO boatrace_payoffs (
                                race_date, stadium_code, race_number,
                                bet_type, combination, payout, popularity
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (race_date, stadium_code, race_number, bet_type, combination) 
                            DO UPDATE SET payout = EXCLUDED.payout
                        ''', (
                            payoff['race_date'], payoff['stadium_code'], payoff['race_number'],
                            payoff['bet_type'], payoff['combination'], payoff['payout'],
                            payoff['popularity']
                        ))
            
            conn.commit()
    
    def save_programs(self, conn, programs: List[Dict]):
        """番組表をデータベースに保存"""
        with conn.cursor() as cur:
            for prog in programs:
                if prog['race_date'] and prog['stadium_code']:
                    cur.execute('''
                        INSERT INTO boatrace_programs (
                            race_date, stadium_code, race_number, boat_number,
                            racer_no, racer_name, age, branch, weight, grade,
                            national_win_rate, national_2rate, local_win_rate, local_2rate,
                            motor_no, motor_2rate, boat_no, boat_2rate, exhibition_order
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (race_date, stadium_code, race_number, boat_number) DO UPDATE SET
                            racer_no = EXCLUDED.racer_no,
                            exhibition_order = EXCLUDED.exhibition_order
                    ''', (
                        prog['race_date'], prog['stadium_code'], prog['race_number'],
                        prog['boat_number'], prog['racer_no'], prog['racer_name'],
                        prog['age'], prog['branch'], prog['weight'], prog['grade'],
                        prog['national_win_rate'], prog['national_2rate'],
                        prog['local_win_rate'], prog['local_2rate'],
                        prog['motor_no'], prog['motor_2rate'],
                        prog['boat_no'], prog['boat_2rate'],
                        prog['exhibition_order']
                    ))
            conn.commit()
    
    def import_all_data(self, data_dir: str):
        """全データをインポート"""
        conn = self.get_db_connection()
        self.create_tables(conn)
        
        # 競走成績をインポート
        results_dir = os.path.join(data_dir, 'race_results')
        if os.path.exists(results_dir):
            for root, dirs, files in os.walk(results_dir):
                for filename in sorted(files):
                    if filename.endswith('.txt') or filename.endswith('.TXT'):
                        filepath = os.path.join(root, filename)
                        logger.info(f"競走成績をパース中: {filename}")
                        results = self.parse_race_result_file(filepath)
                        self.save_race_results(conn, results)
                        logger.info(f"  レース: {len(results['races'])}, 着順: {len(results['entries'])}, 払戻: {len(results['payoffs'])}")
        
        # 番組表をインポート
        programs_dir = os.path.join(data_dir, 'programs')
        if os.path.exists(programs_dir):
            for root, dirs, files in os.walk(programs_dir):
                for filename in sorted(files):
                    if filename.endswith('.txt') or filename.endswith('.TXT'):
                        filepath = os.path.join(root, filename)
                        logger.info(f"番組表をパース中: {filename}")
                        programs = self.parse_program_file(filepath)
                        self.save_programs(conn, programs)
                        logger.info(f"  番組: {len(programs)}件")
        
        conn.close()
        logger.info("全データのインポートが完了しました")


def test_parser():
    """パーサーのテスト"""
    parser = RaceResultParser()
    
    # 競走成績をテスト
    result_file = '/home/ubuntu/ai-auto-mailer/boatrace-collector/data/race_results/202601/k260103.txt'
    if os.path.exists(result_file):
        print("=== 競走成績パース ===")
        results = parser.parse_race_result_file(result_file)
        print(f"レース数: {len(results['races'])}")
        print(f"着順数: {len(results['entries'])}")
        print(f"払戻数: {len(results['payoffs'])}")
        
        if results['races']:
            print(f"\n最初のレース: {results['races'][0]}")
        if results['entries']:
            print(f"\n最初の着順: {results['entries'][0]}")
        if results['payoffs']:
            print(f"\n最初の払戻: {results['payoffs'][0]}")
    
    # 番組表をテスト
    program_file = '/home/ubuntu/ai-auto-mailer/boatrace-collector/data/programs/202601/b260103.txt'
    if os.path.exists(program_file):
        print("\n=== 番組表パース ===")
        programs = parser.parse_program_file(program_file)
        print(f"番組数: {len(programs)}")
        
        if programs:
            print(f"\n最初の番組: {programs[0]}")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python parse_race_data.py test              # パーサーテスト")
        print("  python parse_race_data.py import <data_dir> # データインポート")
        sys.exit(1)
    
    if sys.argv[1] == 'test':
        test_parser()
    elif sys.argv[1] == 'import':
        data_dir = sys.argv[2] if len(sys.argv) > 2 else '/home/ubuntu/ai-auto-mailer/boatrace-collector/data'
        parser = RaceResultParser()
        parser.import_all_data(data_dir)

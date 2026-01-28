'''
レーサー期別成績データのパーサーとデータベースインポート機能
ファン手帳のテキストデータをパースしてPostgreSQLに取り込みます。
'''

import os
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import execute_values

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_racer_record(line: bytes) -> Optional[Dict]:
    """
    ファン手帳の1レコードをパース（バイト単位）
    
    Args:
        line: Shift_JISエンコードされた1行のバイト列
        
    Returns:
        パースされたレーサーデータの辞書、またはNone
    """
    try:
        if len(line) < 400:
            return None
        
        def decode_bytes(data, encoding='shift_jis'):
            return data.decode(encoding, errors='replace').strip()
        
        def decode_ascii(data):
            return data.decode('ascii', errors='replace').strip()
        
        def parse_int(s, default=0):
            s = s.strip()
            return int(s) if s.isdigit() else default
        
        def parse_rate(s, decimal_places=2):
            """勝率等の数値をパース（例: 0756 -> 7.56）"""
            s = s.strip()
            if not s.isdigit():
                return 0.0
            val = int(s)
            return val / (10 ** decimal_places)
        
        # 基本情報（バイト単位でパース）
        pos = 0
        racer = {
            'racer_no': decode_ascii(line[pos:pos+4]),  # 4バイト
        }
        pos += 4
        
        racer['name_kanji'] = decode_bytes(line[pos:pos+16])  # 16バイト
        pos += 16
        
        racer['name_kana'] = decode_bytes(line[pos:pos+15])  # 15バイト
        pos += 15
        
        racer['branch'] = decode_bytes(line[pos:pos+4])  # 4バイト
        pos += 4
        
        racer['rank'] = decode_bytes(line[pos:pos+2])  # 2バイト
        pos += 2
        
        racer['birth_era'] = decode_bytes(line[pos:pos+1])  # 1バイト
        pos += 1
        
        racer['birth_date_raw'] = decode_ascii(line[pos:pos+6])  # 6バイト
        pos += 6
        
        gender_str = decode_ascii(line[pos:pos+1])
        racer['gender'] = int(gender_str) if gender_str.isdigit() else None  # 1バイト
        pos += 1
        
        age_str = decode_ascii(line[pos:pos+2])
        racer['age'] = int(age_str) if age_str.isdigit() else None  # 2バイト
        pos += 2
        
        height_str = decode_ascii(line[pos:pos+3])
        racer['height'] = int(height_str) if height_str.isdigit() else None  # 3バイト
        pos += 3
        
        weight_str = decode_ascii(line[pos:pos+2])
        racer['weight'] = int(weight_str) if weight_str.isdigit() else None  # 2バイト
        pos += 2
        
        racer['blood_type'] = decode_bytes(line[pos:pos+2])  # 2バイト
        pos += 2
        
        # 成績情報
        racer['win_rate'] = parse_rate(decode_ascii(line[pos:pos+4]), 2)  # 4バイト
        pos += 4
        
        racer['place_rate'] = parse_rate(decode_ascii(line[pos:pos+4]), 1)  # 4バイト
        pos += 4
        
        racer['first_count'] = parse_int(decode_ascii(line[pos:pos+3]))  # 3バイト
        pos += 3
        
        racer['second_count'] = parse_int(decode_ascii(line[pos:pos+3]))  # 3バイト
        pos += 3
        
        racer['race_count'] = parse_int(decode_ascii(line[pos:pos+3]))  # 3バイト
        pos += 3
        
        racer['final_count'] = parse_int(decode_ascii(line[pos:pos+2]))  # 2バイト
        pos += 2
        
        racer['win_count'] = parse_int(decode_ascii(line[pos:pos+2]))  # 2バイト
        pos += 2
        
        racer['avg_start_timing'] = parse_rate(decode_ascii(line[pos:pos+3]), 2)  # 3バイト
        pos += 3
        
        # コース別成績（1〜6コース、各13バイト）
        for course in range(1, 7):
            prefix = f'course{course}_'
            racer[prefix + 'entry_count'] = parse_int(decode_ascii(line[pos:pos+3]))
            pos += 3
            racer[prefix + 'place_rate'] = parse_rate(decode_ascii(line[pos:pos+4]), 1)
            pos += 4
            racer[prefix + 'avg_st'] = parse_rate(decode_ascii(line[pos:pos+3]), 2)
            pos += 3
            racer[prefix + 'avg_st_rank'] = parse_rate(decode_ascii(line[pos:pos+3]), 2)
            pos += 3
        
        # 期別情報
        racer['prev_rank'] = decode_bytes(line[pos:pos+2])
        pos += 2
        racer['prev2_rank'] = decode_bytes(line[pos:pos+2])
        pos += 2
        racer['prev3_rank'] = decode_bytes(line[pos:pos+2])
        pos += 2
        racer['prev_ability_index'] = parse_rate(decode_ascii(line[pos:pos+4]), 2)
        pos += 4
        racer['current_ability_index'] = parse_rate(decode_ascii(line[pos:pos+4]), 2)
        pos += 4
        racer['data_year'] = parse_int(decode_ascii(line[pos:pos+4]))
        pos += 4
        racer['data_period'] = parse_int(decode_ascii(line[pos:pos+1]))
        pos += 1
        racer['calc_start_date'] = decode_ascii(line[pos:pos+8])
        pos += 8
        racer['calc_end_date'] = decode_ascii(line[pos:pos+8])
        pos += 8
        racer['training_period'] = parse_int(decode_ascii(line[pos:pos+3]))
        pos += 3
        
        # コース別着順詳細（1〜6コース、各34バイト）
        for course in range(1, 7):
            prefix = f'course{course}_'
            racer[prefix + 'rank1'] = parse_int(decode_ascii(line[pos:pos+3]))
            pos += 3
            racer[prefix + 'rank2'] = parse_int(decode_ascii(line[pos:pos+3]))
            pos += 3
            racer[prefix + 'rank3'] = parse_int(decode_ascii(line[pos:pos+3]))
            pos += 3
            racer[prefix + 'rank4'] = parse_int(decode_ascii(line[pos:pos+3]))
            pos += 3
            racer[prefix + 'rank5'] = parse_int(decode_ascii(line[pos:pos+3]))
            pos += 3
            racer[prefix + 'rank6'] = parse_int(decode_ascii(line[pos:pos+3]))
            pos += 3
            racer[prefix + 'flying'] = parse_int(decode_ascii(line[pos:pos+2]))
            pos += 2
            racer[prefix + 'late0'] = parse_int(decode_ascii(line[pos:pos+2]))
            pos += 2
            racer[prefix + 'late1'] = parse_int(decode_ascii(line[pos:pos+2]))
            pos += 2
            racer[prefix + 'absent0'] = parse_int(decode_ascii(line[pos:pos+2]))
            pos += 2
            racer[prefix + 'absent1'] = parse_int(decode_ascii(line[pos:pos+2]))
            pos += 2
            racer[prefix + 'disq0'] = parse_int(decode_ascii(line[pos:pos+2]))
            pos += 2
            racer[prefix + 'disq1'] = parse_int(decode_ascii(line[pos:pos+2]))
            pos += 2
            racer[prefix + 'disq2'] = parse_int(decode_ascii(line[pos:pos+2]))
            pos += 2
        
        # コースなし情報
        racer['no_course_late0'] = parse_int(decode_ascii(line[pos:pos+2]))
        pos += 2
        racer['no_course_late1'] = parse_int(decode_ascii(line[pos:pos+2]))
        pos += 2
        racer['no_course_absent0'] = parse_int(decode_ascii(line[pos:pos+2]))
        pos += 2
        racer['no_course_absent1'] = parse_int(decode_ascii(line[pos:pos+2]))
        pos += 2
        
        # 出身地
        if len(line) > pos:
            racer['birthplace'] = decode_bytes(line[pos:pos+6])
        else:
            racer['birthplace'] = ''
        
        return racer
        
    except Exception as e:
        logger.error(f"パースエラー: {e}")
        return None


def parse_fan_handbook_file(filepath: str) -> List[Dict]:
    """
    ファン手帳ファイル全体をパース
    
    Args:
        filepath: ファン手帳テキストファイルのパス
        
    Returns:
        レーサーデータのリスト
    """
    racers = []
    
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
        
        # 改行で分割（CRLF対応）
        lines = content.split(b'\r\n')
        if len(lines) <= 1:
            lines = content.split(b'\n')
        
        for line in lines:
            if len(line) < 100:
                continue
            
            racer = parse_racer_record(line)
            if racer and racer['racer_no'].isdigit():
                racers.append(racer)
        
        logger.info(f"パース完了: {len(racers)} 件のレーサーデータ")
        return racers
        
    except Exception as e:
        logger.error(f"ファイル読み込みエラー: {filepath} - {e}")
        return []


def get_db_connection(retries=3, delay=5):
    """データベース接続を取得（リトライ機能付き）"""
    import time
    for attempt in range(retries):
        try:
            return psycopg2.connect(os.environ.get('DATABASE_URL'))
        except psycopg2.OperationalError as e:
            if attempt < retries - 1:
                logger.warning(f"接続失敗、{delay}秒後にリトライ... ({attempt + 1}/{retries})")
                time.sleep(delay)
            else:
                raise e


def create_racer_table(conn):
    """レーサーテーブルを作成"""
    with conn.cursor() as cur:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS racer_period_stats (
                id SERIAL PRIMARY KEY,
                racer_no VARCHAR(4) NOT NULL,
                data_year INTEGER NOT NULL,
                data_period INTEGER NOT NULL,
                name_kanji VARCHAR(20),
                name_kana VARCHAR(20),
                branch VARCHAR(10),
                rank VARCHAR(2),
                birth_era VARCHAR(1),
                birth_date_raw VARCHAR(6),
                gender INTEGER,
                age INTEGER,
                height INTEGER,
                weight INTEGER,
                blood_type VARCHAR(2),
                win_rate DECIMAL(5,2),
                place_rate DECIMAL(5,1),
                first_count INTEGER,
                second_count INTEGER,
                race_count INTEGER,
                final_count INTEGER,
                win_count INTEGER,
                avg_start_timing DECIMAL(4,2),
                prev_rank VARCHAR(2),
                prev2_rank VARCHAR(2),
                prev3_rank VARCHAR(2),
                prev_ability_index DECIMAL(5,2),
                current_ability_index DECIMAL(5,2),
                calc_start_date VARCHAR(8),
                calc_end_date VARCHAR(8),
                training_period INTEGER,
                birthplace VARCHAR(10),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(racer_no, data_year, data_period)
            )
        ''')
        
        # コース別成績テーブル
        cur.execute('''
            CREATE TABLE IF NOT EXISTS racer_period_course_stats (
                id SERIAL PRIMARY KEY,
                racer_no VARCHAR(4) NOT NULL,
                data_year INTEGER NOT NULL,
                data_period INTEGER NOT NULL,
                course INTEGER NOT NULL,
                entry_count INTEGER,
                place_rate DECIMAL(5,1),
                avg_st DECIMAL(4,2),
                avg_st_rank DECIMAL(4,2),
                rank1 INTEGER,
                rank2 INTEGER,
                rank3 INTEGER,
                rank4 INTEGER,
                rank5 INTEGER,
                rank6 INTEGER,
                flying INTEGER,
                late0 INTEGER,
                late1 INTEGER,
                absent0 INTEGER,
                absent1 INTEGER,
                disq0 INTEGER,
                disq1 INTEGER,
                disq2 INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(racer_no, data_year, data_period, course)
            )
        ''')
        
        # インデックス作成
        cur.execute('CREATE INDEX IF NOT EXISTS idx_racer_period_stats_racer_no ON racer_period_stats(racer_no)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_racer_period_stats_year_period ON racer_period_stats(data_year, data_period)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_racer_period_course_stats_racer_no ON racer_period_course_stats(racer_no)')
        
        conn.commit()
        logger.info("レーサーテーブルを作成しました")


def import_racers_to_db(racers: List[Dict], conn):
    """
    レーサーデータをデータベースにインポート
    
    Args:
        racers: レーサーデータのリスト
        conn: データベース接続
    """
    if not racers:
        return
    
    with conn.cursor() as cur:
        # メインテーブルへの挿入
        racer_values = []
        for r in racers:
            racer_values.append((
                r['racer_no'], r['data_year'], r['data_period'],
                r['name_kanji'], r['name_kana'], r['branch'], r['rank'],
                r['birth_era'], r['birth_date_raw'], r['gender'],
                r['age'], r['height'], r['weight'], r['blood_type'],
                r['win_rate'], r['place_rate'], r['first_count'],
                r['second_count'], r['race_count'], r['final_count'],
                r['win_count'], r['avg_start_timing'],
                r['prev_rank'], r['prev2_rank'], r['prev3_rank'],
                r['prev_ability_index'], r['current_ability_index'],
                r['calc_start_date'], r['calc_end_date'],
                r['training_period'], r.get('birthplace', '')
            ))
        
        execute_values(cur, '''
            INSERT INTO racer_period_stats (
                racer_no, data_year, data_period,
                name_kanji, name_kana, branch, rank,
                birth_era, birth_date_raw, gender,
                age, height, weight, blood_type,
                win_rate, place_rate, first_count,
                second_count, race_count, final_count,
                win_count, avg_start_timing,
                prev_rank, prev2_rank, prev3_rank,
                prev_ability_index, current_ability_index,
                calc_start_date, calc_end_date,
                training_period, birthplace
            ) VALUES %s
            ON CONFLICT (racer_no, data_year, data_period) DO UPDATE SET
                name_kanji = EXCLUDED.name_kanji,
                name_kana = EXCLUDED.name_kana,
                branch = EXCLUDED.branch,
                rank = EXCLUDED.rank,
                win_rate = EXCLUDED.win_rate,
                place_rate = EXCLUDED.place_rate,
                first_count = EXCLUDED.first_count,
                second_count = EXCLUDED.second_count,
                race_count = EXCLUDED.race_count,
                final_count = EXCLUDED.final_count,
                win_count = EXCLUDED.win_count,
                avg_start_timing = EXCLUDED.avg_start_timing
        ''', racer_values)
        
        # コース別成績テーブルへの挿入
        course_values = []
        for r in racers:
            for course in range(1, 7):
                prefix = f'course{course}_'
                course_values.append((
                    r['racer_no'], r['data_year'], r['data_period'], course,
                    r[prefix + 'entry_count'], r[prefix + 'place_rate'],
                    r[prefix + 'avg_st'], r[prefix + 'avg_st_rank'],
                    r[prefix + 'rank1'], r[prefix + 'rank2'],
                    r[prefix + 'rank3'], r[prefix + 'rank4'],
                    r[prefix + 'rank5'], r[prefix + 'rank6'],
                    r[prefix + 'flying'], r[prefix + 'late0'],
                    r[prefix + 'late1'], r[prefix + 'absent0'],
                    r[prefix + 'absent1'], r[prefix + 'disq0'],
                    r[prefix + 'disq1'], r[prefix + 'disq2']
                ))
        
        execute_values(cur, '''
            INSERT INTO racer_period_course_stats (
                racer_no, data_year, data_period, course,
                entry_count, place_rate, avg_st, avg_st_rank,
                rank1, rank2, rank3, rank4, rank5, rank6,
                flying, late0, late1, absent0, absent1,
                disq0, disq1, disq2
            ) VALUES %s
            ON CONFLICT (racer_no, data_year, data_period, course) DO UPDATE SET
                entry_count = EXCLUDED.entry_count,
                place_rate = EXCLUDED.place_rate,
                avg_st = EXCLUDED.avg_st,
                avg_st_rank = EXCLUDED.avg_st_rank,
                rank1 = EXCLUDED.rank1,
                rank2 = EXCLUDED.rank2,
                rank3 = EXCLUDED.rank3,
                rank4 = EXCLUDED.rank4,
                rank5 = EXCLUDED.rank5,
                rank6 = EXCLUDED.rank6
        ''', course_values)
        
        conn.commit()
        logger.info(f"データベースにインポート完了: {len(racers)} 件")


def import_fan_handbook(filepath: str):
    """
    ファン手帳ファイルをパースしてデータベースにインポート
    
    Args:
        filepath: ファン手帳テキストファイルのパス
    """
    racers = parse_fan_handbook_file(filepath)
    
    if not racers:
        logger.warning("インポートするデータがありません")
        return
    
    conn = get_db_connection()
    try:
        create_racer_table(conn)
        import_racers_to_db(racers, conn)
    finally:
        conn.close()


def get_imported_periods(conn) -> set:
    """既にインポート済みの期間を取得"""
    with conn.cursor() as cur:
        cur.execute('SELECT DISTINCT data_year, data_period FROM racer_period_stats')
        return {(row[0], row[1]) for row in cur.fetchall()}


def import_all_fan_handbooks(data_dir: str, resume: bool = True):
    """
    指定ディレクトリ内の全ファン手帳ファイルをインポート
    
    Args:
        data_dir: ファン手帳データが格納されたディレクトリ
        resume: Trueの場合、既にインポート済みの期間をスキップ
    """
    import glob
    import time
    
    files = glob.glob(os.path.join(data_dir, '**', '*.txt'), recursive=True)
    logger.info(f"インポート対象: {len(files)} ファイル")
    
    # 既にインポート済みの期間を取得
    imported_periods = set()
    if resume:
        try:
            conn = get_db_connection()
            imported_periods = get_imported_periods(conn)
            conn.close()
            logger.info(f"インポート済み: {len(imported_periods)} 期間")
        except Exception as e:
            logger.warning(f"インポート済み期間の取得に失敗: {e}")
    
    for filepath in sorted(files):
        # ファイル名から期間を抽出（例: fan0504 -> 2005年前期）
        filename = os.path.basename(os.path.dirname(filepath))
        match = re.match(r'fan(\d{2})(\d{2})', filename)
        if match:
            year = 2000 + int(match.group(1))
            period = 1 if match.group(2) == '04' else 2
            
            if (year, period) in imported_periods:
                logger.info(f"スキップ（インポート済み）: {filepath}")
                continue
        
        logger.info(f"処理中: {filepath}")
        try:
            import_fan_handbook(filepath)
            time.sleep(1)  # DB負荷軽減のためのウェイト
        except Exception as e:
            logger.error(f"インポートエラー: {filepath} - {e}")
            time.sleep(5)  # エラー時は長めに待機
            continue


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python import_racer_data.py <filepath>  - 単一ファイルをインポート")
        print("  python import_racer_data.py --all <dir> - ディレクトリ内の全ファイルをインポート")
        sys.exit(1)
    
    if sys.argv[1] == '--all':
        data_dir = sys.argv[2] if len(sys.argv) > 2 else 'data/racer_kibetsu_extracted'
        import_all_fan_handbooks(data_dir)
    else:
        import_fan_handbook(sys.argv[1])

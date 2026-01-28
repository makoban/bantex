#!/usr/bin/env python3
"""
データベースの現状を確認するスクリプト
"""
import psycopg2
from psycopg2 import sql

# Render PostgreSQLの接続情報（仕様書より）
DB_CONFIG = {
    'host': 'dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com',
    'database': 'kokotomo_staging',
    'user': 'kokotomo_staging_user',
    'password': 'lLhHXb4LgvJRPLhxNDjfKVzOWuZWlXNE',
    'sslmode': 'require'
}

def check_database():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print("=" * 60)
        print("データベース接続成功")
        print("=" * 60)
        
        # テーブル一覧とレコード数を取得
        cur.execute("""
            SELECT 
                table_name
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cur.fetchall()
        
        print("\n【テーブル一覧とレコード数】")
        print("-" * 60)
        
        for (table_name,) in tables:
            try:
                cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
                count = cur.fetchone()[0]
                print(f"{table_name}: {count:,} 件")
            except Exception as e:
                print(f"{table_name}: エラー - {e}")
        
        # historical_programsのカラム確認
        print("\n【historical_programs テーブルのカラム】")
        print("-" * 60)
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'historical_programs'
            ORDER BY ordinal_position;
        """)
        for col_name, data_type in cur.fetchall():
            print(f"  {col_name}: {data_type}")
        
        # historical_race_resultsのカラム確認
        print("\n【historical_race_results テーブルのカラム】")
        print("-" * 60)
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'historical_race_results'
            ORDER BY ordinal_position;
        """)
        for col_name, data_type in cur.fetchall():
            print(f"  {col_name}: {data_type}")
        
        # historical_payoffsのカラム確認
        print("\n【historical_payoffs テーブルのカラム】")
        print("-" * 60)
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'historical_payoffs'
            ORDER BY ordinal_position;
        """)
        for col_name, data_type in cur.fetchall():
            print(f"  {col_name}: {data_type}")
        
        # データ範囲の確認
        print("\n【データ範囲】")
        print("-" * 60)
        
        cur.execute("SELECT MIN(race_date), MAX(race_date) FROM historical_programs")
        min_date, max_date = cur.fetchone()
        print(f"historical_programs: {min_date} 〜 {max_date}")
        
        cur.execute("SELECT MIN(race_date), MAX(race_date) FROM historical_race_results")
        min_date, max_date = cur.fetchone()
        print(f"historical_race_results: {min_date} 〜 {max_date}")
        
        cur.execute("SELECT MIN(race_date), MAX(race_date) FROM historical_payoffs")
        min_date, max_date = cur.fetchone()
        print(f"historical_payoffs: {min_date} 〜 {max_date}")
        
        # オッズデータの確認
        print("\n【オッズ関連テーブル】")
        print("-" * 60)
        for table_name in ['odds_data', 'realtime_odds', 'odds']:
            try:
                cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
                count = cur.fetchone()[0]
                print(f"{table_name}: {count:,} 件")
            except:
                print(f"{table_name}: テーブルなし")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    check_database()

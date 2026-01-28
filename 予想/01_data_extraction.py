#!/usr/bin/env python3
"""
Benterモデル構築 - Step 1: データ抽出
競艇のファンダメンタルモデル構築に必要なデータを抽出する
"""
import psycopg2
import pandas as pd
from datetime import datetime

# データベース接続情報
DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def get_connection():
    """データベース接続を取得"""
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def check_tables():
    """テーブル構造とデータ量を確認"""
    conn = get_connection()
    cur = conn.cursor()
    
    print("=" * 60)
    print("データベース接続成功")
    print("=" * 60)
    
    # テーブル一覧
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cur.fetchall()]
    
    print("\n【テーブル一覧とレコード数】")
    print("-" * 60)
    
    for table_name in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cur.fetchone()[0]
            print(f"{table_name}: {count:,} 件")
        except Exception as e:
            print(f"{table_name}: エラー - {e}")
    
    cur.close()
    conn.close()

def get_historical_programs_schema():
    """historical_programsテーブルのスキーマを確認"""
    conn = get_connection()
    cur = conn.cursor()
    
    print("\n【historical_programs テーブルのカラム】")
    print("-" * 60)
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'historical_programs'
        ORDER BY ordinal_position;
    """)
    columns = cur.fetchall()
    for col_name, data_type in columns:
        print(f"  {col_name}: {data_type}")
    
    cur.close()
    conn.close()
    return [col[0] for col in columns]

def get_historical_results_schema():
    """historical_race_resultsテーブルのスキーマを確認"""
    conn = get_connection()
    cur = conn.cursor()
    
    print("\n【historical_race_results テーブルのカラム】")
    print("-" * 60)
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'historical_race_results'
        ORDER BY ordinal_position;
    """)
    columns = cur.fetchall()
    for col_name, data_type in columns:
        print(f"  {col_name}: {data_type}")
    
    cur.close()
    conn.close()
    return [col[0] for col in columns]

def get_sample_data():
    """サンプルデータを取得して構造を確認"""
    conn = get_connection()
    
    print("\n【historical_programs サンプルデータ（5件）】")
    print("-" * 60)
    df_programs = pd.read_sql("SELECT * FROM historical_programs LIMIT 5", conn)
    print(df_programs.to_string())
    
    print("\n【historical_race_results サンプルデータ（5件）】")
    print("-" * 60)
    df_results = pd.read_sql("SELECT * FROM historical_race_results LIMIT 5", conn)
    print(df_results.to_string())
    
    conn.close()

def get_data_range():
    """データの範囲を確認"""
    conn = get_connection()
    cur = conn.cursor()
    
    print("\n【データ範囲】")
    print("-" * 60)
    
    cur.execute("SELECT MIN(race_date), MAX(race_date), COUNT(*) FROM historical_programs")
    min_date, max_date, count = cur.fetchone()
    print(f"historical_programs: {min_date} 〜 {max_date} ({count:,}件)")
    
    cur.execute("SELECT MIN(race_date), MAX(race_date), COUNT(*) FROM historical_race_results")
    min_date, max_date, count = cur.fetchone()
    print(f"historical_race_results: {min_date} 〜 {max_date} ({count:,}件)")
    
    try:
        cur.execute("SELECT MIN(race_date), MAX(race_date), COUNT(*) FROM historical_payoffs")
        min_date, max_date, count = cur.fetchone()
        print(f"historical_payoffs: {min_date} 〜 {max_date} ({count:,}件)")
    except:
        print("historical_payoffs: テーブルなしまたはアクセス不可")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_tables()
    get_historical_programs_schema()
    get_historical_results_schema()
    get_sample_data()
    get_data_range()

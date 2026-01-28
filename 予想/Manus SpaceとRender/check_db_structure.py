#!/usr/bin/env python3
"""DBのテーブル構造を確認するスクリプト"""
import psycopg2

conn = psycopg2.connect(
    host="dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com",
    database="kokotomo_staging",
    user="kokotomo_staging_user",
    password="MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq",
    sslmode="require"
)
cur = conn.cursor()

# bet_typeの種類
print("=== bet_type の種類 ===")
cur.execute("SELECT DISTINCT bet_type FROM historical_payoffs")
for row in cur.fetchall():
    print(f"  {row[0]}")

# popularityの分布（単勝）
print("\n=== tansho の popularity 分布 ===")
cur.execute("""
    SELECT popularity, COUNT(*) 
    FROM historical_payoffs 
    WHERE bet_type = 'tansho' 
    GROUP BY popularity 
    ORDER BY popularity 
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"  popularity={row[0]}: {row[1]}件")

# historical_race_resultsのカラム
print("\n=== historical_race_results カラム ===")
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'historical_race_results'
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

# サンプルデータ
print("\n=== historical_race_results サンプル ===")
cur.execute("SELECT * FROM historical_race_results LIMIT 2")
cols = [desc[0] for desc in cur.description]
print(f"カラム: {cols}")
for row in cur.fetchall():
    print(row)

# historical_programsのサンプル
print("\n=== historical_programs サンプル ===")
cur.execute("SELECT * FROM historical_programs LIMIT 2")
cols = [desc[0] for desc in cur.description]
print(f"カラム: {cols}")
for row in cur.fetchall():
    print(row)

conn.close()

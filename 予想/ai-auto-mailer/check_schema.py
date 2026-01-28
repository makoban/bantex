import psycopg2

db_url = "postgresql://boatrace_db_xjqf_user:fxGJSyPsAKxDlL1KVvBbpVgbLQmZiLLU@dpg-d5gj8b5actks73fo3eag-a.singapore-postgres.render.com/boatrace_db_xjqf?sslmode=require"

conn = psycopg2.connect(db_url)
cur = conn.cursor()

# racesテーブルの構造を確認
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'races'
    ORDER BY ordinal_position
""")
print("=== races テーブル ===")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} (nullable: {row[2]})")

# virtual_betsテーブルの構造を確認
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'virtual_bets'
    ORDER BY ordinal_position
""")
print("\n=== virtual_bets テーブル ===")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} (nullable: {row[2]})")

conn.close()

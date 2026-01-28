"""
race_noのデータ型を確認
"""

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def run_query(query):
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode='require')
    cur = conn.cursor()
    cur.execute(query)
    results = cur.fetchall()
    conn.close()
    return results

# race_noのサンプルを確認
print("【race_noのサンプル】")
results = run_query("""
    SELECT DISTINCT race_no, stadium_code
    FROM historical_payoffs
    WHERE bet_type = 'tansho' AND combination = '1'
    LIMIT 20
""")
for r in results:
    print(f"  race_no: '{r['race_no']}' (type: {type(r['race_no']).__name__}), stadium_code: '{r['stadium_code']}'")

# 戸田のデータを確認
print("\n【戸田(02)のrace_no】")
results = run_query("""
    SELECT DISTINCT race_no
    FROM historical_payoffs
    WHERE bet_type = 'tansho' AND stadium_code = '02'
    ORDER BY race_no
""")
for r in results:
    print(f"  race_no: '{r['race_no']}'")

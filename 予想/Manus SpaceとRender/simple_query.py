"""
シンプルなクエリで分析
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import sys

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

STADIUM_NAMES = {
    '01': '桐生', '02': '戸田', '03': '江戸川', '04': '平和島', '05': '多摩川', '06': '浜名湖',
    '07': '蒲郡', '08': '常滑', '09': '津', '10': '三国', '11': 'びわこ', '12': '住之江',
    '13': '尼崎', '14': '鳴門', '15': '丸亀', '16': '児島', '17': '宮島', '18': '徳山',
    '19': '下関', '20': '若松', '21': '芦屋', '22': '福岡', '23': '唐津', '24': '大村'
}

def run_query(query):
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode='require')
    cur = conn.cursor()
    cur.execute(query)
    results = cur.fetchall()
    conn.close()
    return results

# 複勝の基本統計
print("【複勝の基本統計】")
results = run_query("""
    SELECT 
        COUNT(*) as total_payouts,
        AVG(payout) as avg_payout
    FROM historical_payoffs
    WHERE bet_type = 'fukusho'
""")
result = results[0]
print(f"  総払戻数: {result['total_payouts']:,}")
print(f"  平均払戻: {float(result['avg_payout']):.1f}円")

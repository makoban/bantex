# -*- coding: utf-8 -*-
"""
購入実験初日準備: DBリセット＆virtual_funds初期化
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta

DATABASE_URL = os.environ.get('DATABASE_URL')
JST = timezone(timedelta(hours=9))

conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
cur = conn.cursor()

print("=" * 60)
print("購入実験初日準備: DBリセット")
print("=" * 60)

# 1. virtual_betsテーブルを全削除
print("\n1. virtual_betsテーブルを削除中...")
cur.execute("SELECT COUNT(*) as cnt FROM virtual_bets")
before_count = cur.fetchone()['cnt']
print(f"   削除前: {before_count}件")

cur.execute("DELETE FROM virtual_bets")
conn.commit()
print("   削除完了")

# 2. virtual_fundsテーブルを初期化
print("\n2. virtual_fundsテーブルを初期化中...")
cur.execute("DELETE FROM virtual_funds")
conn.commit()

# 3. 2つの戦略で初期レコードを作成
strategies = [
    ('bias_1_3_2nd', '3穴2nd戦略'),
    ('win_10x_1_3', '１単勝10倍以上１－３'),
]

now = datetime.now(JST)
for strategy_type, name in strategies:
    cur.execute("""
        INSERT INTO virtual_funds (
            strategy_type, initial_fund, current_fund, total_profit,
            total_bets, total_hits, hit_rate, return_rate,
            total_bet_amount, total_return_amount,
            is_active, created_at, updated_at
        ) VALUES (
            %s, 100000, 100000, 0,
            0, 0, 0, 0,
            0, 0,
            true, %s, %s
        )
    """, (strategy_type, now, now))
    print(f"   {name} ({strategy_type}): 初期資金10万円で作成")

conn.commit()

# 4. 確認
print("\n3. 確認:")
cur.execute("SELECT COUNT(*) as cnt FROM virtual_bets")
print(f"   virtual_bets: {cur.fetchone()['cnt']}件")

cur.execute("SELECT strategy_type, initial_fund, current_fund, total_profit FROM virtual_funds")
for row in cur.fetchall():
    print(f"   virtual_funds: {row['strategy_type']} - 資金: {row['current_fund']}, 損益: {row['total_profit']}")

conn.close()
print("\n" + "=" * 60)
print("完了: 明日(2026/01/26)から購入実験開始可能")
print("=" * 60)

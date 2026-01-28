"""システム稼働状況診断"""
import psycopg2
import os
from datetime import datetime, timedelta

# JST現在時刻
now = datetime.utcnow() + timedelta(hours=9)
today_str = now.strftime('%Y-%m-%d') # YYYY-MM-DD形式かも？api.pyではstr
today_str_nodash = now.strftime('%Y%m%d')
print(f"現在時刻(JST): {now}")
print(f"確認対象日: {today_str} / {today_str_nodash}")

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 1. レース情報の確認
    # 日付形式がどちらかわからないので両方試す
    cur.execute("SELECT COUNT(*), MIN(deadline_at), MAX(deadline_at) FROM races WHERE race_date = %s", (today_str,))
    race_stats = cur.fetchone()
    if race_stats[0] == 0:
        cur.execute("SELECT COUNT(*), MIN(deadline_at), MAX(deadline_at) FROM races WHERE race_date = %s", (today_str_nodash,))
        race_stats = cur.fetchone()
        target_date = today_str_nodash
    else:
        target_date = today_str

    print(f"\n1. 今日のレース情報 ({target_date}):")
    print(f"   件数: {race_stats[0]}件")
    print(f"   最初の締切: {race_stats[1]}")
    print(f"   最後の締切: {race_stats[2]}")

    if race_stats[0] > 0:
        # 2. オッズの確認
        cur.execute("""
            SELECT COUNT(DISTINCT race_id)
            FROM odds
            WHERE race_id IN (SELECT DISTINCT id FROM races WHERE race_date = %s)
        """, (target_date,))
        odds_count = cur.fetchone()[0]
        print(f"\n2. オッズ取得状況:")
        print(f"   オッズがあるレース数: {odds_count}/{race_stats[0]}件")

    # 3. 仮想ベットの確認
    cur.execute("""
        SELECT status, COUNT(*)
        FROM virtual_bets
        WHERE race_date = %s
        GROUP BY status
    """, (target_date,))
    bets = cur.fetchall()
    print(f"\n3. 今日の仮想ベット状況:")
    if not bets:
        print("   データなし")
    for status, count in bets:
        print(f"   {status}: {count}件")

    conn.close()

except Exception as e:
    print(f"エラー発生: {e}")

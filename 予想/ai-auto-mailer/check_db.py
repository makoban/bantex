import os
import psycopg2
from datetime import datetime

def check():
    url = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        
        print("=== データベース統計 ===")
        
        # 過去番組表 (historical_programs)
        cur.execute("SELECT COUNT(*), MIN(race_date), MAX(race_date) FROM historical_programs")
        count, min_date, max_date = cur.fetchone()
        print(f"過去番組表 (historical_programs):")
        print(f"  件数: {count:,} 件")
        print(f"  期間: {min_date} ～ {max_date}")
        
        # 過去競走成績 (historical_race_results)
        cur.execute("SELECT COUNT(*), MIN(race_date), MAX(race_date) FROM historical_race_results")
        count, min_date, max_date = cur.fetchone()
        print(f"過去競走成績 (historical_race_results):")
        print(f"  件数: {count:,} 件")
        print(f"  期間: {min_date} ～ {max_date}")
        
        # リアルタイムレース (races)
        cur.execute("SELECT COUNT(*), MIN(race_date), MAX(race_date) FROM races")
        count, min_date, max_date = cur.fetchone()
        print(f"当日/最近のレース (races):")
        print(f"  件数: {count:,} 件")
        print(f"  期間: {min_date} ～ {max_date}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    check()

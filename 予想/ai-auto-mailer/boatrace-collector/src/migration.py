import os
import psycopg2
import sys

def migrate():
    url = os.environ.get('DATABASE_URL')
    if not url:
        print("DATABASE_URLがありません")
        return

    print(f"接続先: {url.split('@')[1]}") # パスワード隠蔽

    try:
        conn = psycopg2.connect(url)
        with conn.cursor() as cur:
            # カラム追加（存在しない場合のみ）
            print("ALTER TABLE実行中...")
            cur.execute("""
                ALTER TABLE historical_race_results
                ADD COLUMN IF NOT EXISTS exhibition_time DECIMAL(4,2);
            """)
            print("カラム追加完了")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"エラー: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate()

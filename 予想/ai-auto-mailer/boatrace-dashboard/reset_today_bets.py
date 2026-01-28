#!/usr/bin/env python3
"""今日の締切超過の購入予定をリセットするスクリプト"""

import psycopg2
import os
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

def reset_today_overdue_bets():
    """今日の締切超過レコードを削除"""
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        print("DATABASE_URL環境変数が設定されていません")
        return
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    today = datetime.now(JST).strftime('%Y-%m-%d')
    
    # 今日の締切超過（見送り）レコードを削除
    cur.execute("""
        DELETE FROM virtual_bets 
        WHERE race_date = %s 
        AND status = 'skipped' 
        AND reason LIKE '%%締切超過%%'
    """, (today,))
    
    deleted = cur.rowcount
    conn.commit()
    print(f'削除完了: {deleted}件')
    
    conn.close()
    return deleted

if __name__ == '__main__':
    reset_today_overdue_bets()

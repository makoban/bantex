#!/usr/bin/env python3
"""
既存の見送りレースにskipReasonを設定するスクリプト
"""
import os
import json
import pymysql

def main():
    # TiDB接続
    conn = pymysql.connect(
        host=os.environ.get('TIDB_HOST'),
        port=int(os.environ.get('TIDB_PORT', 4000)),
        user=os.environ.get('TIDB_USER'),
        password=os.environ.get('TIDB_PASSWORD'),
        database=os.environ.get('TIDB_DATABASE'),
        ssl={'ca': '/etc/ssl/certs/ca-certificates.crt'},
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        with conn.cursor() as cursor:
            # skipReasonが設定されていない見送りレースを取得
            cursor.execute("""
                SELECT id, reason FROM virtualBets 
                WHERE status = 'skipped'
            """)
            skipped_bets = cursor.fetchall()
            
            updated_count = 0
            for bet in skipped_bets:
                reason = {}
                if bet['reason']:
                    try:
                        reason = json.loads(bet['reason']) if isinstance(bet['reason'], str) else bet['reason']
                    except:
                        pass
                
                # skipReasonが設定されていない場合のみ更新
                if 'skipReason' not in reason:
                    reason['skipReason'] = '締切超過（購入判断未実行）'
                    reason['decision'] = 'skipped'
                    
                    cursor.execute("""
                        UPDATE virtualBets 
                        SET reason = %s
                        WHERE id = %s
                    """, (json.dumps(reason, ensure_ascii=False), bet['id']))
                    updated_count += 1
            
            conn.commit()
            print(f"更新完了: {updated_count}件")
            
    finally:
        conn.close()

if __name__ == '__main__':
    main()

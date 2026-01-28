#!/usr/bin/env python3
"""
既存の見送りレースにskipReasonを設定するスクリプト

PostgreSQL（kokotomo-db-staging）を使用
※ Manus Space DBは使用しない
"""

import os
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


def update_existing_skip_reasons():
    """
    既存の見送りレース（status='skipped'）で、skipReasonが設定されていないものに
    デフォルトの見送り理由を設定する
    """
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL環境変数が設定されていません")
        return 0
    
    logger.info("=== 既存の見送りレースのskipReason更新開始 ===")
    
    conn = None
    try:
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        
        with conn.cursor() as cursor:
            # skipReasonが設定されていない見送りレースを取得
            cursor.execute("""
                SELECT id, reason FROM virtual_bets 
                WHERE status = 'skipped'
            """)
            skipped_bets = cursor.fetchall()
            
            logger.info(f"見送りレース数: {len(skipped_bets)}件")
            
            updated_count = 0
            for bet in skipped_bets:
                reason = {}
                if bet.get('reason'):
                    try:
                        if isinstance(bet['reason'], str):
                            reason = json.loads(bet['reason'])
                        elif isinstance(bet['reason'], dict):
                            reason = bet['reason']
                    except:
                        pass
                
                # skipReasonが設定されていない場合のみ更新
                if 'skipReason' not in reason:
                    reason['skipReason'] = '締切超過（購入判断未実行）'
                    reason['decision'] = 'skipped'
                    
                    cursor.execute("""
                        UPDATE virtual_bets 
                        SET reason = %s
                        WHERE id = %s
                    """, (json.dumps(reason, ensure_ascii=False), bet['id']))
                    
                    updated_count += 1
            
            conn.commit()
            logger.info(f"skipReason更新完了: {updated_count}件")
            return updated_count
            
    except Exception as e:
        logger.error(f"skipReason更新エラー: {e}")
        return 0
    finally:
        if conn:
            conn.close()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    update_existing_skip_reasons()


if __name__ == "__main__":
    main()

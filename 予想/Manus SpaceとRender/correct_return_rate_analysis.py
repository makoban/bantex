#!/usr/bin/env python3
"""
競艇21年分データ - 正確な回収率分析
単勝・3穴戦略の回収率100%超え条件を特定
"""

import psycopg2
import os
from decimal import Decimal

# DB接続
DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def run_query(conn, query, description):
    print(f"\n{'='*60}")
    print(f"【{description}】")
    print(f"{'='*60}")
    
    cur = conn.cursor()
    cur.execute(query)
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    
    if not rows:
        print("結果なし")
        return []
    
    # ヘッダー表示
    print(" | ".join(columns))
    print("-" * 60)
    
    # データ表示
    for row in rows[:30]:  # 上位30件
        formatted = []
        for val in row:
            if isinstance(val, Decimal):
                formatted.append(f"{float(val):.2f}")
            elif val is None:
                formatted.append("NULL")
            else:
                formatted.append(str(val))
        print(" | ".join(formatted))
    
    if len(rows) > 30:
        print(f"... 他 {len(rows) - 30} 件")
    
    return rows

def main():
    print("=" * 60)
    print("競艇21年分データ - 正確な回収率分析")
    print("=" * 60)
    
    conn = get_connection()
    print("DB接続OK")
    
    # ============================================================
    # 1. 単勝の正確な回収率（全体）
    # ============================================================
    query1 = """
    WITH race_counts AS (
        -- 全レース数をカウント（号艇別）
        SELECT 
            boat_no,
            COUNT(*) as total_races
        FROM historical_race_results
        WHERE rank IS NOT NULL
        GROUP BY boat_no
    ),
    win_payoffs AS (
        -- 単勝の払戻金（勝った艇の払戻金）
        SELECT 
            r.boat_no,
            COUNT(*) as win_count,
            SUM(p.payout) as total_payout
        FROM historical_race_results r
        JOIN historical_payoffs p 
            ON r.race_date = p.race_date 
            AND r.stadium_code = p.stadium_code 
            AND r.race_no = p.race_no
        WHERE r.rank = '1'
          AND p.bet_type = 'tansho'
          AND p.combination = r.boat_no
        GROUP BY r.boat_no
    )
    SELECT 
        rc.boat_no as 号艇,
        rc.total_races as 全レース数,
        COALESCE(wp.win_count, 0) as 勝利数,
        ROUND(COALESCE(wp.win_count, 0) * 100.0 / rc.total_races, 2) as 勝率,
        ROUND(COALESCE(wp.total_payout, 0) * 1.0 / rc.total_races, 2) as 回収率
    FROM race_counts rc
    LEFT JOIN win_payoffs wp ON rc.boat_no = wp.boat_no
    ORDER BY rc.boat_no
    """
    run_query(conn, query1, "単勝回収率（号艇別・全期間）")
    
    # ============================================================
    # 2. 単勝の正確な回収率（場別×1号艇）
    # ============================================================
    query2 = """
    WITH race_counts AS (
        SELECT 
            stadium_code,
            COUNT(*) as total_races
        FROM historical_race_results
        WHERE boat_no = '1' AND rank IS NOT NULL
        GROUP BY stadium_code
    ),
    win_payoffs AS (
        SELECT 
            r.stadium_code,
            COUNT(*) as win_count,
            SUM(p.payout) as total_payout
        FROM historical_race_results r
        JOIN historical_payoffs p 
            ON r.race_date = p.race_date 
            AND r.stadium_code = p.stadium_code 
            AND r.race_no = p.race_no
        WHERE r.boat_no = '1'
          AND r.rank = '1'
          AND p.bet_type = 'tansho'
          AND p.combination = '1'
        GROUP BY r.stadium_code
    )
    SELECT 
        rc.stadium_code as 場コード,
        rc.total_races as 全レース数,
        COALESCE(wp.win_count, 0) as 勝利数,
        ROUND(COALESCE(wp.win_count, 0) * 100.0 / rc.total_races, 2) as 勝率,
        ROUND(COALESCE(wp.total_payout, 0) * 1.0 / rc.total_races, 2) as 回収率
    FROM race_counts rc
    LEFT JOIN win_payoffs wp ON rc.stadium_code = wp.stadium_code
    ORDER BY 回収率 DESC
    """
    run_query(conn, query2, "1号艇単勝回収率（場別）- 回収率順")
    
    # ============================================================
    # 3. 単勝の正確な回収率（場×R別×1号艇）- 回収率100%超え
    # ============================================================
    query3 = """
    WITH race_counts AS (
        SELECT 
            stadium_code,
            race_no,
            COUNT(*) as total_races
        FROM historical_race_results
        WHERE boat_no = '1' AND rank IS NOT NULL
        GROUP BY stadium_code, race_no
    ),
    win_payoffs AS (
        SELECT 
            r.stadium_code,
            r.race_no,
            COUNT(*) as win_count,
            SUM(p.payout) as total_payout
        FROM historical_race_results r
        JOIN historical_payoffs p 
            ON r.race_date = p.race_date 
            AND r.stadium_code = p.stadium_code 
            AND r.race_no = p.race_no
        WHERE r.boat_no = '1'
          AND r.rank = '1'
          AND p.bet_type = 'tansho'
          AND p.combination = '1'
        GROUP BY r.stadium_code, r.race_no
    )
    SELECT 
        rc.stadium_code as 場,
        rc.race_no as R,
        rc.total_races as 全レース数,
        COALESCE(wp.win_count, 0) as 勝利数,
        ROUND(COALESCE(wp.win_count, 0) * 100.0 / rc.total_races, 2) as 勝率,
        ROUND(COALESCE(wp.total_payout, 0) * 1.0 / rc.total_races, 2) as 回収率
    FROM race_counts rc
    LEFT JOIN win_payoffs wp ON rc.stadium_code = wp.stadium_code AND rc.race_no = wp.race_no
    WHERE COALESCE(wp.total_payout, 0) * 1.0 / rc.total_races >= 100
    ORDER BY 回収率 DESC
    """
    run_query(conn, query3, "1号艇単勝回収率100%超え（場×R別）")
    
    # ============================================================
    # 4. 3穴（2連複1=3）の正確な回収率（全体）
    # ============================================================
    query4 = """
    WITH race_counts AS (
        -- 全レース数（ユニークなレース）
        SELECT COUNT(DISTINCT (race_date, stadium_code, race_no)) as total_races
        FROM historical_race_results
    ),
    hit_payoffs AS (
        -- 2連複1=3の的中（1号艇と3号艇が1着2着）
        SELECT 
            COUNT(*) as hit_count,
            SUM(p.payout) as total_payout
        FROM historical_payoffs p
        WHERE p.bet_type = 'nirenpuku'
          AND p.combination = '1=3'
    )
    SELECT 
        rc.total_races as 全レース数,
        hp.hit_count as 的中数,
        ROUND(hp.hit_count * 100.0 / rc.total_races, 2) as 的中率,
        ROUND(hp.total_payout * 1.0 / rc.total_races, 2) as 回収率
    FROM race_counts rc, hit_payoffs hp
    """
    run_query(conn, query4, "2連複1=3 回収率（全体）")
    
    # ============================================================
    # 5. 3穴（2連複1=3）の正確な回収率（場別）
    # ============================================================
    query5 = """
    WITH race_counts AS (
        SELECT 
            stadium_code,
            COUNT(DISTINCT (race_date, race_no)) as total_races
        FROM historical_race_results
        GROUP BY stadium_code
    ),
    hit_payoffs AS (
        SELECT 
            stadium_code,
            COUNT(*) as hit_count,
            SUM(payout) as total_payout
        FROM historical_payoffs
        WHERE bet_type = 'nirenpuku'
          AND combination = '1=3'
        GROUP BY stadium_code
    )
    SELECT 
        rc.stadium_code as 場コード,
        rc.total_races as 全レース数,
        COALESCE(hp.hit_count, 0) as 的中数,
        ROUND(COALESCE(hp.hit_count, 0) * 100.0 / rc.total_races, 2) as 的中率,
        ROUND(COALESCE(hp.total_payout, 0) * 1.0 / rc.total_races, 2) as 回収率
    FROM race_counts rc
    LEFT JOIN hit_payoffs hp ON rc.stadium_code = hp.stadium_code
    ORDER BY 回収率 DESC
    """
    run_query(conn, query5, "2連複1=3 回収率（場別）- 回収率順")
    
    # ============================================================
    # 6. 3穴（2連複1=3）の正確な回収率（場×R別）- 回収率100%超え
    # ============================================================
    query6 = """
    WITH race_counts AS (
        SELECT 
            stadium_code,
            race_no,
            COUNT(DISTINCT race_date) as total_races
        FROM historical_race_results
        GROUP BY stadium_code, race_no
    ),
    hit_payoffs AS (
        SELECT 
            stadium_code,
            race_no,
            COUNT(*) as hit_count,
            SUM(payout) as total_payout
        FROM historical_payoffs
        WHERE bet_type = 'nirenpuku'
          AND combination = '1=3'
        GROUP BY stadium_code, race_no
    )
    SELECT 
        rc.stadium_code as 場,
        rc.race_no as R,
        rc.total_races as 全レース数,
        COALESCE(hp.hit_count, 0) as 的中数,
        ROUND(COALESCE(hp.hit_count, 0) * 100.0 / rc.total_races, 2) as 的中率,
        ROUND(COALESCE(hp.total_payout, 0) * 1.0 / rc.total_races, 2) as 回収率
    FROM race_counts rc
    LEFT JOIN hit_payoffs hp ON rc.stadium_code = hp.stadium_code AND rc.race_no = hp.race_no
    WHERE COALESCE(hp.total_payout, 0) * 1.0 / rc.total_races >= 100
    ORDER BY 回収率 DESC
    """
    run_query(conn, query6, "2連複1=3 回収率100%超え（場×R別）")
    
    conn.close()
    print("\n" + "=" * 60)
    print("分析完了")
    print("=" * 60)

if __name__ == "__main__":
    main()

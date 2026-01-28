#!/usr/bin/env python3
"""
競艇 21年分データ 勝ちパターン分析（修正版）
結果なしだった項目のみを再分析

使い方:
1. 環境変数を設定
   Windows (PowerShell): $env:DATABASE_URL="postgresql://..."
   Windows (cmd): set DATABASE_URL=postgresql://...
   Linux/Mac: export DATABASE_URL="postgresql://..."

2. 実行
   python boatrace_analysis_runner_v2.py
"""

import os
import csv
import time
from datetime import datetime

# psycopg2のインポート
try:
    import psycopg2
except ImportError:
    print("psycopg2がインストールされていません。")
    print("pip install psycopg2-binary")
    exit(1)

# 出力フォルダ
OUTPUT_DIR = "analysis_results_v2"

# 修正版SQLクエリ（結果なしだった項目のみ）
QUERIES = [
    # 01b: 年別1号艇1着率推移（修正版）
    # 問題: rank='1'ではなく、1着を示す値を確認
    {
        "id": "01b",
        "name": "年別1号艇1着率推移",
        "sql": """
            SELECT 
                LEFT(race_date, 4) as year,
                COUNT(*) as total_races,
                SUM(CASE WHEN boat_no = '1' AND rank = '1' THEN 1 ELSE 0 END) as boat1_wins,
                ROUND(100.0 * SUM(CASE WHEN boat_no = '1' AND rank = '1' THEN 1 ELSE 0 END) / COUNT(DISTINCT (race_date || stadium_code || race_no)), 2) as win_rate
            FROM historical_race_results
            WHERE rank IS NOT NULL AND rank != ''
            GROUP BY LEFT(race_date, 4)
            ORDER BY year
        """
    },
    
    # 02: 人気別単勝回収率（修正版）
    # 問題: popularityがNULLの場合がある、combinationで1着艇を判定
    {
        "id": "02",
        "name": "人気別単勝回収率",
        "sql": """
            SELECT 
                p.popularity,
                COUNT(*) as bet_count,
                SUM(CASE WHEN r.rank = '1' AND r.boat_no = p.combination THEN p.payout ELSE 0 END) as total_payout,
                ROUND(100.0 * SUM(CASE WHEN r.rank = '1' AND r.boat_no = p.combination THEN p.payout ELSE 0 END) / (COUNT(*) * 100), 2) as return_rate
            FROM historical_payoffs p
            JOIN historical_race_results r 
                ON p.race_date = r.race_date 
                AND p.stadium_code = r.stadium_code 
                AND p.race_no = r.race_no
                AND p.combination = r.boat_no
            WHERE p.bet_type = 'tansho'
                AND p.popularity IS NOT NULL
                AND r.rank = '1'
            GROUP BY p.popularity
            ORDER BY p.popularity
            LIMIT 10
        """
    },
    
    # 02b: 単勝の人気と払戻金の関係（シンプル版）
    {
        "id": "02b",
        "name": "単勝人気別払戻金分布",
        "sql": """
            SELECT 
                popularity,
                COUNT(*) as count,
                ROUND(AVG(payout), 0) as avg_payout,
                MIN(payout) as min_payout,
                MAX(payout) as max_payout
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
                AND popularity IS NOT NULL
            GROUP BY popularity
            ORDER BY popularity
            LIMIT 10
        """
    },
    
    # 03: 場別単勝回収率（修正版）
    # 問題: 1番人気の判定方法
    {
        "id": "03",
        "name": "場別単勝1番人気回収率",
        "sql": """
            SELECT 
                p.stadium_code,
                COUNT(*) as bet_count,
                SUM(CASE WHEN r.rank = '1' AND r.boat_no = p.combination THEN 1 ELSE 0 END) as win_count,
                ROUND(100.0 * SUM(CASE WHEN r.rank = '1' AND r.boat_no = p.combination THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate,
                ROUND(AVG(CASE WHEN r.rank = '1' AND r.boat_no = p.combination THEN p.payout ELSE 0 END), 0) as avg_payout
            FROM historical_payoffs p
            JOIN historical_race_results r 
                ON p.race_date = r.race_date 
                AND p.stadium_code = r.stadium_code 
                AND p.race_no = r.race_no
                AND p.combination = r.boat_no
            WHERE p.bet_type = 'tansho'
                AND p.popularity = 1
                AND r.rank = '1'
            GROUP BY p.stadium_code
            ORDER BY win_rate DESC
        """
    },
    
    # 10: 枠番別穴傾向（修正版）
    # 4-6号艇が1着になった時の払戻金分布
    {
        "id": "10",
        "name": "枠番別穴傾向（4-6号艇の激走）",
        "sql": """
            SELECT 
                r.boat_no,
                COUNT(*) as win_count,
                ROUND(AVG(p.payout), 0) as avg_payout,
                MAX(p.payout) as max_payout,
                ROUND(100.0 * COUNT(*) / (SELECT COUNT(DISTINCT race_date || stadium_code || race_no) FROM historical_race_results WHERE rank = '1'), 2) as win_rate
            FROM historical_race_results r
            JOIN historical_payoffs p 
                ON r.race_date = p.race_date 
                AND r.stadium_code = p.stadium_code 
                AND r.race_no = p.race_no
                AND r.boat_no = p.combination
            WHERE r.rank = '1'
                AND r.boat_no IN ('4', '5', '6')
                AND p.bet_type = 'tansho'
            GROUP BY r.boat_no
            ORDER BY r.boat_no
        """
    },
    
    # 17: 回収率100%超え条件ランキング（修正版）
    # 場×レース番号の組み合わせで単勝回収率を計算
    {
        "id": "17",
        "name": "単勝回収率100%超え条件",
        "sql": """
            WITH race_stats AS (
                SELECT 
                    p.stadium_code,
                    p.race_no,
                    COUNT(*) as total_bets,
                    SUM(CASE WHEN r.rank = '1' AND r.boat_no = p.combination THEN p.payout ELSE 0 END) as total_payout
                FROM historical_payoffs p
                JOIN historical_race_results r 
                    ON p.race_date = r.race_date 
                    AND p.stadium_code = r.stadium_code 
                    AND p.race_no = r.race_no
                    AND p.combination = r.boat_no
                WHERE p.bet_type = 'tansho'
                    AND p.popularity = 1
                    AND r.rank = '1'
                GROUP BY p.stadium_code, p.race_no
                HAVING COUNT(*) >= 1000
            )
            SELECT 
                stadium_code,
                race_no,
                total_bets,
                total_payout,
                ROUND(100.0 * total_payout / (total_bets * 100), 2) as return_rate
            FROM race_stats
            WHERE total_payout > total_bets * 100
            ORDER BY return_rate DESC
            LIMIT 50
        """
    },
    
    # 17b: 1号艇の場×R別勝率と回収率
    {
        "id": "17b",
        "name": "1号艇の場×R別成績",
        "sql": """
            SELECT 
                r.stadium_code,
                r.race_no,
                COUNT(*) as total_races,
                SUM(CASE WHEN r.boat_no = '1' AND r.rank = '1' THEN 1 ELSE 0 END) as boat1_wins,
                ROUND(100.0 * SUM(CASE WHEN r.boat_no = '1' AND r.rank = '1' THEN 1 ELSE 0 END) / COUNT(DISTINCT (r.race_date || r.stadium_code || r.race_no)), 2) as win_rate
            FROM historical_race_results r
            WHERE r.rank IS NOT NULL AND r.rank != ''
            GROUP BY r.stadium_code, r.race_no
            HAVING COUNT(DISTINCT (r.race_date || r.stadium_code || r.race_no)) >= 1000
            ORDER BY win_rate DESC
            LIMIT 50
        """
    },
    
    # 追加: 単勝の全体統計
    {
        "id": "00b",
        "name": "単勝の全体統計",
        "sql": """
            SELECT 
                'tansho' as bet_type,
                COUNT(*) as total_records,
                COUNT(DISTINCT race_date || stadium_code || race_no) as unique_races,
                ROUND(AVG(payout), 0) as avg_payout,
                MIN(payout) as min_payout,
                MAX(payout) as max_payout,
                COUNT(CASE WHEN popularity IS NOT NULL THEN 1 END) as with_popularity
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
        """
    },
    
    # 追加: レース結果のrank値の分布
    {
        "id": "00c",
        "name": "レース結果rank値の分布",
        "sql": """
            SELECT 
                rank,
                COUNT(*) as count
            FROM historical_race_results
            GROUP BY rank
            ORDER BY count DESC
            LIMIT 20
        """
    }
]


def get_db_connection():
    """データベース接続を取得"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL環境変数が設定されていません")
        print("\nWindows (PowerShell):")
        print('$env:DATABASE_URL="postgresql://user:pass@host:5432/dbname"')
        print("\nWindows (cmd):")
        print('set DATABASE_URL=postgresql://user:pass@host:5432/dbname')
        exit(1)
    
    return psycopg2.connect(database_url, sslmode='require')


def run_query(conn, query_info):
    """クエリを実行して結果を返す"""
    cur = conn.cursor()
    try:
        start_time = time.time()
        cur.execute(query_info["sql"])
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        elapsed = time.time() - start_time
        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "elapsed": elapsed
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        cur.close()


def save_to_csv(filename, columns, rows):
    """結果をCSVファイルに保存"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    return filepath


def main():
    print("=" * 60)
    print("競艇 21年分データ 勝ちパターン分析（修正版）")
    print("結果なしだった項目の再分析")
    print("=" * 60)
    print()
    
    # 出力フォルダ作成
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"出力フォルダ: {os.path.abspath(OUTPUT_DIR)}")
    print()
    
    # DB接続テスト
    print("データベース接続テスト...")
    try:
        conn = get_db_connection()
        print("接続OK")
    except Exception as e:
        print(f"接続エラー: {e}")
        exit(1)
    
    print()
    print(f"{len(QUERIES)}個の分析クエリを実行します...")
    print()
    
    results_summary = []
    total_records = 0
    start_time = time.time()
    
    for query in QUERIES:
        print(f"[{query['id']}] {query['name']}")
        print("    実行中...")
        
        result = run_query(conn, query)
        
        if result["success"]:
            rows = result["rows"]
            if rows:
                filename = f"{query['id']}_{query['name'].replace('/', '_').replace(' ', '_')}.csv"
                save_to_csv(filename, result["columns"], rows)
                print(f"    完了: {len(rows)}件 → {filename} ({result['elapsed']:.1f}秒)")
                total_records += len(rows)
                results_summary.append({
                    "id": query['id'],
                    "name": query['name'],
                    "status": "success",
                    "records": len(rows)
                })
            else:
                print(f"    結果なし ({result['elapsed']:.1f}秒)")
                results_summary.append({
                    "id": query['id'],
                    "name": query['name'],
                    "status": "no_results",
                    "records": 0
                })
        else:
            print(f"    エラー: {result['error']}")
            results_summary.append({
                "id": query['id'],
                "name": query['name'],
                "status": "error",
                "error": result['error']
            })
        
        print()
    
    conn.close()
    
    total_time = time.time() - start_time
    
    # サマリー出力
    print("=" * 60)
    print("完了サマリー")
    print("=" * 60)
    success_count = sum(1 for r in results_summary if r["status"] == "success")
    print(f"成功: {success_count}/{len(QUERIES)} クエリ")
    print(f"総レコード数: {total_records}件")
    print(f"総実行時間: {total_time:.1f}秒")
    print(f"出力フォルダ: {os.path.abspath(OUTPUT_DIR)}")
    print("=" * 60)
    
    # 結果なしの項目を表示
    no_results = [r for r in results_summary if r["status"] == "no_results"]
    if no_results:
        print("\n結果なしの項目:")
        for r in no_results:
            print(f"  - [{r['id']}] {r['name']}")
    
    # エラーの項目を表示
    errors = [r for r in results_summary if r["status"] == "error"]
    if errors:
        print("\nエラーの項目:")
        for r in errors:
            print(f"  - [{r['id']}] {r['name']}: {r.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
競艇 21年分データ 勝ちパターン分析（修正版v3）
popularity不要版 - 払戻金額から人気を推定

使い方:
1. 環境変数を設定
   Windows (PowerShell): $env:DATABASE_URL="postgresql://..."

2. 実行
   python boatrace_analysis_runner_v3.py
"""

import os
import csv
import time

try:
    import psycopg2
except ImportError:
    print("psycopg2がインストールされていません。")
    print("pip install psycopg2-binary")
    exit(1)

OUTPUT_DIR = "analysis_results_v3"

QUERIES = [
    # 02: 払戻金額別の分布（人気の代替）
    # 低い払戻金 = 高人気、高い払戻金 = 低人気
    {
        "id": "02",
        "name": "単勝払戻金レンジ別分布",
        "sql": """
            SELECT 
                CASE 
                    WHEN payout < 200 THEN '100-199円（本命）'
                    WHEN payout < 300 THEN '200-299円'
                    WHEN payout < 500 THEN '300-499円'
                    WHEN payout < 1000 THEN '500-999円'
                    WHEN payout < 2000 THEN '1000-1999円'
                    WHEN payout < 5000 THEN '2000-4999円'
                    ELSE '5000円以上（大穴）'
                END as payout_range,
                COUNT(*) as count,
                ROUND(AVG(payout), 0) as avg_payout,
                MIN(payout) as min_payout,
                MAX(payout) as max_payout
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
            GROUP BY 
                CASE 
                    WHEN payout < 200 THEN '100-199円（本命）'
                    WHEN payout < 300 THEN '200-299円'
                    WHEN payout < 500 THEN '300-499円'
                    WHEN payout < 1000 THEN '500-999円'
                    WHEN payout < 2000 THEN '1000-1999円'
                    WHEN payout < 5000 THEN '2000-4999円'
                    ELSE '5000円以上（大穴）'
                END
            ORDER BY min_payout
        """
    },
    
    # 03: 場別単勝回収率（本命＝払戻金200円未満）
    {
        "id": "03",
        "name": "場別単勝回収率（本命）",
        "sql": """
            SELECT 
                stadium_code,
                COUNT(*) as total_races,
                SUM(CASE WHEN payout < 200 THEN 1 ELSE 0 END) as honmei_count,
                ROUND(100.0 * SUM(CASE WHEN payout < 200 THEN 1 ELSE 0 END) / COUNT(*), 2) as honmei_rate,
                ROUND(AVG(payout), 0) as avg_payout,
                ROUND(100.0 * AVG(payout) / 100, 2) as return_rate
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
            GROUP BY stadium_code
            ORDER BY return_rate DESC
        """
    },
    
    # 10: 枠番別穴傾向（4-6号艇が1着）
    # 単勝のcombinationは1着艇の番号
    {
        "id": "10",
        "name": "枠番別単勝成績",
        "sql": """
            SELECT 
                combination as boat_no,
                COUNT(*) as win_count,
                ROUND(AVG(payout), 0) as avg_payout,
                MIN(payout) as min_payout,
                MAX(payout) as max_payout,
                ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM historical_payoffs WHERE bet_type = 'tansho'), 2) as win_rate
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
            GROUP BY combination
            ORDER BY combination
        """
    },
    
    # 10b: 4-6号艇の激走（高配当）
    {
        "id": "10b",
        "name": "4-6号艇の激走分析",
        "sql": """
            SELECT 
                combination as boat_no,
                COUNT(*) as win_count,
                SUM(CASE WHEN payout >= 1000 THEN 1 ELSE 0 END) as high_payout_count,
                ROUND(100.0 * SUM(CASE WHEN payout >= 1000 THEN 1 ELSE 0 END) / COUNT(*), 2) as high_payout_rate,
                ROUND(AVG(payout), 0) as avg_payout,
                MAX(payout) as max_payout
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
                AND combination IN ('4', '5', '6')
            GROUP BY combination
            ORDER BY combination
        """
    },
    
    # 17: 場×R別の単勝回収率
    {
        "id": "17",
        "name": "場×R別単勝回収率",
        "sql": """
            SELECT 
                stadium_code,
                race_no,
                COUNT(*) as race_count,
                ROUND(AVG(payout), 0) as avg_payout,
                ROUND(100.0 * AVG(payout) / 100, 2) as return_rate
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
            GROUP BY stadium_code, race_no
            HAVING COUNT(*) >= 1000
            ORDER BY return_rate DESC
            LIMIT 50
        """
    },
    
    # 17b: 回収率100%超えの場×R
    {
        "id": "17b",
        "name": "単勝回収率100%超え条件",
        "sql": """
            SELECT 
                stadium_code,
                race_no,
                COUNT(*) as race_count,
                ROUND(AVG(payout), 0) as avg_payout,
                ROUND(100.0 * AVG(payout) / 100, 2) as return_rate
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
            GROUP BY stadium_code, race_no
            HAVING COUNT(*) >= 1000 AND AVG(payout) > 100
            ORDER BY return_rate DESC
        """
    },
    
    # 追加: 1号艇単勝の場別成績
    {
        "id": "18",
        "name": "1号艇単勝の場別成績",
        "sql": """
            SELECT 
                stadium_code,
                COUNT(*) as boat1_wins,
                ROUND(AVG(payout), 0) as avg_payout,
                MIN(payout) as min_payout,
                MAX(payout) as max_payout
            FROM historical_payoffs
            WHERE bet_type = 'tansho'
                AND combination = '1'
            GROUP BY stadium_code
            ORDER BY boat1_wins DESC
        """
    },
    
    # 追加: 2連複の人気別分布（popularityがある可能性）
    {
        "id": "19",
        "name": "2連複のpopularity分布",
        "sql": """
            SELECT 
                popularity,
                COUNT(*) as count,
                ROUND(AVG(payout), 0) as avg_payout
            FROM historical_payoffs
            WHERE bet_type = 'nirenpuku'
                AND popularity IS NOT NULL
            GROUP BY popularity
            ORDER BY popularity
            LIMIT 20
        """
    },
    
    # 追加: 3連単の人気別分布
    {
        "id": "20",
        "name": "3連単のpopularity分布",
        "sql": """
            SELECT 
                popularity,
                COUNT(*) as count,
                ROUND(AVG(payout), 0) as avg_payout
            FROM historical_payoffs
            WHERE bet_type = 'sanrentan'
                AND popularity IS NOT NULL
            GROUP BY popularity
            ORDER BY popularity
            LIMIT 30
        """
    },
    
    # 追加: 各bet_typeのpopularity有無確認
    {
        "id": "00d",
        "name": "bet_type別popularity有無",
        "sql": """
            SELECT 
                bet_type,
                COUNT(*) as total,
                SUM(CASE WHEN popularity IS NOT NULL THEN 1 ELSE 0 END) as with_popularity,
                ROUND(100.0 * SUM(CASE WHEN popularity IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as popularity_rate
            FROM historical_payoffs
            GROUP BY bet_type
            ORDER BY bet_type
        """
    }
]


def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL環境変数が設定されていません")
        exit(1)
    return psycopg2.connect(database_url, sslmode='require')


def run_query(conn, query_info):
    cur = conn.cursor()
    try:
        start_time = time.time()
        cur.execute(query_info["sql"])
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        elapsed = time.time() - start_time
        return {"success": True, "columns": columns, "rows": rows, "elapsed": elapsed}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        cur.close()


def save_to_csv(filename, columns, rows):
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    return filepath


def main():
    print("=" * 60)
    print("競艇 21年分データ 勝ちパターン分析（修正版v3）")
    print("popularity不要版 - 払戻金額から人気を推定")
    print("=" * 60)
    print()
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"出力フォルダ: {os.path.abspath(OUTPUT_DIR)}")
    print()
    
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
                results_summary.append({"id": query['id'], "name": query['name'], "status": "success", "records": len(rows)})
            else:
                print(f"    結果なし ({result['elapsed']:.1f}秒)")
                results_summary.append({"id": query['id'], "name": query['name'], "status": "no_results", "records": 0})
        else:
            print(f"    エラー: {result['error']}")
            results_summary.append({"id": query['id'], "name": query['name'], "status": "error", "error": result['error']})
        
        print()
    
    conn.close()
    
    total_time = time.time() - start_time
    
    print("=" * 60)
    print("完了サマリー")
    print("=" * 60)
    success_count = sum(1 for r in results_summary if r["status"] == "success")
    print(f"成功: {success_count}/{len(QUERIES)} クエリ")
    print(f"総レコード数: {total_records}件")
    print(f"総実行時間: {total_time:.1f}秒")
    print(f"出力フォルダ: {os.path.abspath(OUTPUT_DIR)}")
    print("=" * 60)
    
    no_results = [r for r in results_summary if r["status"] == "no_results"]
    if no_results:
        print("\n結果なしの項目:")
        for r in no_results:
            print(f"  - [{r['id']}] {r['name']}")
    
    errors = [r for r in results_summary if r["status"] == "error"]
    if errors:
        print("\nエラーの項目:")
        for r in errors:
            print(f"  - [{r['id']}] {r['name']}: {r.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()

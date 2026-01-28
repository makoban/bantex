# get_dashboard_stats関数の構造

## 現在のコード（行473-512以降）

```python
@app.get("/api/stats/dashboard", response_model=DashboardStats)
def get_dashboard_stats():
    """ダッシュボード統計を取得"""
    today = get_adjusted_date()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 今日のレース数
            cur.execute("SELECT COUNT(*) as cnt FROM races WHERE race_date = %s", (today,))
            total_races_today = cur.fetchone()['cnt']
            
            # 完了したレース数
            cur.execute("""
                SELECT COUNT(*) as cnt FROM races r
                JOIN race_results rr ON r.id = rr.race_id
                WHERE r.race_date = %s
            """, (today,))
            completed_races = cur.fetchone()['cnt']
            
            # 今日の購入状況
            cur.execute("""
                SELECT status, COUNT(*) as cnt, COALESCE(SUM(profit), 0) as profit
                FROM virtual_bets
                WHERE race_date = %s
                GROUP BY status
            """, (today,))
            status_counts = {row['status']: {'count': row['cnt'], 'profit': float(row['profit'])} for row in cur}
            
            pending_bets = status_counts.get('pending', {}).get('count', 0)
            confirmed_bets = status_counts.get('confirmed', {}).get('count', 0)
            won_bets = status_counts.get('won', {}).get('count', 0)
            lost_bets = status_counts.get('lost', {}).get('count', 0)
            skipped_bets = status_counts.get('skipped', {}).get('count', 0)
            
            today_profit = sum(s.get('profit', 0) for s in status_counts.values())
            
            # 全体統計
            cur.execute("""
                SELECT
                    COALESCE(SUM(profit), 0) as total_profit,
                    COUNT(CASE WHEN status IN ('won', 'lost') THEN 1 END) as total_bets,
                    ...
            """)
```

## 追加が必要なフィールド

### DashboardStatsクラスに追加
- total_races_all: int  # 累計レース数
- total_bets_all: int   # 累計購入数
- total_won_all: int    # 累計的中数
- total_lost_all: int   # 累計不的中数
- total_return_rate: float  # 累計回収率

### SQLクエリ追加
累計データを取得するクエリを追加する必要がある

# get_dashboard_stats関数の完全なコード構造

## 現在のreturn文（行528-540）

```python
return DashboardStats(
    total_races_today=total_races_today,
    completed_races=completed_races,
    pending_bets=pending_bets,
    confirmed_bets=confirmed_bets,
    won_bets=won_bets,
    lost_bets=lost_bets,
    skipped_bets=skipped_bets,
    today_profit=today_profit,
    total_profit=total_profit,
    hit_rate=hit_rate,
    return_rate=return_rate
)
```

## 現在のDashboardStatsクラス
- total_races_today: int
- completed_races: int
- pending_bets: int
- confirmed_bets: int
- won_bets: int
- lost_bets: int
- skipped_bets: int
- today_profit: float
- total_profit: float
- hit_rate: float
- return_rate: float

## 追加が必要なフィールド（累計）
- total_races_all: int       # 累計レース数
- total_bets_all: int        # 累計購入数
- total_won_all: int         # 累計的中数
- total_lost_all: int        # 累計不的中数
- total_return_rate_all: float  # 累計回収率

## 実装方針
1. DashboardStatsクラスに累計フィールドを追加
2. get_dashboard_stats関数に累計データを取得するSQLを追加
3. フロントエンドに累計カードを追加

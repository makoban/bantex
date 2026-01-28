# 現在のAPI構造

## /api/stats/dashboard レスポンス
```json
{
  "total_races_today": 0,
  "completed_races": 0,
  "pending_bets": 0,
  "confirmed_bets": 0,
  "won_bets": 0,
  "lost_bets": 0,
  "skipped_bets": 0,
  "today_profit": 0.0,
  "total_profit": -10600.0,
  "hit_rate": 10.81081081081081,
  "return_rate": 14.505494505494507
}
```

## 現在のカード（本日の集計）
1. 今日のレース: stats.total_races_today
2. 購入予定: stats.pending_bets
3. 的中: stats.won_bets
4. 不的中: stats.lost_bets
5. 今日の損益: stats.today_profit
6. 回収率: stats.return_rate

## 追加が必要なフィールド（累計）
1. 総レース数: total_races_all
2. 総購入数: total_bets_all
3. 総的中数: total_won_all
4. 総不的中数: total_lost_all
5. 総損益: total_profit (既存)
6. 総回収率: total_return_rate

## 実装方針
1. APIに累計フィールドを追加
2. フロントエンドに累計カードセクションを追加

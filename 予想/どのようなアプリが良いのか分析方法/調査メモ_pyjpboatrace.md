# pyjpboatrace ライブラリ調査結果

## 概要
- **リポジトリ**: https://github.com/hmasdev/pyjpboatrace
- **バージョン**: v0.5.0
- **ライセンス**: MIT
- **Python要件**: >= 3.9

## 主要機能

### 1. スクレイピング機能（データ取得）

| メソッド | 説明 | 引数 |
|---|---|---|
| `get_stadiums(d)` | 当日開催の競艇場一覧 | date |
| `get_12races(d, stadium)` | 指定場の12レース情報 | date, stadium |
| `get_race_info(d, stadium, race)` | レース基本情報 | date, stadium, race |
| `get_odds_win_placeshow(d, stadium, race)` | 単勝・複勝オッズ | date, stadium, race |
| `get_odds_quinellaplace(d, stadium, race)` | 拡連複オッズ | date, stadium, race |
| `get_odds_exacta_quinella(d, stadium, race)` | 二連単・二連複オッズ | date, stadium, race |
| `get_odds_trifecta(d, stadium, race)` | 三連単オッズ | date, stadium, race |
| `get_odds_trio(d, stadium, race)` | 三連複オッズ | date, stadium, race |
| `get_just_before_info(d, stadium, race)` | 直前情報（天候・ST等） | date, stadium, race |
| `get_race_result(d, stadium, race)` | レース結果 | date, stadium, race |

### 2. 操作機能（投票）
- `deposit()` - 入金
- `withdraw()` - 出金
- `bet()` - 投票
- `get_bet_limit()` - 残高確認

## 競艇場コード（stadium）
1: 桐生, 2: 戸田, 3: 江戸川, 4: 平和島, 5: 多摩川, 6: 浜名湖,
7: 蒲郡, 8: 常滑, 9: 津, 10: 三国, 11: びわこ, 12: 住之江,
13: 尼崎, 14: 鳴門, 15: 丸亀, 16: 児島, 17: 宮島, 18: 徳山,
19: 下関, 20: 若松, 21: 芦屋, 22: 福岡, 23: 唐津, 24: 大村

## 依存関係
- requests>=2.28.1
- beautifulsoup4>=4.11.1
- selenium>=4.6（投票機能使用時のみ）

## 注意点
- スクレイピングのため、公式サイトの構造変更で動作しなくなる可能性あり
- オッズ取得はリアルタイムではなく、リクエスト時点のスナップショット
- 高頻度アクセスは公式サイトへの負荷になるため注意が必要

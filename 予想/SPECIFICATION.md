# 競艇予想システム 仕様書
**Ver1.42** | 最終更新: 2026-01-26

---

## 1. プロジェクト概要

### 1.1 目的
競艇の仮想購入シミュレーションシステム。統計的に有利なパターンを検出し、購入判断を自動化してROI（回収率）を検証する。

### 1.2 システム構成

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  boatrace.jp   │────▶│ boatrace-collector │────▶│   PostgreSQL    │
│   (公式サイト)   │     │   (データ収集)     │     │  (Render DB)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                        ┌─────────────────┐              │
                        │ boatrace-dashboard│◀────────────┘
                        │   (Webダッシュボード)  │
                        └─────────────────┘
```

---

## 2. 環境構成

### 2.1 インフラ（Render.com）

| サービス | 名前 | 用途 |
|---------|------|------|
| PostgreSQL | kokotomo-db-staging | メインDB |
| Web Service | boatrace-dashboard | ダッシュボードAPI |
| Cron Job | boatrace-batch | 日次バッチ（6:00 JST） |
| Cron Job | boatrace-betting | 購入判断（毎分） |
| Cron Job | boatrace-result | 結果収集（毎分） |

### 2.2 データベース接続

```
DATABASE_URL=postgresql://kokotomo_staging_user:***@dpg-***.singapore-postgres.render.com/kokotomo_staging
```

### 2.3 ローカル環境

```bash
# Python 3.10+
pip install -r requirements.txt

# 必要なライブラリ
- pyjpboatrace  # 公式サイトスクレイピング
- psycopg2      # PostgreSQL接続
- fastapi       # APIフレームワーク
- requests      # HTTP通信
- beautifulsoup4 # HTMLパース
```

---

## 3. データベーススキーマ

### 3.1 主要テーブル

#### races（レース情報）
| カラム | 型 | 説明 |
|--------|------|------|
| id | SERIAL | PK |
| race_date | DATE | レース日 |
| stadium_code | INT | 競艇場コード (01-24) |
| race_number | INT | レース番号 (1-12) |
| title | VARCHAR | レースタイトル |
| deadline_at | TIMESTAMPTZ | 締切時刻 |

#### virtual_bets（仮想購入）
| カラム | 型 | 説明 |
|--------|------|------|
| id | SERIAL | PK |
| race_date | DATE | レース日 |
| stadium_code | VARCHAR(2) | 競艇場コード |
| race_number | INT | レース番号 |
| strategy_type | VARCHAR | 戦略名 |
| bet_type | VARCHAR | 賭式（exacta/quinella） |
| combination | VARCHAR | 組番（例: 1-3） |
| amount | INT | 賭金（円） |
| odds | DECIMAL | 確定時オッズ |
| status | VARCHAR | pending/confirmed/won/lost/skipped |
| profit | INT | 損益（円） |
| return_amount | INT | 払戻金 |

#### virtual_funds（戦略別資金）
| カラム | 型 | 説明 |
|--------|------|------|
| strategy_type | VARCHAR | PK |
| initial_fund | DECIMAL | 初期資金 |
| current_fund | DECIMAL | 現在資金 |
| total_profit | DECIMAL | 累計損益 |
| is_active | BOOLEAN | 稼働中フラグ |

---

## 4. 戦略仕様

### 4.1 bias_1_3_2nd（3穴2nd戦略）

**コンセプト**: 1号艇が微妙に弱い状況で3号艇が2着に来やすいパターンを狙う

#### 条件
| 項目 | 値 |
|------|-----|
| 対象パターン | 15会場×レース（下記参照） |
| オッズ範囲 | 3.0〜100.0倍 |
| 賭式 | 2連単1-3 または 2連複1=3（高い方を選択） |
| 賭金 | 1,000円/レース |

#### 15パターン
```
蒲郡4R, 蒲郡5R, 江戸川4R, 平和島4R, 津4R,
三国4R, 琵琶湖4R, 住之江5R, 鳴門4R, 丸亀4R,
徳山4R, 下関4R, 若松4R, 芦屋4R, 唐津4R
```

#### 会場コード
```
03=江戸川, 04=平和島, 07=蒲郡, 09=津, 10=三国,
11=琵琶湖, 12=住之江, 14=鳴門, 15=丸亀, 18=徳山,
19=下関, 20=若松, 21=芦屋, 23=唐津
```

### 4.2 win_10x_1_3（1単勝10倍以上1-3戦略）

**コンセプト**: 1号艇の単勝オッズが10倍以上（波乱要素あり）の時に1-3を狙う

#### 条件
| 項目 | 値 |
|------|-----|
| 対象 | 全レース |
| 条件 | 1号艇の単勝オッズ ≥ 10.0倍 |
| 賭式 | 2連単1-3 |
| 賭金 | 1,000円/レース |

---

## 5. バッチ処理フロー

### 5.1 日次バッチ（6:00 JST）

```
run_batch.py
  │
  ├─ 1. 前日結果インポート（LZHファイル）
  │     └─ import_historical_data.run_yesterday_import()
  │
  ├─ 2. 過去データインポート
  │     └─ import_historical_data.run_import()
  │
  ├─ 3. 当日レース収集
  │     └─ collector.run_daily_collection()
  │
  └─ 4. 購入予定登録
        └─ virtual_betting.register_daily_bets()
              │
              ├─ bias_1_3_2nd: 15パターン該当レースを pending 登録
              └─ win_10x_1_3: 朝登録なし（締切前に直接チェック）
```

### 5.2 購入判断バッチ（毎分）

```
run_betting.py
  │
  └─ process_deadline_bets()
        │
        ├─ pendingベットの処理
        │     └─ 締切3分前のpendingを取得
        │     └─ オッズ条件チェック → confirmed/skipped
        │
        ├─ bias_1_3_2nd 直接チェック
        │     └─ 15パターン該当で締切3分以内
        │     └─ オッズ3-100倍なら confirmed
        │
        └─ win_10x_1_3 直接チェック
              └─ 締切3分以内の全レース
              └─ 1号艇単勝10倍以上なら confirmed
```

### 5.3 結果収集バッチ（毎分）

```
run_result.py
  │
  └─ process_completed_races()
        │
        ├─ confirmed ベットの結果確認
        │     └─ 締切を過ぎたレースの結果を取得
        │     └─ 的中判定 → won/lost に更新
        │
        └─ 払戻金・損益計算
              └─ profit = return_amount - bet_amount
              └─ virtual_funds テーブル更新
```

---

## 6. API仕様

### 6.1 エンドポイント一覧

| メソッド | パス | 説明 |
|---------|------|------|
| GET | /api/health | ヘルスチェック |
| GET | /api/stadiums | 競艇場一覧 |
| GET | /api/races/today | 今日のレース |
| GET | /api/races/today/with-odds | 今日のレース（オッズ付き） |
| GET | /api/stats/dashboard | ダッシュボード統計 |
| GET | /api/bets/with-results | 購入履歴（結果付き） |
| GET | /api/funds | 戦略別資金 |

### 6.2 統計API（/api/stats/dashboard）

```json
{
  "total_races_today": 180,
  "pending_bets": 11,
  "confirmed_bets": 0,
  "won_bets": 0,
  "lost_bets": 0,
  "today_profit": 0,
  "total_profit": 0,
  "total_bet_count": 0,
  "total_bet_amount": 0,  // won/lostのみ計算
  "hit_rate": 0,
  "return_rate": 0
}
```

---

## 7. ダッシュボード機能

### 7.1 累計統計（全期間）
- 購入数、的中率、回収率
- 累計損益、全回収/全投資額
- 的中/不的中/購入数

### 7.2 本日統計
- 本日のレース数、購入予定数
- 本日の的中/不的中

### 7.3 タブ機能
- **今日のレース**: オッズ付きレース一覧
- **過去のレース**: 指定日のレース確認
- **購入履歴**: confirmed/won/lost/skippedの一覧
- **資金状況**: 戦略別の稼働状況、推移

---

## 8. 検証・テスト

### 8.1 ローカルテスト

```bash
# 購入予定登録テスト
python -c "from virtual_betting import VirtualBettingManager; m = VirtualBettingManager(); m.register_daily_bets()"

# 状況確認
python check_batch.py

# DBリセット（実験初期化）
python reset_experiment.py
```

### 8.2 確認ポイント

| 項目 | 確認方法 |
|------|---------|
| レース収集 | check_batch.py で本日レース数確認 |
| 購入予定 | pending件数が15パターン中の開催分と一致 |
| 購入判断 | 締切3分前にconfirmed/skippedに変化 |
| 結果反映 | 締切後にwon/lostに変化、損益計算 |
| 統計表示 | ダッシュボードでwon/lostのみ集計 |

---

## 9. ディレクトリ構成

```
ai-auto-mailer/
├── boatrace-collector/
│   └── src/
│       ├── collector.py        # データ収集
│       ├── virtual_betting.py  # 購入ロジック
│       ├── import_historical_data.py  # 過去データ
│       ├── run_batch.py        # 日次バッチ
│       ├── run_betting.py      # 購入判断バッチ
│       ├── run_result.py       # 結果収集バッチ
│       ├── check_batch.py      # 状況確認
│       └── reset_experiment.py # 実験リセット
│
├── boatrace-dashboard/
│   ├── api.py                  # FastAPI
│   └── static/
│       └── index.html          # Vue.jsダッシュボード
│
├── VERSION_HISTORY.md          # バージョン履歴
└── requirements.txt
```

---

## 10. トラブルシューティング

### 10.1 レースが0件
- collector.pyのステータスチェック確認
- 「発売開始前」も収集対象に含める

### 10.2 購入予定が0件
- 15パターンの会場が本日開催されているか確認
- 会場コードが正しいか確認（蒲郡=07など）

### 10.3 統計にpendingが含まれる
- api.pyのget_dashboard_statsでwon/lostのみ計算

---

## 付録: 競艇場コード一覧

| コード | 名称 | コード | 名称 |
|--------|------|--------|------|
| 01 | 桐生 | 13 | 尼崎 |
| 02 | 戸田 | 14 | 鳴門 |
| 03 | 江戸川 | 15 | 丸亀 |
| 04 | 平和島 | 16 | 児島 |
| 05 | 多摩川 | 17 | 宮島 |
| 06 | 浜名湖 | 18 | 徳山 |
| 07 | 蒲郡 | 19 | 下関 |
| 08 | 常滑 | 20 | 若松 |
| 09 | 津 | 21 | 芦屋 |
| 10 | 三国 | 22 | 福岡 |
| 11 | 琵琶湖 | 23 | 唐津 |
| 12 | 住之江 | 24 | 大村 |

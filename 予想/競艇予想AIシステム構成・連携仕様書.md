# 競艇予想AIシステム構成・連携仕様書

**作成日**: 2026年1月19日  
**作成者**: Manus AI

---

## 1. システム全体構成

競艇予想AIシステムは、Render.comで稼働する複数のバッチサービスと外部データベース、およびManus Spaceでホストされるboatrace-predictorアプリケーションで構成されています。

### 1.1 Render.comサービス一覧

Render.comのスクリーンショットから確認された競艇関連サービスは以下の通りです。

| サービス名 | ランタイム | 役割 | 更新頻度 |
|-----------|----------|------|---------|
| boatrace-result-collection | Python 3 | レース結果の収集 | 1日前 |
| boatrace-odds-high-freq-worker | Python 3 | 高頻度オッズ収集（10秒刻み） | 1日前 |
| boatrace-historical-import | Python 3 | 過去データのインポート | 1日前 |
| boatrace-daily-collection | Python 3 | 日次データ収集 | 1日前 |
| boatrace-odds-regular | Python 3 | 通常オッズ収集 | 1日前 |
| kokotomo-db-staging | PostgreSQL 16 | 外部データベース（メイン） | 13日前 |

### 1.2 データフロー図

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Render.com                                       │
│                                                                         │
│  ┌─────────────────────┐    ┌─────────────────────┐                    │
│  │ boatrace-odds-      │    │ boatrace-daily-     │                    │
│  │ high-freq-worker    │    │ collection          │                    │
│  │ (10秒刻みオッズ)    │    │ (レース情報)        │                    │
│  └──────────┬──────────┘    └──────────┬──────────┘                    │
│             │                          │                                │
│             ▼                          ▼                                │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   kokotomo-db-staging                           │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────────┐ ┌─────────────┐ │   │
│  │  │   races   │ │   odds    │ │ odds_history  │ │ historical_ │ │   │
│  │  │           │ │           │ │               │ │ programs    │ │   │
│  │  └───────────┘ └───────────┘ └───────────────┘ └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ PostgreSQL接続
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Manus Space                                      │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   boatrace-predictor                            │   │
│  │                                                                 │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │   │
│  │  │ register_       │  │ realtime_       │  │ update_         │ │   │
│  │  │ pending_bets.ts │  │ virtual_        │  │ virtual_        │ │   │
│  │  │ (購入予定登録)  │  │ betting.ts      │  │ results.ts      │ │   │
│  │  │                 │  │ (締切1分前判断) │  │ (結果更新)      │ │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘ │   │
│  │                                                                 │   │
│  │  ┌─────────────────────────────────────────────────────────┐   │   │
│  │  │              内部DB (Manus TiDB)                        │   │   │
│  │  │  ┌─────────────┐  ┌─────────────┐                       │   │   │
│  │  │  │virtualFunds │  │virtualBets  │                       │   │   │
│  │  │  └─────────────┘  └─────────────┘                       │   │   │
│  │  └─────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 外部データベース（kokotomo-db-staging）

### 2.1 接続情報

```
Host: dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com
Database: kokotomo_staging
User: kokotomo_staging_user
SSL: 必須
接続タイムアウト: 60秒（Render.comの接続遅延対策）
```

### 2.2 主要テーブル構造

#### races（レース情報）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | bigint | 主キー |
| race_date | date | レース日 |
| stadium_code | smallint | 競艇場コード（01-24） |
| race_number | smallint | レース番号（1-12） |
| deadline_at | timestamp | 締切時刻 |
| is_canceled | boolean | 中止フラグ |

#### odds（最新オッズ）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | integer | 主キー |
| race_id | integer | racesテーブルへの外部キー |
| odds_type | varchar | オッズ種別（win, quinella, exacta等） |
| combination | varchar | 組み合わせ（1, 1-3, 1-3-2等） |
| odds_value | numeric | オッズ値 |
| scraped_at | timestamp | 取得時刻 |

#### odds_history（オッズ履歴）

**重要**: このテーブルが締切前のオッズ変動を記録しています。

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | integer | 主キー |
| race_date | date | レース日 |
| stadium_code | varchar | 競艇場コード |
| race_number | integer | レース番号 |
| odds_type | varchar | オッズ種別 |
| combination | varchar | 組み合わせ |
| odds_value | numeric | オッズ値 |
| minutes_to_deadline | integer | **締切何分前のデータか** |
| scraped_at | timestamp | 取得時刻 |

**odds_type の種類**:

| odds_type | 件数 | 説明 |
|-----------|------|------|
| 2t | 439,975件 | 2連単 |
| 2f | 194,876件 | 2連複 |
| place | 108,944件 | 複勝 |
| win | 54,017件 | 単勝 |
| 3t | 234件 | 3連単 |

**minutes_to_deadline の分布**:
締切0分前〜1分前のデータが最も多く、高頻度オッズ収集バッチが正常に動作していることがわかります。

| 締切前 | 件数 |
|--------|------|
| 0分前 | 40,169件 |
| 1分前 | 25,536件 |
| 2分前 | 21,295件 |
| 3分前 | 12,724件 |

#### historical_programs（過去の出走表）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| race_date | varchar | レース日（YYYYMMDD形式） |
| stadium_code | varchar | 競艇場コード |
| race_no | varchar | レース番号 |
| boat_no | varchar | 艇番 |
| racer_no | varchar | 選手登録番号 |
| racer_name | varchar | 選手名 |
| rank | varchar | 級別（A1, A2, B1, B2） |
| national_win_rate | numeric | 全国勝率 |
| local_win_rate | numeric | 当地勝率 |
| deadline_time | varchar | 締切時刻 |

#### historical_race_results（過去のレース結果）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| race_date | varchar | レース日（YYYYMMDD形式） |
| stadium_code | varchar | 競艇場コード |
| race_no | varchar | レース番号 |
| boat_no | varchar | 艇番 |
| rank | varchar | 着順 |
| race_time | varchar | レースタイム |

---

## 3. boatrace-predictorアプリケーション

### 3.1 プロジェクト構成

```
/home/ubuntu/boatrace-predictor/
├── client/                    # フロントエンド（React + Tailwind）
│   └── src/
│       └── pages/
│           └── VirtualFund.tsx  # 仮想投資ダッシュボード
├── server/
│   ├── boatraceDb.ts          # 外部DB接続モジュール
│   ├── predictionEngine.ts    # 予想エンジン
│   ├── routers.ts             # tRPC APIルーター
│   └── scripts/
│       ├── register_pending_bets.ts      # 単勝戦略：購入予定登録
│       ├── realtime_virtual_betting.ts   # 単勝戦略：締切1分前判断
│       ├── update_virtual_results.ts     # 単勝戦略：結果更新
│       ├── register_1_3_bias_bets.ts     # 1-3穴バイアス戦略：購入予定登録
│       ├── realtime_1_3_bias_betting.ts  # 1-3穴バイアス戦略：締切1分前判断
│       └── update_1_3_bias_results.ts    # 1-3穴バイアス戦略：結果更新
└── drizzle/
    └── schema.ts              # 内部DBスキーマ
```

### 3.2 内部DBスキーマ

#### virtualFunds（仮想資金）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | int | 主キー |
| userId | varchar | ユーザーID |
| strategyType | varchar | 戦略タイプ（main, bias_1_3） |
| initialFund | decimal | 初期資金 |
| currentFund | decimal | 現在資金 |
| totalBets | int | 総購入回数 |
| totalWins | int | 的中回数 |
| isActive | boolean | アクティブフラグ |

#### virtualBets（仮想購入履歴）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | int | 主キー |
| fundId | int | virtualFundsへの外部キー |
| strategyType | varchar | 戦略タイプ |
| raceDate | date | レース日 |
| stadiumCode | varchar | 競艇場コード |
| raceNumber | int | レース番号 |
| betType | varchar | 賭け式（win, quinella, exacta） |
| betTarget | varchar | 賭け対象（1, 1-3等） |
| betAmount | decimal | 賭け金額 |
| odds | decimal | オッズ |
| status | varchar | ステータス（pending, confirmed, skipped, won, lost） |
| scheduledDeadline | timestamp | 予定締切時刻 |
| decisionTime | timestamp | 購入決定時刻 |
| executedAt | timestamp | 購入実行時刻 |
| reason | json | 判断理由 |

---

## 4. バッチ処理フロー

### 4.1 単勝戦略（11R・12R 1号艇単勝）

```
[朝] register_pending_bets.ts
  │
  │  1. historical_programsから本日の11R・12Rを取得
  │  2. 1号艇の当地勝率が高いレースを抽出
  │  3. virtualBetsにstatus="pending"で登録
  │
  ▼
[締切1分前] realtime_virtual_betting.ts
  │
  │  1. pendingステータスのレースを監視
  │  2. 締切1分前になったらodds_historyから最新オッズを取得
  │  3. オッズ条件を満たせば"confirmed"、満たさなければ"skipped"
  │
  ▼
[レース終了後] update_virtual_results.ts
  │
  │  1. confirmedステータスのレースを監視
  │  2. historical_race_resultsから結果を取得
  │  3. 的中なら"won"、不的中なら"lost"に更新
  │  4. 資金を更新
```

### 4.2 1-3穴バイアス戦略

```
[朝] register_1_3_bias_bets.ts
  │
  │  1. historical_programsから本日の全レースを取得
  │  2. 1号艇の当地勝率が6.5以上のレースを抽出
  │  3. virtualBetsにstatus="pending", strategyType="bias_1_3"で登録
  │
  ▼
[締切1分前] realtime_1_3_bias_betting.ts
  │
  │  1. bias_1_3戦略のpendingレースを監視
  │  2. 締切1分前にodds_historyから1-3の2連複/2連単オッズを取得
  │  3. オッズ3.0〜30.0倍の範囲なら"confirmed"
  │  4. 2連複と2連単を期待値で比較し、高い方を選択
  │
  ▼
[レース終了後] update_1_3_bias_results.ts
  │
  │  1. bias_1_3戦略のconfirmedレースを監視
  │  2. historical_race_resultsから1着・2着を取得
  │  3. 1-3または3-1なら"won"、それ以外は"lost"
```

---

## 5. オッズデータ取得の仕組み

### 5.1 現在の問題点

現在のboatrace-predictorは、`boatraceDb.getOdds()`関数で`odds`テーブルから最新オッズを取得しています。しかし、このテーブルは**最新の1件のみ**を保持しており、締切1分前の正確なオッズを取得できない場合があります。

### 5.2 推奨される修正

`odds_history`テーブルを使用することで、締切1分前の正確なオッズを取得できます。

**修正前（boatraceDb.ts）**:
```typescript
export async function getOdds(stadiumCode, raceNumber, raceDate) {
  // oddsテーブルから取得（最新1件のみ）
  const result = await pool.query(`
    SELECT o.* FROM odds o
    JOIN races r ON o.race_id = r.id
    WHERE r.stadium_code = $1 AND r.race_number = $2 AND r.race_date = $3
  `, [stadiumCode, raceNumber, raceDate]);
  return result.rows;
}
```

**修正後（推奨）**:
```typescript
export async function getOddsAtDeadline(stadiumCode, raceNumber, raceDate, minutesBefore = 1) {
  // odds_historyから締切N分前のオッズを取得
  const formattedDate = raceDate.replace(/-/g, '');
  const result = await pool.query(`
    SELECT * FROM odds_history
    WHERE stadium_code = $1 
      AND race_number = $2 
      AND race_date = $3
      AND minutes_to_deadline = $4
    ORDER BY scraped_at DESC
  `, [stadiumCode, raceNumber, formattedDate, minutesBefore]);
  return result.rows;
}
```

---

## 6. 競艇場コード一覧

| コード | 競艇場名 | コード | 競艇場名 |
|--------|---------|--------|---------|
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
| 11 | びわこ | 23 | 唐津 |
| 12 | 住之江 | 24 | 大村 |

---

## 7. pm2でのバッチ管理

### 7.1 起動コマンド

```bash
# 単勝戦略
pm2 start npx --name "register-bets" -- tsx server/scripts/register_pending_bets.ts
pm2 start npx --name "realtime-betting" -- tsx server/scripts/realtime_virtual_betting.ts
pm2 start npx --name "result-updater" -- tsx server/scripts/update_virtual_results.ts

# 1-3穴バイアス戦略
pm2 start npx --name "bias-register" -- tsx server/scripts/register_1_3_bias_bets.ts
pm2 start npx --name "bias-realtime" -- tsx server/scripts/realtime_1_3_bias_betting.ts
pm2 start npx --name "bias-results" -- tsx server/scripts/update_1_3_bias_results.ts
```

### 7.2 管理コマンド

```bash
pm2 list                    # 全バッチの状態確認
pm2 logs <name>             # ログ確認
pm2 restart <name>          # 再起動
pm2 stop <name>             # 停止
pm2 delete <name>           # 削除
```

---

## 8. 新しい予想戦略の実装手順

1. **DBスキーマ**: `strategyType`に新しい値を追加（必要に応じて）
2. **購入予定登録バッチ**: `register_<strategy>_bets.ts`を作成
3. **締切1分前判断バッチ**: `realtime_<strategy>_betting.ts`を作成
4. **結果更新バッチ**: `update_<strategy>_results.ts`を作成
5. **フロントエンド**: `VirtualFund.tsx`の戦略選択に追加
6. **pm2で起動**: 3つのバッチをpm2で起動

---

## 9. 参考情報

- **外部DB**: Render.com kokotomo-db-staging
- **内部DB**: Manus TiDB
- **フロントエンド**: React 19 + Tailwind 4 + shadcn/ui
- **バックエンド**: Express + tRPC
- **バッチ実行**: pm2 + tsx

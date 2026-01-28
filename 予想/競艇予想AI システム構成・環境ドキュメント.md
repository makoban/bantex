# 競艇予想AI システム構成・環境ドキュメント

このドキュメントは、競艇予想AIサイトの構成、環境、バッチファイルについて説明します。他のチャットで新しい予想ロジックを実装する際の参考資料として使用してください。

---

## 1. プロジェクト概要

**プロジェクト名**: boatrace-predictor  
**プロジェクトパス**: `/home/ubuntu/boatrace-predictor`  
**技術スタック**: React 19 + Tailwind 4 + Express 4 + tRPC 11 + Drizzle ORM

このアプリは、競艇の過去データとリアルタイムオッズを分析し、予想を行う仮想投資シミュレーションシステムです。

---

## 2. ディレクトリ構成

```
/home/ubuntu/boatrace-predictor/
├── client/                    # フロントエンド（React）
│   └── src/
│       ├── pages/             # ページコンポーネント
│       │   ├── Home.tsx       # 本日のレース一覧
│       │   ├── RaceDetail.tsx # レース詳細・予想表示
│       │   ├── VirtualFund.tsx # 仮想投資ダッシュボード
│       │   ├── Results.tsx    # 結果・的中率
│       │   ├── Statistics.tsx # 統計・分析
│       │   ├── History.tsx    # 予想履歴
│       │   └── OddsAlerts.tsx # オッズアラート
│       ├── components/        # 共通コンポーネント
│       └── lib/trpc.ts        # tRPCクライアント
│
├── server/                    # バックエンド
│   ├── routers.ts             # tRPCルーター（API定義）
│   ├── db.ts                  # 内部DB接続（Drizzle）
│   ├── boatraceDb.ts          # 外部DB接続（競艇データ）★重要
│   ├── predictionEngine.ts    # 予想エンジン★重要
│   ├── storage.ts             # S3ストレージ
│   ├── _core/                 # フレームワーク（編集不要）
│   └── scripts/               # バッチスクリプト★重要
│       ├── register_pending_bets.ts    # 購入予定登録バッチ
│       ├── realtime_virtual_betting.ts # 締切1分前判断バッチ
│       ├── update_virtual_results.ts   # 結果更新バッチ
│       └── fetch_race_info.py          # pyjpboatraceラッパー
│
├── drizzle/                   # DBスキーマ
│   └── schema.ts              # テーブル定義★重要
│
└── shared/                    # 共有型定義
```

---

## 3. データベース構成

### 3.1 内部DB（Manus管理）

アプリ固有のデータを保存するMySQL/TiDBデータベース。

| テーブル名 | 用途 |
|-----------|------|
| `users` | ユーザー認証情報 |
| `predictions` | 予想結果の保存 |
| `dailyReports` | 日次レポート |
| `predictionModels` | 予想モデル設定 |
| `virtualFunds` | 仮想資金管理 |
| `virtualBets` | 仮想購入履歴 |

### 3.2 外部DB（kokotomo-db-staging）

競艇の過去データとリアルタイムデータを格納するPostgreSQLデータベース（Render.com）。

**接続情報**:
```
Host: dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com
Database: kokotomo_staging
User: kokotomo_staging_user
```

**主要テーブル**:

| テーブル名 | 用途 | データ量 |
|-----------|------|---------|
| `historical_programs` | 過去の出走表 | 約666万件 |
| `historical_race_results` | 過去のレース結果 | 大量 |
| `racer_period_stats` | 選手期別成績 | 選手数×期数 |
| `racer_period_course_stats` | 選手コース別成績 | 選手数×6コース |
| `races` | リアルタイムレース情報 | 当日分 |
| `odds` | 最新オッズ | 当日分 |
| `odds_history` | オッズ変動履歴 | 当日分 |
| `race_results` | リアルタイム結果 | 当日分 |

---

## 4. バッチスクリプト詳細

### 4.1 購入予定登録バッチ

**ファイル**: `server/scripts/register_pending_bets.ts`  
**実行タイミング**: 毎朝（レース開始前）  
**実行コマンド**:
```bash
cd /home/ubuntu/boatrace-predictor
npx tsx server/scripts/register_pending_bets.ts
```

**処理内容**:
1. 本日の全レースを外部DBから取得
2. 11R・12Rのみをフィルタリング
3. 各レースを`pending`（購入予定）ステータスでDBに登録
4. 締切時間も一緒に保存

**出力例**:
```
=== 購入予定登録バッチ ===
実行時刻: 2026/1/19 9:00:00 (JST)
対象日: 2026-01-19
対象レース: 11, 12R

仮想資金: メイン
現在の残高: ¥100,000
1回あたりの賭け金: ¥1,000

本日の対象レース数: 28件

[登録] 戸田 11R - 締切: 15:30 - 1号艇単勝 ¥1,000 (購入予定)
[登録] 戸田 12R - 締切: 16:00 - 1号艇単勝 ¥1,000 (購入予定)
...
```

### 4.2 リアルタイム仮想投資バッチ（締切1分前判断）

**ファイル**: `server/scripts/realtime_virtual_betting.ts`  
**実行タイミング**: 常時稼働（pm2で管理）  
**実行コマンド**:
```bash
# 単発実行
npx tsx server/scripts/realtime_virtual_betting.ts

# pm2で常時稼働
pm2 start npx --name "virtual-betting" -- tsx server/scripts/realtime_virtual_betting.ts
```

**処理内容**:
1. 10秒ごとに`pending`ステータスのレースをチェック
2. 締切1分前〜0分前のレースを検出
3. 最終オッズを取得
4. オッズ条件をチェック（1.6〜10倍）
5. 条件を満たせば`confirmed`（購入確定）、満たさなければ`skipped`（見送り）に更新
6. 資金を減算

**戦略設定**（コード内で定義）:
```typescript
const STRATEGY = {
  name: "11R12R_Win_Strategy",
  minOdds: 1.6,           // 最低オッズ
  maxOdds: 10.0,          // 最高オッズ
  expectedHitRate11R: 0.667,  // 11Rの期待的中率
  expectedHitRate12R: 0.715,  // 12Rの期待的中率
};
```

### 4.3 結果更新バッチ

**ファイル**: `server/scripts/update_virtual_results.ts`  
**実行タイミング**: 常時稼働（pm2で管理）  
**実行コマンド**:
```bash
# 単発実行
npx tsx server/scripts/update_virtual_results.ts 2026-01-19

# 監視モード（30秒ごとにチェック）
npx tsx server/scripts/update_virtual_results.ts --watch

# pm2で常時稼働
pm2 start npx --name "result-updater" -- tsx server/scripts/update_virtual_results.ts --watch
```

**処理内容**:
1. `confirmed`ステータスの購入を取得
2. 外部DBからレース結果を取得
3. 的中/不的中を判定
4. ステータスを`won`または`lost`に更新
5. 仮想資金の残高を更新

---

## 5. 予想エンジン

**ファイル**: `server/predictionEngine.ts`

### 5.1 スコア計算要素

| 要素 | 重み | 説明 |
|------|------|------|
| 全国勝率 | 30% | 選手の全国での勝率 |
| 当地勝率 | 10% | 選手のその競艇場での勝率 |
| コース別1着率 | 25% | 選手のそのコースでの1着率 |
| モーター2連率 | 20% | モーターの2連対率 |
| ボート2連率 | 5% | ボートの2連対率 |
| 平均ST | 10% | スタートタイミング |

### 5.2 級別ボーナス

| 級別 | ボーナス倍率 |
|------|-------------|
| A1 | 1.5倍 |
| A2 | 1.2倍 |
| B1 | 1.0倍 |
| B2 | 0.8倍 |

### 5.3 使用方法

```typescript
import { calculatePrediction } from "./predictionEngine";

const result = await calculatePrediction(
  "02",      // 競艇場コード（戸田）
  11,        // レース番号
  "2026-01-19"  // 日付
);

console.log(result.ranking);        // 予想順位 [1, 3, 2, 4, 5, 6]
console.log(result.recommendedBets); // 推奨買い目
console.log(result.oddsAlerts);     // オッズ変動アラート
```

---

## 6. 外部DB接続（boatraceDb.ts）

**ファイル**: `server/boatraceDb.ts`

### 6.1 主要関数

| 関数名 | 用途 | 戻り値 |
|--------|------|--------|
| `getTodayRaces(date?)` | 本日のレース一覧取得 | `Race[]` |
| `getRaceEntries(stadium, race, date)` | 出走表取得 | `RaceEntry[]` |
| `getOdds(stadium, race, date)` | オッズ取得 | `Odds[]` |
| `getOddsHistory(stadium, race, date)` | オッズ履歴取得 | `OddsHistory[]` |
| `getRaceResults(stadium, race, date)` | レース結果取得 | `RaceResult` |
| `getRaceDeadline(stadium, race, date)` | 締切時間取得 | `Date` |
| `getRacerCourseStats(racerNo, course)` | 選手コース別成績 | `RacerCourseStats` |

### 6.2 接続設定

```typescript
const pool = new Pool({
  connectionString: EXTERNAL_DB_URL,
  ssl: { rejectUnauthorized: false },
  max: 10,
  idleTimeoutMillis: 60000,
  connectionTimeoutMillis: 60000,  // Render.comは接続が遅い
});
```

---

## 7. DBスキーマ（virtualBets）

仮想購入履歴の主要カラム:

```typescript
virtualBets = {
  id: int,
  fundId: int,                    // 仮想資金ID
  raceDate: date,                 // レース日
  stadiumCode: varchar(2),        // 競艇場コード
  raceNumber: int,                // レース番号
  stadiumName: varchar(20),       // 競艇場名
  betType: varchar(20),           // win, exacta, etc.
  combination: varchar(20),       // "1", "1-2", etc.
  betAmount: decimal,             // 賭け金
  odds: decimal,                  // オッズ
  reason: json,                   // 購入理由（戦略、期待値、見送り理由など）
  scheduledDeadline: timestamp,   // 締切時間
  decisionTime: timestamp,        // 購入決定時間
  executedAt: timestamp,          // 購入実行時間
  resultConfirmedAt: timestamp,   // 結果確定時間
  status: enum,                   // pending/confirmed/skipped/won/lost/cancelled
  actualResult: varchar(20),      // 実際の結果
  payoff: decimal,                // 払戻金
  returnAmount: decimal,          // 回収額
  profit: decimal,                // 損益
  fundBefore: decimal,            // 購入前残高
  fundAfter: decimal,             // 購入後残高
}
```

---

## 8. pm2でのバッチ管理

### 8.1 現在稼働中のバッチ

```bash
pm2 list
```

| 名前 | スクリプト | 説明 |
|------|-----------|------|
| virtual-betting | realtime_virtual_betting.ts | 締切1分前判断 |
| result-updater | update_virtual_results.ts | 結果更新 |

### 8.2 バッチの操作

```bash
# 起動
pm2 start npx --name "バッチ名" -- tsx server/scripts/スクリプト名.ts

# 停止
pm2 stop バッチ名

# 再起動
pm2 restart バッチ名

# ログ確認
pm2 logs バッチ名 --lines 50

# 削除
pm2 delete バッチ名
```

---

## 9. 新しい予想ロジックの実装手順

### 9.1 予想エンジンを修正する場合

1. `server/predictionEngine.ts`を編集
2. 重みやスコア計算ロジックを変更
3. サーバーを再起動（`pm2 restart all`）

### 9.2 新しいバッチを追加する場合

1. `server/scripts/`に新しいTypeScriptファイルを作成
2. 必要な関数を`boatraceDb.ts`からインポート
3. DBアクセスは`getDb()`で内部DB、`getPool()`で外部DBに接続
4. pm2で起動

### 9.3 DBスキーマを変更する場合

1. `drizzle/schema.ts`を編集
2. マイグレーション実行:
   ```bash
   cd /home/ubuntu/boatrace-predictor
   pnpm db:push
   ```

---

## 10. 競艇場コード一覧

| コード | 競艇場 | コード | 競艇場 |
|--------|--------|--------|--------|
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

## 11. 注意事項

1. **外部DB接続**: Render.comのDBは接続に時間がかかる場合があります（最大60秒）。タイムアウト設定に注意してください。

2. **kokotomo-db-staging**: 外部DBは必ず`kokotomo-db-staging`を使用してください。`kokotomo-db`は使用しないでください。

3. **バッチの重複実行**: pm2でバッチを起動する前に、既存のプロセスがないか確認してください。

4. **日付形式**: 外部DBの`historical_*`テーブルは`YYYYMMDD`形式、`races`テーブルは`YYYY-MM-DD`形式です。

---

**作成日**: 2026年1月19日  
**作成者**: Manus AI

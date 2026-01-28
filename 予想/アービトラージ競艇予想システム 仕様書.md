# アービトラージ競艇予想システム 仕様書

**作成日**: 2026年1月4日  
**バージョン**: 1.0  
**作成者**: Manus AI

---

## 1. システム概要

本システムは、競艇の公式データを収集・蓄積し、AIによるオッズの歪み検知と最適な予想を提供することを目的としています。データ収集バッチ処理とWebフロントエンドの2つのコンポーネントで構成されています。

### 1.1 システム構成図

```
┌─────────────────────────────────────────────────────────────────────┐
│                        データソース                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ 公式サイト        │  │ 公式LZHファイル   │  │ 外部予想サイト    │  │
│  │ (リアルタイム)    │  │ (過去データ)      │  │ (参考情報)        │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │
└───────────┼──────────────────────┼──────────────────────┼───────────┘
            │                      │                      │
            ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Render (バッチ処理)                               │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Cron Jobs                                                     │  │
│  │ ・daily-collection (毎朝8:00 JST)                             │  │
│  │ ・odds-regular (10分ごと)                                     │  │
│  │ ・odds-high-freq (1分ごと、締切5分前から10秒間隔)              │  │
│  │ ・result-collection (15分ごと)                                │  │
│  │ ・historical-import (毎日3:00 UTC)                            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ PostgreSQL (kokotomo_staging)                                 │  │
│  │ ・リアルタイムデータ                                           │  │
│  │ ・過去データ (2005年〜)                                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Manus (フロントエンド)                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Webアプリケーション                                            │  │
│  │ ・ダッシュボード                                               │  │
│  │ ・レース一覧                                                   │  │
│  │ ・レーサー検索                                                 │  │
│  │ ・予想情報                                                     │  │
│  │ ・データ監視                                                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 環境情報

### 2.1 インフラ構成

| コンポーネント | ホスティング | リージョン | 備考 |
|---------------|-------------|-----------|------|
| **フロントエンド** | Manus | Singapore | React + tRPC |
| **バッチ処理** | Render Cron Jobs | Singapore | Python 3 |
| **データベース** | Render PostgreSQL | Singapore | kokotomo_staging |

### 2.2 リポジトリ

| リポジトリ名 | URL | 内容 |
|-------------|-----|------|
| `makoban/ai-auto-mailer` | https://github.com/makoban/ai-auto-mailer | バッチ処理（データ収集） |
| `makoban/arbitrage-boatrace` | https://github.com/makoban/arbitrage-boatrace | フロントエンド（Webアプリ） |

### 2.3 データベース接続情報

| 項目 | 値 |
|------|-----|
| **ホスト** | dpg-ct76h3ij1k6c73b3utpg-a.singapore-postgres.render.com |
| **データベース名** | kokotomo_staging |
| **ユーザー** | kokotomo_staging_user |
| **ポート** | 5432 |
| **SSL** | 必須 |

---

## 3. データベース構造

### 3.1 テーブル一覧

本システムでは、以下のテーブルを使用してデータを管理しています。

| テーブル名 | 用途 | データソース | 収集バッチ |
|-----------|------|-------------|-----------|
| `races` | 当日レース情報 | 公式サイト | daily-collection |
| `odds` | 定期オッズ（10分間隔） | 公式サイト | odds-regular |
| `odds_history` | 高頻度オッズ（10秒間隔） | 公式サイト | odds-high-freq |
| `race_results` | レース結果（着順） | 公式サイト | result-collection |
| `payoffs` | 払戻金 | 公式サイト | result-collection |
| `historical_race_results` | 過去競走成績（2005年〜） | 公式LZH (K) | historical-import |
| `historical_programs` | 過去番組表（2005年〜） | 公式LZH (B) | historical-import |
| `historical_import_progress` | インポート進捗管理 | - | historical-import |
| `boatrace_entries` | 出走表（選手情報） | 公式サイト | daily-collection |
| `boatrace_beforeinfo` | 直前情報 | 公式サイト | **未実装** |
| `boatrace_weather` | 水面気象情報 | 公式サイト | **未実装** |
| `web_predictions` | 外部予想情報 | 外部サイト | **未実装** |
| `stadiums` | 競艇場マスター | 初期データ | - |

### 3.2 リアルタイムデータテーブル

#### 3.2.1 races（レーステーブル）

当日のレース情報を管理します。

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | SERIAL | 主キー |
| race_date | DATE | レース日 |
| stadium_code | INT | 競艇場コード（1〜24） |
| race_number | INT | レース番号（1〜12） |
| title | VARCHAR(100) | レースタイトル |
| deadline_at | TIMESTAMP | 締切時刻 |
| created_at | TIMESTAMP | 作成日時 |
| updated_at | TIMESTAMP | 更新日時 |

#### 3.2.2 odds（定期オッズテーブル）

10分間隔で収集されるオッズデータを保存します。

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | SERIAL | 主キー |
| race_id | INT | レースID（races.id） |
| scraped_at | TIMESTAMP | 収集日時 |
| odds_type | VARCHAR(20) | オッズ種別（exacta, quinella, win, place_show） |
| combination | VARCHAR(20) | 組み合わせ（例: "1-2", "1"） |
| odds_value | DECIMAL(10,2) | オッズ値 |
| odds_min | DECIMAL(10,2) | 最小オッズ（複勝用） |
| odds_max | DECIMAL(10,2) | 最大オッズ（複勝用） |

**odds_type の種別:**

| odds_type | 説明 | 組み合わせ例 |
|-----------|------|-------------|
| exacta | 2連単 | "1-2", "3-4" |
| quinella | 2連複 | "1-2", "3-4" |
| win | 単勝 | "1", "2" |
| place_show | 複勝 | "1", "2" |

#### 3.2.3 odds_history（高頻度オッズテーブル）

締切5分前から10秒間隔で収集されるオッズデータを保存します。

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | SERIAL | 主キー |
| race_date | DATE | レース日 |
| stadium_code | VARCHAR(2) | 競艇場コード |
| race_number | INT | レース番号 |
| odds_type | VARCHAR(10) | オッズ種別 |
| combination | VARCHAR(10) | 組み合わせ |
| odds_value | DECIMAL(10,1) | オッズ値 |
| odds_min | DECIMAL(10,1) | 最小オッズ |
| odds_max | DECIMAL(10,1) | 最大オッズ |
| scraped_at | TIMESTAMP | 収集日時 |
| minutes_to_deadline | INT | 締切までの残り分数 |
| created_at | TIMESTAMP | 作成日時 |

#### 3.2.4 race_results（レース結果テーブル）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | SERIAL | 主キー |
| race_id | INT | レースID |
| first_place | INT | 1着艇番 |
| second_place | INT | 2着艇番 |
| third_place | INT | 3着艇番 |
| fourth_place | INT | 4着艇番 |
| fifth_place | INT | 5着艇番 |
| sixth_place | INT | 6着艇番 |
| created_at | TIMESTAMP | 作成日時 |
| updated_at | TIMESTAMP | 更新日時 |

#### 3.2.5 payoffs（払戻金テーブル）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | SERIAL | 主キー |
| race_id | INT | レースID |
| bet_type | VARCHAR(20) | 賭式（2t, 2f, win, place） |
| combination | VARCHAR(20) | 組み合わせ |
| payoff | INT | 払戻金（円） |
| popularity | INT | 人気順位（NULL可） |

### 3.3 過去データテーブル

#### 3.3.1 historical_race_results（過去競走成績テーブル）

公式LZHファイル（Kファイル）から取得した2005年以降の競走成績を保存します。

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | SERIAL | 主キー |
| race_date | VARCHAR(8) | レース日（YYYYMMDD） |
| stadium_code | VARCHAR(2) | 競艇場コード |
| race_no | VARCHAR(2) | レース番号 |
| boat_no | VARCHAR(1) | 艇番 |
| racer_no | VARCHAR(4) | 選手登録番号 |
| rank | VARCHAR(2) | 着順 |
| race_time | VARCHAR(10) | レースタイム |
| created_at | TIMESTAMP | 作成日時 |

**ユニーク制約:** (race_date, stadium_code, race_no, boat_no)

#### 3.3.2 historical_programs（過去番組表テーブル）

公式LZHファイル（Bファイル）から取得した番組表データを保存します。選手情報、勝率、モーター・ボート情報を含みます。

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | SERIAL | 主キー |
| race_date | VARCHAR(8) | レース日（YYYYMMDD） |
| stadium_code | VARCHAR(2) | 競艇場コード |
| race_no | VARCHAR(2) | レース番号 |
| boat_no | VARCHAR(1) | 艇番 |
| racer_no | VARCHAR(4) | 選手登録番号 |
| racer_name | VARCHAR(20) | 選手名 |
| age | INT | 年齢 |
| branch | VARCHAR(10) | 支部 |
| weight | INT | 体重 |
| rank | VARCHAR(2) | 級別（A1, A2, B1, B2） |
| national_win_rate | DECIMAL(5,2) | 全国勝率 |
| national_2nd_rate | DECIMAL(5,2) | 全国2連率 |
| local_win_rate | DECIMAL(5,2) | 当地勝率 |
| local_2nd_rate | DECIMAL(5,2) | 当地2連率 |
| motor_no | INT | モーター番号 |
| motor_2nd_rate | DECIMAL(5,2) | モーター2連率 |
| boat_no_assigned | INT | ボート番号 |
| boat_2nd_rate | DECIMAL(5,2) | ボート2連率 |
| deadline_time | VARCHAR(10) | 締切時刻 |
| created_at | TIMESTAMP | 作成日時 |

**ユニーク制約:** (race_date, stadium_code, race_no, boat_no)

#### 3.3.3 historical_import_progress（インポート進捗管理テーブル）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | SERIAL | 主キー |
| task_type | VARCHAR(50) | タスク種別 |
| year_month | VARCHAR(6) | 対象年月（YYYYMM） |
| status | VARCHAR(20) | ステータス（pending, running, completed, failed） |
| processed_count | INT | 処理件数 |
| error_message | TEXT | エラーメッセージ |
| started_at | TIMESTAMP | 開始日時 |
| completed_at | TIMESTAMP | 完了日時 |

---

## 4. バッチ処理

### 4.1 バッチ一覧

| バッチ名 | スケジュール | 処理内容 |
|---------|-------------|---------|
| **boatrace-daily-collection** | 毎日 08:00 JST | 当日レース情報・出走表の収集 |
| **boatrace-odds-regular** | 10分ごと (08:00-21:59 JST) | 定期オッズ収集 |
| **boatrace-odds-high-freq** | 1分ごと (08:00-22:00 JST) | 高頻度オッズ収集（締切5分前から10秒間隔） |
| **boatrace-result-collection** | 15分ごと (08:00-22:59 JST) | レース結果・払戻金の収集 |
| **boatrace-historical-import** | 毎日 03:00 UTC (12:00 JST) | 過去データのダウンロード・インポート |

### 4.2 バッチ詳細

#### 4.2.1 daily-collection（日次収集）

**実行コマンド:** `python cron_jobs.py daily`

**処理フロー:**
1. 当日の開催場を取得
2. 各場の全レース情報（1R〜12R）を取得
3. 締切時刻をスクレイピングで取得
4. `races`テーブルに保存
5. 出走表（選手情報）を取得
6. `boatrace_entries`テーブルに保存

**保存先テーブル:** `races`, `boatrace_entries`

#### 4.2.2 odds-regular（定期オッズ収集）

**実行コマンド:** `python cron_jobs.py odds_regular`

**処理フロー:**
1. 未終了レースを取得
2. 各レースの2連単・2連複・単勝・複勝オッズを取得
3. `odds`テーブルに保存

**保存先テーブル:** `odds`

**収集対象オッズ:**
- 2連単（exacta）: 30通り
- 2連複（quinella）: 15通り
- 単勝（win）: 6通り
- 複勝（place_show）: 6通り

#### 4.2.3 odds-high-freq（高頻度オッズ収集）

**実行コマンド:** `python cron_jobs.py odds_high_freq`

**処理フロー:**
1. 締切5分以内のレースを検出
2. 10秒間隔で9回（約90秒間）オッズを収集
3. `odds_history`テーブルに保存

**保存先テーブル:** `odds_history`

**設定パラメータ:**
- タイムアウト: 15秒
- リトライ: 1回
- 収集間隔: 10秒
- 収集回数: 9回/レース

#### 4.2.4 result-collection（結果収集）

**実行コマンド:** `python cron_jobs.py result`

**処理フロー:**
1. 結果未取得のレースを検索
2. 公式サイトから結果を取得
3. `race_results`テーブルに着順を保存
4. `payoffs`テーブルに払戻金を保存

**保存先テーブル:** `race_results`, `payoffs`

#### 4.2.5 historical-import（過去データインポート）

**実行コマンド:** `python import_historical_data.py all`

**処理フロー:**
1. 進捗管理テーブルから未処理月を取得
2. 競走成績（K）ファイルをダウンロード
3. 番組表（B）ファイルをダウンロード
4. LZHファイルを解凍（lhafile使用）
5. テキストファイルをパース
6. `historical_race_results`テーブルに保存
7. `historical_programs`テーブルに保存

**保存先テーブル:** `historical_race_results`, `historical_programs`

**データソース:**
- 競走成績: `https://www1.mbrace.or.jp/od2/K/YYYYMM/kYYMMDD.lzh`
- 番組表: `https://www1.mbrace.or.jp/od2/B/YYYYMM/bYYMMDD.lzh`

---

## 5. インポート進捗状況

### 5.1 過去データインポート進捗（2026年1月4日時点）

| タスク | 対象期間 | 完了 | 進行中 | 残り |
|--------|---------|------|--------|------|
| 競走成績ダウンロード | 2005年1月〜2025年12月 | 12ヶ月 | 2006年1月 | 235ヶ月 |
| 競走成績インポート | 同上 | 0ヶ月 | - | 247ヶ月 |
| 番組表ダウンロード | 同上 | 0ヶ月 | - | 247ヶ月 |
| 番組表インポート | 同上 | 0ヶ月 | - | 247ヶ月 |

**推定完了時間:** 約20〜30時間（1ヶ月あたり約5分）

### 5.2 リアルタイムデータ収集状況

| データ | 状態 | 備考 |
|--------|------|------|
| レース情報 | ✅ 収集中 | 毎朝自動更新 |
| 定期オッズ | ✅ 収集中 | 10分間隔 |
| 高頻度オッズ | ✅ 収集中 | 締切5分前から10秒間隔、成功率約52%→改善中 |
| レース結果 | ✅ 収集中 | 15分間隔 |
| 払戻金 | ✅ 収集中 | 15分間隔 |

---

## 6. 今後の実装予定

### 6.1 未実装データ（追加予定）

| データ | 取得元 | 優先度 | 用途 |
|--------|--------|--------|------|
| **展示タイム** | 番組表（B）に含まれる | 高 | レース直前の実力指標 |
| **スタート展示** | 直前情報ページ | 高 | スタートタイミング傾向 |
| **水面状況（風・波）** | 直前情報ページ | 高 | コンディション分析 |
| **レーサー期別成績** | 公式LZH（別URL） | 高 | 選手の長期成績 |
| **モーター詳細成績** | 番組表（B）に含まれる | 中 | 機力分析 |
| **ボート詳細成績** | 番組表（B）に含まれる | 中 | 艇体分析 |
| **外部予想情報** | 競艇日和など | 低 | 参考情報 |

### 6.2 実装ロードマップ

**Phase 1（完了）:**
- [x] 基本的なデータ収集バッチ
- [x] 定期オッズ収集
- [x] 高頻度オッズ収集
- [x] 過去データインポート（競走成績）
- [x] 過去データインポート（番組表）

**Phase 2（進行中）:**
- [ ] 過去データの完全インポート（2005年〜2025年）
- [ ] 高頻度オッズ収集の成功率改善

**Phase 3（予定）:**
- [ ] 直前情報（展示タイム、スタート展示）の収集
- [ ] 水面状況の収集
- [ ] レーサー期別成績の収集

**Phase 4（予定）:**
- [ ] AI予想モデルの構築
- [ ] オッズの歪み検知アルゴリズム
- [ ] 予想結果の検証システム

---

## 7. 競艇場コード一覧

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

## 8. 技術スタック

### 8.1 バッチ処理

| 項目 | 技術 |
|------|------|
| 言語 | Python 3 |
| データベース接続 | psycopg2 |
| スクレイピング | BeautifulSoup4, requests |
| 競艇データ取得 | pyjpboatrace |
| LZH解凍 | lhafile |
| スケジューリング | Render Cron Jobs |

### 8.2 フロントエンド

| 項目 | 技術 |
|------|------|
| フレームワーク | React 19 |
| スタイリング | Tailwind CSS 4 |
| API | tRPC 11 |
| サーバー | Express 4 |
| ORM | Drizzle |
| 認証 | Manus OAuth |

---

## 9. 参考リンク

- [公式データダウンロード](https://www1.mbrace.or.jp/od2/)
- [競艇公式サイト](https://www.boatrace.jp/)
- [pyjpboatrace GitHub](https://github.com/hmasdev/pyjpboatrace)
- [Render Dashboard](https://dashboard.render.com/)

---

**更新履歴:**

| 日付 | バージョン | 内容 |
|------|-----------|------|
| 2026-01-04 | 1.0 | 初版作成 |

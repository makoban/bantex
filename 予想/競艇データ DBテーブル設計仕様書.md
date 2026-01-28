# 競艇データ DBテーブル設計仕様書

**作成日**: 2026-01-05  
**バージョン**: 1.0

---

## 目次

1. [概要](#概要)
2. [データソース一覧](#データソース一覧)
3. [テーブル設計](#テーブル設計)
   - [レーサー期別成績テーブル](#1-レーサー期別成績テーブル)
   - [レーサーコース別成績テーブル](#2-レーサーコース別成績テーブル)
   - [過去レース結果テーブル](#3-過去レース結果テーブル)
   - [過去番組表テーブル](#4-過去番組表テーブル)
4. [インデックス設計](#インデックス設計)
5. [バッチ処理設計](#バッチ処理設計)

---

## 概要

本仕様書は、競艇公式サイトからダウンロード可能なデータをPostgreSQLデータベースに格納するためのテーブル設計を定義する。

### 対象データ

| データ種別 | ソースファイル | 提供期間 | 更新頻度 |
|-----------|---------------|----------|----------|
| レーサー期別成績（ファン手帳） | fan{YY}{MM}.lzh | 2002年〜 | 年2回（前期/後期） |
| 競走成績 | k{YYMM}{DD}.lzh | 2005年〜 | 日次 |
| 番組表 | b{YYMM}{DD}.lzh | 2005年〜 | 日次 |

---

## データソース一覧

### 1. レーサー期別成績（ファン手帳）

- **URL**: `https://www.boatrace.jp/static_extra/pc_static/download/data/kibetsu/fan{YY}{MM}.lzh`
- **形式**: LZH圧縮、固定長テキスト（Shift-JIS）
- **レコード長**: 約420バイト/行
- **公式レイアウト**: https://www.boatrace.jp/owpc/pc/extra/data/layout.html

### 2. 競走成績（Kファイル）

- **URL**: `https://www1.mbrace.or.jp/od2/K/{YYYYMM}/k{YYMM}{DD}.lzh`
- **形式**: LZH圧縮、固定長テキスト（Shift-JIS）
- **内容**: 各レースの着順・タイム情報

### 3. 番組表（Bファイル）

- **URL**: `https://www1.mbrace.or.jp/od2/B/{YYYYMM}/b{YYMM}{DD}.lzh`
- **形式**: LZH圧縮、テキスト（Shift-JIS）
- **内容**: 出走表（選手情報、勝率、モーター/ボート成績）

---

## テーブル設計

### 1. レーサー期別成績テーブル

**テーブル名**: `racer_period_stats`

レーサーの期別（前期/後期）の成績を格納する。

| カラム名 | データ型 | NULL | 説明 | ソース位置(バイト) |
|---------|---------|------|------|-------------------|
| id | SERIAL | NO | 主キー | - |
| racer_no | VARCHAR(4) | NO | 登録番号 | 1-4 |
| data_year | INTEGER | NO | データ年 | 171-174 |
| data_period | INTEGER | NO | 期（1:前期, 2:後期） | 175 |
| name_kanji | VARCHAR(20) | YES | 氏名（漢字） | 5-20 |
| name_kana | VARCHAR(20) | YES | 氏名（カナ） | 21-35 |
| branch | VARCHAR(10) | YES | 支部 | 36-39 |
| rank | VARCHAR(2) | YES | 級別（A1/A2/B1/B2） | 40-41 |
| birth_era | VARCHAR(1) | YES | 年号（S:昭和, H:平成, R:令和） | 42 |
| birth_date_raw | VARCHAR(6) | YES | 生年月日（YYMMDD） | 43-48 |
| gender | INTEGER | YES | 性別（1:男, 2:女） | 49 |
| age | INTEGER | YES | 年齢 | 50-51 |
| height | INTEGER | YES | 身長（cm） | 52-54 |
| weight | INTEGER | YES | 体重（kg） | 55-56 |
| blood_type | VARCHAR(2) | YES | 血液型 | 57-58 |
| win_rate | DECIMAL(5,2) | YES | 勝率 | 59-62 |
| place_rate | DECIMAL(5,1) | YES | 複勝率（2連対率） | 63-66 |
| first_count | INTEGER | YES | 1着回数 | 67-69 |
| second_count | INTEGER | YES | 2着回数 | 70-72 |
| race_count | INTEGER | YES | 出走回数 | 73-75 |
| final_count | INTEGER | YES | 優出回数 | 76-77 |
| win_count | INTEGER | YES | 優勝回数 | 78-79 |
| avg_start_timing | DECIMAL(4,2) | YES | 平均スタートタイミング | 80-82 |
| prev_rank | VARCHAR(2) | YES | 前期級別 | 161-162 |
| prev2_rank | VARCHAR(2) | YES | 前々期級別 | 163-164 |
| prev3_rank | VARCHAR(2) | YES | 前々々期級別 | 165-166 |
| prev_ability_index | DECIMAL(5,2) | YES | 前期能力指数 | 167-170 |
| current_ability_index | DECIMAL(5,2) | YES | 今期能力指数 | 171-174 |
| calc_start_date | VARCHAR(8) | YES | 算出期間（自）YYYYMMDD | 176-183 |
| calc_end_date | VARCHAR(8) | YES | 算出期間（至）YYYYMMDD | 184-191 |
| training_period | INTEGER | YES | 養成期 | 192-194 |
| birthplace | VARCHAR(10) | YES | 出身地 | 399-404 |
| created_at | TIMESTAMP | YES | 作成日時 | - |

**制約**:
- PRIMARY KEY: `id`
- UNIQUE: `(racer_no, data_year, data_period)`

---

### 2. レーサーコース別成績テーブル

**テーブル名**: `racer_period_course_stats`

レーサーのコース別（1〜6コース）詳細成績を格納する。

| カラム名 | データ型 | NULL | 説明 | 備考 |
|---------|---------|------|------|------|
| id | SERIAL | NO | 主キー | - |
| racer_no | VARCHAR(4) | NO | 登録番号 | FK参照用 |
| data_year | INTEGER | NO | データ年 | |
| data_period | INTEGER | NO | 期（1:前期, 2:後期） | |
| course | INTEGER | NO | コース番号（1-6） | |
| entry_count | INTEGER | YES | 進入回数 | |
| place_rate | DECIMAL(5,1) | YES | 複勝率 | |
| avg_st | DECIMAL(4,2) | YES | 平均スタートタイミング | |
| avg_st_rank | DECIMAL(4,2) | YES | 平均スタート順位 | |
| rank1 | INTEGER | YES | 1着回数 | |
| rank2 | INTEGER | YES | 2着回数 | |
| rank3 | INTEGER | YES | 3着回数 | |
| rank4 | INTEGER | YES | 4着回数 | |
| rank5 | INTEGER | YES | 5着回数 | |
| rank6 | INTEGER | YES | 6着回数 | |
| flying | INTEGER | YES | フライング回数 | |
| late0 | INTEGER | YES | 出遅れ0回数 | |
| late1 | INTEGER | YES | 出遅れ1回数 | |
| absent0 | INTEGER | YES | 欠場0回数 | |
| absent1 | INTEGER | YES | 欠場1回数 | |
| disq0 | INTEGER | YES | 失格0回数 | |
| disq1 | INTEGER | YES | 失格1回数 | |
| disq2 | INTEGER | YES | 失格2回数 | |
| created_at | TIMESTAMP | YES | 作成日時 | |

**制約**:
- PRIMARY KEY: `id`
- UNIQUE: `(racer_no, data_year, data_period, course)`

---

### 3. 過去レース結果テーブル

**テーブル名**: `historical_race_results`

過去の競走成績（着順・タイム）を格納する。

| カラム名 | データ型 | NULL | 説明 | ソース位置 |
|---------|---------|------|------|-----------|
| id | SERIAL | NO | 主キー | - |
| race_date | VARCHAR(8) | NO | レース日（YYYYMMDD） | 1-8 |
| stadium_code | VARCHAR(2) | NO | 競艇場コード（01-24） | 9-10 |
| race_no | VARCHAR(2) | NO | レース番号（01-12） | 11-12 |
| boat_no | VARCHAR(1) | YES | 艇番（1-6） | 13 |
| racer_no | VARCHAR(4) | YES | 登録番号 | 14-17 |
| rank | VARCHAR(2) | YES | 着順（1-6, F, L, K, S等） | 18 |
| race_time | VARCHAR(10) | YES | レースタイム | 19-24 |
| created_at | TIMESTAMP | YES | 作成日時 | - |

**制約**:
- PRIMARY KEY: `id`
- UNIQUE: `(race_date, stadium_code, race_no, boat_no)`

**補足**: Kファイルのフォーマットは公式に公開されていないため、実データ解析に基づく。

---

### 4. 過去番組表テーブル

**テーブル名**: `historical_programs`

過去の番組表（出走表）情報を格納する。

| カラム名 | データ型 | NULL | 説明 | 備考 |
|---------|---------|------|------|------|
| id | SERIAL | NO | 主キー | - |
| race_date | VARCHAR(8) | NO | レース日（YYYYMMDD） | ファイル名から取得 |
| stadium_code | VARCHAR(2) | NO | 競艇場コード（01-24） | BBGN行から取得 |
| race_no | VARCHAR(2) | NO | レース番号（01-12） | |
| boat_no | VARCHAR(1) | NO | 艇番（1-6） | |
| racer_no | VARCHAR(4) | YES | 登録番号 | |
| racer_name | VARCHAR(20) | YES | 選手名 | |
| age | INTEGER | YES | 年齢 | |
| branch | VARCHAR(10) | YES | 支部 | |
| weight | INTEGER | YES | 体重（kg） | |
| rank | VARCHAR(2) | YES | 級別（A1/A2/B1/B2） | |
| national_win_rate | DECIMAL(5,2) | YES | 全国勝率 | |
| national_2nd_rate | DECIMAL(5,2) | YES | 全国2連対率 | |
| local_win_rate | DECIMAL(5,2) | YES | 当地勝率 | |
| local_2nd_rate | DECIMAL(5,2) | YES | 当地2連対率 | |
| motor_no | INTEGER | YES | モーター番号 | |
| motor_2nd_rate | DECIMAL(5,2) | YES | モーター2連対率 | |
| boat_no_assigned | INTEGER | YES | ボート番号 | |
| boat_2nd_rate | DECIMAL(5,2) | YES | ボート2連対率 | |
| deadline_time | VARCHAR(10) | YES | 締切時刻（HH:MM） | |
| created_at | TIMESTAMP | YES | 作成日時 | - |

**制約**:
- PRIMARY KEY: `id`
- UNIQUE: `(race_date, stadium_code, race_no, boat_no)`

---

## インデックス設計

### racer_period_stats

```sql
CREATE INDEX idx_racer_period_stats_racer_no ON racer_period_stats(racer_no);
CREATE INDEX idx_racer_period_stats_year_period ON racer_period_stats(data_year, data_period);
CREATE INDEX idx_racer_period_stats_rank ON racer_period_stats(rank);
CREATE INDEX idx_racer_period_stats_branch ON racer_period_stats(branch);
```

### racer_period_course_stats

```sql
CREATE INDEX idx_racer_period_course_stats_racer_no ON racer_period_course_stats(racer_no);
CREATE INDEX idx_racer_period_course_stats_year_period ON racer_period_course_stats(data_year, data_period);
```

### historical_race_results

```sql
CREATE INDEX idx_hist_results_date ON historical_race_results(race_date);
CREATE INDEX idx_hist_results_racer ON historical_race_results(racer_no);
CREATE INDEX idx_hist_results_stadium ON historical_race_results(stadium_code);
CREATE INDEX idx_hist_results_date_stadium ON historical_race_results(race_date, stadium_code);
```

### historical_programs

```sql
CREATE INDEX idx_hist_programs_date ON historical_programs(race_date);
CREATE INDEX idx_hist_programs_racer ON historical_programs(racer_no);
CREATE INDEX idx_hist_programs_stadium ON historical_programs(stadium_code);
CREATE INDEX idx_hist_programs_date_stadium ON historical_programs(race_date, stadium_code);
```

---

## バッチ処理設計

### 処理フロー

```
1. ダウンロード処理
   ├── LZHファイルをダウンロード
   ├── LZHファイルを解凍
   └── 進捗をhistorical_import_progressテーブルに記録

2. インポート処理
   ├── テーブルが存在しない場合は作成
   ├── テキストファイルをパース
   ├── DBにバルクインサート（ON CONFLICT DO UPDATE）
   └── 進捗を更新
```

### 推奨バッチサイズ

| データ種別 | 推奨バッチサイズ | 理由 |
|-----------|-----------------|------|
| レーサー期別成績 | 全件一括 | 約1,600件/期、メモリ負荷小 |
| 競走成績 | 月単位 | 約7,000件/月 |
| 番組表 | 月単位 | 約42,000件/月 |

### 実行コマンド

```bash
# テーブル作成 + 全データインポート
python import_historical_data.py all

# ダウンロードのみ
python import_historical_data.py download

# インポートのみ（ダウンロード済みデータ）
python import_historical_data.py import

# 進捗確認
python import_historical_data.py status
```

---

## 競艇場コード一覧

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

## 付録: DDL（テーブル作成SQL）

```sql
-- レーサー期別成績テーブル
CREATE TABLE IF NOT EXISTS racer_period_stats (
    id SERIAL PRIMARY KEY,
    racer_no VARCHAR(4) NOT NULL,
    data_year INTEGER NOT NULL,
    data_period INTEGER NOT NULL,
    name_kanji VARCHAR(20),
    name_kana VARCHAR(20),
    branch VARCHAR(10),
    rank VARCHAR(2),
    birth_era VARCHAR(1),
    birth_date_raw VARCHAR(6),
    gender INTEGER,
    age INTEGER,
    height INTEGER,
    weight INTEGER,
    blood_type VARCHAR(2),
    win_rate DECIMAL(5,2),
    place_rate DECIMAL(5,1),
    first_count INTEGER,
    second_count INTEGER,
    race_count INTEGER,
    final_count INTEGER,
    win_count INTEGER,
    avg_start_timing DECIMAL(4,2),
    prev_rank VARCHAR(2),
    prev2_rank VARCHAR(2),
    prev3_rank VARCHAR(2),
    prev_ability_index DECIMAL(5,2),
    current_ability_index DECIMAL(5,2),
    calc_start_date VARCHAR(8),
    calc_end_date VARCHAR(8),
    training_period INTEGER,
    birthplace VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(racer_no, data_year, data_period)
);

-- レーサーコース別成績テーブル
CREATE TABLE IF NOT EXISTS racer_period_course_stats (
    id SERIAL PRIMARY KEY,
    racer_no VARCHAR(4) NOT NULL,
    data_year INTEGER NOT NULL,
    data_period INTEGER NOT NULL,
    course INTEGER NOT NULL,
    entry_count INTEGER,
    place_rate DECIMAL(5,1),
    avg_st DECIMAL(4,2),
    avg_st_rank DECIMAL(4,2),
    rank1 INTEGER,
    rank2 INTEGER,
    rank3 INTEGER,
    rank4 INTEGER,
    rank5 INTEGER,
    rank6 INTEGER,
    flying INTEGER,
    late0 INTEGER,
    late1 INTEGER,
    absent0 INTEGER,
    absent1 INTEGER,
    disq0 INTEGER,
    disq1 INTEGER,
    disq2 INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(racer_no, data_year, data_period, course)
);

-- 過去レース結果テーブル
CREATE TABLE IF NOT EXISTS historical_race_results (
    id SERIAL PRIMARY KEY,
    race_date VARCHAR(8) NOT NULL,
    stadium_code VARCHAR(2) NOT NULL,
    race_no VARCHAR(2) NOT NULL,
    boat_no VARCHAR(1),
    racer_no VARCHAR(4),
    rank VARCHAR(2),
    race_time VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(race_date, stadium_code, race_no, boat_no)
);

-- 過去番組表テーブル
CREATE TABLE IF NOT EXISTS historical_programs (
    id SERIAL PRIMARY KEY,
    race_date VARCHAR(8) NOT NULL,
    stadium_code VARCHAR(2) NOT NULL,
    race_no VARCHAR(2) NOT NULL,
    boat_no VARCHAR(1) NOT NULL,
    racer_no VARCHAR(4),
    racer_name VARCHAR(20),
    age INTEGER,
    branch VARCHAR(10),
    weight INTEGER,
    rank VARCHAR(2),
    national_win_rate DECIMAL(5,2),
    national_2nd_rate DECIMAL(5,2),
    local_win_rate DECIMAL(5,2),
    local_2nd_rate DECIMAL(5,2),
    motor_no INTEGER,
    motor_2nd_rate DECIMAL(5,2),
    boat_no_assigned INTEGER,
    boat_2nd_rate DECIMAL(5,2),
    deadline_time VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(race_date, stadium_code, race_no, boat_no)
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_racer_period_stats_racer_no ON racer_period_stats(racer_no);
CREATE INDEX IF NOT EXISTS idx_racer_period_stats_year_period ON racer_period_stats(data_year, data_period);
CREATE INDEX IF NOT EXISTS idx_racer_period_course_stats_racer_no ON racer_period_course_stats(racer_no);
CREATE INDEX IF NOT EXISTS idx_hist_results_date ON historical_race_results(race_date);
CREATE INDEX IF NOT EXISTS idx_hist_results_racer ON historical_race_results(racer_no);
CREATE INDEX IF NOT EXISTS idx_hist_programs_date ON historical_programs(race_date);
CREATE INDEX IF NOT EXISTS idx_hist_programs_racer ON historical_programs(racer_no);
```

---

## 変更履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2026-01-05 | 1.0 | 初版作成 |

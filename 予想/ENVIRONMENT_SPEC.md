# 競艇予想システム 環境仕様書

**作成日**: 2026年1月4日  
**作成者**: Manus AI  
**バージョン**: 1.0

---

## 1. システム概要

本システムは、競艇レースのオッズデータを収集・分析し、AIによる予想を行うWebアプリケーションです。

---

## 2. インフラ構成

### 2.1 利用サービス一覧

| サービス | プラン | 用途 | 備考 |
|---------|--------|------|------|
| **Render PostgreSQL** | Basic-256mb（有料） | データベース | kokotomo-db-staging |
| **Render Web Service** | Free | バッチ処理 | boatrace-daily-collection |
| **Render Web Service** | Free | Webアプリ | ai-auto-mailer |
| **GitHub** | 有料プラン | ソースコード管理 | ai-auto-mailerリポジトリ |

### 2.2 データベース

**名称**: kokotomo-db-staging  
**種類**: PostgreSQL  
**プラン**: Basic-256mb（$6/月）  
**Service ID**: dpg-d52du3nfte5s73d3ni6g-a  

> **重要**: すべてのアプリケーション・バッチは、このデータベースに接続すること。TiDBやその他のデータベースは使用しない。

**接続情報**:
- ホスト: Renderダッシュボードで確認
- ポート: 5432
- データベース名: kokotomo_staging
- ユーザー名: kokotomo_staging_user
- SSL: 必須

### 2.3 GitHubリポジトリ

**リポジトリ名**: makoban/ai-auto-mailer  
**ブランチ**: main  
**プラン**: 有料プラン

> **重要**: 競艇予想システムのコードは、このリポジトリ内で他のプログラムと共存させる。新規リポジトリは作成しない。

---

## 3. アプリケーション構成

### 3.1 バッチ処理（boatrace-daily-collection）

**場所**: Render Cron Job  
**ソース**: ai-auto-mailer/boatrace-collector/  

| ジョブ名 | スケジュール | 機能 |
|---------|-------------|------|
| daily | 毎日 8:00 | 当日レース情報収集 |
| odds_regular | 10分ごと | オッズ定期収集 |
| odds_high_freq | 締切5分前〜 | 高頻度オッズ収集（10秒間隔） |
| result | 15分ごと | レース結果・払戻金収集 |

**収集データ**:
- レース情報（races）
- オッズ履歴（odds）- 2連単、2連複、単勝、複勝
- レース結果（race_results）
- 払戻金（payoffs）

### 3.2 Webアプリケーション（ai-auto-mailer）

**URL**: https://ai-auto-mailer.onrender.com  
**Service ID**: srv-d5agshali9vc73b6b99g  
**フレームワーク**: Node.js

---

## 4. データベーススキーマ

### 4.1 主要テーブル

| テーブル名 | 説明 | 主キー |
|-----------|------|--------|
| races | レース情報 | id |
| odds | オッズ履歴 | id |
| race_results | レース結果 | id |
| payoffs | 払戻金 | id |
| racer_period_stats | レーサー期別成績 | id |
| before_info | 直前情報 | id |
| weather_info | 水面気象 | id |
| web_predictions | WEB予想 | id |

### 4.2 テーブル詳細

#### races（レース情報）
```sql
CREATE TABLE races (
    id SERIAL PRIMARY KEY,
    race_date DATE NOT NULL,
    stadium_code INTEGER NOT NULL,
    race_number INTEGER NOT NULL,
    deadline_time TIMESTAMP,
    result VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(race_date, stadium_code, race_number)
);
```

#### odds（オッズ履歴）
```sql
CREATE TABLE odds (
    id SERIAL PRIMARY KEY,
    race_id INTEGER REFERENCES races(id),
    odds_type VARCHAR(20) NOT NULL,
    combination VARCHAR(10) NOT NULL,
    odds_value DECIMAL(10,2),
    scraped_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. 環境変数

### 5.1 バッチ処理（boatrace-daily-collection）

| 変数名 | 説明 | 例 |
|--------|------|-----|
| DATABASE_URL | PostgreSQL接続文字列 | postgresql://user:pass@host:5432/db |
| TZ | タイムゾーン | Asia/Tokyo |

### 5.2 Webアプリケーション

| 変数名 | 説明 |
|--------|------|
| DATABASE_URL | PostgreSQL接続文字列 |
| NODE_ENV | 実行環境（production/development） |

---

## 6. 運用ルール

### 6.1 データベース

1. **kokotomo-db-staging**のみを使用する
2. TiDB、MySQL、その他のデータベースは使用しない
3. スキーマ変更時は必ずマイグレーションファイルを作成する

### 6.2 ソースコード

1. **ai-auto-mailer**リポジトリのみを使用する
2. 新規リポジトリは作成しない
3. 競艇関連コードは`boatrace-collector/`ディレクトリに配置

### 6.3 デプロイ

1. GitHubへのpushで自動デプロイ（Render連携）
2. 手動デプロイはRenderダッシュボードから実行

---

## 7. 連絡先・参照

- **Renderダッシュボード**: https://dashboard.render.com/
- **GitHubリポジトリ**: https://github.com/makoban/ai-auto-mailer

---

## 変更履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2026/01/04 | 1.0 | 初版作成 |

# 競艇データ自動収集システム (Boatrace Data Collector)

競艇公式サイトからリアルタイムオッズ、レース情報、過去データを自動収集し、PostgreSQLデータベースに蓄積するシステムです。

## 機能概要

- **リアルタイムオッズ収集**: 全24競艇場の全レース（1日最大288レース）のオッズを定期収集
- **高頻度オッズ収集**: 締切直前のレースに対して5分間隔でオッズを収集
- **過去データ収集**: 指定期間の過去レースデータを一括収集
- **時系列データ保存**: オッズの時間変化を秒単位で記録

## システム構成

```
boatrace-collector/
├── src/
│   ├── collector.py           # メインデータ収集クラス
│   ├── collector_advanced.py  # pyjpboatrace版（高機能）
│   ├── cron_job.py           # Render Cron Job エントリポイント
│   └── init_db.py            # データベース初期化
├── requirements.txt          # Python依存パッケージ
├── render.yaml              # Render Blueprint設定
├── Dockerfile               # Docker設定
└── README.md
```

## デプロイ方法（Render）

### 1. GitHubリポジトリの準備

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-username/boatrace-collector.git
git push -u origin main
```

### 2. Render Blueprintでデプロイ

1. [Render Dashboard](https://dashboard.render.com/) にログイン
2. 「New」→「Blueprint」を選択
3. GitHubリポジトリを接続
4. `render.yaml` が自動検出され、以下のサービスが作成されます:
   - `boatrace-odds-collector`: 30分ごとのオッズ収集
   - `boatrace-odds-highfreq`: 5分ごとの高頻度収集
   - `boatrace-historical-collector`: 毎日深夜の過去データ収集

### 3. 環境変数の設定

Renderダッシュボードで以下の環境変数を設定:

| 変数名 | 説明 |
|--------|------|
| `DATABASE_URL` | PostgreSQL接続URL（既存DBを使用する場合は手動設定） |

### 4. データベース初期化

初回デプロイ後、以下のコマンドでテーブルを作成:

```bash
# Render Shell または ローカルから
python src/init_db.py
```

## 既存データベース（kokotomo-db-staging）への接続

既にRenderで `kokotomo-db-staging` を運用中の場合:

1. Renderダッシュボードで `kokotomo-db-staging` の接続情報を確認
2. 各Cron Jobの環境変数 `DATABASE_URL` に接続URLを設定
3. `init_db.py` を実行してテーブルを追加作成

## データベーススキーマ

### 主要テーブル

| テーブル名 | 説明 |
|-----------|------|
| `stadiums` | 競艇場マスター（24場） |
| `racers` | レーサーマスター |
| `races` | レース基本情報 |
| `race_entries` | 出走表 |
| `odds` | 時系列オッズデータ（最重要） |
| `before_race_info` | 直前情報（天候・展示タイム等） |
| `race_results` | レース結果 |
| `payouts` | 払戻金 |
| `collection_logs` | 収集ログ |

### オッズデータの時系列保存

`odds` テーブルは同一レースの同一組み合わせに対して、収集時刻（`scraped_at`）ごとに別レコードとして保存されます。これにより、オッズの時間変化を分析できます。

```sql
-- 特定レースの三連単オッズ推移を取得
SELECT bet_combination, odds_value, scraped_at
FROM odds
WHERE race_id = 123 AND odds_type = 'trifecta'
ORDER BY scraped_at;
```

## ローカル開発

### 環境構築

```bash
# 仮想環境作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存パッケージインストール
pip install -r requirements.txt

# 環境変数設定
export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
```

### テスト実行

```bash
# テストモード（DB接続確認）
python src/collector.py test

# 単一レース収集
python src/collector_advanced.py single 2026-01-04 1 1
```

## 収集頻度とサーバー負荷

公式サイトへの負荷を考慮し、以下の間隔を設定しています:

- リクエスト間: 0.5〜1秒
- レース間: 1秒
- 競艇場間: 2秒
- 日付間（過去データ収集時）: 5秒

## 注意事項

1. **利用規約の確認**: 競艇公式サイトの利用規約を確認し、適切な範囲で利用してください
2. **アクセス頻度**: 過度なアクセスはサーバーに負荷をかけるため、適切な間隔を設けてください
3. **データの利用**: 収集したデータの商用利用については、関係機関に確認してください

## ライセンス

MIT License

# 競艇データ収集システム (boatrace-collector)

競艇公式サイトから、全国24場の全レースに関するデータを自動収集し、PostgreSQLデータベースに蓄積するシステムです。

## 機能

- **日次収集**: 毎朝、当日の全レース情報と初期オッズを収集
- **定期オッズ収集**: 10分ごとに未終了レースのオッズを収集
- **結果収集**: 15分ごとに終了したレースの結果と払戻金を収集

## 収集データ

| データ種別 | 内容 |
|-----------|------|
| レース情報 | 日付、場、レース番号、レース名 |
| 出走表 | 選手情報、モーター番号、ボート番号 |
| オッズ | 単勝、複勝、2連単、2連複、拡連複（時系列で蓄積） |
| レース結果 | 着順、決まり手 |
| 払戻金 | 各賭式の払戻金額と人気順 |

## セットアップ

### 1. データベースの準備

`db_schema_v2_fixed_final.sql` をDBeaverなどで実行し、必要なテーブルを作成してください。

### 2. 環境変数の設定

Renderのダッシュボードで以下の環境変数を設定してください。

| 変数名 | 説明 |
|--------|------|
| `DATABASE_URL` | PostgreSQLの接続URL |
| `TZ` | `Asia/Tokyo` |

### 3. デプロイ

#### 方法A: render.yaml を使用（推奨）

1. このディレクトリ（`boatrace-collector`）をリポジトリのルートに配置
2. `render.yaml` をリポジトリのルートにコピー
3. Renderダッシュボードで「New Blueprint Instance」を選択
4. リポジトリを接続してデプロイ

#### 方法B: 手動でCron Jobを作成

1. Renderダッシュボードで「New Cron Job」を選択
2. 以下の設定で作成:
   - **Name**: `boatrace-daily-collection`
   - **Runtime**: Python
   - **Build Command**: `pip install -r boatrace-collector/requirements.txt`
   - **Start Command**: `cd boatrace-collector/src && python cron_jobs.py daily`
   - **Schedule**: `0 23 * * *` (毎日 08:00 JST)

## ローカルでのテスト

```bash
# 依存関係のインストール
pip install -r requirements.txt

# 環境変数の設定
export DATABASE_URL="postgresql://user:pass@host:port/dbname"

# テスト実行
cd src
python cron_jobs.py test
```

## ファイル構成

```
boatrace-collector/
├── README.md           # このファイル
├── requirements.txt    # Python依存関係
├── render.yaml         # Renderデプロイ設定
└── src/
    ├── collector.py    # メインの収集ロジック
    └── cron_jobs.py    # Cron Jobエントリポイント
```

## 注意事項

- 公式サイトへの過度なアクセスを避けるため、収集間隔は適切に設定されています
- `pyjpboatrace` ライブラリを使用しており、公式サイトの仕様変更に追従しています
- 3連単・3連複はデータ量が膨大になるため、収集対象外としています

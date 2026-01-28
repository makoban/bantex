# 競艇予想ダッシュボード

仮想購入シミュレーションのダッシュボードアプリケーション。

## 概要

- **データベース**: kokotomo-db-staging（PostgreSQL）のみを使用
- **認証**: 不要（シンプル構成）
- **機能**:
  - 今日のレース一覧表示
  - 仮想購入の履歴表示
  - 見送りレースの結果表示
  - 資金状況の表示
  - 統計情報の表示

## 技術スタック

- **バックエンド**: Python / FastAPI
- **フロントエンド**: Vue.js 3 + Tailwind CSS（CDN）
- **データベース**: PostgreSQL（Render.com）

## ローカル開発

```bash
# 依存関係インストール
pip install -r requirements.txt

# 環境変数設定
export DATABASE_URL="postgresql://..."

# サーバー起動
uvicorn api:app --reload --port 8000
```

## デプロイ（Render.com）

1. GitHubリポジトリにプッシュ
2. Render.comでBlueprintを使用してデプロイ
3. `render.yaml`が自動的に読み込まれる

## APIエンドポイント

| エンドポイント | 説明 |
|---------------|------|
| `GET /api/health` | ヘルスチェック |
| `GET /api/stadiums` | 競艇場一覧 |
| `GET /api/races/today` | 今日のレース一覧 |
| `GET /api/races/{date}` | 指定日のレース一覧 |
| `GET /api/results/{race_id}` | レース結果 |
| `GET /api/bets` | 仮想購入一覧 |
| `GET /api/bets/with-results` | 購入結果（見送り含む） |
| `GET /api/funds` | 資金状況 |
| `GET /api/stats/dashboard` | ダッシュボード統計 |
| `GET /api/odds/latest/{date}/{stadium}/{race}` | 最新オッズ |

## 自動バッチ処理

| ジョブ | スケジュール | 説明 |
|-------|-------------|------|
| `register` | 毎日 08:00 JST | 購入予定を登録 |
| `decide` | 5分ごと | 締切1分前に購入判断 |
| `result` | 15分ごと | 結果を更新 |

## 戦略

### 11R・12R単勝戦略
- 対象: 11R、12R
- 式別: 単勝
- 組合せ: 1号艇
- オッズ範囲: 1.5〜10.0

### 1-3穴バイアス戦略
- 対象: 全レース
- 式別: 2連複
- 組合せ: 1=3
- オッズ範囲: 3.0〜50.0

## データベーステーブル

### virtual_bets（仮想購入）
- 購入予定・結果を管理
- ステータス: pending, confirmed, won, lost, skipped

### virtual_funds（仮想資金）
- 戦略ごとの資金状況を管理
- 初期資金: 100,000円

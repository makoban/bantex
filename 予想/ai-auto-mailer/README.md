# AI Auto Mailer

エレガントで完璧なスタイルのシンプルなAI自動メーラー。5分毎にIMAP経由で新着メールをチェックし、Google Gemini AIが重要度を判定・要約。営業メールや迷惑メールを除外し、重要なメールのみを自動通知します。

## 主な機能

- **自動メールチェック**: 5分毎にIMAP経由で新着メールを取得
- **AI分析**: Google Gemini APIでメール内容を分析・要約
- **重要度フィルタリング**: 営業メール・迷惑メールを自動除外
- **通知メール送信**: 重要なメールのみSMTP経由で通知
- **Webアプリ**: メール要約履歴を時系列表示
- **認証不要**: 試作版として誰でもアクセス可能

## 技術スタック

- **フロントエンド**: Vite + React + TypeScript + TailwindCSS
- **バックエンド**: Express + tRPC
- **データベース**: PostgreSQL (Render)
- **AI**: Google Gemini API
- **バッチ処理**: Render Cron Job (5分毎)
- **IMAP**: Python imap-tools
- **SMTP**: Nodemailer

## Renderへのデプロイ手順

### 1. 前提条件

- Renderアカウント
- PostgreSQLデータベース（既存のRender PostgreSQL）
- Google Gemini APIキー
- SMTPサーバー情報

### 2. GitHubリポジトリの接続

1. Render ダッシュボードにログイン
2. 「New +」→「Blueprint」を選択
3. GitHubリポジトリ `makoban/ai-auto-mailer` を接続
4. `render.yaml` が自動検出されます

### 3. 環境変数の設定

以下の環境変数を設定してください：

#### データベース
```
DATABASE_URL=postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging
```

#### Gemini API
```
GEMINI_API_KEY=AIzaSyAgewUsQBbx570_LPYKw6ndnwvAGSTzjvE
```

#### SMTP設定
```
SMTP_HOST=beigecow4.sakura.ne.jp
SMTP_PORT=587
SMTP_USER=aimail@becreative.co.jp
SMTP_PASSWORD=aimailaimail2025
SMTP_FROM=aimail@becreative.co.jp
```

### 4. データベースマイグレーション

初回デプロイ後、以下のコマンドでデータベーススキーマを作成してください：

```bash
# Renderのシェルから実行
pnpm db:push
```

または、手動でSQLを実行：

```sql
-- Enums
CREATE TYPE role AS ENUM ('user', 'admin');
CREATE TYPE is_active AS ENUM ('active', 'inactive');
CREATE TYPE importance AS ENUM ('high', 'medium', 'low', 'spam');
CREATE TYPE is_notified AS ENUM ('yes', 'no');

-- Users table
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  "openId" VARCHAR(64) NOT NULL UNIQUE,
  name TEXT,
  email VARCHAR(320),
  "loginMethod" VARCHAR(64),
  role role DEFAULT 'user' NOT NULL,
  "createdAt" TIMESTAMP DEFAULT NOW() NOT NULL,
  "updatedAt" TIMESTAMP DEFAULT NOW() NOT NULL,
  "lastSignedIn" TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Email accounts table
CREATE TABLE email_accounts (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  email VARCHAR(320) NOT NULL,
  imap_host VARCHAR(255) NOT NULL,
  imap_port INTEGER NOT NULL DEFAULT 993,
  imap_username VARCHAR(320) NOT NULL,
  imap_password TEXT NOT NULL,
  notification_email VARCHAR(320) NOT NULL,
  is_active is_active DEFAULT 'active' NOT NULL,
  last_checked_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW() NOT NULL,
  updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Email summaries table
CREATE TABLE email_summaries (
  id SERIAL PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE,
  message_id VARCHAR(512) NOT NULL,
  sender VARCHAR(320) NOT NULL,
  subject TEXT NOT NULL,
  summary TEXT NOT NULL,
  importance importance NOT NULL,
  is_notified is_notified DEFAULT 'no' NOT NULL,
  received_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP DEFAULT NOW() NOT NULL
);
```

### 5. デプロイ

1. 「Apply」ボタンをクリック
2. 2つのサービスが作成されます：
   - `ai-auto-mailer-web`: Webアプリ（常時起動）
   - `ai-auto-mailer-batch`: バッチ処理（5分毎）

### 6. 動作確認

1. Webアプリにアクセス
2. 「アカウント設定」からメールアカウントを追加
3. 5分以内にバッチ処理が実行され、メールがチェックされます
4. 重要なメールがあれば通知メールが送信されます

## ローカル開発

### 1. 依存関係のインストール

```bash
pnpm install
```

### 2. Python仮想環境のセットアップ

```bash
python3 -m venv venv
source venv/bin/activate  # Windowsの場合: venv\Scripts\activate
pip install imap-tools
```

### 3. 環境変数の設定

`.env` ファイルを作成し、以下の環境変数を設定：

```env
DATABASE_URL=postgresql://...
GEMINI_API_KEY=...
SMTP_HOST=...
SMTP_PORT=...
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=...
```

### 4. データベースマイグレーション

```bash
pnpm db:push
```

### 5. 開発サーバーの起動

```bash
pnpm dev
```

### 6. バッチ処理のテスト

```bash
tsx batch.ts
```

## ライセンス

MIT

## 作成者

Manus AI Agent

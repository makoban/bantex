# AIメールシステム v7.8 変更内容

## 新機能

### 通知フィルター設定

ユーザー設定に「通知フィルター設定」セクションを追加しました。

#### 1. 送信する重要度レベルの選択
- **中以上（中・高）**: 中重要度と高重要度のメールを通知（デフォルト）
- **高のみ**: 高重要度のメールのみを通知

#### 2. 重要なメールがない場合の通知制御
- **デフォルト（オフ）**: 重要なメールがない場合は通知を送信しない
- **オン**: 重要なメールがない場合でも「現在、重要なメールはありません」という通知を送信

## 技術的な変更

### データベーススキーマ
- `user_settings` テーブルに以下のカラムを追加:
  - `send_empty_notification` (boolean, default: false)
  - `minimum_importance` (varchar(20), default: 'medium')

### バックエンド
- `server/db.ts`: `getUserSettings` と `upsertUserSettings` 関数を更新
- `server/routers/userSettings.ts`: APIエンドポイントに新しいフィールドを追加
- `server/batchScheduler.ts`: 通知ロジックに重要度フィルターを実装

### フロントエンド
- `client/src/pages/UserSettings.tsx`: 新しい設定UIを追加

## マイグレーション

データベースマイグレーションファイル: `drizzle/0004_even_nomad.sql`

```sql
ALTER TABLE "user_settings" ADD COLUMN "send_empty_notification" boolean DEFAULT false;
ALTER TABLE "user_settings" ADD COLUMN "minimum_importance" varchar(20) DEFAULT 'medium';
```

## 既存機能への影響

- **既存ユーザー**: デフォルト設定により、重要なメールがない場合は通知が送信されなくなります
- **低重要度メール**: 「中以上」設定の場合、低重要度メールは通知されません
- **spam判定メール**: 引き続き通知対象外です

## バージョン

- 旧バージョン: 7.7
- 新バージョン: 7.8

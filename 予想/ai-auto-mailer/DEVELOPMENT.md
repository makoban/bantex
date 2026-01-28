# AIメールシステム 開発ガイド

## 1. プロジェクト情報

| 項目 | 値 |
|------|-----|
| GitHubリポジトリ | makoban/ai-auto-mailer |
| デプロイ先 | Render (https://ai-auto-mailer.onrender.com) |
| ブランチ | main |

## 2. 開発フロー

```
1. コード修正
2. バージョン番号を更新（タブとアプリ表示の両方）
3. git add -A && git commit -m "メッセージ" && git push origin main
4. Renderが自動デプロイ（数分かかる）
5. 動作確認
```

## 3. 必要な外部サービス

### 3.1 GitHub
- リポジトリ: `makoban/ai-auto-mailer`
- mainブランチにプッシュするとRenderが自動デプロイ

### 3.2 Render
- サービス名: ai-auto-mailer
- URL: https://ai-auto-mailer.onrender.com
- プラン: Free
- リージョン: Singapore
- mainブランチへのプッシュで自動デプロイ

### 3.3 データベース (PostgreSQL)
- Render PostgreSQLまたは外部PostgreSQL
- 接続文字列は環境変数 `DATABASE_URL` で設定

### 3.4 Google Gemini API
- メール分析に使用
- 環境変数: `GEMINI_API_KEY`

### 3.5 Chatwork API
- 通知送信に使用
- 環境変数: `CHATWORK_API_TOKEN`

## 4. 環境変数一覧

| 変数名 | 説明 | 必須 |
|--------|------|------|
| DATABASE_URL | PostgreSQL接続文字列 | ○ |
| GEMINI_API_KEY | Google Gemini APIキー | ○ |
| CHATWORK_API_TOKEN | Chatwork APIトークン | ○ |
| NODE_ENV | 環境（production/development） | ○ |
| SMTP_HOST | SMTPサーバー（未使用） | × |
| SMTP_PORT | SMTPポート（未使用） | × |
| SMTP_USER | SMTPユーザー（未使用） | × |
| SMTP_PASSWORD | SMTPパスワード（未使用） | × |
| SMTP_FROM | 送信元メール（未使用） | × |

※SMTP関連は現在未使用（Chatwork通知のみ）

## 5. 主要ファイル

### バックエンド
| ファイル | 役割 |
|----------|------|
| server/llm.ts | AIプロンプト（要約・返信案生成） |
| server/chatworkService.ts | Chatwork通知フォーマット |
| server/emailService.ts | メール受信・分析処理 |
| server/batchScheduler.ts | 5分ごとのバッチ処理 |
| server/db.ts | データベース操作 |
| drizzle/schema.ts | DBスキーマ定義 |

### フロントエンド
| ファイル | 役割 |
|----------|------|
| client/src/pages/Settings.tsx | メールアカウント設定 |
| client/src/pages/UserSettings.tsx | AI分析カスタマイズ |
| client/src/pages/Summaries.tsx | 要約一覧表示 |

### 設定
| ファイル | 役割 |
|----------|------|
| shared/version.ts | バージョン番号（変更時は必ず更新） |
| render.yaml | Renderデプロイ設定 |
| package.json | 依存関係 |

## 6. バージョン更新

コード変更時は必ずバージョンを更新する：

```typescript
// shared/version.ts
export const APP_VERSION = "7.x.x";
```

## 7. よくある修正箇所

### Chatwork通知の内容を変更したい
→ `server/chatworkService.ts`

### AIの要約・返信案の質を改善したい
→ `server/llm.ts` のプロンプト部分

### 重要度判定を変更したい
→ `server/llm.ts` の「重要度の判定基準」セクション

### 設定画面のUIを変更したい
→ `client/src/pages/Settings.tsx`

## 8. デバッグ

Renderのログで確認：
- `[Batch]` - バッチ処理のログ
- `[IMAP]` - メール受信のログ
- `[AI]` - Gemini分析のログ
- `[Chatwork]` - 通知送信のログ

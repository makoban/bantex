# AI Auto Mailer - TODO List

## GitHub + Render デプロイ対応
- [x] データベーススキーマをPostgreSQLに変換
- [x] Drizzle ORMの設定をPostgreSQLに変更
- [x] Gemini API統合（OpenAI APIから変更）
- [x] Render Cron Job用の設定ファイル作成
- [x] 環境変数設定ファイルの作成
- [x] GitHubリポジトリ作成（ai-auto-mailer、プライベート）
- [x] コードをGitHubにプッシュ
- [x] Renderデプロイ手順書の作成
- [x] .gitignoreファイルの作成
- [x] README.mdの作成

## バグ修正（Render環境）
- [x] Python仮想環境パスを修正（システムのpython3を使用）
- [x] emailService.tsのPython実行パスを修正

## Renderデプロイ問題の解決
- [x] Renderで古いコードが実行される問題を解決
- [x] ダミーコミットを作成して強制再デプロイ
- [x] package.jsonのbuildスクリプトにpip install imap-toolsを追加

## Python依存関係の問題
- [x] Render環境でimap_toolsモジュールがインストールされていない問題を解決
- [x] requirements.txtまたはrender.yamlにPython依存関係を追加

## UX改善
- [x] メールアドレス入力時に通知先メールアドレスとIMAPユーザー名に自動コピー

## データベース修正
- [x] user_idカラムの外部キー制約を削除
- [x] user_idカラムをNULL許容に変更
- [x] マイグレーションファイルを修正（新環境でも動作するように）

## UI改善
- [x] トップ画面にバージョン表示（Ver1.0）を追加
- [x] キャッチコピーを変更

## バグ修正
- [x] getActiveEmailAccountsのカラム名マッピングを修正（snake_case→camelCase）

## 新機能
- [x] 手動メールチェックトリガー機能を追加（Ver 1.5）
- [x] メール取得期間を変更：初回30日分、2回目以降は新着のみ、開封状態は無関係（Ver 1.6）

## バグ調査
- [x] メールが0件のまま処理されない問題を調査・修正（Ver 1.7）
  - Geminiモデル名をgemini-pro→gemini-1.5-flashに変更
  - Date型をISO文字列に変換してPostgreSQLに保存
- [x] デバッグログを追加してIMAP取得状況を確認可能に（Ver 1.8）
- [x] Python IMAPスクリプトに詳細デバッグログを追加（Ver 1.9）
- [x] LLMをManus組み込みLLMヘルパーに変更（Gemini APIエラー修正）（Ver 2.0）

## Ver 3.0 Chatwork通知実装
- [x] Chatwork API統合を実装
- [x] DBスキーマを更新
- [x] バッチ処理を修正してChatwork通知を送信
- [x] UIにChatworkルームID入力欄を追加
- [ ] テストして動作確認

## ロールバック
- [x] Ver 2.0（Chatwork + Python IMAP）にロールバック
- [ ] Renderでデプロイしてテスト

## Render環境対応
- [x] Manus LLMヘルパーからGemini APIに戻す修正
- [x] GitHubにプッシュしてRenderデプロイ
- [ ] Render環境でテスト

## Python IMAP接続テスト修正
- [ ] render.yamlのビルドコマンドを確認・修正
- [ ] requirements.txtを確認
- [ ] GitHubにプッシュして再デプロイ

## Ver 4.0 機能拡張

### ユーザー設定
- [x] ユーザーごとにChatwork Room IDを設定（メールアドレスごとではなく）
- [x] 個人名・会社名の設定（重要度判定の材料）
- [x] AIプロンプトのカスタマイズ設定
### AI分析の改善
- [x] 送信者名をメール内容から自動判定（メールアドレスではなく人名で表示）
- [x] 「自分が返信すべきか」の判定機能
- [x] 宣伝・営業メールの自動無視オプション
- [x] 個人名が含まれていたら重要度を上げる

### 通知の改善
- [x] Chatworkには概要のみ送信
- [x] 詳細はWebページで確認
- [x] 不要なメールの除外設定（無視リスト）

### 表示の改善
- [x] 送信者をメールアドレスではなく人名で表示
- [x] 返信要否バッジ表示

## Ver 4.1 DBリセット・再要約機能
- [x] DBリセットボタン（要約データをクリア）
- [x] 既存メールの再要約機能（アカウントごとのリセット）
- [x] GitHubにプッシュしてRenderデプロイ

## Ver 4.1 バグ修正
- [ ] DBリセット後にlast_checked_atがリセットされていない問題を修正
- [x] バージョン表示を4.1に更新

## Ver 4.2 AI分析プロンプト改善
- [x] 広告・営業メールは短い要約（20文字以内）
- [x] 送り主の名前をメール本文から抽出（署名、「○○です」など）
- [x] 個人メールは詳細な要約（80～150文字）
- [x] 返信要否の判定を強化（具体的な理由も記載）

## Ver 4.3 リセット・今すぐチェック修正
- [x] 「今すぐチェック」ボタンを追加
- [x] リセット後に自動でバッチ実行
- [x] ボタンのラベルを「リセットして再分析」に変更

## Ver 4.4 AI分析プロンプト再改善
- [x] 送り主の名前をメール本文から確実に抽出（署名、「○○です」などから優先的に抽出）
- [x] 業務メール（営業・広告以外）の要約を100～200文字で具体的に
- [x] 営業・広告メールは20文字以内の簡潔な要約

## Ver 4.5 Gemini APIモデル名修正
- [x] gemini-1.5-flashをgemini-2.0-flash-expに変更

## Ver 5.0 フィルタリング・Chatwork改善
- [ ] 優先度フィルタリング（高/中/低のトグル選択、複数選択対応）
- [ ] 総メール数クリックで全フィルタ解除
- [ ] Chatwork通知間隔設定（10/20/60分）
- [ ] Chatwork通知をまとめて1メッセージで送信
- [ ] 設定画面にChatwork Room IDと間隔設定を追加

## Ver 4.7 メールアカウントごとのChatwork通知
- [x] メールアカウント設定画面にChatwork Room ID入力欄を追加
- [x] バッチ処理を変更して各アカウントのRoom IDに個別通知
- [x] ユーザー設定のChatwork Room IDを削除（不要になるため）

## Ver 4.8 メールアカウント編集機能
- [x] メールアカウント編集API（updateEmailAccount）を実装
- [x] Settings.tsxに編集UIを追加（Chatwork Room ID変更可能）

## Ver 4.9 Chatworkテスト送信機能
- [x] Chatworkテスト送信API（testChatworkNotification）を実装
- [x] Settings.tsxにテスト送信ボタンを追加

## Ver 5.0 Chatwork通知フォーマット改善
- [x] 通知対象を全メール（営業・広告以外）に変更
- [x] 全要素を表示（送信者名、時刻、件名、要約、優先度、返信要否）
- [x] 返信必要性を強調表示
- [x] 色分けで視認性向上

## Ver 5.1 バグ修正: データベース接続エラー
- [x] データベース接続設定を改善（タイムアウト延長、接続プール増加）
- [x] バッチ処理にリトライロジックを追加
- [x] 接続エラー時に接続をリセット

## Ver 5.2 バグ修正: 通知間隔判定ロジック
- [x] 通知間隔の判定を「メール受信時刻」から「未通知メール全て」に変更
- [x] 未通知のメールを確実に送信

## Ver 6.0 マルチユーザー対応
- [x] usersテーブルにemail, password_hashカラムを追加
- [x] email_accountsテーブルにuser_idカラムを追加
- [x] email_summariesテーブルにuser_idカラムを追加
- [x] user_settingsテーブルにuser_idカラムを追加
- [x] ignored_sendersテーブルにuser_idカラムを追加
- [x] 独自ログイン・登録APIを実装
- [x] フロントエンドにログイン・登録画面を追加
- [x] 全データ取得をユーザー別にフィルタリング
- [x] パスワードハッシュ化（bcrypt）
- [x] JWT認証
- [x] ログアウト機能
- [x] 保護されたルート（未ログイン時はリダイレクト）
- [x] 認証モジュールのユニットテスト
- [x] GitHubにプッシュしてRenderデプロイ

## Ver 6.0.1 バグ修正
- [x] localAuth.me APIエラー修正（auth_token未定義）
- [x] GitHubにプッシュしてRenderデプロイ

## Ver 6.0.2 データベースマイグレーション
- [x] マイグレーションファイルを確認
- [x] Render環境のDBにマイグレーションを適用
- [x] 動作確認
- [x] Cookieパースの修正（ctx.req.cookiesが空の場合のフォールバック）
- [x] MySQL2ドライバーでの認証処理修正

## Ver 6.0.3 Render環境DBマイグレーション
- [ ] Render環境のPostgreSQLにpassword_hashカラムを追加
- [ ] emailカラムの制約を更新
- [ ] 動作確認

## Ver 6.0.4 Render環境接続エラー修正
- [x] auth.tsをMySQL2からPostgreSQLドライバーに変更
- [x] GitHubにプッシュしてRenderデプロイ
- [ ] 動作確認

## Ver 6.0.5 401 Unauthorizedエラー修正
- [x] context.tsを修正してローカル認証をサポート
- [x] GitHubにプッシュしてRenderデプロイ
- [ ] 動作確認

## Ver 6.0.6 バージョン表記追加
- [x] バージョン定数を共通化
- [x] ログイン・登録画面にバージョン表記を追加
- [x] その他の画面にバージョン表記を追加
- [x] GitHubにプッシュしてRenderデプロイ

## Ver 6.1 Chatwork通知フォーマット改善
- [x] 現状のフォーマットを確認して問題点を特定
- [x] アカウント別にメッセージを分割
- [x] フォーマットをシンプル化（件名と要約のみ）
- [x] 低優先度メールは件数のみ表示
- [x] [color]タグを削除
- [x] GitHubにプッシュしてRenderデプロイ

## Ver 6.2: Chatwork通知エラー修正
- [x] Chatwork body too longエラーを修正（256件の未通知メールが多すぎる）
- [x] 未通知メールを分割して送信（1回あたり最大15件）
- [x] 古い未通知メールを通知済みにマークする処理を追加
- [x] GitHubにプッシュしてRenderデプロイ

## Ver 7.0: AI秘書通知機能
- [x] DBスキーマにreply_suggestionカラムを追加
- [x] AI分析プロンプトを更新（返信例生成追加）
- [x] AImail送信者を無視する処理を追加
- [x] Chatwork通知を秘書スタイルに変更
- [x] メール通知も同じフォーマットに変更
- [x] GitHubにプッシュしてRenderデプロイ

## Ver 7.0.1: Render DB マイグレーション修正
- [x] Render環境のDBにreply_suggestionカラムがなくても動作するようにフォールバック追加
- [x] GitHubにプッシュしてRenderデプロイ

## Ver 7.1: 通知フォーマット改善
- [x] Chatwork通知をより自然な秘書スタイルに変更
- [x] GitHubにプッシュしてRenderデプロイ

## Ver 7.2: Chatworkとメール両方に通知
- [x] batchScheduler.tsを修正して両方に送信
- [x] GitHubにプッシュしてRenderデプロイ

## Ver 7.3: 通知フォーマット改善（詳細・装飾）
- [ ] AI分析プロンプトを改善（100文字程度の詳細要約、定型文付き返信例）
- [ ] Chatwork通知フォーマットを改善（絵文字装飾、わかりやすく）
- [ ] GitHubにプッシュしてRenderデプロイ

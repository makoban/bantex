# アービトラージ競艇予想 - TODO

## ダッシュボード機能

- [x] ダッシュボードレイアウトとナビゲーション構築
- [x] レース一覧・フィルタリング機能（日付・会場・レース番号）
- [x] オッズ時系列グラフ可視化（締切5分前からの10秒間隔データ）
- [x] アービトラージ式オッズ分析（歪み検知・アラート）
- [x] レーサー期別成績検索・表示（2002年〜2026年）
- [x] WEB予想情報表示（競艇日和・公式予想）
- [x] 予想的中率分析
- [ ] レース結果・払戻金表示
- [x] 直前情報表示（展示タイム・チルト・水面気象）
- [x] データ収集状況モニタリング
- [ ] 管理者向けデータ収集設定画面

## データベース連携

- [x] PostgreSQL接続設定
- [x] レース情報テーブル連携
- [x] オッズ履歴テーブル連携
- [x] レーサー成績テーブル連携
- [x] 予想情報テーブル連携

## デザイン

- [x] ダークテーマ対応
- [x] レスポンシブデザイン
- [ ] グラフ・チャート表示（Chart.js統合）

## API実装

- [x] getStadiums - 会場マスタ
- [x] getTodayRaces - 本日のレース一覧
- [x] getRacesByDateRange - 日付範囲でレース検索
- [x] getOddsHistory - オッズ履歴（時系列）
- [x] detectOddsAnomaly - オッズ異常検知
- [x] searchRacerStats - レーサー成績検索
- [x] getPeriods - 期別一覧
- [x] getRacerDetail - レーサー詳細
- [x] getBeforeInfo - 直前情報
- [x] getWeatherInfo - 水面気象情報
- [x] getWebPredictions - WEB予想情報
- [x] getPredictionAccuracy - 予想的中率
- [x] getStadiumRankings - 場状況ランキング
- [x] getCollectionStats - データ収集統計

## テスト

- [ ] API統合テスト
- [ ] フロントエンドコンポーネントテスト

## 今後の機能

- [ ] オッズグラフ可視化（Chart.js）
- [ ] アービトラージ自動検知アラート
- [ ] AI予想機能
- [ ] 管理者設定画面

## バッチ修正（データベース統一）

- [x] RenderバッチをTiDB（MySQL互換）に接続変更
- [x] psycopg2からmysql-connectorへ変更
- [x] テーブル作成SQLのMySQL互換化
- [x] 払戻金保存エラーの修正

## PostgreSQL接続（既存データ活用）

- [ ] ダッシュボードをRenderのPostgreSQLに接続
- [ ] 既存データの表示確認

## 環境仕様書

- [x] 環境仕様書の作成（kokotomo-db-staging、ai-auto-mailer）

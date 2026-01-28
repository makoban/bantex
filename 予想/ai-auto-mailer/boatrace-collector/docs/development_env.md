# 競艇予想AI - 開発環境メモ

## プロジェクト構成

```
/home/ubuntu/ai-auto-mailer/
├── boatrace-collector/     # 競艇データ収集システム（Python）
│   ├── src/
│   │   ├── collector.py        # pyjpboatraceを使用したメインコレクター
│   │   ├── collect_odds.py     # オッズ収集（10秒間隔対応）
│   │   ├── cron_jobs.py        # Render cronジョブ用エントリーポイント
│   │   ├── download_race_data.py   # 競走成績・番組表ダウンロード
│   │   ├── download_racer_data.py  # レーサー期別成績ダウンロード
│   │   ├── import_racer_data.py    # レーサーデータDBインポート
│   │   └── parse_race_data.py      # 競走成績・番組表パーサー
│   ├── data/               # ダウンロードしたデータ（.gitignore）
│   ├── docs/               # ドキュメント
│   └── schema/             # DBスキーマ
├── client/                 # フロントエンド（React）
├── server/                 # バックエンドAPI（Node.js）
└── render.yaml             # Renderデプロイ設定
```

## データベース

- **本番/ステージング**: Render PostgreSQL
- **接続URL**: `postgresql://kokotomo_staging_user:***@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging`

### 競艇関連テーブル（boatrace_プレフィックス）

| テーブル名 | 用途 |
|-----------|------|
| `racer_period_stats` | レーサー期別成績 |
| `racer_period_course_stats` | レーサー期別コース別成績 |
| `odds_history` | オッズ履歴（10秒間隔） |
| `boatrace_results` | レース結果 |
| `boatrace_entries` | 着順・決まり手 |
| `boatrace_payoffs` | 払戻金 |
| `boatrace_programs` | 番組表 |

### 既存テーブル（他システム用）

- `races`, `race_results`, `payoffs` など（既存システム用、使用しない）

## オッズ収集仕様（確定）

- **対象オッズ**: 2連単・2連複・単勝・複勝（**3連は無し**）
- **高頻度収集**: 締切5分前から10秒間隔
- **通常収集**: 10分間隔
- **運用時間**: 8:00〜21:30（レース開催日のみ）
- **開催チェック**: 毎朝8:00に確認、開催なしなら翌日まで停止

## Render cronジョブ

| ジョブ名 | スケジュール | 内容 |
|---------|-------------|------|
| `boatrace-daily-collection` | 毎日23:00 UTC (8:00 JST) | 日次データ収集 |
| `boatrace-odds-regular` | 10分ごと (8:00-21:00 JST) | 定期オッズ収集 |
| `boatrace-result-collection` | 15分ごと | レース結果収集 |

## 主要ライブラリ

- **pyjpboatrace**: 競艇公式サイトAPIラッパー
- **psycopg2**: PostgreSQL接続
- **requests**: HTTP通信
- **beautifulsoup4**: HTMLパース

## データソース

### 公式データ（認証不要）

| データ | URL形式 | 備考 |
|--------|---------|------|
| レーサー期別成績 | `https://www.boatrace.jp/static_extra/pc_static/download/data/kibetsu/fan{YYMM}.lzh` | 2002年〜 |
| 競走成績 | `https://www1.mbrace.or.jp/od2/K/{YYYYMM}/k{YYMM}{DD}.lzh` | 2005年〜 |
| 番組表 | `https://www1.mbrace.or.jp/od2/B/{YYYYMM}/b{YYMM}{DD}.lzh` | 2005年〜 |
| オッズ | `https://www.boatrace.jp/owpc/pc/race/odds2tf?rno={R}&jcd={JJ}&hd={YYYYMMDD}` | リアルタイム |

## データベース状況（2026/1/4時点）

| テーブル | 件数 | 状態 |
|---------|------|------|
| `racer_period_stats` | 49,423件 | インポート中（31期分完了） |
| `racer_period_course_stats` | 296,538件 | インポート中 |
| `odds_history` | 462件 | テスト収集済み |
| `boatrace_beforeinfo` | 6件 | テスト収集済み（直前情報） |
| `boatrace_weather` | 1件 | テスト収集済み（水面気象） |
| `boatrace_results` | 0件 | 競走成績ダウンロード中 |
| `boatrace_programs` | 0件 | 番組表ダウンロード中 |

## 今後の実装予定

1. X（Twitter）予想情報の収集
2. WEB予想サイト情報の収集
3. 予想的中履歴の記録・分析
4. 予想AIモデルの構築

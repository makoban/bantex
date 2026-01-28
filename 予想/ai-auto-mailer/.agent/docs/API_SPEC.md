# 競艇予想システム API仕様書

> **目的**: 関数名・引数・戻り値を明確に定義し、実装時のタイプミスを防止する
> **最終更新**: 2026-01-26 Ver1.46

---

## 📌 ファイル構成

| ファイル | 役割 | 主要クラス/関数数 |
|----------|------|------------------|
| `boatrace-collector/src/virtual_betting.py` | 仮想購入システム | VirtualBettingManager (29メソッド) |
| `boatrace-collector/src/cron_jobs.py` | Cronジョブ | 12関数 |
| `boatrace-collector/src/collector.py` | データ収集 | BoatraceCollector (14メソッド) |
| `boatrace-dashboard/api.py` | REST API | 30+エンドポイント |

---

## 1. VirtualBettingManager クラス

> **ファイル**: `boatrace-collector/src/virtual_betting.py`
> **責務**: 仮想購入の作成・管理・結果更新

### 1.1 コンストラクタ・接続

| メソッド | 引数 | 戻り値 | 説明 |
|----------|------|--------|------|
| `__init__` | `db_url: str = None` | `None` | PostgreSQL接続URLで初期化 |
| `get_db_connection` | なし | `connection` or `None` | DB接続を取得 |

> ⚠️ **注意**: `get_connection()` は存在しない。必ず `get_db_connection()` を使用

### 1.2 購入管理

| メソッド | 引数 | 戻り値 | 説明 |
|----------|------|--------|------|
| `create_bet` | `race_date: str`, `stadium_code: str`, `race_number: int`, `strategy_type: str`, `combination: str`, `bet_type: str`, `amount: int = 1000`, `reason: dict = None` | `int` (bet_id) | 仮想購入を作成 |
| `confirm_bet` | `bet_id: int`, `final_odds: float`, `reason: dict = None` | `None` | 購入を確定（pending→confirmed） |
| `skip_bet` | `bet_id: int`, `reason: str` | `None` | 購入を見送り（pending→skipped） |
| `update_result` | `bet_id: int`, `is_won: bool`, `payout: int = 0` | `None` | 結果を更新（won/lost） |

### 1.3 購入取得

| メソッド | 引数 | 戻り値 | 説明 |
|----------|------|--------|------|
| `get_pending_bets` | `race_date: str = None` | `List[Dict]` | 保留中の購入を取得 |
| `get_all_pending_bets_near_deadline` | `minutes_to_deadline: int = 2` | `List[Dict]` | 締切N分以内のpending購入を取得 |
| `get_summary` | `race_date: str = None` | `Dict` | 購入サマリーを取得 |

### 1.4 オッズ取得

| メソッド | 引数 | 戻り値 | 説明 |
|----------|------|--------|------|
| `get_latest_odds` | `race_date: str`, `stadium_code: str`, `race_number: int`, `odds_type: str`, `combination: str` | `Optional[float]` | DBからオッズを取得 |
| `fetch_odds_from_website` | `race_date: str`, `stadium_code: str`, `race_number: int`, `odds_type: str`, `combination: str` | `Optional[float]` | 公式サイトからオッズを取得 |
| `get_odds_with_fallback` | `race_date: str`, `stadium_code: str`, `race_number: int`, `odds_type: str`, `combination: str` | `Optional[float]` | DB→Web の順でオッズ取得 |

#### odds_type の値

| 値 | 意味 |
|----|------|
| `'win'` | 単勝 |
| `'2t'` | 2連単 |
| `'2f'` | 2連複 |

### 1.5 戦略処理

| メソッド | 引数 | 戻り値 | 説明 |
|----------|------|--------|------|
| `register_daily_bets` | なし | `None` | 本日分の購入予定を登録 |
| `process_deadline_bets` | なし | `None` | 締切前の購入判断を実行 |
| `_process_bias_1_3_strategy` | なし | `None` | bias_1_3_2nd戦略の処理 |
| `_process_win_10x_strategy` | なし | `None` | win_10x_1_3戦略の処理 |
| `_process_single_bet` | `bet: Dict` | `None` | 単一購入の処理 |
| `expire_overdue_bets` | なし | `int` (件数) | 締切超過をskippedに更新 |

### 1.6 結果処理

| メソッド | 引数 | 戻り値 | 説明 |
|----------|------|--------|------|
| `process_results` | なし | `None` | 確定済みレースの結果を更新 |
| `_process_single_result` | `bet: Dict` | `None` | 単一結果の処理 |
| `_get_race_result` | `race_date: str`, `stadium_code: str`, `race_number: int` | `Optional[Dict]` | レース結果を取得 |
| `_check_win` | `combination: str`, `bet_type: str`, `result: Dict` | `bool` | 的中判定 |

### 1.7 補助メソッド

| メソッド | 引数 | 戻り値 | 説明 |
|----------|------|--------|------|
| `get_boat1_local_win_rate` | `race_date: str`, `stadium_code: str`, `race_number: int` | `Optional[float]` | 1号艇の当地勝率を取得 |
| `_parse_2tf_odds` | `soup: BeautifulSoup`, `odds_type: str`, `combination: str` | `Optional[float]` | 2連オッズをパース |
| `_parse_win_odds` | `soup: BeautifulSoup`, `combination: str` | `Optional[float]` | 単勝オッズをパース |
| `_parse_odds_text` | `text: str` | `Optional[float]` | オッズ文字列をパース |

---

## 2. Cronジョブ関数

> **ファイル**: `boatrace-collector/src/cron_jobs.py`

### 2.1 メインジョブ

| 関数 | 引数 | 戻り値 | 実行タイミング |
|------|------|--------|----------------|
| `job_daily_batch` | なし | `None` | 毎朝6:00 JST |
| `job_betting_process` | なし | `None` | 1分ごと |
| `job_result_collection` | なし | `None` | 5分ごと |
| `job_daily_collection` | なし | `None` | 毎朝8:00 JST |
| `job_odds_collection_regular` | なし | `None` | 10分ごと |
| `job_odds_collection_high_freq` | なし | `None` | 締切5分前から10秒間隔 |
| `job_test` | なし | `None` | デプロイ確認用 |

### 2.2 ユーティリティ

| 関数 | 引数 | 戻り値 | 説明 |
|------|------|--------|------|
| `is_within_operation_hours` | なし | `bool` | 運用時間内か（8:00-21:30 JST） |
| `get_database_url` | なし | `str` | DATABASE_URL環境変数を取得 |
| `has_races_near_deadline` | `minutes: int = 2` | `bool` | 締切N分以内のレースがあるか |
| `has_races_after_deadline` | `minutes: int = 15` | `bool` | 締切後N分以内のレースがあるか |

### 2.3 結果更新

| 関数 | 引数 | 戻り値 | 説明 |
|------|------|--------|------|
| `update_manus_virtual_bets` | `boatrace_db_url: str` | `None` | 結果をvirtual_betsに反映 |
| `process_single_bet_result` | `bet: dict`, `manus_conn`, `pg_conn` | `None` | 単一購入結果を処理 |

---

## 3. BoatraceCollector クラス

> **ファイル**: `boatrace-collector/src/collector.py`
> **責務**: 公式サイトからのデータ収集

### 3.1 接続管理

| メソッド | 引数 | 戻り値 | 説明 |
|----------|------|--------|------|
| `__init__` | `database_url: str` | `None` | 初期化 |
| `connect_db` | なし | `None` | DB接続 |
| `close_db` | なし | `None` | DB切断 |

### 3.2 レース情報取得

| メソッド | 引数 | 戻り値 | 説明 |
|----------|------|--------|------|
| `get_today_races` | `target_date: datetime` | `List[Dict]` | 指定日の全レース情報 |
| `get_race_deadlines` | `target_date: datetime`, `stadium_code: int` | `Dict[int, datetime]` | 締切時刻取得 |
| `save_races` | `races: List[Dict]` | `Dict[str, int]` | レース情報をDB保存 |
| `get_active_races` | `target_date: datetime` | `List[Dict]` | 発売中レース一覧 |
| `get_finished_races` | `target_date: datetime` | `List[Dict]` | 終了レース一覧 |

### 3.3 オッズ収集

| メソッド | 引数 | 戻り値 | 説明 |
|----------|------|--------|------|
| `collect_odds_for_race` | `target_date: datetime`, `stadium_code: int`, `race_number: int` | `Dict` or `None` | オッズ収集 |
| `save_odds` | `race_id: int`, `odds_data: Dict` | `None` | オッズをDB保存 |

### 3.4 結果収集

| メソッド | 引数 | 戻り値 | 説明 |
|----------|------|--------|------|
| `collect_result_for_race` | `stadium_code: int`, `race_number: int`, `target_date: datetime` | `Dict` or `None` | 結果収集 |
| `save_result` | `race_id: int`, `result_data: Dict`, `race_date: str = None`, `stadium_code: int = None`, `race_number: int = None` | `None` | 結果をDB保存 |

### 3.5 モジュール関数

| 関数 | 引数 | 戻り値 | 説明 |
|------|------|--------|------|
| `run_daily_collection` | `database_url: str` | `None` | 日次収集実行 |
| `run_odds_regular_collection` | `database_url: str` | `None` | 定期オッズ収集実行 |
| `run_result_collection` | `database_url: str`, `target_date: datetime = None` | `None` | 結果収集実行 |

---

## 4. Dashboard API エンドポイント

> **ファイル**: `boatrace-dashboard/api.py`
> **ベースURL**: `/api`

### 4.1 基本API

| エンドポイント | メソッド | 引数 | 戻り値 |
|----------------|----------|------|--------|
| `/health` | GET | なし | `{"status": "ok"}` |
| `/stadiums` | GET | なし | `List[StadiumInfo]` |

### 4.2 レース情報

| エンドポイント | メソッド | 引数 | 戻り値 |
|----------------|----------|------|--------|
| `/races/today` | GET | なし | `List[RaceInfo]` |
| `/races/today/with-odds` | GET | なし | レース+オッズ |
| `/races/{race_date}` | GET | `race_date: str` | `List[RaceInfo]` |
| `/result/{race_id}` | GET | `race_id: int` | `RaceResult` |

### 4.3 仮想購入

| エンドポイント | メソッド | 引数 | 戻り値 |
|----------------|----------|------|--------|
| `/virtual-bets` | GET | `status`, `race_date`, `strategy_type`, `limit` | `List[VirtualBet]` |
| `/virtual-funds` | GET | なし | `List[VirtualFund]` |
| `/dashboard/stats` | GET | なし | `DashboardStats` |
| `/bets/with-results` | GET | `race_date`, `include_skipped`, `limit` | 購入結果一覧 |

### 4.4 オッズ

| エンドポイント | メソッド | 引数 | 戻り値 |
|----------------|----------|------|--------|
| `/odds/latest` | GET | `race_date: str`, `stadium_code: str`, `race_number: int` | オッズ情報 |
| `/debug/odds-history` | GET | `race_date`, `stadium_code`, `race_number`, `combination` | デバッグ情報 |

### 4.5 過去データ

| エンドポイント | メソッド | 引数 | 戻り値 |
|----------------|----------|------|--------|
| `/historical/races/{race_date}` | GET | `race_date: str` | 過去レース一覧 |
| `/historical/race/{race_date}/{stadium_code}/{race_no}` | GET | 3パラメータ | レース詳細 |
| `/historical/dates` | GET | `limit: int` | 利用可能日付一覧 |

### 4.6 分析・統計

| エンドポイント | メソッド | 引数 | 戻り値 |
|----------------|----------|------|--------|
| `/skipped/analysis` | GET | `start_date`, `end_date`, `strategy_type` | 見送り分析 |
| `/period/summary` | GET | `period`, `limit` | 周期別サマリー |
| `/strategy/comparison` | GET | `start_date`, `end_date` | 戦略比較 |
| `/skipped/virtual-results` | GET | `start_date`, `end_date`, `strategy_type`, `limit` | 見送り仮想結果 |

### 4.7 管理API

| エンドポイント | メソッド | 引数 | 戻り値 |
|----------------|----------|------|--------|
| `/admin/update-skip-reasons` | POST | なし | 更新件数 |
| `/admin/reset-overdue-bets` | POST | なし | 削除件数 |
| `/admin/register-today-bets` | POST | なし | 登録結果 |
| `/admin/backfill-historical` | POST | `start_date`, `end_date` | 補正結果 |

---

## 5. 戦略設定（STRATEGIES）

> **ファイル**: `boatrace-collector/src/virtual_betting.py` 26-67行目

### 5.1 bias_1_3_2nd（3穴2nd戦略）

```python
{
    'name': '3穴2nd戦略',
    'combination': '1-3',
    'bet_type': 'auto',  # 2連単/2連複の高い方を選択
    'base_amount': 1000,
    'min_local_win_rate': 4.5,
    'max_local_win_rate': 6.0,
    'min_odds': 3.0,
    'max_odds': 100.0,
    'target_conditions': [  # 15パターン
        ('03', 4),   # 江戸川 4R
        ('04', 4),   # 平和島 4R
        # ... 全15パターン
    ],
    'register_at_batch': True,  # 朝にpending登録
}
```

### 5.2 win_10x_1_3（単勝10倍以上戦略）

```python
{
    'name': '１単勝10倍以上１－３',
    'combination': '1-3',
    'bet_type': 'exacta',  # 2連単固定
    'base_amount': 1000,
    'min_win_odds': 10.0,  # 1号艇単勝10倍以上
    'register_at_batch': False,  # 朝登録なし（締切3分前に直接チェック）
}
```

---

## 6. 共通の型定義

### 6.1 stadium_code

| コード | 競艇場 | コード | 競艇場 |
|--------|--------|--------|--------|
| 01 | 桐生 | 13 | 尼崎 |
| 02 | 戸田 | 14 | 鳴門 |
| 03 | 江戸川 | 15 | 丸亀 |
| 04 | 平和島 | 16 | 児島 |
| 05 | 多摩川 | 17 | 宮島 |
| 06 | 浜名湖 | 18 | 徳山 |
| 07 | 蒲郡 | 19 | 下関 |
| 08 | 常滑 | 20 | 若松 |
| 09 | 津 | 21 | 芦屋 |
| 10 | 三国 | 22 | 福岡 |
| 11 | びわこ | 23 | 唐津 |
| 12 | 住之江 | 24 | 大村 |

### 6.2 bet_type

| 値 | 意味 |
|----|------|
| `'win'` | 単勝 |
| `'place'` | 複勝 |
| `'exacta'` | 2連単 |
| `'quinella'` | 2連複 |
| `'wide'` | ワイド |
| `'auto'` | 2連単/2連複の高い方を自動選択 |

### 6.3 status（virtual_bets）

| 値 | 意味 |
|----|------|
| `'pending'` | 購入予定（判断待ち） |
| `'confirmed'` | 購入確定 |
| `'skipped'` | 見送り |
| `'won'` | 的中 |
| `'lost'` | 不的中 |

---

## 7. 重要な注意事項

### 7.1 よくある間違い

| ❌ 間違い | ✅ 正解 |
|----------|---------|
| `get_connection()` | `get_db_connection()` |
| `stadium_code` を int で渡す | `stadium_code` は文字列 `"01"` 形式 |
| `race_date` を datetime で渡す | `race_date` は文字列 `"20260126"` または `"2026-01-26"` |

### 7.2 日付形式

| 用途 | 形式 | 例 |
|------|------|-----|
| DB保存・クエリ | `YYYY-MM-DD` | `2026-01-26` |
| オッズ取得 | `YYYYMMDD` | `20260126` |
| API引数 | `YYYY-MM-DD` | `2026-01-26` |

---

## 更新履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|----------|
| 2026-01-26 | 1.0 | 初版作成 |

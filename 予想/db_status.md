# データベース確認結果

## 接続成功

## 主要テーブルのデータ状況

| テーブル | レコード数 | データ範囲 |
|---------|-----------|-----------|
| historical_programs | 6,396,827件 | 2005/01/01 〜 2026/01/19 |
| historical_race_results | 6,667,634件 | 2005/01/01 〜 2026/01/24 |
| historical_payoffs | 8,682,359件 | 2005/01/01 〜 2026/01/24 |

**払戻金データが補完されている！** 仕様書では不完全とされていたが、現在は完全なデータが存在。

## historical_programs テーブルのカラム（ファンダメンタル要因）

| カラム名 | 型 | 説明 |
|---------|---|------|
| race_date | varchar | レース日 (YYYYMMDD) |
| stadium_code | varchar | 競艇場コード |
| race_no | varchar | レース番号 |
| boat_no | varchar | ボート番号（枠番） |
| racer_no | varchar | 選手登録番号 |
| racer_name | varchar | 選手名 |
| age | integer | 年齢 |
| branch | varchar | 支部 |
| weight | integer | 体重 |
| rank | varchar | 級別 (A1, A2, B1, B2) |
| national_win_rate | numeric | 全国勝率 |
| national_2nd_rate | numeric | 全国2連対率 |
| local_win_rate | numeric | 当地勝率 |
| local_2nd_rate | numeric | 当地2連対率 |
| motor_no | integer | モーター番号 |
| motor_2nd_rate | numeric | モーター2連対率 |
| boat_no_assigned | integer | ボート番号 |
| boat_2nd_rate | numeric | ボート2連対率 |

## historical_race_results テーブルのカラム

| カラム名 | 型 | 説明 |
|---------|---|------|
| race_date | varchar | レース日 |
| stadium_code | varchar | 競艇場コード |
| race_no | varchar | レース番号 |
| boat_no | varchar | ボート番号 |
| racer_no | varchar | 選手登録番号 |
| rank | varchar | 着順 |
| race_time | varchar | レースタイム |

## Benterモデル構築に利用可能な特徴量

1. **選手要因**
   - national_win_rate（全国勝率）
   - national_2nd_rate（全国2連対率）
   - local_win_rate（当地勝率）
   - local_2nd_rate（当地2連対率）
   - rank（級別: A1, A2, B1, B2）
   - age（年齢）
   - weight（体重）

2. **機材要因**
   - motor_2nd_rate（モーター2連対率）
   - boat_2nd_rate（ボート2連対率）

3. **レース条件**
   - boat_no（枠番: 1〜6）
   - stadium_code（競艇場: 24場）

## 結論

**ファンダメンタルモデルの構築に必要なデータは全て揃っている！**

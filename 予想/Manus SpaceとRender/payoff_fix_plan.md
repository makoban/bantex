# 払戻金表示問題の根本原因と修正計画

## 問題の整理

### 1. 今日のレース（2026-01-20）の払戻金
- **payoffsテーブル**: 一部の場のみデータあり（浜名湖、津、尼崎、徳山、丸亀）
- **原因**: スクレイピング時に2025年1月19日のデータを取得しているが、2025年1月19日に開催していない場は結果がない
- **例**: 戸田は2025年1月19日に開催なし → 「データがありません」

### 2. 過去のレースタブ
- **historical_race_results**: 2026-01-16までのデータあり（2026-01-17以降なし）
- **historical_payoffs**: 0件（全くデータなし）
- **原因**: 履歴データインポートで払戻金がインポートされていない

### 3. 2連複払戻の表示
- **api.py 309行目**: `payoffs.get('2f', [])` を使用
- **DBのbet_type**: `quinella`
- **原因**: bet_typeの不一致

## 修正計画

### 修正1: api.pyの2連複払戻表示修正
```python
# 309行目を修正
'quinella': payoffs.get('quinella', [])
```

### 修正2: 日付変換ロジックの修正
- 現在: システム日付2026年 → スクレイピング日付2025年
- 問題: 2025年と2026年で開催場が異なる
- **解決策**: 日付変換をやめて、2026年のデータをそのまま使用するか、開催日程を事前にチェック

### 修正3: historical_payoffsのインポート
- `import_historical_data.py import_payoffs` を実行して払戻金データをインポート

### 修正4: 過去のレースタブの日付範囲
- 2026-01-17以降のhistorical_race_resultsデータがない
- 履歴データインポートの進捗を確認し、最新まで追いつかせる

## 優先順位

1. **高**: api.pyの2連複払戻修正（即時対応可能）
2. **高**: historical_payoffsのインポート
3. **中**: 日付変換ロジックの見直し
4. **低**: 履歴データインポートの完了待ち

## 実装

### api.py修正
```python
# 309行目
'quinella': payoffs.get('quinella', [])
```

### デプロイ
```bash
cd /home/ubuntu/ai-auto-mailer
git add boatrace-dashboard/api.py
git commit -m "fix: 2連複払戻のbet_type修正 (2f -> quinella)"
git push
```

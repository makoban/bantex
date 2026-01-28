# 払戻金インポートの実行計画

## 現状
- boatrace-historical-importのコマンド: `cd boatrace-collector/src && python import_historical_data.py all`
- `all`コマンドは結果データと番組表のダウンロード・インポートを行う
- 払戻金インポートは`import_payoffs`コマンドで別途実行が必要

## 解決策

### オプション1: 既存のCronジョブのコマンドを変更
コマンドを変更: `cd boatrace-collector/src && python import_historical_data.py import_payoffs`

### オプション2: 新しいCronジョブを作成
払戻金インポート専用のCronジョブを作成

### オプション3: allコマンドに払戻金インポートを追加
import_historical_data.pyのrun_all()関数に払戻金インポートを追加

## 推奨: オプション3
allコマンドに払戻金インポートを追加することで、1つのCronジョブで全てのインポートが完了する

## 実装
run_all()関数を修正して、払戻金インポートも実行するようにする

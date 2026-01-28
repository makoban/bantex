---
description: バージョン変更時のルール（ダッシュボード・VERSION_HISTORY更新）
---

# バージョン変更ルール

システムに変更を加えた場合、以下の3つを**必ず**更新してください。

## 1. VERSION_HISTORY.md

`ai-auto-mailer/VERSION_HISTORY.md` に変更内容を追記：

```markdown
## Ver1.XX (日付)
### 変更内容
- **主要な変更**: 説明
  - 詳細1
  - 詳細2
```

## 2. ダッシュボードのバージョン表示

`boatrace-dashboard/static/index.html` の約894行目：

```javascript
const version = ref('Ver1.XX');  // 変更内容の簡潔な説明
```

## 3. cron_jobs.pyのログバージョン（必要に応じて）

`boatrace-collector/src/cron_jobs.py` のジョブログ：

```python
logger.info("=== オッズ収集+購入判断ジョブ開始 (v9.X) ===")
```

## チェックリスト

// turbo
- [ ] VERSION_HISTORY.md に追記
// turbo
- [ ] index.html の version を更新
// turbo
- [ ] Git コミット＆プッシュ

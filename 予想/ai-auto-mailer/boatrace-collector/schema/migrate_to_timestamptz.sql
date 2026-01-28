-- ============================================================
-- タイムゾーン対応マイグレーション
-- ============================================================
-- 目的: 全てのTIMESTAMPカラムをTIMESTAMP WITH TIME ZONEに変更
-- 既存データ: JSTとして保存されているため、JSTとして解釈して変換
-- 
-- 実行方法: Renderのダッシュボードシェルから実行
-- ============================================================

-- PostgreSQLのタイムゾーンを確認
SHOW timezone;

-- ============================================================
-- 1. racesテーブル
-- ============================================================
-- deadline_at: 締切時刻（JSTで保存されている）
-- created_at: 作成日時

ALTER TABLE races 
    ALTER COLUMN deadline_at TYPE TIMESTAMP WITH TIME ZONE 
    USING deadline_at AT TIME ZONE 'Asia/Tokyo';

ALTER TABLE races 
    ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE 
    USING created_at AT TIME ZONE 'Asia/Tokyo';

-- ============================================================
-- 2. virtual_betsテーブル
-- ============================================================
-- scheduled_deadline: 購入予定の締切時刻（JSTで保存されている）
-- created_at, updated_at, confirmed_at, result_confirmed_at

ALTER TABLE virtual_bets 
    ALTER COLUMN scheduled_deadline TYPE TIMESTAMP WITH TIME ZONE 
    USING scheduled_deadline AT TIME ZONE 'Asia/Tokyo';

ALTER TABLE virtual_bets 
    ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE 
    USING created_at AT TIME ZONE 'Asia/Tokyo';

ALTER TABLE virtual_bets 
    ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE 
    USING updated_at AT TIME ZONE 'Asia/Tokyo';

ALTER TABLE virtual_bets 
    ALTER COLUMN confirmed_at TYPE TIMESTAMP WITH TIME ZONE 
    USING confirmed_at AT TIME ZONE 'Asia/Tokyo';

ALTER TABLE virtual_bets 
    ALTER COLUMN result_confirmed_at TYPE TIMESTAMP WITH TIME ZONE 
    USING result_confirmed_at AT TIME ZONE 'Asia/Tokyo';

-- ============================================================
-- 3. odds_historyテーブル
-- ============================================================
-- scraped_at: オッズ取得時刻
-- created_at: 作成日時

ALTER TABLE odds_history 
    ALTER COLUMN scraped_at TYPE TIMESTAMP WITH TIME ZONE 
    USING scraped_at AT TIME ZONE 'Asia/Tokyo';

ALTER TABLE odds_history 
    ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE 
    USING created_at AT TIME ZONE 'Asia/Tokyo';

-- ============================================================
-- 4. race_resultsテーブル
-- ============================================================
ALTER TABLE race_results 
    ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE 
    USING created_at AT TIME ZONE 'Asia/Tokyo';

ALTER TABLE race_results 
    ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE 
    USING updated_at AT TIME ZONE 'Asia/Tokyo';

-- ============================================================
-- 5. betting_historyテーブル（存在する場合）
-- ============================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'betting_history') THEN
        ALTER TABLE betting_history 
            ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE 
            USING created_at AT TIME ZONE 'Asia/Tokyo';
    END IF;
END $$;

-- ============================================================
-- 確認クエリ
-- ============================================================
-- マイグレーション後、以下のクエリで確認
-- SELECT column_name, data_type 
-- FROM information_schema.columns 
-- WHERE table_name IN ('races', 'virtual_bets', 'odds_history', 'race_results')
-- AND data_type LIKE '%timestamp%'
-- ORDER BY table_name, column_name;

-- ============================================================
-- 完了メッセージ
-- ============================================================
SELECT 'マイグレーション完了: 全てのTIMESTAMPカラムがTIMESTAMP WITH TIME ZONEに変換されました' AS message;

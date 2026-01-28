```sql
-- 競艇データ収集システム データベーススキーマ V2
-- 役割分担に基づき、DBeaverで実行してください。

-- テーブルが存在する場合は削除（開発用・再作成時に便利）
DROP TABLE IF EXISTS odds, payouts, race_results, before_race_info, race_entries, races, racers, stadiums, external_predictions, collection_logs CASCADE;

-- 競艇場マスターテーブル
CREATE TABLE stadiums (
    stadium_code SMALLINT PRIMARY KEY, -- 競艇場コード (例: 01)
    name VARCHAR(10) NOT NULL UNIQUE -- 競艇場名 (例: 桐生)
);

-- レーサーマスターテーブル
CREATE TABLE racers (
    racer_id INT PRIMARY KEY, -- 選手登録番号 (例: 3415)
    name VARCHAR(50) NOT NULL, -- 選手名
    birth_date DATE, -- 生年月日
    height SMALLINT, -- 身長
    weight SMALLINT, -- 体重
    branch VARCHAR(10), -- 支部
    birth_prefecture VARCHAR(10), -- 出身地
    last_updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP -- 最終更新日時
);

-- レース基本情報テーブル
CREATE TABLE races (
    id BIGSERIAL PRIMARY KEY, -- 内部ID
    race_date DATE NOT NULL, -- 開催日
    stadium_code SMALLINT NOT NULL REFERENCES stadiums(stadium_code), -- 競艇場コード
    race_number SMALLINT NOT NULL, -- レース番号
    title VARCHAR(255), -- レース名
    deadline_at TIMESTAMPTZ, -- 締切予定時刻
    is_canceled BOOLEAN DEFAULT FALSE, -- 中止フラグ
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP, -- 作成日時
    UNIQUE(race_date, stadium_code, race_number) -- 日付・場・レース番号でユニーク
);

-- 出走表テーブル
CREATE TABLE race_entries (
    id BIGSERIAL PRIMARY KEY, -- 内部ID
    race_id BIGINT NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    boat_number SMALLINT NOT NULL, -- 艇番 (1-6)
    racer_id INT NOT NULL REFERENCES racers(racer_id), -- 選手登録番号
    motor_number SMALLINT, -- モーター番号
    boat_number_provided SMALLINT, -- ボート番号
    UNIQUE(race_id, boat_number) -- 同一レースで同じ艇番はありえない
);

-- 時系列オッズテーブル
CREATE TABLE odds (
    id BIGSERIAL PRIMARY KEY, -- 内部ID
    race_id BIGINT NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    odds_type VARCHAR(10) NOT NULL, -- オッズ種別 (例: 'win', 'place', 'exacta', 'quinella', 'wide')
    bet_combination VARCHAR(10) NOT NULL, -- 組み合わせ (例: '1', '1-2')
    odds_value NUMERIC(8, 2) NOT NULL, -- オッズ値
    scraped_at TIMESTAMPTZ NOT NULL, -- 収集時刻（秒単位）
    collection_phase VARCHAR(20) -- 収集タイミング (例: 'initial', 'pre_30', 'pre_5_high_freq')
);
CREATE INDEX idx_odds_race_id ON odds(race_id);
CREATE INDEX idx_odds_scraped_at ON odds(scraped_at);

-- 直前情報テーブル
CREATE TABLE before_race_info (
    id BIGSERIAL PRIMARY KEY,
    race_id BIGINT NOT NULL UNIQUE REFERENCES races(id) ON DELETE CASCADE,
    weather VARCHAR(10),
    wind_speed NUMERIC(4, 1), -- m
    wind_direction SMALLINT, -- 1-16 の方角
    temperature NUMERIC(4, 1), -- ℃
    water_temperature NUMERIC(4, 1), -- ℃
    wave_height NUMERIC(4, 1), -- cm
    exhibition_times JSONB, -- 展示タイム (例: {'1': 6.78, '2': 6.82, ...})
    scraped_at TIMESTAMPTZ NOT NULL
);

-- レース結果テーブル
CREATE TABLE race_results (
    id BIGSERIAL PRIMARY KEY,
    race_id BIGINT NOT NULL UNIQUE REFERENCES races(id) ON DELETE CASCADE,
    arrival_orders JSONB, -- 着順 (例: {'1': 1, '2': 3, '3': 2, ...})
    winning_trick VARCHAR(20), -- 決まり手
    scraped_at TIMESTAMPTZ NOT NULL
);

-- 払戻金テーブル
CREATE TABLE payouts (
    id BIGSERIAL PRIMARY KEY,
    race_result_id BIGINT NOT NULL REFERENCES race_results(id) ON DELETE CASCADE,
    odds_type VARCHAR(10) NOT NULL, -- オッズ種別
    bet_combination VARCHAR(10) NOT NULL, -- 組み合わせ
    payout_amount INT NOT NULL, -- 払戻金額 (円)
    popularity SMALLINT, -- 人気順
    UNIQUE(race_result_id, odds_type, bet_combination)
);

-- 外部予想情報テーブル
CREATE TABLE external_predictions (
    id BIGSERIAL PRIMARY KEY,
    race_id BIGINT NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    source_type VARCHAR(20) NOT NULL, -- 情報源種別 (例: 'x', 'yoso_site')
    source_name VARCHAR(50), -- 情報源名 (例: '競艇太郎', 'マクール')
    prediction_data JSONB, -- 予想内容 (例: {'main_bet': '1-3-2', 'confidence': 'A'})
    author_id VARCHAR(100), -- XのユーザーIDなど
    posted_at TIMESTAMPTZ, -- 投稿日時
    scraped_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_external_predictions_race_id ON external_predictions(race_id);

-- データ収集ログテーブル
CREATE TABLE collection_logs (
    id BIGSERIAL PRIMARY KEY,
    collection_type VARCHAR(50) NOT NULL, -- 収集種別 (例: 'odds_batch', 'result_batch')
    status VARCHAR(20) NOT NULL, -- 状態 ('success', 'failure')
    target_date DATE, -- 対象日
    target_stadium_code SMALLINT, -- 対象場コード
    records_inserted INT, -- 登録レコード数
    message TEXT, -- メッセージやエラー内容
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ
);

-- 初期データの投入（競艇場マスター）
INSERT INTO stadiums (stadium_code, name) VALUES
(1, '桐生'), (2, '戸田'), (3, '江戸川'), (4, '平和島'), (5, '多摩川'),
(6, '浜名湖'), (7, '蒲郡'), (8, '常滑'), (9, '津'), (10, '三国'),
(11, 'びわこ'), (12, '住之江'), (13, '尼崎'), (14, '鳴門'), (15, '丸亀'),
(16, '児島'), (17, '宮島'), (18, '徳山'), (19, '下関'), (20, '若松'),
(21, '芦屋'), (22, '福岡'), (23, '唐津'), (24, '大村');

```

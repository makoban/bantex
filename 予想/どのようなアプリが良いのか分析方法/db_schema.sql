```sql
-- 競艇AIプロジェクト データベーススキーマ
-- PostgreSQL 向け

-- 全てのタイムスタンプはUTCで保存することを推奨

-- 1. 競艇場マスターテーブル
CREATE TABLE IF NOT EXISTS stadiums (
    stadium_code SMALLINT PRIMARY KEY, -- 競艇場コード (例: 01)
    name VARCHAR(10) NOT NULL UNIQUE, -- 競艇場名 (例: 桐生)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. レーサーマスターテーブル
CREATE TABLE IF NOT EXISTS racers (
    racer_id INT PRIMARY KEY, -- 選手登録番号
    name VARCHAR(50) NOT NULL, -- 選手名
    birth_date DATE, -- 生年月日
    height SMALLINT, -- 身長
    weight SMALLINT, -- 体重
    blood_type VARCHAR(2), -- 血液型
    branch VARCHAR(10), -- 支部
    birth_prefecture VARCHAR(10), -- 出身地
    rank VARCHAR(5), -- 級別 (A1, A2, B1, B2)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. レース情報テーブル
CREATE TABLE IF NOT EXISTS races (
    id BIGSERIAL PRIMARY KEY,
    race_date DATE NOT NULL, -- 開催日
    stadium_code SMALLINT NOT NULL REFERENCES stadiums(stadium_code), -- 競艇場コード
    race_number SMALLINT NOT NULL, -- レース番号 (1-12)
    title VARCHAR(255), -- レース名 (例: 第５９回スポーツニッポン杯)
    distance SMALLINT, -- 距離 (例: 1800)
    deadline_time TIMESTAMPTZ, -- 締切予定時刻
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (race_date, stadium_code, race_number) -- 同一日の同一場・同一レースはユニーク
);

-- 4. 出走表テーブル
CREATE TABLE IF NOT EXISTS race_entries (
    id BIGSERIAL PRIMARY KEY,
    race_id BIGINT NOT NULL REFERENCES races(id),
    boat_number SMALLINT NOT NULL, -- 艇番 (1-6)
    racer_id INT NOT NULL REFERENCES racers(racer_id), -- 選手登録番号
    motor_number SMALLINT, -- モーター番号
    boat_body_number SMALLINT, -- ボート番号
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (race_id, boat_number)
);

-- 5. 時系列オッズデータテーブル (最重要)
CREATE TABLE IF NOT EXISTS odds (
    id BIGSERIAL PRIMARY KEY,
    race_id BIGINT NOT NULL REFERENCES races(id),
    odds_type VARCHAR(20) NOT NULL, -- オッズ種別 (例: 'trifecta', 'win', 'placeshow')
    bet_combination VARCHAR(10) NOT NULL, -- 組み合わせ (例: '1-2-3', '1-2', '1')
    odds_value NUMERIC(8, 2) NOT NULL, -- オッズ値
    scraped_at TIMESTAMPTZ NOT NULL, -- スクレイピング実行時刻 (秒単位)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- オッズデータへの高速アクセスのためのインデックス
CREATE INDEX IF NOT EXISTS idx_odds_race_id_scraped_at ON odds (race_id, scraped_at DESC);

-- 6. レース直前情報テーブル
CREATE TABLE IF NOT EXISTS before_race_info (
    id BIGSERIAL PRIMARY KEY,
    race_id BIGINT NOT NULL REFERENCES races(id) UNIQUE, -- レースID
    weather VARCHAR(10), -- 天候
    wind_direction VARCHAR(5), -- 風向
    wind_speed SMALLINT, -- 風速 (m)
    wave_height SMALLINT, -- 波高 (cm)
    temperature NUMERIC(4, 1), -- 気温 (℃)
    water_temperature NUMERIC(4, 1), -- 水温 (℃)
    scraped_at TIMESTAMPTZ NOT NULL, -- スクレイピング実行時刻
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. レース結果テーブル
CREATE TABLE IF NOT EXISTS race_results (
    id BIGSERIAL PRIMARY KEY,
    race_id BIGINT NOT NULL REFERENCES races(id) UNIQUE, -- レースID
    weather VARCHAR(10), -- 天候（レース終了時）
    wind_direction VARCHAR(5), -- 風向
    wind_speed SMALLINT, -- 風速
    wave_height SMALLINT, -- 波高
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. 払戻金テーブル
CREATE TABLE IF NOT EXISTS payouts (
    id BIGSERIAL PRIMARY KEY,
    race_result_id BIGINT NOT NULL REFERENCES race_results(id),
    odds_type VARCHAR(20) NOT NULL, -- オッズ種別
    bet_combination VARCHAR(10) NOT NULL, -- 的中組み合わせ
    payout_amount INT NOT NULL, -- 払戻金額
    popularity SMALLINT, -- 人気順
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (race_result_id, odds_type, bet_combination)
);

-- 初期データ投入（競艇場マスター）
INSERT INTO stadiums (stadium_code, name) VALUES
(1, '桐生'), (2, '戸田'), (3, '江戸川'), (4, '平和島'), (5, '多摩川'), (6, '浜名湖'),
(7, '蒲郡'), (8, '常滑'), (9, '津'), (10, '三国'), (11, 'びわこ'), (12, '住之江'),
(13, '尼崎'), (14, '鳴門'), (15, '丸亀'), (16, '児島'), (17, '宮島'), (18, '徳山'),
(19, '下関'), (20, '若松'), (21, '芦屋'), (22, '福岡'), (23, '唐津'), (24, '大村')
ON CONFLICT (stadium_code) DO NOTHING;

```

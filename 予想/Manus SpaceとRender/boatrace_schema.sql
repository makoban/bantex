-- 競艇データ収集システム - データベーススキーマ
-- 作成日: 2026-01-04

-- ============================================================
-- 1. races テーブル（既存）
-- ============================================================
-- レースの基本情報を格納
-- CREATE TABLE IF NOT EXISTS races (
--     id SERIAL PRIMARY KEY,
--     race_date DATE NOT NULL,
--     stadium_code INTEGER NOT NULL,
--     race_number INTEGER NOT NULL,
--     title VARCHAR(255),
--     deadline_at TIMESTAMP,
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     UNIQUE(race_date, stadium_code, race_number)
-- );

-- ============================================================
-- 2. odds テーブル（新規）
-- ============================================================
-- オッズの時系列データを格納
-- 各レースのオッズを定期的に収集し、時系列で保存する

CREATE TABLE IF NOT EXISTS odds (
    id SERIAL PRIMARY KEY,
    race_id INTEGER NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    scraped_at TIMESTAMP NOT NULL,  -- オッズ取得時刻
    odds_type VARCHAR(20) NOT NULL, -- 'trifecta', 'trio', 'exacta', 'quinella', 'win', 'place_show'
    combination VARCHAR(20) NOT NULL, -- '1-2-3', '1=2=3', '1-2', '1=2', '1' など
    odds_value DECIMAL(10, 2),      -- オッズ値（単一値の場合）
    odds_min DECIMAL(10, 2),        -- オッズ最小値（複勝の場合）
    odds_max DECIMAL(10, 2),        -- オッズ最大値（複勝の場合）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(race_id, scraped_at, odds_type, combination)
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_odds_race_id ON odds(race_id);
CREATE INDEX IF NOT EXISTS idx_odds_scraped_at ON odds(scraped_at);
CREATE INDEX IF NOT EXISTS idx_odds_type ON odds(odds_type);

-- ============================================================
-- 3. race_results テーブル（新規）
-- ============================================================
-- レース結果を格納

CREATE TABLE IF NOT EXISTS race_results (
    id SERIAL PRIMARY KEY,
    race_id INTEGER NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    
    -- 着順（1着〜6着の艇番）
    first_place INTEGER,
    second_place INTEGER,
    third_place INTEGER,
    fourth_place INTEGER,
    fifth_place INTEGER,
    sixth_place INTEGER,
    
    -- レース状況
    race_status VARCHAR(50),        -- '成立', '不成立', '中止' など
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(race_id)
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_race_results_race_id ON race_results(race_id);

-- ============================================================
-- 4. payoffs テーブル（新規）
-- ============================================================
-- 払戻金情報を格納

CREATE TABLE IF NOT EXISTS payoffs (
    id SERIAL PRIMARY KEY,
    race_id INTEGER NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    bet_type VARCHAR(20) NOT NULL,  -- 'win', 'place_show', 'exacta', 'quinella', 'quinella_place', 'trifecta', 'trio'
    combination VARCHAR(20) NOT NULL, -- '1', '1-2', '1=2', '1-2-3', '1=2=3' など
    payoff INTEGER NOT NULL,        -- 払戻金（円）
    popularity INTEGER,             -- 人気順
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(race_id, bet_type, combination)
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_payoffs_race_id ON payoffs(race_id);
CREATE INDEX IF NOT EXISTS idx_payoffs_bet_type ON payoffs(bet_type);

-- ============================================================
-- 5. stadiums マスタテーブル（参考）
-- ============================================================
-- 競艇場のマスタデータ

CREATE TABLE IF NOT EXISTS stadiums (
    code INTEGER PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    prefecture VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 初期データ投入
INSERT INTO stadiums (code, name, prefecture) VALUES
    (1, '桐生', '群馬県'),
    (2, '戸田', '埼玉県'),
    (3, '江戸川', '東京都'),
    (4, '平和島', '東京都'),
    (5, '多摩川', '東京都'),
    (6, '浜名湖', '静岡県'),
    (7, '蒲郡', '愛知県'),
    (8, '常滑', '愛知県'),
    (9, '津', '三重県'),
    (10, '三国', '福井県'),
    (11, 'びわこ', '滋賀県'),
    (12, '住之江', '大阪府'),
    (13, '尼崎', '兵庫県'),
    (14, '鳴門', '徳島県'),
    (15, '丸亀', '香川県'),
    (16, '児島', '岡山県'),
    (17, '宮島', '広島県'),
    (18, '徳山', '山口県'),
    (19, '下関', '山口県'),
    (20, '若松', '福岡県'),
    (21, '芦屋', '福岡県'),
    (22, '福岡', '福岡県'),
    (23, '唐津', '佐賀県'),
    (24, '大村', '長崎県')
ON CONFLICT (code) DO NOTHING;

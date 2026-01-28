#!/usr/bin/env python3
"""
データベース初期化スクリプト
テーブル作成と初期データ投入
"""

import os
import sys
import logging
import psycopg2

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- 競艇AIプロジェクト データベーススキーマ

-- 1. 競艇場マスターテーブル
CREATE TABLE IF NOT EXISTS stadiums (
    stadium_code SMALLINT PRIMARY KEY,
    name VARCHAR(10) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. レーサーマスターテーブル
CREATE TABLE IF NOT EXISTS racers (
    racer_id INT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    birth_date DATE,
    height SMALLINT,
    weight SMALLINT,
    blood_type VARCHAR(2),
    branch VARCHAR(10),
    birth_prefecture VARCHAR(10),
    rank VARCHAR(5),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. レース情報テーブル
CREATE TABLE IF NOT EXISTS races (
    id BIGSERIAL PRIMARY KEY,
    race_date DATE NOT NULL,
    stadium_code SMALLINT NOT NULL REFERENCES stadiums(stadium_code),
    race_number SMALLINT NOT NULL,
    title VARCHAR(255),
    distance SMALLINT,
    deadline_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (race_date, stadium_code, race_number)
);

-- 4. 出走表テーブル
CREATE TABLE IF NOT EXISTS race_entries (
    id BIGSERIAL PRIMARY KEY,
    race_id BIGINT NOT NULL REFERENCES races(id),
    boat_number SMALLINT NOT NULL,
    racer_id INT NOT NULL REFERENCES racers(racer_id),
    motor_number SMALLINT,
    boat_body_number SMALLINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (race_id, boat_number)
);

-- 5. 時系列オッズデータテーブル
CREATE TABLE IF NOT EXISTS odds (
    id BIGSERIAL PRIMARY KEY,
    race_id BIGINT NOT NULL REFERENCES races(id),
    odds_type VARCHAR(20) NOT NULL,
    bet_combination VARCHAR(10) NOT NULL,
    odds_value NUMERIC(8, 2) NOT NULL,
    scraped_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- オッズデータへのインデックス
CREATE INDEX IF NOT EXISTS idx_odds_race_id_scraped_at ON odds (race_id, scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_odds_race_type ON odds (race_id, odds_type);

-- 6. レース直前情報テーブル
CREATE TABLE IF NOT EXISTS before_race_info (
    id BIGSERIAL PRIMARY KEY,
    race_id BIGINT NOT NULL REFERENCES races(id) UNIQUE,
    weather VARCHAR(10),
    wind_direction VARCHAR(5),
    wind_speed SMALLINT,
    wave_height SMALLINT,
    temperature NUMERIC(4, 1),
    water_temperature NUMERIC(4, 1),
    scraped_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. レース結果テーブル
CREATE TABLE IF NOT EXISTS race_results (
    id BIGSERIAL PRIMARY KEY,
    race_id BIGINT NOT NULL REFERENCES races(id) UNIQUE,
    weather VARCHAR(10),
    wind_direction VARCHAR(5),
    wind_speed SMALLINT,
    wave_height SMALLINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. 払戻金テーブル
CREATE TABLE IF NOT EXISTS payouts (
    id BIGSERIAL PRIMARY KEY,
    race_result_id BIGINT NOT NULL REFERENCES race_results(id),
    odds_type VARCHAR(20) NOT NULL,
    bet_combination VARCHAR(10) NOT NULL,
    payout_amount INT NOT NULL,
    popularity SMALLINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (race_result_id, odds_type, bet_combination)
);

-- 9. データ収集ログテーブル
CREATE TABLE IF NOT EXISTS collection_logs (
    id BIGSERIAL PRIMARY KEY,
    collection_type VARCHAR(50) NOT NULL,
    target_date DATE,
    stadium_code SMALLINT,
    race_number SMALLINT,
    status VARCHAR(20) NOT NULL,
    records_collected INT DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

STADIUM_DATA = """
INSERT INTO stadiums (stadium_code, name) VALUES
(1, '桐生'), (2, '戸田'), (3, '江戸川'), (4, '平和島'), (5, '多摩川'), (6, '浜名湖'),
(7, '蒲郡'), (8, '常滑'), (9, '津'), (10, '三国'), (11, 'びわこ'), (12, '住之江'),
(13, '尼崎'), (14, '鳴門'), (15, '丸亀'), (16, '児島'), (17, '宮島'), (18, '徳山'),
(19, '下関'), (20, '若松'), (21, '芦屋'), (22, '福岡'), (23, '唐津'), (24, '大村')
ON CONFLICT (stadium_code) DO NOTHING;
"""


def init_database(db_url: str):
    """データベースを初期化"""
    logger.info("Connecting to database...")
    conn = psycopg2.connect(db_url)
    
    try:
        with conn.cursor() as cur:
            # スキーマ作成
            logger.info("Creating tables...")
            cur.execute(SCHEMA_SQL)
            conn.commit()
            logger.info("Tables created successfully")

            # 初期データ投入
            logger.info("Inserting initial data...")
            cur.execute(STADIUM_DATA)
            conn.commit()
            logger.info("Initial data inserted successfully")

            # テーブル一覧を確認
            cur.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' ORDER BY table_name
            """)
            tables = cur.fetchall()
            logger.info(f"Created tables: {[t[0] for t in tables]}")

    finally:
        conn.close()

    logger.info("Database initialization completed!")


def main():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL environment variable is not set")
        sys.exit(1)

    init_database(db_url)


if __name__ == '__main__':
    main()

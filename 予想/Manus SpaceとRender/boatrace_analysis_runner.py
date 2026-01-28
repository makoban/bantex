#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
競艇 21年分データ 勝ちパターン分析プログラム
各SQLクエリを個別に実行し、結果をCSVファイルに出力します。

使用方法:
1. 環境変数でDB接続情報を設定:
   export DATABASE_URL="postgresql://user:password@host:port/dbname"
   または
   export DB_HOST="your-host"
   export DB_PORT="5432"
   export DB_NAME="your-db"
   export DB_USER="your-user"
   export DB_PASSWORD="your-password"

2. 実行:
   python boatrace_analysis_runner.py

3. 結果は analysis_results/ フォルダにCSVで出力されます
"""

import os
import sys
import csv
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# 出力フォルダ
OUTPUT_DIR = "analysis_results"

# 17項目の分析クエリ定義
ANALYSIS_QUERIES = [
    {
        "id": "01",
        "name": "1号艇1着率分析",
        "filename": "01_boat1_win_rate.csv",
        "sql": """
SELECT 
    '1号艇1着率分析' as analysis_type,
    COUNT(*) as total_races,
    SUM(CASE WHEN r.boat_no = '1' AND r.rank = '1' THEN 1 ELSE 0 END) as boat1_wins,
    ROUND(SUM(CASE WHEN r.boat_no = '1' AND r.rank = '1' THEN 1 ELSE 0 END)::numeric / COUNT(DISTINCT (r.race_date || r.stadium_code || r.race_no)) * 100, 2) as boat1_win_rate,
    ROUND(AVG(CASE WHEN p.bet_type = 'tansho' AND p.combination = '1' THEN p.payout ELSE NULL END), 0) as avg_boat1_payout
FROM historical_race_results r
LEFT JOIN historical_payoffs p 
    ON r.race_date = p.race_date 
    AND r.stadium_code = p.stadium_code 
    AND r.race_no = p.race_no
    AND p.bet_type = 'tansho'
    AND p.combination = '1'
WHERE r.rank = '1'
"""
    },
    {
        "id": "01b",
        "name": "年別1号艇1着率推移",
        "filename": "01b_boat1_win_rate_yearly.csv",
        "sql": """
SELECT 
    LEFT(r.race_date, 4) as year,
    COUNT(DISTINCT (r.race_date || r.stadium_code || r.race_no)) as total_races,
    SUM(CASE WHEN r.boat_no = '1' THEN 1 ELSE 0 END) as boat1_wins,
    ROUND(SUM(CASE WHEN r.boat_no = '1' THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as boat1_win_rate
FROM historical_race_results r
WHERE r.rank = '1'
GROUP BY LEFT(r.race_date, 4)
ORDER BY year
"""
    },
    {
        "id": "02",
        "name": "人気別単勝回収率",
        "filename": "02_popularity_return_rate.csv",
        "sql": """
SELECT 
    p.popularity,
    COUNT(*) as bet_count,
    SUM(p.payout) as total_payout,
    ROUND(SUM(p.payout)::numeric / COUNT(*), 2) as avg_payout,
    ROUND(SUM(p.payout)::numeric / (COUNT(*) * 100) * 100, 2) as return_rate
FROM historical_payoffs p
WHERE p.bet_type = 'tansho'
    AND p.popularity BETWEEN 1 AND 6
GROUP BY p.popularity
ORDER BY p.popularity
"""
    },
    {
        "id": "03",
        "name": "場別単勝回収率（1番人気）",
        "filename": "03_stadium_return_rate.csv",
        "sql": """
SELECT 
    p.stadium_code,
    CASE p.stadium_code
        WHEN '01' THEN '桐生' WHEN '02' THEN '戸田' WHEN '03' THEN '江戸川'
        WHEN '04' THEN '平和島' WHEN '05' THEN '多摩川' WHEN '06' THEN '浜名湖'
        WHEN '07' THEN '蒲郡' WHEN '08' THEN '常滑' WHEN '09' THEN '津'
        WHEN '10' THEN '三国' WHEN '11' THEN 'びわこ' WHEN '12' THEN '住之江'
        WHEN '13' THEN '尼崎' WHEN '14' THEN '鳴門' WHEN '15' THEN '丸亀'
        WHEN '16' THEN '児島' WHEN '17' THEN '宮島' WHEN '18' THEN '徳山'
        WHEN '19' THEN '下関' WHEN '20' THEN '若松' WHEN '21' THEN '芦屋'
        WHEN '22' THEN '福岡' WHEN '23' THEN '唐津' WHEN '24' THEN '大村'
    END as stadium_name,
    COUNT(*) as total_races,
    ROUND(AVG(p.payout), 0) as avg_tansho_payout,
    ROUND(AVG(p.payout)::numeric / 100 * 100, 2) as return_rate_percent
FROM historical_payoffs p
WHERE p.bet_type = 'tansho'
    AND p.popularity = 1
GROUP BY p.stadium_code
ORDER BY return_rate_percent DESC
"""
    },
    {
        "id": "04",
        "name": "1号艇勝率別の成績",
        "filename": "04_boat1_winrate_performance.csv",
        "sql": """
SELECT 
    CASE 
        WHEN prog.national_win_rate >= 8.0 THEN '8.0以上'
        WHEN prog.national_win_rate >= 7.0 THEN '7.0-7.99'
        WHEN prog.national_win_rate >= 6.0 THEN '6.0-6.99'
        WHEN prog.national_win_rate >= 5.0 THEN '5.0-5.99'
        ELSE '5.0未満'
    END as win_rate_range,
    COUNT(*) as total_races,
    SUM(CASE WHEN r.rank = '1' THEN 1 ELSE 0 END) as wins,
    ROUND(SUM(CASE WHEN r.rank = '1' THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as win_rate,
    ROUND(AVG(CASE WHEN r.rank = '1' THEN p.payout ELSE 0 END), 0) as avg_return
FROM historical_programs prog
JOIN historical_race_results r 
    ON prog.race_date = r.race_date 
    AND prog.stadium_code = r.stadium_code 
    AND prog.race_no = r.race_no
    AND prog.boat_no = r.boat_no
LEFT JOIN historical_payoffs p 
    ON prog.race_date = p.race_date 
    AND prog.stadium_code = p.stadium_code 
    AND prog.race_no = p.race_no
    AND p.bet_type = 'tansho'
    AND p.combination = prog.boat_no
WHERE prog.boat_no = '1'
    AND prog.national_win_rate IS NOT NULL
GROUP BY CASE 
        WHEN prog.national_win_rate >= 8.0 THEN '8.0以上'
        WHEN prog.national_win_rate >= 7.0 THEN '7.0-7.99'
        WHEN prog.national_win_rate >= 6.0 THEN '6.0-6.99'
        WHEN prog.national_win_rate >= 5.0 THEN '5.0-5.99'
        ELSE '5.0未満'
    END
ORDER BY win_rate DESC
"""
    },
    {
        "id": "05",
        "name": "月別傾向",
        "filename": "05_monthly_trend.csv",
        "sql": """
SELECT 
    SUBSTRING(p.race_date, 5, 2) as month,
    CASE SUBSTRING(p.race_date, 5, 2)
        WHEN '01' THEN '1月' WHEN '02' THEN '2月' WHEN '03' THEN '3月'
        WHEN '04' THEN '4月' WHEN '05' THEN '5月' WHEN '06' THEN '6月'
        WHEN '07' THEN '7月' WHEN '08' THEN '8月' WHEN '09' THEN '9月'
        WHEN '10' THEN '10月' WHEN '11' THEN '11月' WHEN '12' THEN '12月'
    END as month_name,
    COUNT(*) as total_races,
    ROUND(AVG(p.payout), 0) as avg_tansho_payout,
    ROUND(AVG(CASE WHEN p.popularity = 1 THEN p.payout END), 0) as avg_fav_payout,
    ROUND(AVG(CASE WHEN p.popularity >= 4 THEN p.payout END), 0) as avg_longshot_payout
FROM historical_payoffs p
WHERE p.bet_type = 'tansho'
GROUP BY SUBSTRING(p.race_date, 5, 2)
ORDER BY month
"""
    },
    {
        "id": "06",
        "name": "レース番号別傾向",
        "filename": "06_race_number_trend.csv",
        "sql": """
SELECT 
    p.race_no,
    CASE 
        WHEN p.race_no IN ('01', '02', '03', '04') THEN '序盤(1-4R)'
        WHEN p.race_no IN ('05', '06', '07', '08') THEN '中盤(5-8R)'
        ELSE '終盤(9-12R)'
    END as race_period,
    COUNT(*) as total_races,
    ROUND(AVG(p.payout), 0) as avg_tansho_payout,
    ROUND(AVG(CASE WHEN p.popularity = 1 THEN p.payout END), 0) as avg_fav_payout,
    SUM(CASE WHEN p.popularity >= 4 THEN 1 ELSE 0 END) as longshot_wins,
    ROUND(SUM(CASE WHEN p.popularity >= 4 THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as longshot_rate
FROM historical_payoffs p
WHERE p.bet_type = 'tansho'
GROUP BY p.race_no
ORDER BY p.race_no
"""
    },
    {
        "id": "07",
        "name": "曜日別傾向",
        "filename": "07_day_of_week_trend.csv",
        "sql": """
SELECT 
    EXTRACT(DOW FROM TO_DATE(p.race_date, 'YYYYMMDD')) as dow_num,
    CASE EXTRACT(DOW FROM TO_DATE(p.race_date, 'YYYYMMDD'))
        WHEN 0 THEN '日曜'
        WHEN 1 THEN '月曜'
        WHEN 2 THEN '火曜'
        WHEN 3 THEN '水曜'
        WHEN 4 THEN '木曜'
        WHEN 5 THEN '金曜'
        WHEN 6 THEN '土曜'
    END as day_of_week,
    COUNT(*) as total_races,
    ROUND(AVG(p.payout), 0) as avg_tansho_payout,
    ROUND(AVG(CASE WHEN p.popularity = 1 THEN p.payout END), 0) as avg_fav_payout,
    ROUND(AVG(CASE WHEN p.popularity = 1 THEN p.payout END)::numeric / 100 * 100, 2) as fav_return_rate
FROM historical_payoffs p
WHERE p.bet_type = 'tansho'
GROUP BY EXTRACT(DOW FROM TO_DATE(p.race_date, 'YYYYMMDD'))
ORDER BY dow_num
"""
    },
    {
        "id": "08",
        "name": "選手級別成績",
        "filename": "08_racer_rank_performance.csv",
        "sql": """
SELECT 
    prog.rank as boat1_rank,
    COUNT(*) as total_races,
    SUM(CASE WHEN r.rank = '1' THEN 1 ELSE 0 END) as wins,
    ROUND(SUM(CASE WHEN r.rank = '1' THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as win_rate,
    ROUND(AVG(CASE WHEN r.rank = '1' THEN p.payout ELSE 0 END), 0) as avg_return
FROM historical_programs prog
JOIN historical_race_results r 
    ON prog.race_date = r.race_date 
    AND prog.stadium_code = r.stadium_code 
    AND prog.race_no = r.race_no
    AND prog.boat_no = r.boat_no
LEFT JOIN historical_payoffs p 
    ON prog.race_date = p.race_date 
    AND prog.stadium_code = p.stadium_code 
    AND prog.race_no = p.race_no
    AND p.bet_type = 'tansho'
    AND p.combination = '1'
WHERE prog.boat_no = '1'
    AND prog.rank IN ('A1', 'A2', 'B1', 'B2')
GROUP BY prog.rank
ORDER BY win_rate DESC
"""
    },
    {
        "id": "09",
        "name": "モーター2連率別成績",
        "filename": "09_motor_rate_performance.csv",
        "sql": """
SELECT 
    CASE 
        WHEN prog.motor_2nd_rate >= 50 THEN '50%以上'
        WHEN prog.motor_2nd_rate >= 40 THEN '40-49%'
        WHEN prog.motor_2nd_rate >= 30 THEN '30-39%'
        ELSE '30%未満'
    END as motor_rate_range,
    COUNT(*) as total_entries,
    SUM(CASE WHEN r.rank = '1' THEN 1 ELSE 0 END) as wins,
    ROUND(SUM(CASE WHEN r.rank = '1' THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as win_rate,
    SUM(CASE WHEN r.rank IN ('1', '2') THEN 1 ELSE 0 END) as top2_count,
    ROUND(SUM(CASE WHEN r.rank IN ('1', '2') THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as top2_rate
FROM historical_programs prog
JOIN historical_race_results r 
    ON prog.race_date = r.race_date 
    AND prog.stadium_code = r.stadium_code 
    AND prog.race_no = r.race_no
    AND prog.boat_no = r.boat_no
WHERE prog.motor_2nd_rate IS NOT NULL
GROUP BY CASE 
        WHEN prog.motor_2nd_rate >= 50 THEN '50%以上'
        WHEN prog.motor_2nd_rate >= 40 THEN '40-49%'
        WHEN prog.motor_2nd_rate >= 30 THEN '30-39%'
        ELSE '30%未満'
    END
ORDER BY win_rate DESC
"""
    },
    {
        "id": "10",
        "name": "枠番別穴傾向",
        "filename": "10_boat_number_upset.csv",
        "sql": """
SELECT 
    r.boat_no,
    COUNT(*) as total_wins,
    ROUND(AVG(p.payout), 0) as avg_payout,
    SUM(CASE WHEN p.payout >= 1000 THEN 1 ELSE 0 END) as high_payout_count,
    ROUND(SUM(CASE WHEN p.payout >= 1000 THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as high_payout_rate,
    MAX(p.payout) as max_payout
FROM historical_race_results r
JOIN historical_payoffs p 
    ON r.race_date = p.race_date 
    AND r.stadium_code = p.stadium_code 
    AND r.race_no = p.race_no
    AND p.bet_type = 'tansho'
    AND p.combination = r.boat_no
WHERE r.rank = '1'
GROUP BY r.boat_no
ORDER BY r.boat_no
"""
    },
    {
        "id": "11",
        "name": "荒れるレース条件",
        "filename": "11_upset_conditions.csv",
        "sql": """
SELECT 
    p.stadium_code,
    CASE p.stadium_code
        WHEN '01' THEN '桐生' WHEN '02' THEN '戸田' WHEN '03' THEN '江戸川'
        WHEN '04' THEN '平和島' WHEN '05' THEN '多摩川' WHEN '06' THEN '浜名湖'
        WHEN '07' THEN '蒲郡' WHEN '08' THEN '常滑' WHEN '09' THEN '津'
        WHEN '10' THEN '三国' WHEN '11' THEN 'びわこ' WHEN '12' THEN '住之江'
        WHEN '13' THEN '尼崎' WHEN '14' THEN '鳴門' WHEN '15' THEN '丸亀'
        WHEN '16' THEN '児島' WHEN '17' THEN '宮島' WHEN '18' THEN '徳山'
        WHEN '19' THEN '下関' WHEN '20' THEN '若松' WHEN '21' THEN '芦屋'
        WHEN '22' THEN '福岡' WHEN '23' THEN '唐津' WHEN '24' THEN '大村'
    END as stadium_name,
    p.race_no,
    COUNT(*) as total_races,
    ROUND(AVG(p.payout), 0) as avg_payout,
    SUM(CASE WHEN p.payout >= 2000 THEN 1 ELSE 0 END) as upset_count,
    ROUND(SUM(CASE WHEN p.payout >= 2000 THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as upset_rate
FROM historical_payoffs p
WHERE p.bet_type = 'tansho'
GROUP BY p.stadium_code, p.race_no
HAVING COUNT(*) >= 1000
ORDER BY upset_rate DESC
LIMIT 50
"""
    },
    {
        "id": "12",
        "name": "鉄板レース条件",
        "filename": "12_solid_conditions.csv",
        "sql": """
SELECT 
    p.stadium_code,
    CASE p.stadium_code
        WHEN '01' THEN '桐生' WHEN '02' THEN '戸田' WHEN '03' THEN '江戸川'
        WHEN '04' THEN '平和島' WHEN '05' THEN '多摩川' WHEN '06' THEN '浜名湖'
        WHEN '07' THEN '蒲郡' WHEN '08' THEN '常滑' WHEN '09' THEN '津'
        WHEN '10' THEN '三国' WHEN '11' THEN 'びわこ' WHEN '12' THEN '住之江'
        WHEN '13' THEN '尼崎' WHEN '14' THEN '鳴門' WHEN '15' THEN '丸亀'
        WHEN '16' THEN '児島' WHEN '17' THEN '宮島' WHEN '18' THEN '徳山'
        WHEN '19' THEN '下関' WHEN '20' THEN '若松' WHEN '21' THEN '芦屋'
        WHEN '22' THEN '福岡' WHEN '23' THEN '唐津' WHEN '24' THEN '大村'
    END as stadium_name,
    p.race_no,
    COUNT(*) as total_races,
    SUM(CASE WHEN p.popularity = 1 THEN 1 ELSE 0 END) as fav_wins,
    ROUND(SUM(CASE WHEN p.popularity = 1 THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as fav_win_rate
FROM historical_payoffs p
WHERE p.bet_type = 'tansho'
GROUP BY p.stadium_code, p.race_no
HAVING COUNT(*) >= 1000
ORDER BY fav_win_rate DESC
LIMIT 50
"""
    },
    {
        "id": "13",
        "name": "コース別2連率",
        "filename": "13_course_top2_rate.csv",
        "sql": """
SELECT 
    r.boat_no as course,
    COUNT(*) as total_entries,
    SUM(CASE WHEN r.rank = '1' THEN 1 ELSE 0 END) as first_place,
    SUM(CASE WHEN r.rank = '2' THEN 1 ELSE 0 END) as second_place,
    ROUND(SUM(CASE WHEN r.rank = '1' THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as win_rate,
    ROUND(SUM(CASE WHEN r.rank IN ('1', '2') THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as top2_rate
FROM historical_race_results r
GROUP BY r.boat_no
ORDER BY r.boat_no
"""
    },
    {
        "id": "14",
        "name": "2連複1=3回収率",
        "filename": "14_quinella_1_3_return.csv",
        "sql": """
SELECT 
    p.stadium_code,
    CASE p.stadium_code
        WHEN '01' THEN '桐生' WHEN '02' THEN '戸田' WHEN '03' THEN '江戸川'
        WHEN '04' THEN '平和島' WHEN '05' THEN '多摩川' WHEN '06' THEN '浜名湖'
        WHEN '07' THEN '蒲郡' WHEN '08' THEN '常滑' WHEN '09' THEN '津'
        WHEN '10' THEN '三国' WHEN '11' THEN 'びわこ' WHEN '12' THEN '住之江'
        WHEN '13' THEN '尼崎' WHEN '14' THEN '鳴門' WHEN '15' THEN '丸亀'
        WHEN '16' THEN '児島' WHEN '17' THEN '宮島' WHEN '18' THEN '徳山'
        WHEN '19' THEN '下関' WHEN '20' THEN '若松' WHEN '21' THEN '芦屋'
        WHEN '22' THEN '福岡' WHEN '23' THEN '唐津' WHEN '24' THEN '大村'
    END as stadium_name,
    COUNT(*) as hit_count,
    ROUND(AVG(p.payout), 0) as avg_payout,
    ROUND(AVG(p.payout)::numeric / 100 * 100, 2) as return_rate
FROM historical_payoffs p
WHERE p.bet_type = 'nirenpuku'
    AND p.combination IN ('1=3', '1-3', '3=1', '3-1')
GROUP BY p.stadium_code
ORDER BY return_rate DESC
"""
    },
    {
        "id": "15",
        "name": "3連単万舟出現率",
        "filename": "15_trifecta_high_payout.csv",
        "sql": """
SELECT 
    p.stadium_code,
    CASE p.stadium_code
        WHEN '01' THEN '桐生' WHEN '02' THEN '戸田' WHEN '03' THEN '江戸川'
        WHEN '04' THEN '平和島' WHEN '05' THEN '多摩川' WHEN '06' THEN '浜名湖'
        WHEN '07' THEN '蒲郡' WHEN '08' THEN '常滑' WHEN '09' THEN '津'
        WHEN '10' THEN '三国' WHEN '11' THEN 'びわこ' WHEN '12' THEN '住之江'
        WHEN '13' THEN '尼崎' WHEN '14' THEN '鳴門' WHEN '15' THEN '丸亀'
        WHEN '16' THEN '児島' WHEN '17' THEN '宮島' WHEN '18' THEN '徳山'
        WHEN '19' THEN '下関' WHEN '20' THEN '若松' WHEN '21' THEN '芦屋'
        WHEN '22' THEN '福岡' WHEN '23' THEN '唐津' WHEN '24' THEN '大村'
    END as stadium_name,
    COUNT(*) as total_races,
    SUM(CASE WHEN p.payout >= 10000 THEN 1 ELSE 0 END) as manbune_count,
    ROUND(SUM(CASE WHEN p.payout >= 10000 THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as manbune_rate,
    ROUND(AVG(p.payout), 0) as avg_payout,
    MAX(p.payout) as max_payout
FROM historical_payoffs p
WHERE p.bet_type = 'sanrentan'
GROUP BY p.stadium_code
ORDER BY manbune_rate DESC
"""
    },
    {
        "id": "16",
        "name": "1号艇A1選手の場別成績",
        "filename": "16_boat1_a1_by_stadium.csv",
        "sql": """
SELECT 
    prog.stadium_code,
    CASE prog.stadium_code
        WHEN '01' THEN '桐生' WHEN '02' THEN '戸田' WHEN '03' THEN '江戸川'
        WHEN '04' THEN '平和島' WHEN '05' THEN '多摩川' WHEN '06' THEN '浜名湖'
        WHEN '07' THEN '蒲郡' WHEN '08' THEN '常滑' WHEN '09' THEN '津'
        WHEN '10' THEN '三国' WHEN '11' THEN 'びわこ' WHEN '12' THEN '住之江'
        WHEN '13' THEN '尼崎' WHEN '14' THEN '鳴門' WHEN '15' THEN '丸亀'
        WHEN '16' THEN '児島' WHEN '17' THEN '宮島' WHEN '18' THEN '徳山'
        WHEN '19' THEN '下関' WHEN '20' THEN '若松' WHEN '21' THEN '芦屋'
        WHEN '22' THEN '福岡' WHEN '23' THEN '唐津' WHEN '24' THEN '大村'
    END as stadium_name,
    COUNT(*) as total_races,
    SUM(CASE WHEN r.rank = '1' THEN 1 ELSE 0 END) as wins,
    ROUND(SUM(CASE WHEN r.rank = '1' THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as win_rate,
    ROUND(AVG(CASE WHEN r.rank = '1' THEN p.payout ELSE 0 END), 0) as avg_return
FROM historical_programs prog
JOIN historical_race_results r 
    ON prog.race_date = r.race_date 
    AND prog.stadium_code = r.stadium_code 
    AND prog.race_no = r.race_no
    AND prog.boat_no = r.boat_no
LEFT JOIN historical_payoffs p 
    ON prog.race_date = p.race_date 
    AND prog.stadium_code = p.stadium_code 
    AND prog.race_no = p.race_no
    AND p.bet_type = 'tansho'
    AND p.combination = '1'
WHERE prog.boat_no = '1'
    AND prog.rank = 'A1'
GROUP BY prog.stadium_code
ORDER BY win_rate DESC
"""
    },
    {
        "id": "17",
        "name": "回収率100%超え条件ランキング",
        "filename": "17_winning_pattern_ranking.csv",
        "sql": """
WITH condition_stats AS (
    SELECT 
        p.stadium_code,
        p.race_no,
        SUBSTRING(p.race_date, 5, 2) as month,
        COUNT(*) as bet_count,
        SUM(CASE WHEN p.popularity = 1 THEN p.payout ELSE 0 END) as total_return,
        SUM(CASE WHEN p.popularity = 1 THEN 100 ELSE 0 END) as total_bet
    FROM historical_payoffs p
    WHERE p.bet_type = 'tansho'
    GROUP BY p.stadium_code, p.race_no, SUBSTRING(p.race_date, 5, 2)
    HAVING COUNT(*) >= 500
)
SELECT 
    stadium_code,
    CASE stadium_code
        WHEN '01' THEN '桐生' WHEN '02' THEN '戸田' WHEN '03' THEN '江戸川'
        WHEN '04' THEN '平和島' WHEN '05' THEN '多摩川' WHEN '06' THEN '浜名湖'
        WHEN '07' THEN '蒲郡' WHEN '08' THEN '常滑' WHEN '09' THEN '津'
        WHEN '10' THEN '三国' WHEN '11' THEN 'びわこ' WHEN '12' THEN '住之江'
        WHEN '13' THEN '尼崎' WHEN '14' THEN '鳴門' WHEN '15' THEN '丸亀'
        WHEN '16' THEN '児島' WHEN '17' THEN '宮島' WHEN '18' THEN '徳山'
        WHEN '19' THEN '下関' WHEN '20' THEN '若松' WHEN '21' THEN '芦屋'
        WHEN '22' THEN '福岡' WHEN '23' THEN '唐津' WHEN '24' THEN '大村'
    END as stadium_name,
    race_no,
    month,
    bet_count,
    ROUND(total_return::numeric / NULLIF(total_bet, 0) * 100, 2) as return_rate
FROM condition_stats
WHERE total_bet > 0
ORDER BY return_rate DESC
LIMIT 100
"""
    },
    {
        "id": "00",
        "name": "データ件数確認",
        "filename": "00_data_summary.csv",
        "sql": """
SELECT 
    'historical_race_results' as table_name,
    COUNT(*) as record_count,
    MIN(race_date) as min_date,
    MAX(race_date) as max_date
FROM historical_race_results
UNION ALL
SELECT 
    'historical_programs' as table_name,
    COUNT(*) as record_count,
    MIN(race_date) as min_date,
    MAX(race_date) as max_date
FROM historical_programs
UNION ALL
SELECT 
    'historical_payoffs' as table_name,
    COUNT(*) as record_count,
    MIN(race_date) as min_date,
    MAX(race_date) as max_date
FROM historical_payoffs
"""
    }
]


def get_db_connection():
    """データベース接続を取得"""
    # DATABASE_URL環境変数を優先
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        return psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    
    # 個別の環境変数から接続
    host = os.environ.get('DB_HOST', 'localhost')
    port = os.environ.get('DB_PORT', '5432')
    dbname = os.environ.get('DB_NAME', 'boatrace')
    user = os.environ.get('DB_USER', 'postgres')
    password = os.environ.get('DB_PASSWORD', '')
    
    return psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        cursor_factory=RealDictCursor
    )


def execute_query_to_csv(query_info, output_dir):
    """クエリを実行してCSVに出力"""
    query_id = query_info['id']
    query_name = query_info['name']
    filename = query_info['filename']
    sql = query_info['sql']
    
    output_path = os.path.join(output_dir, filename)
    
    print(f"\n[{query_id}] {query_name}")
    print(f"    実行中...")
    
    start_time = datetime.now()
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            
            if rows:
                # CSVに出力
                with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
                
                elapsed = (datetime.now() - start_time).total_seconds()
                print(f"    完了: {len(rows)}件 → {filename} ({elapsed:.1f}秒)")
                return True, len(rows)
            else:
                print(f"    結果なし")
                return True, 0
                
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"    エラー: {e} ({elapsed:.1f}秒)")
        return False, 0
    finally:
        if 'conn' in locals():
            conn.close()


def main():
    """メイン処理"""
    print("=" * 60)
    print("競艇 21年分データ 勝ちパターン分析")
    print("=" * 60)
    
    # 出力フォルダ作成
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"\n出力フォルダ: {os.path.abspath(OUTPUT_DIR)}")
    
    # DB接続テスト
    print("\nデータベース接続テスト...")
    try:
        conn = get_db_connection()
        conn.close()
        print("接続OK")
    except Exception as e:
        print(f"接続エラー: {e}")
        print("\n環境変数を設定してください:")
        print("  export DATABASE_URL='postgresql://user:password@host:port/dbname'")
        print("または")
        print("  export DB_HOST='your-host'")
        print("  export DB_PORT='5432'")
        print("  export DB_NAME='your-db'")
        print("  export DB_USER='your-user'")
        print("  export DB_PASSWORD='your-password'")
        sys.exit(1)
    
    # 各クエリを実行
    print(f"\n{len(ANALYSIS_QUERIES)}個の分析クエリを実行します...")
    
    total_start = datetime.now()
    success_count = 0
    total_records = 0
    
    for query_info in ANALYSIS_QUERIES:
        success, records = execute_query_to_csv(query_info, OUTPUT_DIR)
        if success:
            success_count += 1
            total_records += records
    
    total_elapsed = (datetime.now() - total_start).total_seconds()
    
    # サマリー
    print("\n" + "=" * 60)
    print("完了サマリー")
    print("=" * 60)
    print(f"成功: {success_count}/{len(ANALYSIS_QUERIES)} クエリ")
    print(f"総レコード数: {total_records:,}件")
    print(f"総実行時間: {total_elapsed:.1f}秒")
    print(f"出力フォルダ: {os.path.abspath(OUTPUT_DIR)}")
    print("=" * 60)


if __name__ == "__main__":
    main()

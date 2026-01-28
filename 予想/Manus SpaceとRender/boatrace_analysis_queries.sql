-- ============================================================
-- 競艇 21年分データ 勝ちパターン分析SQLクエリ集
-- 対象期間: 2005年1月 〜 2026年1月
-- 対象テーブル: historical_race_results, historical_programs, historical_payoffs
-- ============================================================

-- ============================================================
-- 1. 1号艇1着率（単勝）分析
-- ============================================================
-- 1号艇が1着になる確率と、単勝回収率を計算
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
WHERE r.rank = '1';

-- 年別1号艇1着率推移
SELECT 
    LEFT(r.race_date, 4) as year,
    COUNT(DISTINCT (r.race_date || r.stadium_code || r.race_no)) as total_races,
    SUM(CASE WHEN r.boat_no = '1' THEN 1 ELSE 0 END) as boat1_wins,
    ROUND(SUM(CASE WHEN r.boat_no = '1' THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as boat1_win_rate
FROM historical_race_results r
WHERE r.rank = '1'
GROUP BY LEFT(r.race_date, 4)
ORDER BY year;

-- ============================================================
-- 2. 1-3番人気の単勝回収率
-- ============================================================
-- 人気別の単勝回収率（100円賭けた場合の期待値）
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
ORDER BY p.popularity;

-- ============================================================
-- 3. 場別の単勝回収率
-- ============================================================
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
    AND p.popularity = 1  -- 1番人気のみ
GROUP BY p.stadium_code
ORDER BY return_rate_percent DESC;

-- ============================================================
-- 4. 1号艇オッズ別の回収率（番組表の勝率から推定）
-- ============================================================
-- 1号艇選手の全国勝率別の1着率と回収率
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
ORDER BY win_rate DESC;

-- ============================================================
-- 5. 季節別傾向（月別）
-- ============================================================
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
ORDER BY month;

-- ============================================================
-- 6. レース番号別（時間帯別）傾向
-- ============================================================
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
ORDER BY p.race_no;

-- ============================================================
-- 7. 曜日別傾向
-- ============================================================
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
ORDER BY dow_num;

-- ============================================================
-- 8. 選手級別組み合わせ分析
-- ============================================================
-- 1号艇の級別と1着率
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
ORDER BY win_rate DESC;

-- ============================================================
-- 9. モーター2連率別の成績
-- ============================================================
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
ORDER BY win_rate DESC;

-- ============================================================
-- 10. 枠番別の穴傾向（4-6号艇の激走）
-- ============================================================
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
ORDER BY r.boat_no;

-- ============================================================
-- 11. 荒れるレース条件（高配当が出やすい条件）
-- ============================================================
-- 場×レース番号で荒れやすい組み合わせ
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
LIMIT 30;

-- ============================================================
-- 12. 鉄板レース条件（1番人気が勝ちやすい条件）
-- ============================================================
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
LIMIT 30;

-- ============================================================
-- 13. コース別2連率（1-2着に入る確率）
-- ============================================================
SELECT 
    r.boat_no as course,
    COUNT(*) as total_entries,
    SUM(CASE WHEN r.rank = '1' THEN 1 ELSE 0 END) as first_place,
    SUM(CASE WHEN r.rank = '2' THEN 1 ELSE 0 END) as second_place,
    ROUND(SUM(CASE WHEN r.rank = '1' THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as win_rate,
    ROUND(SUM(CASE WHEN r.rank IN ('1', '2') THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as top2_rate
FROM historical_race_results r
GROUP BY r.boat_no
ORDER BY r.boat_no;

-- ============================================================
-- 14. 2連複1=3の回収率分析
-- ============================================================
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
ORDER BY return_rate DESC;

-- ============================================================
-- 15. 3連単の高配当パターン分析
-- ============================================================
-- 高配当（万舟）の出現率
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
ORDER BY manbune_rate DESC;

-- ============================================================
-- 16. 1号艇A1選手の場別成績
-- ============================================================
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
ORDER BY win_rate DESC;

-- ============================================================
-- 17. 回収率100%超えの勝ちパターン総合分析
-- ============================================================
-- 条件別の回収率ランキング（単勝1番人気）
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
LIMIT 50;

-- ============================================================
-- おまけ: データ件数確認
-- ============================================================
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
FROM historical_payoffs;

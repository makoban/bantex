-- ============================================================
-- 3戦略 動的購入金額シミュレーション用SQL
-- Render.comのDBシェルで実行してください
-- ============================================================

-- ============================================================
-- 【1】関東4場単勝戦略
-- 対象: 桐生(01)1-4R, 戸田(02)1-4,6,8R, 平和島(04)1-4,6-8R, 多摩川(05)2-7R
-- ============================================================

-- 基本統計（固定金額1,000円での回収率）
SELECT 
    '関東4場単勝' as strategy,
    COUNT(*) as total_races,
    SUM(CASE WHEN r.first_place = '1' THEN 1 ELSE 0 END) as hits,
    ROUND(SUM(CASE WHEN r.first_place = '1' THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as hit_rate,
    COUNT(*) * 1000 as total_bet,
    SUM(CASE WHEN r.first_place = '1' THEN COALESCE(p.win_payoff, p.win_odds_1 * 100) * 10 ELSE 0 END) as total_return,
    ROUND(SUM(CASE WHEN r.first_place = '1' THEN COALESCE(p.win_payoff, p.win_odds_1 * 100) * 10 ELSE 0 END)::numeric / (COUNT(*) * 1000) * 100, 2) as return_rate
FROM historical_race_results r
JOIN historical_programs p ON r.race_date = p.race_date 
    AND r.stadium_code = p.stadium_code 
    AND r.race_no = p.race_no
WHERE (
    (r.stadium_code = '01' AND r.race_no IN ('01','02','03','04'))
    OR (r.stadium_code = '02' AND r.race_no IN ('01','02','03','04','06','08'))
    OR (r.stadium_code = '04' AND r.race_no IN ('01','02','03','04','06','07','08'))
    OR (r.stadium_code = '05' AND r.race_no IN ('02','03','04','05','06','07'))
)
AND p.win_odds_1 IS NOT NULL
AND p.win_odds_1 > 0;

-- オッズ帯別の詳細（動的金額計算用）
SELECT 
    CASE 
        WHEN p.win_odds_1 < 1.5 THEN '1.0-1.5倍'
        WHEN p.win_odds_1 < 2.0 THEN '1.5-2.0倍'
        WHEN p.win_odds_1 < 3.0 THEN '2.0-3.0倍'
        WHEN p.win_odds_1 < 5.0 THEN '3.0-5.0倍'
        WHEN p.win_odds_1 < 8.0 THEN '5.0-8.0倍'
        ELSE '8.0倍以上'
    END as odds_range,
    CASE 
        WHEN p.win_odds_1 < 1.5 THEN 1000
        WHEN p.win_odds_1 < 2.0 THEN 2000
        WHEN p.win_odds_1 < 3.0 THEN 3000
        WHEN p.win_odds_1 < 5.0 THEN 4000
        WHEN p.win_odds_1 < 8.0 THEN 3000
        ELSE 2000
    END as bet_amount,
    COUNT(*) as races,
    SUM(CASE WHEN r.first_place = '1' THEN 1 ELSE 0 END) as hits,
    ROUND(SUM(CASE WHEN r.first_place = '1' THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as hit_rate,
    ROUND(AVG(COALESCE(p.win_payoff, p.win_odds_1 * 100)), 2) as avg_payoff
FROM historical_race_results r
JOIN historical_programs p ON r.race_date = p.race_date 
    AND r.stadium_code = p.stadium_code 
    AND r.race_no = p.race_no
WHERE (
    (r.stadium_code = '01' AND r.race_no IN ('01','02','03','04'))
    OR (r.stadium_code = '02' AND r.race_no IN ('01','02','03','04','06','08'))
    OR (r.stadium_code = '04' AND r.race_no IN ('01','02','03','04','06','07','08'))
    OR (r.stadium_code = '05' AND r.race_no IN ('02','03','04','05','06','07'))
)
AND p.win_odds_1 IS NOT NULL
AND p.win_odds_1 > 0
GROUP BY 
    CASE 
        WHEN p.win_odds_1 < 1.5 THEN '1.0-1.5倍'
        WHEN p.win_odds_1 < 2.0 THEN '1.5-2.0倍'
        WHEN p.win_odds_1 < 3.0 THEN '2.0-3.0倍'
        WHEN p.win_odds_1 < 5.0 THEN '3.0-5.0倍'
        WHEN p.win_odds_1 < 8.0 THEN '5.0-8.0倍'
        ELSE '8.0倍以上'
    END,
    CASE 
        WHEN p.win_odds_1 < 1.5 THEN 1000
        WHEN p.win_odds_1 < 2.0 THEN 2000
        WHEN p.win_odds_1 < 3.0 THEN 3000
        WHEN p.win_odds_1 < 5.0 THEN 4000
        WHEN p.win_odds_1 < 8.0 THEN 3000
        ELSE 2000
    END
ORDER BY bet_amount;


-- ============================================================
-- 【2】3穴戦略（論文準拠）
-- 対象: 大村(24)、当地勝率6.5以上、2連単/2連複の高い方
-- ============================================================

-- 基本統計（固定金額1,000円での回収率）
SELECT 
    '3穴（論文準拠）' as strategy,
    COUNT(*) as total_races,
    SUM(CASE 
        WHEN (p.exacta_odds_1_3 >= p.quinella_odds_1_3 AND r.first_place = '1' AND r.second_place = '3')
        OR (p.quinella_odds_1_3 > p.exacta_odds_1_3 AND ((r.first_place = '1' AND r.second_place = '3') OR (r.first_place = '3' AND r.second_place = '1')))
        THEN 1 ELSE 0 
    END) as hits,
    ROUND(SUM(CASE 
        WHEN (p.exacta_odds_1_3 >= p.quinella_odds_1_3 AND r.first_place = '1' AND r.second_place = '3')
        OR (p.quinella_odds_1_3 > p.exacta_odds_1_3 AND ((r.first_place = '1' AND r.second_place = '3') OR (r.first_place = '3' AND r.second_place = '1')))
        THEN 1 ELSE 0 
    END)::numeric / COUNT(*) * 100, 2) as hit_rate,
    COUNT(*) * 1000 as total_bet,
    SUM(CASE 
        WHEN p.exacta_odds_1_3 >= p.quinella_odds_1_3 AND r.first_place = '1' AND r.second_place = '3'
        THEN COALESCE(p.exacta_payoff_1_3, p.exacta_odds_1_3 * 100) * 10
        WHEN p.quinella_odds_1_3 > p.exacta_odds_1_3 AND ((r.first_place = '1' AND r.second_place = '3') OR (r.first_place = '3' AND r.second_place = '1'))
        THEN COALESCE(p.quinella_payoff_1_3, p.quinella_odds_1_3 * 100) * 10
        ELSE 0 
    END) as total_return,
    ROUND(SUM(CASE 
        WHEN p.exacta_odds_1_3 >= p.quinella_odds_1_3 AND r.first_place = '1' AND r.second_place = '3'
        THEN COALESCE(p.exacta_payoff_1_3, p.exacta_odds_1_3 * 100) * 10
        WHEN p.quinella_odds_1_3 > p.exacta_odds_1_3 AND ((r.first_place = '1' AND r.second_place = '3') OR (r.first_place = '3' AND r.second_place = '1'))
        THEN COALESCE(p.quinella_payoff_1_3, p.quinella_odds_1_3 * 100) * 10
        ELSE 0 
    END)::numeric / (COUNT(*) * 1000) * 100, 2) as return_rate
FROM historical_race_results r
JOIN historical_programs p ON r.race_date = p.race_date 
    AND r.stadium_code = p.stadium_code 
    AND r.race_no = p.race_no
WHERE r.stadium_code = '24'
    AND p.local_win_rate >= 6.5
    AND (p.exacta_odds_1_3 > 0 OR p.quinella_odds_1_3 > 0);


-- ============================================================
-- 【3】3穴2nd戦略
-- 対象: 特定場×R、当地勝率4.5〜6.0、オッズ3.0〜100.0
-- ============================================================

-- 基本統計（固定金額1,000円での回収率）
SELECT 
    '3穴2nd' as strategy,
    COUNT(*) as total_races,
    SUM(CASE 
        WHEN (GREATEST(p.exacta_odds_1_3, p.quinella_odds_1_3) = p.exacta_odds_1_3 AND r.first_place = '1' AND r.second_place = '3')
        OR (GREATEST(p.exacta_odds_1_3, p.quinella_odds_1_3) = p.quinella_odds_1_3 AND p.quinella_odds_1_3 > p.exacta_odds_1_3 AND ((r.first_place = '1' AND r.second_place = '3') OR (r.first_place = '3' AND r.second_place = '1')))
        THEN 1 ELSE 0 
    END) as hits,
    COUNT(*) * 1000 as total_bet,
    SUM(CASE 
        WHEN GREATEST(p.exacta_odds_1_3, p.quinella_odds_1_3) = p.exacta_odds_1_3 AND r.first_place = '1' AND r.second_place = '3'
        THEN COALESCE(p.exacta_payoff_1_3, p.exacta_odds_1_3 * 100) * 10
        WHEN GREATEST(p.exacta_odds_1_3, p.quinella_odds_1_3) = p.quinella_odds_1_3 AND p.quinella_odds_1_3 > p.exacta_odds_1_3 AND ((r.first_place = '1' AND r.second_place = '3') OR (r.first_place = '3' AND r.second_place = '1'))
        THEN COALESCE(p.quinella_payoff_1_3, p.quinella_odds_1_3 * 100) * 10
        ELSE 0 
    END) as total_return
FROM historical_race_results r
JOIN historical_programs p ON r.race_date = p.race_date 
    AND r.stadium_code = p.stadium_code 
    AND r.race_no = p.race_no
WHERE (
    (r.stadium_code = '11' AND r.race_no = '04')
    OR (r.stadium_code = '18' AND r.race_no = '10')
    OR (r.stadium_code = '13' AND r.race_no = '04')
    OR (r.stadium_code = '18' AND r.race_no = '06')
    OR (r.stadium_code = '05' AND r.race_no = '02')
    OR (r.stadium_code = '11' AND r.race_no = '02')
    OR (r.stadium_code = '24' AND r.race_no = '04')
    OR (r.stadium_code = '05' AND r.race_no = '04')
    OR (r.stadium_code = '11' AND r.race_no = '05')
    OR (r.stadium_code = '11' AND r.race_no = '09')
    OR (r.stadium_code = '18' AND r.race_no = '03')
    OR (r.stadium_code = '05' AND r.race_no = '11')
    OR (r.stadium_code = '13' AND r.race_no = '06')
    OR (r.stadium_code = '05' AND r.race_no = '06')
    OR (r.stadium_code = '13' AND r.race_no = '01')
)
AND p.local_win_rate >= 4.5
AND p.local_win_rate < 6.0
AND GREATEST(p.exacta_odds_1_3, p.quinella_odds_1_3) >= 3.0
AND GREATEST(p.exacta_odds_1_3, p.quinella_odds_1_3) <= 100.0;

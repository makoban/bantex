
-- 1. オッズ帯別の単勝分析
SELECT
    FLOOR(p.payoff / 100) AS odds_range,
    COUNT(*) AS total_bets,
    SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) AS total_wins,
    ROUND(100.0 * SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS win_rate,
    ROUND(SUM(CASE WHEN r.result_1st = 1 THEN p.payoff ELSE 0 END) / (COUNT(*) * 100.0), 2) AS recovery_rate
FROM historical_payoffs p
JOIN historical_race_results r ON p.race_date = r.race_date AND p.stadium_code = r.stadium_code AND p.race_number = r.race_number
WHERE p.bet_type = 'win' AND p.combination = '1'
GROUP BY odds_range
ORDER BY odds_range;

-- 2. 開催地別の単勝分析
SELECT
    r.stadium_code,
    COUNT(*) AS total_bets,
    SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) AS total_wins,
    ROUND(100.0 * SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS win_rate,
    ROUND(SUM(CASE WHEN r.result_1st = 1 THEN p.payoff ELSE 0 END) / (COUNT(*) * 100.0), 2) AS recovery_rate
FROM historical_payoffs p
JOIN historical_race_results r ON p.race_date = r.race_date AND p.stadium_code = r.stadium_code AND p.race_number = r.race_number
WHERE p.bet_type = 'win' AND p.combination = '1'
GROUP BY r.stadium_code
ORDER BY recovery_rate DESC;

-- 3. レース番号別の単勝分析
SELECT
    r.race_number,
    COUNT(*) AS total_bets,
    SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) AS total_wins,
    ROUND(100.0 * SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS win_rate,
    ROUND(SUM(CASE WHEN r.result_1st = 1 THEN p.payoff ELSE 0 END) / (COUNT(*) * 100.0), 2) AS recovery_rate
FROM historical_payoffs p
JOIN historical_race_results r ON p.race_date = r.race_date AND p.stadium_code = r.stadium_code AND p.race_number = r.race_number
WHERE p.bet_type = 'win' AND p.combination = '1'
GROUP BY r.race_number
ORDER BY r.race_number;

-- 4. 曜日別の単勝分析
SELECT
    TO_CHAR(r.race_date, 'Day') AS weekday,
    COUNT(*) AS total_bets,
    SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) AS total_wins,
    ROUND(100.0 * SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS win_rate,
    ROUND(SUM(CASE WHEN r.result_1st = 1 THEN p.payoff ELSE 0 END) / (COUNT(*) * 100.0), 2) AS recovery_rate
FROM historical_payoffs p
JOIN historical_race_results r ON p.race_date = r.race_date AND p.stadium_code = r.stadium_code AND p.race_number = r.race_number
WHERE p.bet_type = 'win' AND p.combination = '1'
GROUP BY weekday
ORDER BY MIN(EXTRACT(ISODOW FROM r.race_date));

-- 5. 季節別の単勝分析
SELECT
    CASE 
        WHEN EXTRACT(MONTH FROM r.race_date) IN (3, 4, 5) THEN 'Spring'
        WHEN EXTRACT(MONTH FROM r.race_date) IN (6, 7, 8) THEN 'Summer'
        WHEN EXTRACT(MONTH FROM r.race_date) IN (9, 10, 11) THEN 'Autumn'
        ELSE 'Winter'
    END AS season,
    COUNT(*) AS total_bets,
    SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) AS total_wins,
    ROUND(100.0 * SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS win_rate,
    ROUND(SUM(CASE WHEN r.result_1st = 1 THEN p.payoff ELSE 0 END) / (COUNT(*) * 100.0), 2) AS recovery_rate
FROM historical_payoffs p
JOIN historical_race_results r ON p.race_date = r.race_date AND p.stadium_code = r.stadium_code AND p.race_number = r.race_number
WHERE p.bet_type = 'win' AND p.combination = '1'
GROUP BY season
ORDER BY MIN(EXTRACT(MONTH FROM r.race_date));

-- 6. グレード別の単勝分析
SELECT
    r.grade,
    COUNT(*) AS total_bets,
    SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) AS total_wins,
    ROUND(100.0 * SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS win_rate,
    ROUND(SUM(CASE WHEN r.result_1st = 1 THEN p.payoff ELSE 0 END) / (COUNT(*) * 100.0), 2) AS recovery_rate
FROM historical_payoffs p
JOIN historical_race_results r ON p.race_date = r.race_date AND p.stadium_code = r.stadium_code AND p.race_number = r.race_number
WHERE p.bet_type = 'win' AND p.combination = '1'
GROUP BY r.grade
ORDER BY r.grade;

-- 7. 選手級別の単勝分析
SELECT
    prog.racer_class_1 AS racer_class,
    COUNT(*) AS total_bets,
    SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) AS total_wins,
    ROUND(100.0 * SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS win_rate,
    ROUND(SUM(CASE WHEN r.result_1st = 1 THEN p.payoff ELSE 0 END) / (COUNT(*) * 100.0), 2) AS recovery_rate
FROM historical_payoffs p
JOIN historical_race_results r ON p.race_date = r.race_date AND p.stadium_code = r.stadium_code AND p.race_number = r.race_number
JOIN historical_programs prog ON r.race_date = prog.race_date AND r.stadium_code = prog.stadium_code AND r.race_number = prog.race_number
WHERE p.bet_type = 'win' AND p.combination = '1'
GROUP BY racer_class
ORDER BY racer_class;

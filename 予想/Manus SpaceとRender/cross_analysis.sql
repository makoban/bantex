-- 1. 開催地 × オッズ帯別の単勝分析
SELECT
    r.stadium_code,
    FLOOR(p.payoff / 100) AS odds_range,
    COUNT(*) AS total_bets,
    SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) AS total_wins,
    ROUND(100.0 * SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS win_rate,
    ROUND(SUM(CASE WHEN r.result_1st = 1 THEN p.payoff ELSE 0 END) / (COUNT(*) * 100.0), 2) AS recovery_rate
FROM historical_payoffs p
JOIN historical_race_results r ON p.race_date = r.race_date AND p.stadium_code = r.stadium_code AND p.race_number = r.race_number
WHERE p.bet_type = 'win' AND p.combination = '1'
GROUP BY r.stadium_code, odds_range
ORDER BY r.stadium_code, odds_range;

-- 2. 開催地 × 選手級別の単勝分析
SELECT
    r.stadium_code,
    prog.racer_class_1 AS racer_class,
    COUNT(*) AS total_bets,
    SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) AS total_wins,
    ROUND(100.0 * SUM(CASE WHEN r.result_1st = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS win_rate,
    ROUND(SUM(CASE WHEN r.result_1st = 1 THEN p.payoff ELSE 0 END) / (COUNT(*) * 100.0), 2) AS recovery_rate
FROM historical_payoffs p
JOIN historical_race_results r ON p.race_date = r.race_date AND p.stadium_code = r.stadium_code AND p.race_number = r.race_number
JOIN historical_programs prog ON r.race_date = prog.race_date AND r.stadium_code = prog.stadium_code AND r.race_number = prog.race_number
WHERE p.bet_type = 'win' AND p.combination = '1'
GROUP BY r.stadium_code, racer_class
ORDER BY r.stadium_code, recovery_rate DESC;

-- 3. レース番号 × オッズ帯別の1-3穴分析
SELECT
    r.race_number,
    FLOOR(p.payoff / 100) AS odds_range,
    COUNT(*) AS total_bets,
    SUM(CASE WHEN (r.result_1st = 1 AND r.result_2nd = 3) OR (r.result_1st = 3 AND r.result_2nd = 1) THEN 1 ELSE 0 END) AS total_wins,
    ROUND(100.0 * SUM(CASE WHEN (r.result_1st = 1 AND r.result_2nd = 3) OR (r.result_1st = 3 AND r.result_2nd = 1) THEN 1 ELSE 0 END) / COUNT(*), 2) AS win_rate,
    ROUND(SUM(CASE WHEN (r.result_1st = 1 AND r.result_2nd = 3) OR (r.result_1st = 3 AND r.result_2nd = 1) THEN p.payoff ELSE 0 END) / (COUNT(*) * 100.0), 2) AS recovery_rate
FROM historical_payoffs p
JOIN historical_race_results r ON p.race_date = r.race_date AND p.stadium_code = r.stadium_code AND p.race_number = r.race_number
WHERE p.bet_type = 'quinella' AND p.combination = '1-3'
GROUP BY r.race_number, odds_range
ORDER BY r.race_number, odds_range;

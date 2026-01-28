# -*- coding: utf-8 -*-
"""3穴2nd戦略 検証（レポート準拠、rank修正版）"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get('DATABASE_URL')

conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
cur = conn.cursor()

query = """
WITH bias_conditions AS (
    SELECT '02' as stadium_code, '04' as race_no UNION ALL
    SELECT '02', '05' UNION ALL
    SELECT '04', '04' UNION ALL
    SELECT '06', '04' UNION ALL
    SELECT '09', '04' UNION ALL
    SELECT '10', '04' UNION ALL
    SELECT '11', '04' UNION ALL
    SELECT '12', '05' UNION ALL
    SELECT '14', '04' UNION ALL
    SELECT '15', '04' UNION ALL
    SELECT '17', '04' UNION ALL
    SELECT '19', '04' UNION ALL
    SELECT '20', '04' UNION ALL
    SELECT '21', '04' UNION ALL
    SELECT '23', '04'
),
target_races AS (
    SELECT DISTINCT r.race_date, r.stadium_code, r.race_no
    FROM historical_race_results r
    JOIN historical_programs p ON r.race_date = p.race_date
        AND r.stadium_code = p.stadium_code
        AND r.race_no = p.race_no
        AND p.boat_no = '1'
    JOIN bias_conditions bc ON r.stadium_code = bc.stadium_code
        AND r.race_no = bc.race_no
    WHERE CAST(p.local_win_rate AS FLOAT) >= 4.5
        AND CAST(p.local_win_rate AS FLOAT) < 6.0
),
race_results AS (
    SELECT t.race_date, t.stadium_code, t.race_no,
           MAX(CASE WHEN r.rank IN ('1', '01') THEN r.boat_no END) as first_boat,
           MAX(CASE WHEN r.rank IN ('2', '02') THEN r.boat_no END) as second_boat
    FROM target_races t
    JOIN historical_race_results r ON t.race_date = r.race_date
        AND t.stadium_code = r.stadium_code AND t.race_no = r.race_no
    GROUP BY t.race_date, t.stadium_code, t.race_no
)
SELECT
    COUNT(*) as total_races,
    SUM(CASE WHEN (rr.first_boat = '1' AND rr.second_boat = '3')
             OR (rr.first_boat = '3' AND rr.second_boat = '1') THEN 1 ELSE 0 END) as total_hits,
    ROUND(SUM(CASE WHEN (rr.first_boat = '1' AND rr.second_boat = '3')
             OR (rr.first_boat = '3' AND rr.second_boat = '1') THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as hit_rate,
    ROUND(SUM(CASE
        WHEN rr.first_boat = '1' AND rr.second_boat = '3' THEN
            GREATEST(COALESCE(tan.payout, 0), COALESCE(puku.payout, 0)) * 10
        WHEN rr.first_boat = '3' AND rr.second_boat = '1' THEN
            COALESCE(puku.payout, 0) * 10
        ELSE 0
    END)::numeric / (COUNT(*) * 1000) * 100, 2) as return_rate
FROM race_results rr
LEFT JOIN historical_payoffs tan ON rr.race_date = tan.race_date
    AND rr.stadium_code = tan.stadium_code
    AND rr.race_no = tan.race_no
    AND tan.bet_type = 'nirentan'
    AND tan.combination = '1-3'
LEFT JOIN historical_payoffs puku ON rr.race_date = puku.race_date
    AND rr.stadium_code = puku.stadium_code
    AND rr.race_no = puku.race_no
    AND puku.bet_type = 'nirenpuku'
    AND puku.combination = '1-3'
"""

cur.execute(query)
row = cur.fetchone()

print("=" * 60)
print("3穴2nd戦略 検証結果（レポート準拠、rank修正版）")
print("=" * 60)
print("Total Races:", row['total_races'])
print("Total Hits:", row['total_hits'])
print("Hit Rate:", row['hit_rate'], "%")
print("Return Rate:", row['return_rate'], "%")

if row['return_rate'] and float(row['return_rate']) > 100:
    print("*** 100% OVER ***")

conn.close()

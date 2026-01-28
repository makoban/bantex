"""100倍以上単勝戦略の詳細分析"""
import psycopg2

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# 全レース数を確認
print("=== 基本データ ===")
cur.execute("SELECT COUNT(DISTINCT race_date || stadium_code || race_no) FROM historical_payoffs WHERE bet_type IN ('win', 'tansho')")
total_races = cur.fetchone()[0]
print(f"全レース数: {total_races:,}件")

# 100倍以上の詳細分析
print("\n=== 単勝100倍以上（万舟）の分析 ===")
cur.execute("""
    SELECT
        COUNT(*) as races_100plus,
        ROUND(AVG(payout), 0) as avg_payout,
        MIN(payout) as min_payout,
        MAX(payout) as max_payout
    FROM historical_payoffs
    WHERE bet_type IN ('win', 'tansho')
      AND payout >= 10000
""")
row = cur.fetchone()
print(f"100倍以上の的中レース: {row[0]:,}件")
print(f"平均払戻: {row[1]:,.0f}円")
print(f"最小: {row[2]:,}円, 最大: {row[3]:,}円")

# 競艇場別でどこが多いか
print("\n=== 100倍以上が多い競艇場TOP10 ===")
cur.execute("""
    SELECT
        stadium_code,
        COUNT(*) as count,
        ROUND(AVG(payout), 0) as avg_payout
    FROM historical_payoffs
    WHERE bet_type IN ('win', 'tansho')
      AND payout >= 10000
    GROUP BY stadium_code
    ORDER BY count DESC
    LIMIT 10
""")
print("場   件数    平均払戻")
for row in cur.fetchall():
    print(f"{row[0]:>2}  {row[1]:>4}件  {row[2]:>8,.0f}円")

# 枠番別でどの艇が多いか
print("\n=== 100倍以上が多い枠番 ===")
cur.execute("""
    SELECT
        combination as boat_no,
        COUNT(*) as count,
        ROUND(AVG(payout), 0) as avg_payout
    FROM historical_payoffs
    WHERE bet_type IN ('win', 'tansho')
      AND payout >= 10000
    GROUP BY combination
    ORDER BY boat_no
""")
print("枠   件数    平均払戻")
for row in cur.fetchall():
    print(f"{row[0]:>2}  {row[1]:>4}件  {row[2]:>8,.0f}円")

# 正しい回収率計算
# 仮定: 各レースで6号艇に100円ずつ賭けた場合
print("\n=== 6号艇に毎レース100円賭けた場合（20年間） ===")
cur.execute("""
    SELECT
        COUNT(*) as wins,
        SUM(payout) as total_payout
    FROM historical_payoffs
    WHERE bet_type IN ('win', 'tansho')
      AND combination = '6'
""")
wins_6 = cur.fetchone()
investment = total_races * 100
return_rate = (wins_6[1] / investment) * 100
print(f"投資: {investment:,}円 ({total_races:,}レース × 100円)")
print(f"的中: {wins_6[0]:,}回")
print(f"払戻合計: {wins_6[1]:,}円")
print(f"回収率: {return_rate:.1f}%")

conn.close()

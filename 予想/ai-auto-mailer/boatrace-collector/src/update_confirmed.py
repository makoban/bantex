# -*- coding: utf-8 -*-
"""confirmedレコードの結果を反映"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os

DATABASE_URL = "postgresql://kokotomo_staging_user:MdaXINo3sbdaPy1cPwp7lvnm8O7SLdLq@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging"

conn = psycopg2.connect(DATABASE_URL)
try:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT vb.id, vb.bet_type, vb.combination, vb.bet_amount,
                   rr.first_place, rr.second_place, rr.third_place,
                   r.id as race_id
            FROM virtual_bets vb
            JOIN races r ON vb.race_date = r.race_date
                AND vb.stadium_code::int = r.stadium_code
                AND vb.race_number = r.race_number
            JOIN race_results rr ON r.id = rr.race_id
            WHERE vb.status = 'confirmed'
              AND rr.first_place IS NOT NULL
        """)
        confirmed_bets = cur.fetchall()
        print(f"confirmed bets with results: {len(confirmed_bets)}")

        if not confirmed_bets:
            print("No confirmed bets to update")
            exit()

        race_ids = [b['race_id'] for b in confirmed_bets]
        cur.execute("""
            SELECT race_id, bet_type, combination, payoff
            FROM payoffs
            WHERE race_id = ANY(%s)
        """, (race_ids,))
        bet_type_map = {'2連複': 'quinella', '2連単': 'exacta', '単勝': 'win'}
        payoffs_map = {}
        for p in cur.fetchall():
            bt = p['bet_type']
            bt_en = bet_type_map.get(bt, bt)
            key = (p['race_id'], bt_en, p['combination'])
            payoffs_map[key] = p['payoff']

        for bet in confirmed_bets:
            bet_type = bet['bet_type']
            combination = bet['combination']
            bet_amount = bet['bet_amount'] or 100
            first = bet['first_place']
            second = bet['second_place']
            third = bet['third_place']

            is_hit = False
            payoff = 0

            if bet_type in ('quinella', 'auto'):
                actual_pair = set([str(first), str(second)])
                bet_pair = set(combination.replace('-', '=').split('='))
                is_hit = actual_pair == bet_pair
                if is_hit:
                    pair_list = sorted([str(first), str(second)])
                    payoff_comb = f"{pair_list[0]}={pair_list[1]}"
                    payoff = payoffs_map.get((bet['race_id'], 'quinella', payoff_comb), 0) or 0
            elif bet_type == 'exacta':
                actual_exacta = f"{first}-{second}"
                is_hit = actual_exacta == combination
                if is_hit:
                    payoff = payoffs_map.get((bet['race_id'], 'exacta', actual_exacta), 0) or 0

            return_amount = int((payoff / 100) * bet_amount) if payoff else 0
            profit = return_amount - bet_amount if is_hit else -bet_amount
            new_status = 'won' if is_hit else 'lost'
            actual_result = f"{first}-{second}-{third}"

            print(f"id={bet['id']}, combo={combination}, result={actual_result}, hit={is_hit}, status={new_status}, profit={profit}")

            cur.execute("""
                UPDATE virtual_bets
                SET status = %s, actual_result = %s,
                    payoff = %s, return_amount = %s, profit = %s
                WHERE id = %s
            """, (new_status, actual_result, payoff if is_hit else 0, return_amount, profit, bet['id']))

        conn.commit()
        print("Updated successfully")
finally:
    conn.close()

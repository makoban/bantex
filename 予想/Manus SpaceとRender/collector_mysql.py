            logger.error(f"終了レース取得中にエラー: {e}", exc_info=True)

        return finished_races

    def collect_result_for_race(self, target_date: datetime, stadium_code: int, race_number: int) -> Optional[Dict[str, Any]]:
        '''特定レースの結果を収集'''
        try:
            result = self.boatrace.get_race_result(
                d=target_date.date(), stadium=stadium_code, race=race_number
            )
            if not result:
                return None

            return {
                "result": result.get("result", {}),
                "payoff": result.get("payoff", {}),
            }

        except Exception as e:
            logger.error(f"結果取得エラー (場:{stadium_code}, R:{race_number}): {e}")
            return None

    def save_result(self, race_id: int, result_data: Dict[str, Any]):
        '''レース結果をDBに保存'''
        self.connect_db()

        # 着順情報を抽出
        result_info = result_data.get("result", {})
        places = [None] * 6
        if isinstance(result_info, dict):
            for i in range(1, 7):
                boat_info = result_info.get(str(i), {})
                if isinstance(boat_info, dict):
                    places[i - 1] = boat_info.get("rank")

        cursor = self.conn.cursor()
        try:
            # race_resultsテーブルに保存
            cursor.execute('''
                INSERT INTO race_results (race_id, first_place, second_place, third_place, fourth_place, fifth_place, sixth_place)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                first_place = VALUES(first_place),
                second_place = VALUES(second_place),
                third_place = VALUES(third_place),
                fourth_place = VALUES(fourth_place),
                fifth_place = VALUES(fifth_place),
                sixth_place = VALUES(sixth_place),
                updated_at = CURRENT_TIMESTAMP
            ''', (race_id, *places))
            self.conn.commit()
            logger.info(f"race_id={race_id}: 結果を保存")

            # payoffsテーブルに保存
            payoff_info = result_data.get("payoff", {})
            for bet_type in ['win', 'exacta', 'quinella', 'quinella_place', 'trifecta', 'trio']:
                payoff_data = payoff_info.get(bet_type)
                if isinstance(payoff_data, dict):
                    combo = payoff_data.get("result", "")
                    amount = payoff_data.get("payoff", 0)
                    popularity = payoff_data.get("popularity")
                    # popularityが空文字の場合はNULLに変換
                    if popularity == '' or popularity is None:
                        popularity = None
                    if combo and amount:
                        cursor.execute('''
                            INSERT INTO payoffs (race_id, bet_type, combination, payoff, popularity)
                            VALUES (%s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                            payoff = VALUES(payoff),
                            popularity = VALUES(popularity)
                        ''', (race_id, bet_type, combo, amount, popularity))
            
            self.conn.commit()
            logger.info(f"race_id={race_id}: 払戻金を保存")
        except Exception as e:
            logger.error(f"結果保存エラー: {e}")
            self.conn.rollback()
        finally:
            cursor.close()
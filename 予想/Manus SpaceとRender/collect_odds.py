        return None
    
    def _parse_odds_range(self, text: str) -> Optional[Tuple[float, float]]:
        """範囲オッズをパース（例: "1.3-1.9"）"""
        try:
            match = re.match(r'([\d.]+)-([\d.]+)', text)
            if match:
                return float(match.group(1)), float(match.group(2))
        except:
            pass
        return None
    
    def save_odds(self, conn, race_date: str, stadium_code: str, race_number: int,
                  odds_list: List[Dict], minutes_to_deadline: int = None):
        """オッズをデータベースに保存"""
        if not odds_list:
            return
        
        with conn.cursor() as cur:
            values = []
            for odds in odds_list:
                # 日付をフォーマット
                if len(race_date) == 8:
                    formatted_date = f"{race_date[:4]}-{race_date[4:6]}-{race_date[6:8]}"
                else:
                    formatted_date = race_date
                
                values.append((
                    formatted_date,
                    stadium_code,
                    race_number,
                    odds['odds_type'],
                    odds['combination'],
                    odds.get('odds_value'),
                    odds.get('odds_min'),
                    odds.get('odds_max'),
                    odds['scraped_at'],
                    minutes_to_deadline
                ))
            
            execute_values(cur, '''
                INSERT INTO odds_history (
                    race_date, stadium_code, race_number, odds_type, combination,
                    odds_value, odds_min, odds_max, scraped_at, minutes_to_deadline
                ) VALUES %s
            ''', values)
            
            conn.commit()
    
    def collect_race_odds(self, stadium_code: str, race_number: int, race_date: str,
                          deadline_time: datetime = None, high_freq_minutes: int = 5,
                          high_freq_interval: int = 10, normal_interval: int = 600) -> int:
        """
        レースのオッズを収集
        
        Args:
            stadium_code: 競艇場コード
            race_number: レース番号
            race_date: レース日（YYYYMMDD形式）
            deadline_time: 締切時刻
            high_freq_minutes: 高頻度収集開始（締切何分前から）
            high_freq_interval: 高頻度収集間隔（秒）
            normal_interval: 通常収集間隔（秒）
            
        Returns:
            収集したオッズ数
        """
        conn = self.get_db_connection()
        self.create_odds_table(conn)
        
        total_collected = 0
        stadium_name = STADIUM_CODES.get(stadium_code, stadium_code)
        
        logger.info(f"オッズ収集開始: {stadium_name} {race_number}R")
        
        try:
            while True:
                now = datetime.now()
                
                # 締切時刻を過ぎたら終了
                if deadline_time and now > deadline_time:
                    logger.info(f"締切時刻を過ぎました: {stadium_name} {race_number}R")
                    break
                
                # 締切までの残り時間を計算
                minutes_to_deadline = None
                if deadline_time:
                    delta = deadline_time - now
                    minutes_to_deadline = int(delta.total_seconds() / 60)
                
                # オッズを取得
                odds_list = self.fetch_all_odds(stadium_code, race_number, race_date)
                
                if odds_list:
                    self.save_odds(conn, race_date, stadium_code, race_number,
                                  odds_list, minutes_to_deadline)
                    total_collected += len(odds_list)
                    logger.info(f"収集: {len(odds_list)}件 (残り{minutes_to_deadline}分)")
                
                # 次の収集間隔を決定
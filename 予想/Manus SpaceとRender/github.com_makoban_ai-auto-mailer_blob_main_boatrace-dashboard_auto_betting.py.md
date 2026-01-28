# ai-auto-mailer/boatrace-dashboard/auto_betting.py at main · makoban/ai-auto-mailer

**URL:** https://github.com/makoban/ai-auto-mailer/blob/main/boatrace-dashboard/auto_betting.py

---

Skip to content
makoban
ai-auto-mailer
Type / to search
Repository navigation
Code
Issues
Pull requests
Actions
Projects
Security
Insights
Settings
 main
Breadcrumbs
ai-auto-mailer/boatrace-dashboard
/auto_betting.py
t
Latest commit
makoban
feat: 3穴戦略を論文準拠に改善 (v1.11.0)
eeb5b5c
 · 
History
History
File metadata and controls
Code
Blame
Raw
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
41
42
43
44
45
46
47
48
49
50
51
52
53
54
55
56
57
58
59
60
61
62
63
64
65
66
67
68
69
70
71
72
73
74
75
76
77
78
79
80
81
82
83
84
85
86
87
88
89
90
91
92
93
94
95
96
97
98
99
100
101
102
103
104
105
106
107
108
109
110
111
112
113
114
115
116
117
118
119
120
121
122
123
124
125
126
127
128
129
130
131
132
133
134
135
136
137
138
139
140
141
142
143
144
145
146
147
148
149
150
151
152
153
154
155
156
157
158
159
160
161
162
163
164
165
166
167
168
169
170
171
172
173
174
175
176
177
178
179
180
"""
自動購入バッチ処理
PostgreSQL（kokotomo-db-staging）のみを使用
機能:
1. 毎朝8:00に購入予定を自動登録（レースデータ収集も同時実行）
2. 締切1分前に購入判断
3. 結果収集後に当選/外れを更新
"""


import os
import time


# タイムゾーンを日本時間に設定（pyjpboatraceの日付バリデーション対策）
os.environ['TZ'] = 'Asia/Tokyo'
if hasattr(time, 'tzset'):
    time.tzset()


import logging
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Optional, Any
from decimal import Decimal
import json
import re


import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
import requests
from bs4 import BeautifulSoup


# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# 日本時間
JST = timezone(timedelta(hours=9))


# データベースURL
DATABASE_URL = os.environ.get("DATABASE_URL")


# 競艇場名とコードのマッピング
STADIUM_MAP = {
    '桐生': 1, '戸田': 2, '江戸川': 3, '平和島': 4, '多摩川': 5, '浜名湖': 6,
    '蒲郡': 7, '常滑': 8, '津': 9, '三国': 10, 'びわこ': 11, '住之江': 12,
    '尼崎': 13, '鳴門': 14, '丸亀': 15, '児島': 16, '宮島': 17, '徳山': 18,
    '下関': 19, '若松': 20, '芦屋': 21, '福岡': 22, '唐津': 23, '大村': 24
}


def get_adjusted_date() -> date:
    """現在の日付を返す（JST）"""
    now_jst = datetime.now(JST)
    return date(now_jst.year, now_jst.month, now_jst.day)


# 戦略設定
STRATEGIES = {
    '11r12r_win': {
        'name': '11R・12R単勝戦略',
        'target_races': [11, 12],
        'bet_type': 'win',
        'min_odds': 1.5,
        'max_odds': 10.0,
        'bet_amount': 1000,
        'min_expected_value': 1.0,
    },
    'bias_1_3': {
        'name': '1-3穴バイアス戦略（論文準拠）',
        'target_stadium': '24',  # 大村競艇場のみ（論文の対象場）
        'target_races': 'all',
        'bet_type': 'auto',  # 2連単/2連複の高い方を自動選択（論文の条件）
        'combination': '1-3',
        'min_odds': 1.0,  # オッズ制限なし（論文に従う）
        'max_odds': 999.0,  # オッズ制限なし（論文に従う）
        'bet_amount': 1000,
        'min_local_win_rate': 6.5,  # 1号艇の当地勝率下限（論文の条件）
    },
    'bias_1_3_2nd': {
        'name': '3穴2nd戦略',
        'target_conditions': [
            # 回収率110%以上の条件（競艇場コード, R番号）
            ('11', 4),   # 琵琶湖 4R - 122.9%
            ('18', 10),  # 徳山 10R - 122.2%
            ('13', 4),   # 尼崎 4R - 116.4%
            ('18', 6),   # 徳山 6R - 114.9%
            ('05', 2),   # 多摩川 2R - 114.6%
            ('11', 2),   # 琵琶湖 2R - 114.5%
            ('24', 4),   # 大村 4R - 114.0%
            ('05', 4),   # 多摩川 4R - 113.5%
            ('11', 5),   # 琵琶湖 5R - 112.1%
            ('11', 9),   # 琵琶湖 9R - 112.0%
            ('18', 3),   # 徳山 3R - 111.9%
            ('05', 11),  # 多摩川 11R - 111.4%
            ('13', 6),   # 尼崎 6R - 111.0%
            ('05', 6),   # 多摩川 6R - 110.9%
            ('13', 1),   # 尼崎 1R - 110.5%
        ],
        'bet_type': 'auto',  # 2連単/2連複の高い方を自動選択
        'combination': '1-3',
        'min_odds': 3.0,
        'max_odds': 100.0,
        'bet_amount': 1000,
        'min_local_win_rate': 4.5,  # 1号艇の当地勝率下限
        'max_local_win_rate': 6.0,  # 1号艇の当地勝率上限
    }
}




def get_db_connection():
    """データベース接続を取得"""
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not configured")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)




def collect_today_races() -> List[Dict[str, Any]]:
    """
    今日のレース情報を公式サイトから収集
    pyjpboatraceライブラリを使用
    """
    logger.info("=== レースデータ収集開始 ===")
    races = []
    target_date = datetime.now(JST)
    
    try:
        from pyjpboatrace import PyJPBoatrace
        boatrace = PyJPBoatrace()
        
        stadiums_info = boatrace.get_stadiums(d=target_date.date())
        if not stadiums_info:
            logger.info("開催中のレース情報はありませんでした。")
            return []
        
        for stadium_name, info in stadiums_info.items():
            # infoが辞書型でない場合（例: 'date'キー）、スキップ
            if not isinstance(info, dict):
                continue
            
            # statusが発売中でない場合はスキップ
            status = info.get("status", "")
            if "発売中" not in status:
                continue
            
            stadium_code = STADIUM_MAP.get(stadium_name)
            if not stadium_code:
                logger.warning(f"不明な競艇場名です: {stadium_name}")
                continue
            
            # 締切時刻を取得
            deadlines = get_race_deadlines(target_date, stadium_code)
            
            # この場は開催中、各レースの情報を取得
            for race_num in range(1, 13):
                races.append({
                    "race_date": target_date.date(),
                    "stadium_code": stadium_code,
                    "race_number": race_num,
                    "title": info.get("title", ""),
                    "deadline_at": deadlines.get(race_num),
                })
        
    except Exception as e:
        logger.error(f"レース情報取得中にエラーが発生しました: {e}", exc_info=True)
    
    logger.info(f"収集したレース数: {len(races)}")
    return races




def get_race_deadlines(target_date: datetime, stadium_code: int) -> Dict[int, datetime]:
    """公式サイトから各レースの締切時刻を取得"""
    deadlines = {}
    try:
        url = f'https://www.boatrace.jp/owpc/pc/race/raceindex?jcd={stadium_code:02d}&hd={target_date.strftime("%Y%m%d")}'
        response = requests.get(url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 各レースの行を探す
        race_rows = soup.select('table tr')
        for row in race_rows:
Symbols
Find definitions and references for functions and other symbols in this file by clicking a symbol below or in the code.
r
const
logger
const
JST
const
DATABASE_URL
const
STADIUM_MAP
func
get_adjusted_date
const
STRATEGIES
func
get_db_connection
func
collect_today_races
func
get_race_deadlines
func
save_races_to_db
func
register_daily_bets
func
expire_overdue_bets
func
process_deadline_bets
func
process_single_bet
func
get_odds
func
get_boat1_local_win_rate
func
confirm_bet_with_type
func
confirm_bet
func
skip_bet
func
update_results
func
update_single_result
func
update_fund
func
update_skipped_results
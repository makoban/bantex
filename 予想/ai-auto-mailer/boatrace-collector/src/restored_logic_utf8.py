"""
閾ｪ蜍戊ｳｼ蜈･繝舌ャ繝∝・逅・PostgreSQL・・okotomo-db-staging・峨・縺ｿ繧剃ｽｿ逕ｨ

讖溯・:
1. 豈取悃8:00縺ｫ雉ｼ蜈･莠亥ｮ壹ｒ閾ｪ蜍慕匳骭ｲ・医Ξ繝ｼ繧ｹ繝・・繧ｿ蜿朱寔繧ょ酔譎ょｮ溯｡鯉ｼ・2. 邱蛻・蛻・燕縺ｫ雉ｼ蜈･蛻､譁ｭ
3. 邨先棡蜿朱寔蠕後↓蠖馴∈/螟悶ｌ繧呈峩譁ｰ
"""

import os
import time

# 繧ｿ繧､繝繧ｾ繝ｼ繝ｳ繧呈律譛ｬ譎る俣縺ｫ險ｭ螳夲ｼ・yjpboatrace縺ｮ譌･莉倥ヰ繝ｪ繝・・繧ｷ繝ｧ繝ｳ蟇ｾ遲厄ｼ・os.environ['TZ'] = 'Asia/Tokyo'
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

# 繝ｭ繧ｰ險ｭ螳・logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 譌･譛ｬ譎る俣
JST = timezone(timedelta(hours=9))

# 繝・・繧ｿ繝吶・繧ｹURL
DATABASE_URL = os.environ.get("DATABASE_URL")

# 遶ｶ濶・ｴ蜷阪→繧ｳ繝ｼ繝峨・繝槭ャ繝斐Φ繧ｰ
STADIUM_MAP = {
    '譯千函': 1, '謌ｸ逕ｰ': 2, '豎滓虻蟾・: 3, '蟷ｳ蜥悟ｳｶ': 4, '螟壽束蟾・: 5, '豬懷錐貉・: 6,
    '闥ｲ驛｡': 7, '蟶ｸ貊・: 8, '豢･': 9, '荳牙嵜': 10, '縺ｳ繧上％': 11, '菴丈ｹ区ｱ・: 12,
    '蟆ｼ蟠・: 13, '魑ｴ髢': 14, '荳ｸ莠': 15, '蜈仙ｳｶ': 16, '螳ｮ蟲ｶ': 17, '蠕ｳ螻ｱ': 18,
    '荳矩未': 19, '闍･譚ｾ': 20, '闃ｦ螻・: 21, '遖丞ｲ｡': 22, '蜚先ｴ･': 23, '螟ｧ譚・: 24
}

def get_adjusted_date() -> date:
    """迴ｾ蝨ｨ縺ｮ譌･莉倥ｒ霑斐☆・・ST・・""
    now_jst = datetime.now(JST)
    return date(now_jst.year, now_jst.month, now_jst.day)

# 謌ｦ逡･險ｭ螳・STRATEGIES = {
    'tansho_kanto': {
        'name': '髢｢譚ｱ4蝣ｴ蜊伜享謌ｦ逡･',
        'target_stadiums': ['01', '02', '04', '05'],  # 譯千函縲∵虻逕ｰ縲∝ｹｳ蜥悟ｳｶ縲∝､壽束蟾・        'target_races_by_stadium': {
            '01': [1, 2, 3, 4],           # 譯千函: 1-4R
            '02': [1, 2, 3, 4, 6, 8],     # 謌ｸ逕ｰ: 1-4,6,8R
            '04': [1, 2, 3, 4, 6, 7, 8],  # 蟷ｳ蜥悟ｳｶ: 1-4,6-8R
            '05': [2, 3, 4, 5, 6, 7],     # 螟壽束蟾・ 2-7R
        },
        'bet_type': 'win',
        'min_odds': 1.0,   # 繧ｪ繝・ぜ蛻ｶ髯舌↑縺・        'max_odds': 999.0, # 繧ｪ繝・ぜ蛻ｶ髯舌↑縺・        'bet_amount': 1000,
    },
    'bias_1_3': {
        'name': '1-3遨ｴ繝舌う繧｢繧ｹ謌ｦ逡･・郁ｫ匁枚貅匁侠・・,
        'target_stadium': '24',  # 螟ｧ譚醍ｫｶ濶・ｴ縺ｮ縺ｿ・郁ｫ匁枚縺ｮ蟇ｾ雎｡蝣ｴ・・        'target_races': 'all',
        'bet_type': 'auto',  # 2騾｣蜊・2騾｣隍・・鬮倥＞譁ｹ繧定・蜍暮∈謚橸ｼ郁ｫ匁枚縺ｮ譚｡莉ｶ・・        'combination': '1-3',
        'min_odds': 1.0,  # 繧ｪ繝・ぜ蛻ｶ髯舌↑縺暦ｼ郁ｫ匁枚縺ｫ蠕薙≧・・        'max_odds': 999.0,  # 繧ｪ繝・ぜ蛻ｶ髯舌↑縺暦ｼ郁ｫ匁枚縺ｫ蠕薙≧・・        'bet_amount': 1000,
        'min_local_win_rate': 6.5,  # 1蜿ｷ濶・・蠖灘慍蜍晉紫荳矩剞・郁ｫ匁枚縺ｮ譚｡莉ｶ・・    },
    'bias_1_3_2nd': {
        'name': '3遨ｴ2nd謌ｦ逡･',
        'target_conditions': [
            # 蝗槫庶邇・10%莉･荳翫・譚｡莉ｶ・育ｫｶ濶・ｴ繧ｳ繝ｼ繝・ R逡ｪ蜿ｷ・・            ('11', 4),   # 逅ｵ逅ｶ貉・4R - 122.9%
            ('18', 10),  # 蠕ｳ螻ｱ 10R - 122.2%
            ('13', 4),   # 蟆ｼ蟠・4R - 116.4%
            ('18', 6),   # 蠕ｳ螻ｱ 6R - 114.9%
            ('05', 2),   # 螟壽束蟾・2R - 114.6%
            ('11', 2),   # 逅ｵ逅ｶ貉・2R - 114.5%
            ('24', 4),   # 螟ｧ譚・4R - 114.0%
            ('05', 4),   # 螟壽束蟾・4R - 113.5%
            ('11', 5),   # 逅ｵ逅ｶ貉・5R - 112.1%
            ('11', 9),   # 逅ｵ逅ｶ貉・9R - 112.0%
            ('18', 3),   # 蠕ｳ螻ｱ 3R - 111.9%
            ('05', 11),  # 螟壽束蟾・11R - 111.4%
            ('13', 6),   # 蟆ｼ蟠・6R - 111.0%
            ('05', 6),   # 螟壽束蟾・6R - 110.9%
            ('13', 1),   # 蟆ｼ蟠・1R - 110.5%
        ],
        'bet_type': 'auto',  # 2騾｣蜊・2騾｣隍・・鬮倥＞譁ｹ繧定・蜍暮∈謚・        'combination': '1-3',
        'min_odds': 3.0,
        'max_odds': 100.0,
        'bet_amount': 1000,
        'min_local_win_rate': 4.5,  # 1蜿ｷ濶・・蠖灘慍蜍晉紫荳矩剞
        'max_local_win_rate': 6.0,  # 1蜿ｷ濶・・蠖灘慍蜍晉紫荳企剞
    }
}


# 雉ｼ蜈･驥鷹｡崎ｨｭ螳・BASE_AMOUNT = 1000   # 蝓ｺ譛ｬ驥鷹｡・MIN_AMOUNT = 1000    # 譛菴朱≡鬘・MAX_AMOUNT = 10000   # 譛鬮倬≡鬘・

def calculate_bet_amount(strategy_type: str, odds: float, local_win_rate: float = None) -> int:
    """
    雉ｼ蜈･驥鷹｡阪ｒ險育ｮ暦ｼ医こ繝ｪ繝ｼ蝓ｺ貅悶・繝ｼ繧ｹ・・    
    Args:
        strategy_type: 謌ｦ逡･繧ｿ繧､繝・        odds: 譛邨ゅが繝・ぜ
        local_win_rate: 蠖灘慍蜍晉紫・・遨ｴ謌ｦ逡･縺ｮ縺ｿ菴ｿ逕ｨ・・    
    Returns:
        雉ｼ蜈･驥鷹｡搾ｼ・,000縲・0,000蜀・・00蜀・腰菴搾ｼ・    """
    
    if strategy_type == 'tansho_kanto':
        # 髢｢譚ｱ4蝣ｴ蜊伜享謌ｦ逡･: 繧ｪ繝・ぜ繝吶・繧ｹ縺ｮ隱ｿ謨ｴ
        # 迚ｹ諤ｧ: 蜍晉紫47%縲∵悄蠕・屓蜿守紫129%
        if odds < 1.5:
            multiplier = 1.0  # 菴弱が繝・ぜ: 繝ｪ繧ｿ繝ｼ繝ｳ蟆・        elif odds < 2.0:
            multiplier = 2.0  # 荳ｭ菴弱が繝・ぜ: 繝舌Λ繝ｳ繧ｹ濶ｯ縺・        elif odds < 3.0:
            multiplier = 3.0  # 荳ｭ繧ｪ繝・ぜ: 譛溷ｾ・､鬮倥＞
        elif odds < 5.0:
            multiplier = 4.0  # 荳ｭ鬮倥が繝・ぜ: 鬮倥Μ繧ｿ繝ｼ繝ｳ譛溷ｾ・        elif odds < 8.0:
            multiplier = 3.0  # 鬮倥が繝・ぜ: 繝ｪ繧ｹ繧ｯ霆ｽ貂・        else:
            multiplier = 2.0  # 雜・ｫ倥が繝・ぜ: 繝ｪ繧ｹ繧ｯ霆ｽ貂・    
    elif strategy_type == 'bias_1_3':
        # 3遨ｴ謌ｦ逡･・郁ｫ匁枚貅匁侠・・ 蠖灘慍蜍晉紫ﾃ励が繝・ぜ縺ｮ隱ｿ謨ｴ
        # 迚ｹ諤ｧ: 蜍晉紫12%縲∵悄蠕・屓蜿守紫110-120%
        
        # 蠖灘慍蜍晉紫縺ｫ繧医ｋ隱ｿ謨ｴ
        if local_win_rate is None:
            rate_multiplier = 1.0
        elif local_win_rate < 7.0:
            rate_multiplier = 1.0  # 譚｡莉ｶ繧ｮ繝ｪ繧ｮ繝ｪ
        elif local_win_rate < 7.5:
            rate_multiplier = 1.5  # 濶ｯ螂ｽ
        elif local_win_rate < 8.0:
            rate_multiplier = 2.0  # 蜆ｪ遘
        else:
            rate_multiplier = 2.5  # 髱槫ｸｸ縺ｫ蜆ｪ遘
        
        # 繧ｪ繝・ぜ縺ｫ繧医ｋ隱ｿ謨ｴ
        if odds < 4.0:
            odds_multiplier = 1.5  # 菴弱が繝・ぜ: 譛溷ｾ・､鬮倥＞
        elif odds < 8.0:
            odds_multiplier = 1.2  # 驕ｩ豁｣繧ｪ繝・ぜ
        elif odds < 15.0:
            odds_multiplier = 1.0  # 荳ｭ繧ｪ繝・ぜ
        elif odds < 25.0:
            odds_multiplier = 0.8  # 鬮倥が繝・ぜ: 繝ｪ繧ｹ繧ｯ霆ｽ貂・        else:
            odds_multiplier = 0.5  # 雜・ｫ倥が繝・ぜ: 螟ｧ蟷・Μ繧ｹ繧ｯ霆ｽ貂・        
        multiplier = rate_multiplier * odds_multiplier
    
    elif strategy_type == 'bias_1_3_2nd':
        # 3遨ｴ2nd謌ｦ逡･: 蠖灘慍蜍晉紫ﾃ励が繝・ぜ縺ｮ隱ｿ謨ｴ
        # 迚ｹ諤ｧ: 蜍晉紫12%縲∵悄蠕・屓蜿守紫110%
        
        # 蠖灘慍蜍晉紫縺ｫ繧医ｋ隱ｿ謨ｴ
        if local_win_rate is None:
            rate_multiplier = 1.0
        elif local_win_rate < 5.0:
            rate_multiplier = 1.0  # 譚｡莉ｶ繧ｮ繝ｪ繧ｮ繝ｪ
        elif local_win_rate < 5.5:
            rate_multiplier = 1.5  # 濶ｯ螂ｽ
        else:
            rate_multiplier = 2.0  # 蜆ｪ遘
        
        # 繧ｪ繝・ぜ縺ｫ繧医ｋ隱ｿ謨ｴ
        if odds < 4.0:
            odds_multiplier = 1.5
        elif odds < 8.0:
            odds_multiplier = 1.2
        elif odds < 15.0:
            odds_multiplier = 1.0
        elif odds < 25.0:
            odds_multiplier = 0.8
        else:
            odds_multiplier = 0.5
        
        multiplier = rate_multiplier * odds_multiplier
    
    else:
        multiplier = 1.0
    
    # 譛邨る≡鬘阪ｒ險育ｮ暦ｼ・00蜀・腰菴阪↓荳ｸ繧・ｼ・    amount = int(BASE_AMOUNT * multiplier / 100) * 100
    
    # 荳贋ｸ矩剞繧帝←逕ｨ
    return max(MIN_AMOUNT, min(MAX_AMOUNT, amount))


def get_db_connection():
    """繝・・繧ｿ繝吶・繧ｹ謗･邯壹ｒ蜿門ｾ・""
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not configured")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def collect_today_races() -> List[Dict[str, Any]]:
    """
    莉頑律縺ｮ繝ｬ繝ｼ繧ｹ諠・ｱ繧貞・蠑上し繧､繝医°繧牙庶髮・    pyjpboatrace繝ｩ繧､繝悶Λ繝ｪ繧剃ｽｿ逕ｨ
    """
    logger.info("=== 繝ｬ繝ｼ繧ｹ繝・・繧ｿ蜿朱寔髢句ｧ・===")
    races = []
    target_date = datetime.now(JST)
    
    try:
        from pyjpboatrace import PyJPBoatrace
        boatrace = PyJPBoatrace()
        
        stadiums_info = boatrace.get_stadiums(d=target_date.date())
        if not stadiums_info:
            logger.info("髢句ぎ荳ｭ縺ｮ繝ｬ繝ｼ繧ｹ諠・ｱ縺ｯ縺ゅｊ縺ｾ縺帙ｓ縺ｧ縺励◆縲・)
            return []
        
        for stadium_name, info in stadiums_info.items():
            # info縺瑚ｾ樊嶌蝙九〒縺ｪ縺・ｴ蜷茨ｼ井ｾ・ 'date'繧ｭ繝ｼ・峨√せ繧ｭ繝・・
            if not isinstance(info, dict):
                continue
            
            # status縺檎匱螢ｲ荳ｭ縺ｧ縺ｪ縺・ｴ蜷医・繧ｹ繧ｭ繝・・
            status = info.get("status", "")
            if "逋ｺ螢ｲ荳ｭ" not in status:
                continue
            
            stadium_code = STADIUM_MAP.get(stadium_name)
            if not stadium_code:
                logger.warning(f"荳肴・縺ｪ遶ｶ濶・ｴ蜷阪〒縺・ {stadium_name}")
                continue
            
            # 邱蛻・凾蛻ｻ繧貞叙蠕・            deadlines = get_race_deadlines(target_date, stadium_code)
            
            # 縺薙・蝣ｴ縺ｯ髢句ぎ荳ｭ縲∝推繝ｬ繝ｼ繧ｹ縺ｮ諠・ｱ繧貞叙蠕・            for race_num in range(1, 13):
                races.append({
                    "race_date": target_date.date(),
                    "stadium_code": stadium_code,
                    "race_number": race_num,
                    "title": info.get("title", ""),
                    "deadline_at": deadlines.get(race_num),
                })
        
    except Exception as e:
        logger.error(f"繝ｬ繝ｼ繧ｹ諠・ｱ蜿門ｾ嶺ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {e}", exc_info=True)
    
    logger.info(f"蜿朱寔縺励◆繝ｬ繝ｼ繧ｹ謨ｰ: {len(races)}")
    return races


def get_race_deadlines(target_date: datetime, stadium_code: int) -> Dict[int, datetime]:
    """蜈ｬ蠑上し繧､繝医°繧牙推繝ｬ繝ｼ繧ｹ縺ｮ邱蛻・凾蛻ｻ繧貞叙蠕・""
    deadlines = {}
    try:
        url = f'https://www.boatrace.jp/owpc/pc/race/raceindex?jcd={stadium_code:02d}&hd={target_date.strftime("%Y%m%d")}'
        response = requests.get(url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 蜷・Ξ繝ｼ繧ｹ縺ｮ陦後ｒ謗｢縺・        race_rows = soup.select('table tr')
        for row in race_rows:
            cells = row.select('td')
            if len(cells) >= 2:
                race_text = cells[0].text.strip()
                time_text = cells[1].text.strip()
                
                # 繝ｬ繝ｼ繧ｹ逡ｪ蜿ｷ繧呈歓蜃ｺ
                race_match = re.match(r'(\d+)R', race_text)
                if race_match:
                    race_num = int(race_match.group(1))
                    # 譎ょ綾繧呈歓蜃ｺ
                    time_match = re.match(r'(\d{1,2}):(\d{2})', time_text)
                    if time_match:
                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2))
                        deadline = target_date.replace(
                            hour=hour, minute=minute, second=0, microsecond=0,
                            tzinfo=JST
                        )
                        deadlines[race_num] = deadline
        
        logger.info(f"蝣ｴ{stadium_code}: {len(deadlines)}莉ｶ縺ｮ邱蛻・凾蛻ｻ繧貞叙蠕・)
    except Exception as e:
        logger.warning(f"邱蛻・凾蛻ｻ蜿門ｾ励お繝ｩ繝ｼ (蝣ｴ:{stadium_code}): {e}")
    
    return deadlines


def save_races_to_db(races: List[Dict[str, Any]]) -> int:
    """繝ｬ繝ｼ繧ｹ諠・ｱ繧奪B縺ｫ菫晏ｭ・""
    if not races:
        return 0
    
    conn = get_db_connection()
    saved_count = 0
    
    try:
        with conn.cursor() as cur:
            # 譌｢蟄倥・繝ｬ繝ｼ繧ｹID繧貞・縺ｫ蜿門ｾ・            race_keys = [(r['race_date'], r['stadium_code'], r['race_number']) for r in races]
            
            cur.execute(
                "SELECT id, race_date, stadium_code, race_number FROM races WHERE (race_date, stadium_code, race_number) IN %s",
                (tuple(race_keys),)
            )
            existing_races = {(row['race_date'], row['stadium_code'], row['race_number']): row['id'] for row in cur.fetchall()}
            
            # 譁ｰ隕上Ξ繝ｼ繧ｹ縺ｨ譖ｴ譁ｰ繝ｬ繝ｼ繧ｹ繧貞・縺代ｋ
            new_races = []
            races_to_update = []
            
            for race in races:
                key = (race['race_date'], race['stadium_code'], race['race_number'])
                if key in existing_races:
                    # 邱蛻・凾蛻ｻ縺後≠繧後・譖ｴ譁ｰ蟇ｾ雎｡縺ｫ霑ｽ蜉
                    if race.get('deadline_at'):
                        races_to_update.append({
                            'id': existing_races[key],
                            'deadline_at': race['deadline_at']
                        })
                else:
                    new_races.append(race)
            
            # 譌｢蟄倥Ξ繝ｼ繧ｹ縺ｮ邱蛻・凾蛻ｻ繧呈峩譁ｰ
            for race in races_to_update:
                cur.execute(
                    "UPDATE races SET deadline_at = %s WHERE id = %s AND deadline_at IS NULL",
                    (race['deadline_at'], race['id'])
                )
            
            # 譁ｰ隕上Ξ繝ｼ繧ｹ繧剃ｸ諡ｬ逋ｻ骭ｲ
            if new_races:
                insert_query = """
                    INSERT INTO races (race_date, stadium_code, race_number, title, deadline_at)
                    VALUES %s
                    ON CONFLICT (race_date, stadium_code, race_number) DO UPDATE
                    SET deadline_at = COALESCE(EXCLUDED.deadline_at, races.deadline_at)
                """
                values = [
                    (r['race_date'], r['stadium_code'], r['race_number'], r['title'], r['deadline_at'])
                    for r in new_races
                ]
                execute_values(cur, insert_query, values)
                saved_count = len(new_races)
            
            conn.commit()
            logger.info(f"繝ｬ繝ｼ繧ｹ菫晏ｭ伜ｮ御ｺ・ 譁ｰ隕旬saved_count}莉ｶ, 譖ｴ譁ｰ{len(races_to_update)}莉ｶ")
            
    except Exception as e:
        logger.error(f"繝ｬ繝ｼ繧ｹ菫晏ｭ倥お繝ｩ繝ｼ: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
    
    return saved_count


def register_daily_bets():
    """
    豈取悃8:00縺ｫ螳溯｡・ 莉頑律縺ｮ雉ｼ蜈･莠亥ｮ壹ｒ逋ｻ骭ｲ
    
    縲先ｹ譛ｬ菫ｮ豁｣縲代Ξ繝ｼ繧ｹ繝・・繧ｿ蜿朱寔繧貞・縺ｫ陦後▲縺ｦ縺九ｉ雉ｼ蜈･莠亥ｮ壹ｒ逋ｻ骭ｲ
    縺薙ｌ縺ｫ繧医ｊ縲｜oatrace-daily-collection縺ｨ縺ｮ螳溯｡碁・ｺ上↓萓晏ｭ倥＠縺ｪ縺上↑繧・    """
    logger.info("=== 譌･谺｡雉ｼ蜈･莠亥ｮ夂匳骭ｲ髢句ｧ・===")
    
    # 繧ｹ繝・ャ繝・: 繝ｬ繝ｼ繧ｹ繝・・繧ｿ繧貞庶髮・＠縺ｦDB縺ｫ菫晏ｭ・    logger.info("繧ｹ繝・ャ繝・: 繝ｬ繝ｼ繧ｹ繝・・繧ｿ蜿朱寔")
    races = collect_today_races()
    if races:
        save_races_to_db(races)
    else:
        logger.warning("繝ｬ繝ｼ繧ｹ繝・・繧ｿ縺悟叙蠕励〒縺阪∪縺帙ｓ縺ｧ縺励◆")
    
    # 繧ｹ繝・ャ繝・: 雉ｼ蜈･莠亥ｮ壹ｒ逋ｻ骭ｲ
    logger.info("繧ｹ繝・ャ繝・: 雉ｼ蜈･莠亥ｮ夂匳骭ｲ")
    today = get_adjusted_date()
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 莉頑律縺ｮ繝ｬ繝ｼ繧ｹ荳隕ｧ繧貞叙蠕暦ｼ・B縺九ｉ・・            cur.execute("""
                SELECT r.id, r.race_date, r.stadium_code, r.race_number, r.deadline_at, s.name as stadium_name
                FROM races r
                JOIN stadiums s ON r.stadium_code = s.stadium_code
                WHERE r.race_date = %s AND r.is_canceled = FALSE
                ORDER BY r.deadline_at
            """, (today,))
            races = cur.fetchall()
            
            logger.info(f"莉頑律縺ｮ繝ｬ繝ｼ繧ｹ謨ｰ: {len(races)}")
            
            if not races:
                logger.warning("莉頑律縺ｮ繝ｬ繝ｼ繧ｹ縺後≠繧翫∪縺帙ｓ")
                return
            
            # 譌｢蟄倥・雉ｼ蜈･莠亥ｮ壹ｒ蜿門ｾ・            cur.execute("""
                SELECT strategy_type, stadium_code, race_number
                FROM virtual_bets
                WHERE race_date = %s
            """, (today,))
            existing = set((r['strategy_type'], r['stadium_code'], r['race_number']) for r in cur.fetchall())
            
            # 荳諡ｬ逋ｻ骭ｲ逕ｨ縺ｮ繝・・繧ｿ繧呈ｺ門ｙ
            insert_data = []
            now_str = datetime.now(JST).isoformat()
            
            for race in races:
                race_number = race['race_number']
                stadium_code = str(race['stadium_code']).zfill(2)
                deadline_at = race['deadline_at']
                
                for strategy_type, config in STRATEGIES.items():
                    # tansho_kanto謌ｦ逡･縺ｮ蝣ｴ蜷医・迚ｹ螳壹・蝣ｴﾃ由縺ｮ縺ｿ
                    if strategy_type == 'tansho_kanto':
                        target_stadiums = config.get('target_stadiums', [])
                        if stadium_code not in target_stadiums:
                            continue
                        target_races_by_stadium = config.get('target_races_by_stadium', {})
                        target_races = target_races_by_stadium.get(stadium_code, [])
                        if race_number not in target_races:
                            continue
                    # bias_1_3_2nd謌ｦ逡･縺ｮ蝣ｴ蜷医・迚ｹ蛻･縺ｪ譚｡莉ｶ繝√ぉ繝・け
                    elif strategy_type == 'bias_1_3_2nd':
                        target_conditions = config.get('target_conditions', [])
                        if (stadium_code, race_number) not in target_conditions:
                            continue
                    # bias_1_3謌ｦ逡･縺ｮ蝣ｴ蜷医・螟ｧ譚醍ｫｶ濶・ｴ縺ｮ縺ｿ・郁ｫ匁枚貅匁侠・・                    elif strategy_type == 'bias_1_3':
                        target_stadium = config.get('target_stadium')
                        if target_stadium and stadium_code != target_stadium:
                            continue
                    else:
                        # 蟇ｾ雎｡繝ｬ繝ｼ繧ｹ縺九メ繧ｧ繝・け
                        target_races = config.get('target_races')
                        if target_races != 'all' and race_number not in target_races:
                            continue
                    
                    # 譌｢蟄倥メ繧ｧ繝・け
                    if (strategy_type, stadium_code, race_number) in existing:
                        continue
                    
                    # 邨・∩蜷医ｏ縺帙→雉ｼ蜈･繧ｿ繧､繝励ｒ豎ｺ螳・                    if strategy_type == 'tansho_kanto':
                        combination = '1'
                        bet_type = config['bet_type']
                    elif strategy_type == 'bias_1_3':
                        combination = '1-3'  # 隲匁枚縺ｫ蜷医ｏ縺帙※螟画峩
                        bet_type = 'auto'  # 2騾｣蜊・2騾｣隍・・鬮倥＞譁ｹ繧定・蜍暮∈謚橸ｼ郁ｫ匁枚縺ｮ譚｡莉ｶ・・                    elif strategy_type == 'bias_1_3_2nd':
                        combination = '1-3'
                        bet_type = 'auto'  # 邱蛻・燕縺ｫ2騾｣蜊・2騾｣隍・・鬮倥＞譁ｹ繧帝∈謚・                    else:
                        continue
                    
                    insert_data.append((
                        strategy_type,
                        today,
                        stadium_code,
                        race_number,
                        bet_type,
                        combination,
                        config['bet_amount'],
                        deadline_at,
                        json.dumps({'strategy': config['name'], 'registered_at': now_str})
                    ))
            
            # 荳諡ｬINSERT
            if insert_data:
                execute_values(cur, """
                    INSERT INTO virtual_bets (
                        strategy_type, race_date, stadium_code, race_number,
                        bet_type, combination, bet_amount, scheduled_deadline, reason
                    ) VALUES %s
                """, insert_data)
            
            conn.commit()
            logger.info(f"雉ｼ蜈･莠亥ｮ夂匳骭ｲ螳御ｺ・ {len(insert_data)}莉ｶ")
            
    except Exception as e:
        logger.error(f"雉ｼ蜈･莠亥ｮ夂匳骭ｲ繧ｨ繝ｩ繝ｼ: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def expire_overdue_bets():
    """
    邱蛻・′驕弱℃縺殫ending迥ｶ諷九・雉ｼ蜈･莠亥ｮ壹ｒexpired縺ｫ譖ｴ譁ｰ
    """
    logger.info("=== 譛滄剞蛻・ｌ雉ｼ蜈･莠亥ｮ壹・蜃ｦ逅・幕蟋・===")
    
    # aware datetime(JST)縺ｧ邨ｱ荳縺励※豈碑ｼ・    now = datetime.now(JST)
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 邱蛻・′驕弱℃縺殫ending縺ｮ雉ｼ蜈･莠亥ｮ壹ｒ蜿門ｾ励＠縺ｦexpired縺ｫ譖ｴ譁ｰ
            cur.execute("""
                UPDATE virtual_bets
                SET status = 'expired',
                    reason = jsonb_set(
                        COALESCE(reason::jsonb, '{}'::jsonb),
                        '{expiredReason}',
                        '"\u7de0\u5207\u6642\u523b\u3092\u904e\u304e\u305f\u305f\u3081\u81ea\u52d5\u7121\u52b9\u5316"'::jsonb
                    ),
                    updated_at = NOW()
                WHERE status = 'pending'
                AND scheduled_deadline < %s
                RETURNING id, stadium_code, race_number, scheduled_deadline
            """, (now,))
            
            expired_bets = cur.fetchall()
            
            if expired_bets:
                logger.info(f"譛滄剞蛻・ｌ縺ｧ辟｡蜉ｹ蛹・ {len(expired_bets)}莉ｶ")
                for bet in expired_bets:
                    logger.info(f"  - bet_id={bet['id']}, {bet['stadium_code']} {bet['race_number']}R, 邱蛻・{bet['scheduled_deadline']}")
            else:
                logger.info("譛滄剞蛻・ｌ縺ｮ雉ｼ蜈･莠亥ｮ壹・縺ゅｊ縺ｾ縺帙ｓ")
            
            conn.commit()
            return len(expired_bets)
            
    except Exception as e:
        logger.error(f"譛滄剞蛻・ｌ蜃ｦ逅・お繝ｩ繝ｼ: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def process_deadline_bets():
    """
    邱蛻・蛻・燕縺ｮ雉ｼ蜈･蛻､譁ｭ蜃ｦ逅・    """
    logger.info("=== 邱蛻・蛻・燕縺ｮ雉ｼ蜈･蛻､譁ｭ蜃ｦ逅・幕蟋・===")
    
    # 縺ｾ縺壹∵悄髯仙・繧後・雉ｼ蜈･莠亥ｮ壹ｒ蜃ｦ逅・    expire_overdue_bets()
    
    # aware datetime(JST)縺ｧ邨ｱ荳縺励※豈碑ｼ・    now = datetime.now(JST)
    # 邱蛻・蛻・燕縲・蛻・燕縺ｮ繝ｬ繝ｼ繧ｹ繧貞ｯｾ雎｡
    deadline_start = now + timedelta(seconds=30)
    deadline_end = now + timedelta(minutes=2)
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 蟇ｾ雎｡縺ｮ雉ｼ蜈･莠亥ｮ壹ｒ蜿門ｾ・            cur.execute("""
                SELECT * FROM virtual_bets
                WHERE status = 'pending'
                AND scheduled_deadline BETWEEN %s AND %s
            """, (deadline_start, deadline_end))
            pending_bets = cur.fetchall()
            
            if not pending_bets:
                logger.info("蜃ｦ逅・ｯｾ雎｡縺ｮ雉ｼ蜈･莠亥ｮ壹′縺ゅｊ縺ｾ縺帙ｓ")
                return
            
            logger.info(f"蜃ｦ逅・ｯｾ雎｡: {len(pending_bets)}莉ｶ")
            
            for bet in pending_bets:
                try:
                    process_single_bet(cur, bet)
                except Exception as e:
                    logger.error(f"雉ｼ蜈･蜃ｦ逅・お繝ｩ繝ｼ: bet_id={bet['id']}, error={e}")
            
            conn.commit()
            
    except Exception as e:
        logger.error(f"雉ｼ蜈･蛻､譁ｭ蜃ｦ逅・お繝ｩ繝ｼ: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def process_single_bet(cur, bet: Dict):
    """蜊倅ｸ縺ｮ雉ｼ蜈･莠亥ｮ壹ｒ蜃ｦ逅・""
    bet_id = bet['id']
    strategy_type = bet['strategy_type']
    race_date = bet['race_date']
    stadium_code = bet['stadium_code']
    race_number = bet['race_number']
    combination = bet['combination']
    bet_type = bet['bet_type']
    
    config = STRATEGIES.get(strategy_type, {})
    
    logger.info(f"蜃ｦ逅・ｸｭ: {stadium_code} {race_number}R {combination} ({strategy_type})")
    
    race_date_str = race_date.strftime('%Y-%m-%d') if hasattr(race_date, 'strftime') else str(race_date)
    race_date_yyyymmdd = race_date_str.replace('-', '')
    
    # bias_1_3謌ｦ逡･縺ｮ蝣ｴ蜷医・隲匁枚貅匁侠縺ｮ蜃ｦ逅・ｼ亥ｽ灘慍蜍晉紫6.5莉･荳翫・騾｣蜊・2騾｣隍・・鬮倥＞譁ｹ・・    if strategy_type == 'bias_1_3':
        # 1蜿ｷ濶・・蠖灘慍蜍晉紫繧偵メ繧ｧ繝・け
        local_win_rate = get_boat1_local_win_rate(cur, race_date_yyyymmdd, stadium_code, race_number)
        
        if local_win_rate is None:
            skip_bet(cur, bet_id, "蠖灘慍蜍晉紫蜿門ｾ怜､ｱ謨・)
            return
        
        min_local_win_rate = config.get('min_local_win_rate', 6.5)
        
        if local_win_rate < min_local_win_rate:
            skip_bet(cur, bet_id, f"蠖灘慍蜍晉紫縺御ｸ矩剞譛ｪ貅 ({local_win_rate:.1f} < {min_local_win_rate})")
            return
        
        # 2騾｣蜊倥→2騾｣隍・・繧ｪ繝・ぜ繧貞叙蠕励＠縲・ｫ倥＞譁ｹ繧帝∈謚橸ｼ郁ｫ匁枚縺ｮ譚｡莉ｶ・・        exacta_odds = get_odds(cur, race_date_str, stadium_code, race_number, '2t', '1-3')
        quinella_odds = get_odds(cur, race_date_str, stadium_code, race_number, '2f', '1-3')
        
        if exacta_odds is None and quinella_odds is None:
            skip_bet(cur, bet_id, "繧ｪ繝・ぜ蜿門ｾ怜､ｱ謨・)
            return
        
        # 鬮倥＞譁ｹ繧帝∈謚・        if exacta_odds is not None and quinella_odds is not None:
            if exacta_odds >= quinella_odds:
                final_odds = exacta_odds
                selected_bet_type = 'exacta'
            else:
                final_odds = quinella_odds
                selected_bet_type = 'quinella'
        elif exacta_odds is not None:
            final_odds = exacta_odds
            selected_bet_type = 'exacta'
        else:
            final_odds = quinella_odds
            selected_bet_type = 'quinella'
        
        logger.info(f"3遨ｴ(隲匁枚貅匁侠): 蠖灘慍蜍晉紫={local_win_rate:.1f}, 2騾｣蜊・{exacta_odds}, 2騾｣隍・{quinella_odds} -> {selected_bet_type}")
        
        # 雉ｼ蜈･遒ｺ螳夲ｼ磯∈謚槭＠縺溯ｳｼ蜈･繧ｿ繧､繝励〒譖ｴ譁ｰ縲∝虚逧・≡鬘崎ｨ育ｮ暦ｼ・        confirm_bet_with_type(cur, bet_id, final_odds, selected_bet_type, local_win_rate, strategy_type)
        return
    
    # bias_1_3_2nd謌ｦ逡･縺ｮ蝣ｴ蜷医・迚ｹ蛻･縺ｪ蜃ｦ逅・    if strategy_type == 'bias_1_3_2nd':
        # 1蜿ｷ濶・・蠖灘慍蜍晉紫繧偵メ繧ｧ繝・け
        local_win_rate = get_boat1_local_win_rate(cur, race_date_yyyymmdd, stadium_code, race_number)
        
        if local_win_rate is None:
            skip_bet(cur, bet_id, "蠖灘慍蜍晉紫蜿門ｾ怜､ｱ謨・)
            return
        
        min_local_win_rate = config.get('min_local_win_rate', 4.5)
        max_local_win_rate = config.get('max_local_win_rate', 6.0)
        
        if local_win_rate < min_local_win_rate or local_win_rate >= max_local_win_rate:
            skip_bet(cur, bet_id, f"蠖灘慍蜍晉紫縺檎ｯ・峇螟・({local_win_rate:.1f} not in [{min_local_win_rate}, {max_local_win_rate}))")
            return
        
        # 2騾｣蜊倥→2騾｣隍・・繧ｪ繝・ぜ繧貞叙蠕励＠縲・ｫ倥＞譁ｹ繧帝∈謚・        exacta_odds = get_odds(cur, race_date_str, stadium_code, race_number, '2t', '1-3')
        quinella_odds = get_odds(cur, race_date_str, stadium_code, race_number, '2f', '1-3')
        
        if exacta_odds is None and quinella_odds is None:
            skip_bet(cur, bet_id, "繧ｪ繝・ぜ蜿門ｾ怜､ｱ謨・)
            return
        
        # 鬮倥＞譁ｹ繧帝∈謚・        if exacta_odds is not None and quinella_odds is not None:
            if exacta_odds >= quinella_odds:
                final_odds = exacta_odds
                selected_bet_type = 'exacta'
            else:
                final_odds = quinella_odds
                selected_bet_type = 'quinella'
        elif exacta_odds is not None:
            final_odds = exacta_odds
            selected_bet_type = 'exacta'
        else:
            final_odds = quinella_odds
            selected_bet_type = 'quinella'
        
        logger.info(f"3遨ｴ2nd: 蠖灘慍蜍晉紫={local_win_rate:.1f}, 2騾｣蜊・{exacta_odds}, 2騾｣隍・{quinella_odds} -> {selected_bet_type}")
        
        # 繧ｪ繝・ぜ譚｡莉ｶ蛻､螳・        min_odds = config.get('min_odds', 3.0)
        max_odds = config.get('max_odds', 100.0)
        
        if final_odds < min_odds:
            skip_bet(cur, bet_id, f"繧ｪ繝・ぜ縺御ｽ弱☆縺弱ｋ ({final_odds} < {min_odds})")
            return
        
        if final_odds > max_odds:
            skip_bet(cur, bet_id, f"繧ｪ繝・ぜ縺碁ｫ倥☆縺弱ｋ ({final_odds} > {max_odds})")
            return
        
        # 雉ｼ蜈･遒ｺ螳夲ｼ磯∈謚槭＠縺溯ｳｼ蜈･繧ｿ繧､繝励〒譖ｴ譁ｰ縲∝虚逧・≡鬘崎ｨ育ｮ暦ｼ・        confirm_bet_with_type(cur, bet_id, final_odds, selected_bet_type, local_win_rate, strategy_type)
        return
    
    # 騾壼ｸｸ縺ｮ謌ｦ逡･縺ｮ蜃ｦ逅・    # 繧ｪ繝・ぜ繧ｿ繧､繝励ｒ螟画鋤
    odds_type_map = {'win': 'win', 'quinella': '2f', 'exacta': '2t'}
    odds_type = odds_type_map.get(bet_type, 'win')
    
    # 譛譁ｰ繧ｪ繝・ぜ繧貞叙蠕・    final_odds = get_odds(cur, race_date_str, stadium_code, race_number, odds_type, combination)
    
    if final_odds is None or final_odds == 0:
        skip_bet(cur, bet_id, "繧ｪ繝・ぜ蜿門ｾ怜､ｱ謨・)
        return
    
    # 譚｡莉ｶ蛻､螳・    min_odds = config.get('min_odds', 1.0)
    max_odds = config.get('max_odds', 100.0)
    
    if final_odds < min_odds:
        skip_bet(cur, bet_id, f"繧ｪ繝・ぜ縺御ｽ弱☆縺弱ｋ ({final_odds} < {min_odds})")
        return
    
    if final_odds > max_odds:
        skip_bet(cur, bet_id, f"繧ｪ繝・ぜ縺碁ｫ倥☆縺弱ｋ ({final_odds} > {max_odds})")
        return
    
    # 雉ｼ蜈･遒ｺ螳夲ｼ亥虚逧・≡鬘崎ｨ育ｮ暦ｼ・    confirm_bet(cur, bet_id, final_odds, strategy_type)


def get_odds(cur, race_date_str: str, stadium_code: str, race_number: int, odds_type: str, combination: str) -> Optional[float]:
    """繧ｪ繝・ぜ繧貞叙蠕・""
    cur.execute("""
        SELECT odds_value, odds_min, odds_max
        FROM odds_history
        WHERE race_date = %s AND stadium_code = %s AND race_number = %s
        AND odds_type = %s AND combination = %s
        ORDER BY scraped_at DESC
        LIMIT 1
    """, (race_date_str, stadium_code, race_number, odds_type, combination))
    
    odds_row = cur.fetchone()
    
    if not odds_row:
        return None
    
    odds_value = odds_row.get('odds_value')
    if odds_value:
        return float(odds_value)
    
    odds_min = odds_row.get('odds_min')
    if odds_min:
        return float(odds_min)
    
    return None


def get_boat1_local_win_rate(cur, race_date_yyyymmdd: str, stadium_code: str, race_number: int) -> Optional[float]:
    """
    1蜿ｷ濶・・蠖灘慍蜍晉紫繧貞叙蠕・    historical_programs繝・・繝悶Ν縺九ｉ蜿門ｾ・    """
    # stadium_code繧・譯√↓繝代ョ繧｣繝ｳ繧ｰ
    stadium_code_padded = str(stadium_code).zfill(2)
    race_no_padded = str(race_number).zfill(2)
    
    cur.execute("""
        SELECT local_win_rate
        FROM historical_programs
        WHERE race_date = %s AND stadium_code = %s AND race_no = %s AND boat_no = '1'
        LIMIT 1
    """, (race_date_yyyymmdd, stadium_code_padded, race_no_padded))
    
    row = cur.fetchone()
    
    if row and row.get('local_win_rate'):
        return float(row['local_win_rate'])
    
    return None


def confirm_bet_with_type(cur, bet_id: int, final_odds: float, selected_bet_type: str, local_win_rate: float, strategy_type: str = None):
    """雉ｼ蜈･繧堤｢ｺ螳夲ｼ郁ｳｼ蜈･繧ｿ繧､繝励ｂ譖ｴ譁ｰ縲∝虚逧・≡鬘崎ｨ育ｮ暦ｼ・""
    now = datetime.now(JST)
    
    # 雉ｼ蜈･驥鷹｡阪ｒ蜍慕噪縺ｫ險育ｮ・    if strategy_type:
        bet_amount = calculate_bet_amount(strategy_type, final_odds, local_win_rate)
    else:
        bet_amount = BASE_AMOUNT
    
    # reason縺ｫ蠖灘慍蜍晉紫縺ｨ驕ｸ謚槭＠縺溯ｳｼ蜈･繧ｿ繧､繝励ｒ險倬鹸
    cur.execute("SELECT reason FROM virtual_bets WHERE id = %s", (bet_id,))
    row = cur.fetchone()
    
    current_reason = row['reason'] if row and row['reason'] else {}
    if isinstance(current_reason, str):
        try:
            current_reason = json.loads(current_reason)
        except:
            current_reason = {}
    
    current_reason['localWinRate'] = local_win_rate
    current_reason['selectedBetType'] = selected_bet_type
    current_reason['decision'] = 'confirmed'
    current_reason['calculatedBetAmount'] = bet_amount
    current_reason['amountReason'] = f"繧ｪ繝・ぜ{final_odds:.1f}蛟・ 蠖灘慍蜍晉紫{local_win_rate:.1f}"
    
    cur.execute("""
        UPDATE virtual_bets
        SET status = 'confirmed',
            bet_type = %s,
            odds = %s,
            bet_amount = %s,
            decision_time = %s,
            executed_at = %s,
            updated_at = %s,
            reason = %s
        WHERE id = %s
    """, (selected_bet_type, final_odds, bet_amount, now, now, now, json.dumps(current_reason, ensure_ascii=False), bet_id))
    
    logger.info(f"雉ｼ蜈･遒ｺ螳・ bet_id={bet_id}, odds={final_odds}, type={selected_bet_type}, local_win_rate={local_win_rate}, amount={bet_amount}蜀・)


def confirm_bet(cur, bet_id: int, final_odds: float, strategy_type: str = None):
    """雉ｼ蜈･繧堤｢ｺ螳夲ｼ亥虚逧・≡鬘崎ｨ育ｮ暦ｼ・""
    now = datetime.now(JST)
    
    # 雉ｼ蜈･驥鷹｡阪ｒ蜍慕噪縺ｫ險育ｮ・    if strategy_type:
        bet_amount = calculate_bet_amount(strategy_type, final_odds)
    else:
        bet_amount = BASE_AMOUNT
    
    # reason縺ｫ驥鷹｡崎ｨ育ｮ礼炊逕ｱ繧定ｨ倬鹸
    cur.execute("SELECT reason FROM virtual_bets WHERE id = %s", (bet_id,))
    row = cur.fetchone()
    
    current_reason = row['reason'] if row and row['reason'] else {}
    if isinstance(current_reason, str):
        try:
            current_reason = json.loads(current_reason)
        except:
            current_reason = {}
    
    current_reason['decision'] = 'confirmed'
    current_reason['calculatedBetAmount'] = bet_amount
    current_reason['amountReason'] = f"繧ｪ繝・ぜ{final_odds:.1f}蛟・
    
    cur.execute("""
        UPDATE virtual_bets
        SET status = 'confirmed',
            odds = %s,
            bet_amount = %s,
            decision_time = %s,
            executed_at = %s,
            updated_at = %s,
            reason = %s
        WHERE id = %s
    """, (final_odds, bet_amount, now, now, now, json.dumps(current_reason, ensure_ascii=False), bet_id))
    
    logger.info(f"雉ｼ蜈･遒ｺ螳・ bet_id={bet_id}, odds={final_odds}, amount={bet_amount}蜀・)


def skip_bet(cur, bet_id: int, reason: str):
    """雉ｼ蜈･繧定ｦ矩√ｊ"""
    now = datetime.now(JST)
    
    # 迴ｾ蝨ｨ縺ｮ逅・罰繧貞叙蠕励＠縺ｦ譖ｴ譁ｰ
    cur.execute("SELECT reason FROM virtual_bets WHERE id = %s", (bet_id,))
    row = cur.fetchone()
    
    current_reason = row['reason'] if row and row['reason'] else {}
    if isinstance(current_reason, str):
        try:
            current_reason = json.loads(current_reason)
        except:
            current_reason = {}
    
    current_reason['skipReason'] = reason
    current_reason['decision'] = 'skipped'
    
    cur.execute("""
        UPDATE virtual_bets
        SET status = 'skipped',
            reason = %s,
            decision_time = %s,
            updated_at = %s
        WHERE id = %s
    """, (json.dumps(current_reason, ensure_ascii=False), now, now, bet_id))
    
    logger.info(f"雉ｼ蜈･隕矩√ｊ: bet_id={bet_id}, reason={reason}")


def update_results():
    """
    邨先棡繧呈峩譁ｰ
    confirmed迥ｶ諷九・雉ｼ蜈･縺ｧ縲√Ξ繝ｼ繧ｹ邨先棡縺悟・縺ｦ縺・ｋ繧ゅ・繧呈峩譁ｰ
    """
    logger.info("=== 邨先棡譖ｴ譁ｰ蜃ｦ逅・幕蟋・===")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 邨先棡蠕・■縺ｮ雉ｼ蜈･繧貞叙蠕・            cur.execute("""
                SELECT vb.*, r.id as race_id
                FROM virtual_bets vb
                JOIN races r ON vb.race_date = r.race_date 
                    AND vb.stadium_code::int = r.stadium_code 
                    AND vb.race_number = r.race_number
                WHERE vb.status = 'confirmed'
            """)
            confirmed_bets = cur.fetchall()
            
            if not confirmed_bets:
                logger.info("邨先棡蠕・■縺ｮ雉ｼ蜈･縺後≠繧翫∪縺帙ｓ")
                return
            
            logger.info(f"邨先棡蠕・■: {len(confirmed_bets)}莉ｶ")
            
            for bet in confirmed_bets:
                try:
                    update_single_result(cur, bet)
                except Exception as e:
                    logger.error(f"邨先棡譖ｴ譁ｰ繧ｨ繝ｩ繝ｼ: bet_id={bet['id']}, error={e}")
            
            conn.commit()
            
    except Exception as e:
        logger.error(f"邨先棡譖ｴ譁ｰ蜃ｦ逅・お繝ｩ繝ｼ: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def update_single_result(cur, bet: Dict):
    """蜊倅ｸ縺ｮ雉ｼ蜈･邨先棡繧呈峩譁ｰ"""
    bet_id = bet['id']
    race_id = bet['race_id']
    bet_type = bet['bet_type']
    combination = bet['combination']
    bet_amount = bet['bet_amount']
    odds = float(bet['odds']) if bet['odds'] else 0
    strategy_type = bet['strategy_type']
    
    # 繝ｬ繝ｼ繧ｹ邨先棡繧貞叙蠕・    cur.execute("""
        SELECT first_place, second_place, third_place, race_status
        FROM race_results
        WHERE race_id = %s
    """, (race_id,))
    result = cur.fetchone()
    
    if not result:
        return  # 縺ｾ縺邨先棡縺悟・縺ｦ縺・↑縺・    
    if result['race_status'] and result['race_status'] != '謌千ｫ・:
        # 繝ｬ繝ｼ繧ｹ荳肴・遶・        cur.execute("""
            UPDATE virtual_bets
            SET status = 'canceled',
                actual_result = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (result['race_status'], bet_id))
        logger.info(f"繝ｬ繝ｼ繧ｹ荳肴・遶・ bet_id={bet_id}, status={result['race_status']}")
        return
    
    first = result['first_place']
    second = result['second_place']
    third = result['third_place']
    
    if not first or not second:
        return  # 邨先棡縺御ｸ榊ｮ悟・
    
    actual_result = f"{first}-{second}-{third}" if third else f"{first}-{second}"
    
    # 逧・ｸｭ蛻､螳・    is_hit = False
    if bet_type == 'win':
        is_hit = str(first) == combination
    elif bet_type == 'quinella':
        # 2騾｣隍・ 鬆・ｸ榊酔
        actual_pair = set([str(first), str(second)])
        bet_pair = set(combination.replace('-', '=').split('='))
        is_hit = actual_pair == bet_pair
    elif bet_type == 'exacta':
        # 2騾｣蜊・ 鬆・分騾壹ｊ
        actual_exacta = f"{first}-{second}"
        is_hit = actual_exacta == combination
    
    # 謇墓綾驥代ｒ蜿門ｾ・    payoff = 0
    if is_hit:
        payoff_type_map = {'win': 'win', 'quinella': 'quinella', 'exacta': 'exacta'}
        payoff_type = payoff_type_map.get(bet_type, bet_type)
        
        cur.execute("""
            SELECT payoff FROM payoffs
            WHERE race_id = %s AND bet_type = %s AND combination = %s
        """, (race_id, payoff_type, combination))
        payoff_row = cur.fetchone()
        if payoff_row:
            payoff = payoff_row['payoff']
    
    # 謳咲寢險育ｮ・    return_amount = int(payoff * bet_amount / 100) if is_hit else 0
    profit = return_amount - bet_amount
    
    now = datetime.now(JST)
    status = 'won' if is_hit else 'lost'
    
    cur.execute("""
        UPDATE virtual_bets
        SET status = %s,
            actual_result = %s,
            payoff = %s,
            return_amount = %s,
            profit = %s,
            result_confirmed_at = %s,
            updated_at = %s
        WHERE id = %s
    """, (status, actual_result, payoff, return_amount, profit, now, now, bet_id))
    
    logger.info(f"邨先棡譖ｴ譁ｰ: bet_id={bet_id}, status={status}, profit={profit}")
    
    # 雉・≡繧呈峩譁ｰ
    update_fund(cur, strategy_type, profit, is_hit, bet_amount, return_amount)


def update_fund(cur, strategy_type: str, profit: float, is_hit: bool, bet_amount: int, return_amount: int):
    """雉・≡繧呈峩譁ｰ"""
    cur.execute("""
        SELECT * FROM virtual_funds
        WHERE strategy_type = %s AND is_active = TRUE
        LIMIT 1
    """, (strategy_type,))
    fund = cur.fetchone()
    
    if not fund:
        logger.warning(f"繧｢繧ｯ繝・ぅ繝悶↑雉・≡縺瑚ｦ九▽縺九ｊ縺ｾ縺帙ｓ: {strategy_type}")
        return
    
    current_fund = float(fund['current_fund']) + profit
    total_profit = float(fund['total_profit']) + profit
    total_bets = fund['total_bets'] + 1
    total_hits = fund['total_hits'] + (1 if is_hit else 0)
    hit_rate = (total_hits / total_bets * 100) if total_bets > 0 else 0
    
    total_bet_amount = float(fund['total_bet_amount']) + bet_amount
    total_return_amount = float(fund['total_return_amount']) + return_amount
    return_rate = (total_return_amount / total_bet_amount * 100) if total_bet_amount > 0 else 0
    
    cur.execute("""
        UPDATE virtual_funds
        SET current_fund = %s,
            total_profit = %s,
            total_bets = %s,
            total_hits = %s,
            hit_rate = %s,
            total_bet_amount = %s,
            total_return_amount = %s,
            return_rate = %s,
            updated_at = NOW()
        WHERE id = %s
    """, (current_fund, total_profit, total_bets, total_hits, hit_rate,
          total_bet_amount, total_return_amount, return_rate, fund['id']))
    
    logger.info(f"雉・≡譖ｴ譁ｰ: {strategy_type}, current={current_fund}, profit={profit}")


def update_skipped_results():
    """
    隕矩√ｊ繝ｬ繝ｼ繧ｹ縺ｮ邨先棡繧よ峩譁ｰ・郁｡ｨ遉ｺ逕ｨ・・    """
    logger.info("=== 隕矩√ｊ繝ｬ繝ｼ繧ｹ邨先棡譖ｴ譁ｰ髢句ｧ・===")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 隕矩√ｊ縺ｧ邨先棡譛ｪ險ｭ螳壹・雉ｼ蜈･繧貞叙蠕・            cur.execute("""
                SELECT vb.*, r.id as race_id
                FROM virtual_bets vb
                JOIN races r ON vb.race_date = r.race_date 
                    AND vb.stadium_code::int = r.stadium_code 
                    AND vb.race_number = r.race_number
                WHERE vb.status = 'skipped'
                AND vb.actual_result IS NULL
            """)
            skipped_bets = cur.fetchall()
            
            if not skipped_bets:
                logger.info("譖ｴ譁ｰ蟇ｾ雎｡縺ｮ隕矩√ｊ繝ｬ繝ｼ繧ｹ縺後≠繧翫∪縺帙ｓ")
                return
            
            logger.info(f"隕矩√ｊ繝ｬ繝ｼ繧ｹ: {len(skipped_bets)}莉ｶ")
            
            for bet in skipped_bets:
                race_id = bet['race_id']
                bet_id = bet['id']
                
                # 繝ｬ繝ｼ繧ｹ邨先棡繧貞叙蠕・                cur.execute("""
                    SELECT first_place, second_place, third_place, race_status
                    FROM race_results
                    WHERE race_id = %s
                """, (race_id,))
                result = cur.fetchone()
                
                if not result or not result['first_place']:
                    continue
                
                actual_result = f"{result['first_place']}-{result['second_place']}-{result['third_place']}"
                
                cur.execute("""
                    UPDATE virtual_bets
                    SET actual_result = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (actual_result, bet_id))
            
            conn.commit()
            logger.info("隕矩√ｊ繝ｬ繝ｼ繧ｹ邨先棡譖ｴ譁ｰ螳御ｺ・)
            
    except Exception as e:
        logger.error(f"隕矩√ｊ繝ｬ繝ｼ繧ｹ邨先棡譖ｴ譁ｰ繧ｨ繝ｩ繝ｼ: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python auto_betting.py <command>")
        print("Commands: register, decide, result, skipped")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "register":
        register_daily_bets()
    elif command == "decide":
        process_deadline_bets()
    elif command == "expire":
        expire_overdue_bets()
    elif command == "result":
        update_results()
        update_skipped_results()
    elif command == "skipped":
        update_skipped_results()
    else:
        print(f"Unknown command: {command}")
        print("Commands: register, decide, expire, result, skipped")
        sys.exit(1)

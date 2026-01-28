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
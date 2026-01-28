競艇予想ダッシュボード API
PostgreSQL（kokotomo-db-staging）のみを使用
"""

import os
import json
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional, Dict, Any
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="競艇予想ダッシュボード API")

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# データベース接続
DATABASE_URL = os.environ.get("DATABASE_URL")

# タイムゾーン設定
JST = timezone(timedelta(hours=9))

def get_adjusted_date() -> date:
    """現在の日付を返す（JST）"""
    now_jst = datetime.now(JST)
    return date(now_jst.year, now_jst.month, now_jst.day)


def get_db_connection():
    """データベース接続を取得"""
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def decimal_to_float(obj):
    """Decimalをfloatに変換"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(item) for item in obj]
    return obj


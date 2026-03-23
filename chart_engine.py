"""
chart_engine.py — Antigravity Nexus V30
Chart Data Pipeline with Ralph Loop Compliance

Architecture:
  Resolution      → 時間粒度常數
  ChartContext    → 查詢參數封裝
  ChartPipelineV2 → 資料抓取、清洗、Coverage 計算
  chart_engine    → 單例物件，供 app.py 直接呼叫

Data Source Priority:
  1. SQLite Cache (market_data.db) — 若 coverage >= 60% 直接使用
  2. Finazon API                   — 主要資料來源
  3. yFinance                      — 備援 (Finazon 失敗時)

Return Dict:
  {
    'df'                 : pd.DataFrame  (DatetimeIndex tz-naive, Title Case OHLCV),
    'coverage'           : float         (0.0–1.0),
    'missing_count'      : int           (app.py 使用),
    'missing_days_count' : int           (ralph_loop_validator 使用),
    'expected_days_count': int           (ralph_loop_validator 使用),
    'source'             : str           ("Cache" | "Finazon" | "yFinance" | "Unknown"),
    'reliability'        : bool          (True = NYSE 交易日曆, False = BDay fallback)
  }
"""

import sqlite3
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional

# ─── 交易日曆（optional）────────────────────────────────────────
try:
    import pandas_market_calendars as mcal
    _HAS_MCAL = True
except ImportError:
    _HAS_MCAL = False


# ============================================================
# ⚙️  Constants
# ============================================================
FINAZON_ENDPOINT   = "https://api.finazon.io/latest/finazon/us_stocks_essential/time_series"
SQLITE_DB          = "market_data.db"
CACHE_MIN_COVERAGE = 0.60   # 低於此值才觸發 API 補抓

PERIOD_DAYS = {
    "1mo":   30,
    "3mo":   90,
    "6mo":  180,
    "1y":   365,
    "5y":  1825,
}


# ============================================================
# 📐  Resolution
# ============================================================
class Resolution:
    DAILY  = "1d"
    WEEKLY = "1w"
    HOURLY = "1h"


# ============================================================
# 📦  ChartContext — Query Parameter Bag
# ============================================================
@dataclass
class ChartContext:
    symbol:      str
    interval:    str             # e.g. Resolution.DAILY
    period:      str             # e.g. "1y"
    finazon_key: Optional[str] = field(default=None)


# ============================================================
# 🔧  Internal Helpers
# ============================================================
def _period_to_daterange(period: str):
    """Return (start_date, end_date) as UTC-naive datetime objects."""
    days  = PERIOD_DAYS.get(period, 365)
    end   = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    return start, end


def _expected_trading_days(start: datetime, end: datetime):
    """
    Returns (expected_count, reliability).
      reliability = True  → NYSE calendar (excludes holidays)
      reliability = False → BDay fallback  (does not exclude holidays)
    """
    if _HAS_MCAL:
        try:
            nyse     = mcal.get_calendar('NYSE')
            schedule = nyse.schedule(start_date=start, end_date=end)
            return len(schedule), True
        except Exception:
            pass

    # BDay fallback
    bdays = len(pd.date_range(start=start, end=end, freq='B'))
    return bdays, False


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardise column names → Title Case (Open High Low Close Volume),
    set DatetimeIndex (UTC tz-naive, normalised to midnight), sort ascending.
    """
    # Rename lowercase / single-char → Title Case
    rename_map = {
        'open':  'Open',  'high':  'High',  'low':  'Low',
        'close': 'Close', 'volume': 'Volume',
        'o':     'Open',  'h':     'High',  'l':    'Low',
        'c':     'Close', 'v':     'Volume',
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Promote date column to DatetimeIndex if not already set
    if not isinstance(df.index, pd.DatetimeIndex):
        for col in ('Date', 'date', 'timestamp', 'Datetime', 'datetime'):
            if col in df.columns:
                df = df.set_index(col)
                break

    df.index = pd.to_datetime(df.index, utc=False)

    # Strip timezone → tz-naive (G1 requirement)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    # Normalise to midnight (no intra-day time for 1d data)
    df.index = df.index.normalize()
    df       = df.sort_index()

    # Keep only OHLCV columns
    keep = [c for c in ('Open', 'High', 'Low', 'Close', 'Volume') if c in df.columns]
    return df[keep].copy()


def _clean_ohlc(df: pd.DataFrame):
    """
    Remove rows where OHLC semantics are violated.
    Rule: High >= max(Open, Close)  AND  Low <= min(Open, Close)
    Returns (clean_df, dropped_count).
    """
    if df.empty:
        return df, 0

    mask_valid = (
        (df['High'] >= df[['Open', 'Close']].max(axis=1)) &
        (df['Low']  <= df[['Open', 'Close']].min(axis=1)) &
        (df['High'] >= df['Low'])
    )
    dropped = int((~mask_valid).sum())
    return df[mask_valid].copy(), dropped


def _compute_coverage(df: pd.DataFrame, start: datetime, end: datetime):
    """
    Returns (coverage, missing_count, expected_count, reliability).
    """
    expected_count, reliability = _expected_trading_days(start, end)
    if expected_count == 0:
        return 0.0, 0, 0, reliability

    actual_days = df.index.normalize().nunique() if not df.empty else 0
    missing     = max(0, expected_count - actual_days)
    coverage    = actual_days / expected_count

    return round(min(coverage, 1.0), 4), missing, expected_count, reliability


# ============================================================
# 📡  Data Fetchers
# ============================================================
def _fetch_from_sqlite(ticker: str, start: datetime, end: datetime) -> pd.DataFrame:
    """
    Read OHLCV from market_data.db (written by ingest_engine.py).
    Returns empty DataFrame if DB or table is missing.
    """
    try:
        start_ts = int(start.timestamp())
        end_ts   = int(end.timestamp())
        conn     = sqlite3.connect(SQLITE_DB)
        query    = (
            "SELECT timestamp, open, high, low, close, volume "
            "FROM prices "
            f"WHERE ticker = '{ticker.upper()}' "
            f"  AND timestamp >= {start_ts} "
            f"  AND timestamp <= {end_ts} "
            "ORDER BY timestamp ASC"
        )
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            return pd.DataFrame()

        df['Date'] = pd.to_datetime(df['timestamp'], unit='s')
        df = df.drop(columns=['timestamp']).set_index('Date')
        return _normalize_df(df)
    except Exception:
        return pd.DataFrame()


def _fetch_from_finazon(ticker: str, start: datetime, end: datetime,
                        api_key: str) -> pd.DataFrame:
    """
    Fetch daily OHLCV from Finazon API.
    Returns empty DataFrame on any failure.
    """
    if not api_key:
        return pd.DataFrame()

    params = {
        "ticker":    ticker.upper(),
        "interval":  "1d",
        "start_at":  int(start.timestamp()),
        "end_at":    int(end.timestamp()),
        "page_size": 1000,
        "apikey":    api_key,
    }
    try:
        res = requests.get(FINAZON_ENDPOINT, params=params, timeout=10)

        # Single retry on rate-limit
        if res.status_code == 429:
            time.sleep(2)
            res = requests.get(FINAZON_ENDPOINT, params=params, timeout=10)

        if res.status_code != 200:
            return pd.DataFrame()

        data = res.json().get('data', [])
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df['Date'] = pd.to_datetime(df['t'], unit='s')
        df = df.rename(columns={
            'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume'
        })
        df = df.set_index('Date')
        return _normalize_df(df)
    except Exception:
        return pd.DataFrame()


def _fetch_from_yfinance(ticker: str, start: datetime, end: datetime) -> pd.DataFrame:
    """
    Fetch OHLCV from yfinance as last-resort fallback.
    Returns empty DataFrame on any failure.
    """
    try:
        import yfinance as yf
        raw = yf.download(
            ticker,
            start=start,
            end=end + timedelta(days=1),
            auto_adjust=True,
            progress=False
        )
        if raw is None or raw.empty:
            return pd.DataFrame()
        return _normalize_df(raw)
    except Exception:
        return pd.DataFrame()


# ============================================================
# 🚀  ChartPipelineV2
# ============================================================
class ChartPipelineV2:
    """
    Ralph-compliant chart data pipeline.
    Priority: SQLite Cache → Finazon API → yFinance
    """

    def __init__(self, context: ChartContext):
        self.ctx = context

    def run(self) -> dict:
        ctx        = self.ctx
        start, end = _period_to_daterange(ctx.period)
        source     = "Unknown"
        df         = pd.DataFrame()

        # ── Stage 1: SQLite Cache ──────────────────────────────────
        df_cache = _fetch_from_sqlite(ctx.symbol, start, end)
        if not df_cache.empty:
            cov_cache, _, _, _ = _compute_coverage(df_cache, start, end)
            if cov_cache >= CACHE_MIN_COVERAGE:
                df     = df_cache
                source = "Cache"

        # ── Stage 2: Finazon API ───────────────────────────────────
        if df.empty and ctx.finazon_key:
            df_fin = _fetch_from_finazon(ctx.symbol, start, end, ctx.finazon_key)
            if not df_fin.empty:
                df     = df_fin
                source = "Finazon"

        # ── Stage 3: yFinance Fallback ─────────────────────────────
        if df.empty:
            df_yf = _fetch_from_yfinance(ctx.symbol, start, end)
            if not df_yf.empty:
                df     = df_yf
                source = "yFinance"

        # ── Clean OHLC (G6) ────────────────────────────────────────
        if not df.empty:
            df, _dropped = _clean_ohlc(df)

        # ── Coverage Calculation (G4) ──────────────────────────────
        coverage, missing, expected, reliability = _compute_coverage(df, start, end)

        return {
            'df':                  df,
            'coverage':            coverage,
            'missing_count':       missing,       # app.py
            'missing_days_count':  missing,       # ralph_loop_validator.py
            'expected_days_count': expected,      # ralph_loop_validator.py
            'source':              source,
            'reliability':         reliability,
        }


# ============================================================
# 🔌  Singleton — for app.py direct call
# ============================================================
class _ChartEngineSingleton:
    """
    Stateless singleton so app.py can call:
        chart_engine.run(ticker, interval, period, finazon_key)
    """

    def run(self, ticker: str, interval: str = "1d",
            period: str = "1y", finazon_key: str = "") -> dict:
        ctx      = ChartContext(
            symbol=ticker, interval=interval,
            period=period, finazon_key=finazon_key
        )
        pipeline = ChartPipelineV2(ctx)
        return pipeline.run()


chart_engine = _ChartEngineSingleton()

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import pytz
from preload_db import preload
from governance import gov
import requests
import time
import traceback

try:
    import pandas_market_calendars as mcal
    HAS_MCAL = True
except:
    HAS_MCAL = False

from dataclasses import dataclass
from enum import Enum

class Resolution(str, Enum):
    DAILY = "1d"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"

@dataclass
class ChartContext:
    symbol: str
    interval: Resolution
    period: str
    finazon_key: str = None


class ChartPipelineV2:
    """
    Nexus V2 Charting Pipeline (Strict Mode & UTC)
    """
    
    def __init__(self, context: ChartContext = None):
        self.context = context
        self.nyse = mcal.get_calendar('NYSE') if HAS_MCAL else None


    def get_expected_schedule(self, start_date, end_date):
        # Force conversion to Timestamp if not already
        start_date = pd.Timestamp(start_date)
        end_date = pd.Timestamp(end_date)
        
        if HAS_MCAL and self.nyse:
            schedule = self.nyse.schedule(start_date=start_date, end_date=end_date)
            dates = schedule.index
            # Normalize to midnight and ensure naive (UTC baseline)
            dates = dates.normalize().tz_localize(None)
            return dates, True 
        else:
            print("⚠️ [ChartPipeline] Calendar Unavailable. Using BDay.")
            dates = pd.date_range(start=start_date, end=end_date, freq='B')
            return dates.normalize(), False

    def _calculate_gaps(self, df, expected_dates):
        if df.empty:
            return expected_dates, 0.0
            
        # Ensure we have a clean DatetimeIndex
        # normalize() returns a Series, so we must use .dt accessor again for tz_localize
        # Data in DB is UTC, converted to datetime.
        actual_dates = pd.to_datetime(df['Date']).dt.normalize()
        
        # If dates are already tz-aware (UTC), convert to naive
        if actual_dates.dt.tz is not None:
             actual_dates = actual_dates.dt.tz_localize(None)
             
        actual_index = pd.DatetimeIndex(actual_dates.unique()).sort_values()
        
        missing_dates = expected_dates.difference(actual_index)
        
        # Filter future
        now_norm = pd.Timestamp(datetime.utcnow().date())
        missing_dates = missing_dates[missing_dates < now_norm]
        
        if len(expected_dates) > 0:
            coverage = 1.0 - (len(missing_dates) / len(expected_dates))
        else:
            coverage = 0.0
            
        return missing_dates, coverage

    def _fetch_range(self, ticker, start_ts, end_ts, finazon_key, label="Segment"):
        """
        Generic fetcher given a timestamp range.
        Returns: records_fetched (int)
        """
        allowed, msg = gov.allow_request(ticker)
        if not allowed:
            print(f"🛑 [Gov] Blocked ({label}): {msg}")
            return 0

        dt_start = datetime.fromtimestamp(start_ts, tz=timezone.utc).date()
        dt_end = datetime.fromtimestamp(end_ts, tz=timezone.utc).date()
        
        print(f"🔄 [Fetch] {label}: {dt_start} -> {dt_end}")
        
                
        try:
            url = "https://api.finazon.io/latest/finazon/us_stocks_essential/time_series"
            params = {
                "ticker": ticker, "interval": "1d", "apikey": finazon_key,
                "start_at": start_ts, "end_at": end_ts,
                "page_size": 1000 # Ensure we get full data
            }
            res = requests.get(url, params=params, timeout=10)
            
            if res.status_code == 200:
                data = res.json().get('data', [])
                if data:
                    new_df = pd.DataFrame(data)
                    new_df = new_df.rename(columns={'t': 'Date', 'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume'})
                    new_df['Date'] = pd.to_datetime(new_df['Date'], unit='s')
                    new_df['Ticker'] = ticker 
                    preload.save_v2(new_df, source="finazon")
                    return len(data)
                else:
                    print("⚠️ [Fetch] Success but NO DATA returned.")
                    return 0
            else:
                body_snippet = res.text[:200]
                print(f"⚠️ [Fetch] API Error {res.status_code}: {body_snippet}")
                return 0
                
        except Exception as e:
            print(f"⚠️ [Fetch] Exception: {e}")
            return 0

    def _smart_fill(self, ticker, coverage, missing_dates, start_ts, end_ts, finazon_key):
        """
        Strategy:
        - coverage < 0.6: Full Rebuild (1 Call)
        - coverage >= 0.6: Segmentation (Top 1-2 gaps)
        """
        total_fetched = 0
        
        # STRATEGY A: REBUILD
        if coverage < 0.6:
            print(f"📉 Low Coverage ({coverage:.2%}). Triggering FULL REBUILD.")
            # Fetch entire range
            count = self._fetch_range(ticker, start_ts, end_ts, finazon_key, label="Rebuild")
            total_fetched += count
            
        # STRATEGY B: SEGMENTATION
        else:
            if len(missing_dates) == 0: return 0
            # Group gaps
            s_dates = pd.Series(missing_dates)
            diffs = s_dates.diff().dt.days
            breaks = diffs.fillna(1) > 1
            groups = breaks.cumsum()
            
            target_groups = [g for _, g in s_dates.groupby(groups)]
            target_groups.sort(key=len, reverse=True)
            
            # Fetch Top 2
            for group in target_groups[:2]:
                grp_start = int(group.min().replace(hour=0, minute=0, second=0).timestamp())
                grp_end = int((group.max() + timedelta(days=1)).replace(hour=0, minute=0, second=0).timestamp())
                
                count = self._fetch_range(ticker, grp_start, grp_end, finazon_key, label="GapFill")
                total_fetched += count
                
        return total_fetched

    def run(self, ticker=None, interval="1d", period="1mo", finazon_key=None):
        # Support running from context if provided in __init__ or args
        if self.context:
            ticker = self.context.symbol
            interval = self.context.interval
            period = self.context.period
            finazon_key = self.context.finazon_key
        
        # 1. Determine Range (UTC)
        now = datetime.utcnow()
        days_map = {"1mo": 35, "3mo": 95, "6mo": 185, "1y": 370}
        days = days_map.get(period, 35)
        
        start_date = now - timedelta(days=days)
        start_ts = int(start_date.timestamp())
        end_ts = int(now.timestamp())
        
        print(f"📊 [Query] {period} ({days}d) | Range: {start_date.date()} -> {now.date()}")
        print(f"   TS: {start_ts} -> {end_ts}")
        
        # 2. Query DB
        df = preload.get_v2(ticker, interval, start_ts, end_ts)
        
        # DB Debug Stats
        if not df.empty:
            db_min = df['Date'].min()
            db_max = df['Date'].max()
            uniq_days = df['Date'].dt.normalize().nunique()
            # print(f"   DB Found: {len(df)} rows | Min: {db_min.date()} | Max: {db_max.date()} | UniqDays: {uniq_days}")
        else:
            # print("   DB Found: 0 rows")
            uniq_days = 0

        # 3. OHLC Validation (Before Gaps)
        # Rule: Low <= min(O,C) AND High >= max(O,C)
        invalid_ohlc_count = 0
        if not df.empty:
            # Vectorized check
            min_oc = df[['Open', 'Close']].min(axis=1)
            max_oc = df[['Open', 'Close']].max(axis=1)
            
            invalid_mask = (df['Low'] > min_oc) | (df['High'] < max_oc) 
            invalid_ohlc_count = invalid_mask.sum()
            
            if invalid_ohlc_count > 0:
                print(f"⚠️ [Data] Dropping {invalid_ohlc_count} Invalid OHLC rows.")
                df = df[~invalid_mask]
        
        # 4. Gap Calculation
        expected_dates, reliability = self.get_expected_schedule(start_date, now)
        missing_dates, coverage = self._calculate_gaps(df, expected_dates)
        
        print(f"   ExpTradingDays: {len(expected_dates)} | ActUnique: {df['Date'].dt.normalize().nunique() if not df.empty else 0}")
        print(f"   Cov: {coverage:.2%} | Missing: {len(missing_dates)}")

        # 5. Smart Fill
        source_label = "DB (Cached)"
        filled_total = 0
        needs_fill = (coverage < 0.99)
        
        if needs_fill and finazon_key:
            filled_total = self._smart_fill(ticker, coverage, missing_dates, start_ts, end_ts, finazon_key)
            
            if filled_total > 0:
                # Refresh & Recalc
                df = preload.get_v2(ticker, interval, start_ts, end_ts)
                
                # Re-Validate OHLC post-fetch
                if not df.empty:
                     min_oc = df[['Open', 'Close']].min(axis=1)
                     max_oc = df[['Open', 'Close']].max(axis=1)
                     invalid_mask = (df['Low'] > min_oc) | (df['High'] < max_oc)
                     if invalid_mask.sum() > 0:
                         df = df[~invalid_mask]
                
                missing_dates, coverage = self._calculate_gaps(df, expected_dates)
                source_label = f"DB + Filled ({filled_total} rows)"
                print(f"✅ [Filled] New Cov: {coverage:.2%} | Missing: {len(missing_dates)}")

        # Ensure Date index for consumer
        if not df.empty and 'Date' in df.columns:
            df = df.set_index('Date')
            
        return {
            "df": df,
            "coverage": coverage,
            "missing_count": len(missing_dates),
            "source": source_label,
            "reliability": reliability,
            "expected_days_count": len(expected_dates),
            "invalid_ohlc_count": invalid_ohlc_count,
            "missing_dates": missing_dates
        }

chart_engine = ChartPipelineV2()

if __name__ == "__main__":
    print("🧪 Running ChartPipelineV2 Self-Test (Strict)...")
    import toml
    try:
        secrets = toml.load(".streamlit/secrets.toml")
        key = secrets.get("FINAZON_KEY")
        chart_engine.run("AMZN", "1d", "1mo", key)
        print("✅ Done")
    except KeyError:
        print("❌ No Secrets file found.")
    except Exception as e:
        print("❌ CRASHED:")
        traceback.print_exc()

import sqlite3
import pandas as pd
import json
import argparse
from datetime import datetime, timedelta
import sys

# Try import calendar
try:
    import pandas_market_calendars as mcal
    HAS_MCAL = True
except ImportError:
    HAS_MCAL = False

DB_FILE = "nexus_preload.db"

def run_forensics(ticker, interval, days_back):
    print(f"🔎 FORENSIC LAB: Analyzing {ticker} ({interval}) for last {days_back} days...")
    
    conn = sqlite3.connect(DB_FILE)
    
    # 1. Fetch Raw Data
    cutoff_ts = int((datetime.now() - timedelta(days=days_back)).timestamp())
    query = f"""
        SELECT ticker, interval, timestamp, open, high, low, close, volume 
        FROM ohlcv 
        WHERE ticker='{ticker}' AND interval='{interval}' AND timestamp >= {cutoff_ts}
        ORDER BY timestamp ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    results = {
        "meta": {"ticker": ticker, "interval": interval, "days_back": days_back},
        "basic_stats": {},
        "integrity": {},
        "gaps": {}
    }
    
    if df.empty:
        print("❌ NO DATA FOUND IN DB.")
        return results

    # 1.1 Basic Stats
    df['Date'] = pd.to_datetime(df['timestamp'], unit='s')
    results['basic_stats']['row_count'] = len(df)
    results['basic_stats']['min_ts'] = df['Date'].min().strftime('%Y-%m-%d')
    results['basic_stats']['max_ts'] = df['Date'].max().strftime('%Y-%m-%d')
    results['basic_stats']['distinct_ts'] = df['timestamp'].nunique()
    
    # Duplicate Check (PK should enforce this, but let's verify logical dupes)
    # Group by Ticker, Interval, Timestamp
    dupes = df.duplicated(subset=['ticker', 'interval', 'timestamp'], keep=False).sum()
    results['basic_stats']['duplicate_key_count'] = int(dupes) # Cast to native int
    
    # 1.2 Constraint Integrity
    # H >= L, H >= O, H >= C, L <= O, L <= C
    # Allowing small float tolerance? No, strict.
    invalid_ohlc = df[
        (df['high'] < df['low']) |
        (df['high'] < df['open']) |
        (df['high'] < df['close']) |
        (df['low'] > df['open']) |
        (df['low'] > df['close'])
    ]
    results['integrity']['ohlc_invalid_count'] = len(invalid_ohlc)
    
    # Volume Integrity
    null_vol = df['volume'].isnull().sum()
    neg_vol = (df['volume'] < 0).sum()
    results['integrity']['volume_null_count'] = int(null_vol)
    results['integrity']['volume_neg_count'] = int(neg_vol)
    
    # 1.3 Calendar Gaps (NYSE)
    start_date = df['Date'].min()
    end_date = df['Date'].max() # or now? Use data range for coverage logic inside the collected period
    
    expected_dates = []
    if HAS_MCAL:
        nyse = mcal.get_calendar('NYSE')
        schedule = nyse.schedule(start_date=start_date, end_date=end_date)
        expected_dates = mcal.date_range(schedule, frequency='1D').normalize()
        # Filter out weekends if mcal includes them? mcal usually handles valid trading days.
        # Ensure timezone naivety for comparison
        expected_dates = expected_dates.tz_localize(None)
    else:
        # Fallback: Business Days
        print("⚠️ pandas_market_calendars not found. Using BDay.")
        expected_dates = pd.date_range(start=start_date, end=end_date, freq='B')

    # Actual Dates (Normalized to Midnight)
    actual_dates = df['Date'].dt.normalize().unique()
    actual_dates = pd.Series(actual_dates).sort_values()
    
    # Find Missing
    missing = [d for d in expected_dates if d not in actual_dates]
    
    total_expected = len(expected_dates)
    coverage = (len(actual_dates) / total_expected) if total_expected > 0 else 0
    
    results['gaps']['expected_days'] = total_expected
    results['gaps']['actual_days'] = len(actual_dates)
    results['gaps']['missing_count'] = len(missing)
    results['gaps']['coverage_ratio'] = round(coverage, 4)
    results['gaps']['missing_dates'] = [d.strftime('%Y-%m-%d') for d in missing[:10]] # Top 10
    
    # Print Report
    print(json.dumps(results, indent=2))
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", type=str, default="AMZN")
    parser.add_argument("--range", type=str, default="1mo")
    args = parser.parse_args()
    
    days = 30
    if args.range == "1mo": days = 30
    elif args.range == "3mo": days = 90
    
    run_forensics(args.ticker, "1d", days)

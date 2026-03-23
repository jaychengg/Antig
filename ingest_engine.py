import streamlit as st
import pandas as pd
import requests
import time
import sqlite3
import os
from datetime import datetime, timezone

class MarketDataEngine:
    """
    Antigravity V12.0 Core Engine
    - Backend: SQLite (Incremental Storage)
    - Strategy: Fetch ONLY missing data via 'start_at'
    - Safety: Rate Limit Enforcement (Max 5 req/min safe mode)
    """
    
    def __init__(self):
        try:
            self.api_key = st.secrets["FINAZON_KEY"]
            self.dataset = st.secrets.get("FINAZON_DATASET", "us_stocks_essential")
        except:
            self.api_key = ""
            self.dataset = "us_stocks_essential"
            
        # Initialize Local DB
        self.db_path = "market_data.db"
        self._init_db()

    def _init_db(self):
        """Create table if not exists"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS prices
                     (ticker TEXT, timestamp INTEGER, open REAL, high REAL, 
                      low REAL, close REAL, volume REAL,
                      UNIQUE(ticker, timestamp) ON CONFLICT REPLACE)''')
        conn.commit()
        conn.close()

    def _get_last_timestamp(self, ticker):
        """Find the latest data point we already have"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT MAX(timestamp) FROM prices WHERE ticker=?", (ticker,))
        result = c.fetchone()[0]
        conn.close()
        return result if result else 0

    def get_price_data(self, ticker):
        """Wrapper for backward compatibility with app.py"""
        return self.sync_ticker(ticker)

    def sync_ticker(self, ticker):
        """
        Smart Sync: Only fetches what we don't have.
        Returns: DataFrame (Full History from DB)
        """
        if not self.api_key: return pd.DataFrame()

        # 1. Check what we have
        last_ts = self._get_last_timestamp(ticker)
        current_time = int(time.time())
        
        # If data is fresh (less than 12 hours old), skip API
        if (current_time - last_ts) < 43200: # 12 hours
            print(f"[{ticker}] Data is fresh. Loading from DB.")
            return self.load_from_db(ticker)

        # 2. Fetch NEW data only (Incremental)
        # Start from last_ts + 1 second
        start_at = last_ts + 1 if last_ts > 0 else 0
        
        print(f"[{ticker}] Fetching from Finazon (Start: {start_at})...")
        
        # Rate Limit Sleep (Safe Mode: 1 request every 2 seconds to stay under limits)
        time.sleep(2.0) 

        url = "https://api.finazon.io/latest/time_series"
        params = {
            "dataset": self.dataset,
            "ticker": ticker.upper(),
            "interval": "1d",
            "page_size": 1000, # Max allowed
            "start_at": start_at, 
            "apikey": self.api_key
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if "data" in data and data["data"]:
                    # 3. Save to DB
                    new_records = []
                    for d in data["data"]:
                        new_records.append((
                            ticker.upper(), d['t'], d['o'], d['h'], d['l'], d['c'], d['v']
                        ))
                    
                    conn = sqlite3.connect(self.db_path)
                    c = conn.cursor()
                    c.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?)", new_records)
                    conn.commit()
                    conn.close()
                    print(f"[{ticker}] Saved {len(new_records)} new candles.")
            elif response.status_code == 429:
                st.toast(f"⚠️ API Rate Limit Hit for {ticker}. Slowing down...")
                time.sleep(5)
            else:
                print(f"[{ticker}] API Error: {response.text}")

        except Exception as e:
            print(f"[{ticker}] Sync Error: {e}")

        # 4. Return combined data
        return self.load_from_db(ticker)

    def load_from_db(self, ticker):
        """Read full history from SQLite"""
        conn = sqlite3.connect(self.db_path)
        # Read and sort by timestamp
        df = pd.read_sql(f"SELECT * FROM prices WHERE ticker='{ticker}' ORDER BY timestamp ASC", conn)
        conn.close()
        
        if df.empty: return pd.DataFrame()

        # Processing
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        
        # Indicators
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['MA100'] = df['close'].rolling(window=100).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        return df

    def get_macro_dashboard(self):
        """
        Fetches macro proxies (USO, IEF, VIXY, UUP).
        Checks DB first to save API calls.
        """
        proxies = {
            "🛢️ WTI (USO)": "USO",
            "🏦 10Y Yield (IEF)": "IEF", # Note: Inverse to Yield
            "😨 VIX (VIXY)": "VIXY",
            "💵 DXY (UUP)": "UUP"
        }
        results = {}
        
        for label, ticker in proxies.items():
            # Reuse the sync logic (Smart Fetch)
            df = self.sync_ticker(ticker)
            if not df.empty:
                latest = df.iloc[-1]['close']
                prev = df.iloc[-2]['close'] if len(df)>1 else latest
                pct = ((latest - prev) / prev) * 100
                results[label] = (latest, pct)
            else:
                results[label] = (0.0, 0.0)
        return results

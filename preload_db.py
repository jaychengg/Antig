import sqlite3
import pandas as pd
import os
import json

class PreloadDB:
    DB_FILE = "nexus_preload.db"
    
    def __init__(self):
        self._init_db()
        
    def _init_db(self):
        conn = sqlite3.connect(self.DB_FILE)
        c = conn.cursor()
        
        # V1 Table (Legacy)
        c.execute('''CREATE TABLE IF NOT EXISTS ohlcv (
            ticker TEXT,
            interval TEXT,
            timestamp INTEGER,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (ticker, interval, timestamp)
        )''')
        
        # V2 Table (Strict Schema)
        # Adds: source, adjustment, resolution_ranking
        c.execute('''CREATE TABLE IF NOT EXISTS ohlcv_v2 (
            symbol TEXT,
            interval TEXT,
            timestamp INTEGER,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            source TEXT,
            adjustment TEXT,
            PRIMARY KEY (symbol, interval, timestamp, source, adjustment)
        )''')
        
        c.execute('CREATE INDEX IF NOT EXISTS idx_v2_ts ON ohlcv_v2 (symbol, interval, timestamp)')
        conn.commit()
        conn.close()
        
    def save_v2(self, df, source="finazon", adjustment="raw"):
        if df.empty: return
        conn = sqlite3.connect(self.DB_FILE)
        c = conn.cursor()
        
        records = []
        for _, row in df.iterrows():
            ts = int(row['Date'].timestamp())
            records.append((
                row.get('Ticker', 'UNKNOWN'), 
                "1d", # Hardcoded for now, should pass param
                ts,
                row['Open'], row['High'], row['Low'], row['Close'], row['Volume'],
                source, adjustment
            ))
            
        # Bulk Upsert
        c.executemany('''
            INSERT OR REPLACE INTO ohlcv_v2 
            (symbol, interval, timestamp, open, high, low, close, volume, source, adjustment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', records)
        conn.commit()
        conn.close()

    def get_v2(self, symbol, interval, start_ts, end_ts):
        conn = sqlite3.connect(self.DB_FILE)
        query = """
            SELECT timestamp, open, high, low, close, volume, source 
            FROM ohlcv_v2 
            WHERE symbol=? AND interval=? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
        """
        df = pd.read_sql_query(query, conn, params=[symbol, interval, start_ts, end_ts])
        conn.close()
        
        if not df.empty:
            df['Date'] = pd.to_datetime(df['timestamp'], unit='s')
            df['High'] = df['high']
            df['Low'] = df['low']
            df['Open'] = df['open']
            df['Close'] = df['close']
            df['Volume'] = df['volume']
            # Return standardized columns
            return df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'source']]
        return df

    # Legacy Support
    def save_data(self, ticker, interval, df):
        # We also save to V1 for backward compat just in case
        if df.empty: return
        conn = sqlite3.connect(self.DB_FILE)
        records = []
        for _, row in df.iterrows():
            ts = int(row['Date'].timestamp())
            records.append((ticker, interval, ts, row['Open'], row['High'], row['Low'], row['Close'], row['Volume']))
        c = conn.cursor()
        c.executemany('INSERT OR REPLACE INTO ohlcv VALUES (?,?,?,?,?,?,?,?)', records)
        conn.commit()
        conn.close()
        
        # Auto-Migrate to V2
        df_v2 = df.copy()
        df_v2['Ticker'] = ticker
        self.save_v2(df_v2, source="legacy_bridge")

    def get_data(self, ticker, interval, start_ts=None, end_ts=None):
        # Redirect to V2 if possible or fallback
        # For now, keep V1 logic to avoid breaking app.py immediately
        conn = sqlite3.connect(self.DB_FILE)
        query = "SELECT timestamp, open, high, low, close, volume FROM ohlcv WHERE ticker=? AND interval=?"
        params = [ticker, interval]
        if start_ts: query += " AND timestamp >= ?"; params.append(start_ts)
        if end_ts: query += " AND timestamp <= ?"; params.append(end_ts)
        query += " ORDER BY timestamp ASC"
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        if not df.empty:
            df['Date'] = pd.to_datetime(df['timestamp'], unit='s')
            df.columns = ['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'Date']
            return df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
        return df

preload = PreloadDB()

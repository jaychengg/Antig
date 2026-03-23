import sqlite3
import pandas as pd
import os

DB_FILE = 'market_data.db'

def inspect():
    if not os.path.exists(DB_FILE):
        print(f"❌ Database {DB_FILE} not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    print(f"🔍 Scanning {DB_FILE} for low-volume price spikes...")
    print("   Criteria: Price Change > 30% AND Volume < 5% of 20-day Average")

    try:
        # Get all tickers
        tickers = pd.read_sql("SELECT DISTINCT ticker FROM market_data", conn)['ticker'].tolist()
        glitch_list = []

        for t in tickers:
            # Fix: ORDER BY timestamp (Schema uses timestamp, not date)
            df = pd.read_sql(f"SELECT * FROM market_data WHERE ticker = '{t}' ORDER BY timestamp", conn)
            if df.empty: continue
            
            # Numeric conversion
            # Handle case difference in DB columns just in case
            df.columns = [c.capitalize() for c in df.columns] 
            
            # Fix: Ensure Date column exists from Timestamp
            if 'Timestamp' in df.columns:
                 df['Date'] = pd.to_datetime(df['Timestamp'], unit='s')
            
            df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
            df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce').fillna(0)
            
            # Calculate Indicators
            df['Prev_Close'] = df['Close'].shift(1)
            df['Pct_Change'] = (df['Close'] - df['Prev_Close']) / df['Prev_Close']
            df['Vol_MA20'] = df['Volume'].rolling(20).mean().fillna(df['Volume']) # Self-fill if too short
            
            # Avoid div by zero
            df['Vol_Ratio'] = df['Volume'] / df['Vol_MA20'].replace(0, 1)

            # --- THE USER'S LOGIC ---
            # Outlier = |Change| > 30% AND Vol_Ratio < 0.05
            mask = (df['Pct_Change'].abs() > 0.30) & (df['Vol_Ratio'] < 0.05)
            
            glitches = df[mask]
            
            if not glitches.empty:
                for idx, row in glitches.iterrows():
                    glitch_list.append({
                        'Ticker': t,
                        'Date': row['Date'],
                        'Price': f"{row['Close']:.2f}",
                        'Change': f"{row['Pct_Change']:.2%}",
                        'Volume': f"{int(row['Volume'])}",
                        'Vol_Ratio': f"{row['Vol_Ratio']:.2%}"
                    })

        # Report
        if glitch_list:
            res_df = pd.DataFrame(glitch_list)
            print("\n🚨 DETECTED CANDIDATES FOR DELETION 🚨")
            print(res_df.to_string(index=False))
            print(f"\nTotal: {len(res_df)} suspicious rows found.")
        else:
            print("\n✅ No data points matched the criteria. Your data might be clean or the threshold is too strict.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    inspect()

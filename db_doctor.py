import sqlite3
import pandas as pd
import os

DB_FILE = 'market_data.db'

def run_doctor():
    if not os.path.exists(DB_FILE):
        print("❌ No database found.")
        return

    conn = sqlite3.connect(DB_FILE)
    print(f"🏥 Boris Protocol DB Doctor - Connected to {DB_FILE}")

    while True:
        print("\nOptions:")
        print("1. Scan for Bad Data (Zeros / Spikes)")
        print("2. Purge a Ticker (Force Re-download)")
        print("3. Exit")
        
        choice = input("Select [1-3]: ").strip()
        
        if choice == '1':
            # Simple scan logic
            try:
                # Check for table existence first
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='market_data';")
                if not cursor.fetchone():
                     print("⚠️ Table 'market_data' not found. (May be using old 'prices' table?)")
                     cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                     print(f"Tables found: {[row[0] for row in cursor.fetchall()]}")
                     continue

                df = pd.read_sql("SELECT ticker, count(*) as count, min(close) as min_price FROM market_data GROUP BY ticker", conn)
                print("\n--- Health Report ---")
                print(df.to_string(index=False))
                
                # Highlight suspects
                suspects = df[df['min_price'] <= 0.01]
                if not suspects.empty:
                    print(f"\n⚠️ SUSPECT TICKERS (Price <= 0): {suspects['ticker'].tolist()}")
            except Exception as e:
                print(f"Error: {e}")

        elif choice == '2':
            t = input("Enter Ticker to PURGE (e.g., AMZN): ").upper().strip()
            if t:
                cursor = conn.cursor()
                try:
                    cursor.execute("DELETE FROM market_data WHERE ticker = ?", (t,))
                    conn.commit()
                    if cursor.rowcount > 0:
                        print(f"✅ PURGED {cursor.rowcount} rows for {t}. Restart App to re-fetch.")
                    else:
                        print(f"⚠️ No data found for {t}.")
                except Exception as e:
                    print(f"Error: {e}")
        
        elif choice == '3':
            print("Exiting.")
            break
    
    conn.close()

if __name__ == "__main__":
    run_doctor()

import sqlite3
import pandas as pd
import os

DB_PATH = 'market_data.db'

def check_db():
    print(f"Checking for database at: {os.path.abspath(DB_PATH)}")
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: Database file '{DB_PATH}' not found.")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        query = "SELECT * FROM prices LIMIT 5"
        df = pd.read_sql(query, conn)
        conn.close()

        if df.empty:
            print("⚠️ Database exists but table 'prices' is empty.")
        else:
            print("✅ Database loaded successfully.")
            print(f"Shape: {df.shape}")
            print("Columns:", df.columns.tolist())
            print("\nFirst 3 Rows:")
            print(df.head(3))
            
            # Count total rows
            conn = sqlite3.connect(DB_PATH)
            count = pd.read_sql("SELECT count(*) as total FROM prices", conn).iloc[0]['total']
            print(f"\nTotal Rows in DB: {count}")
            conn.close()

    except Exception as e:
        print(f"❌ Error reading database: {e}")

if __name__ == "__main__":
    check_db()

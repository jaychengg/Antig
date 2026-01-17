import time
import streamlit as st
import os
import toml
from ingest_engine import MarketDataEngine

# Define Target List
TARGET_TICKERS = ['AAPL', 'AMD', 'PLTR', 'META', 'TSM', 'TSLA', 'MU', 
                  'AMZN', 'LLY', 'ASTS', 'IONQ', 'RKLB', 'ALAB', 'SMR', 'LEU']

def load_secrets_manually():
    """Fallback to load secrets if Streamlit doesn't pick them up automatically"""
    try:
        if os.path.exists(".streamlit/secrets.toml"):
            with open(".streamlit/secrets.toml", "r") as f:
                return toml.load(f)
    except Exception as e:
        print(f"Error loading secrets manually: {e}")
    return {}

def main():
    print("🚀 Starting Data Preload Sequence...")
    
    # Initialize Engine
    engine = MarketDataEngine()
    
    # Verify API Key
    if not engine.api_key:
        print("⚠️ Streamlit secrets not found. Attempting manual load...")
        secrets = load_secrets_manually()
        if "FINAZON_KEY" in secrets:
            engine.api_key = secrets["FINAZON_KEY"]
            engine.dataset = secrets.get("FINAZON_DATASET", "us_stocks_essential")
            print("✅ API Key loaded manually.")
        else:
            print("❌ Critical: No API Key found in .streamlit/secrets.toml")
            return

    # Process Loop
    total = len(TARGET_TICKERS)
    print(f"🎯 Targets identified: {total}")
    
    for i, ticker in enumerate(TARGET_TICKERS, 1):
        print(f"\n[{i}/{total}] Syncing {ticker}...")
        
        try:
            # Sync Ticker (Smart Sync)
            df = engine.sync_ticker(ticker)
            
            if not df.empty:
                last_date = df.iloc[-1]['timestamp'].date()
                print(f"   ✅ {ticker}: Sync Complete. Records: {len(df)}. Latest: {last_date}")
            else:
                print(f"   ⚠️ {ticker}: No data returned.")
                
        except Exception as e:
            print(f"   ❌ {ticker}: Failed ({str(e)})")
            
        # Rate Limit Safety
        time.sleep(1.0)

    print("\n🏁 Preload Sequence Complete.")

if __name__ == "__main__":
    main()

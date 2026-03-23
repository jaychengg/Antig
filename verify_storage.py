
import storage
import time
import sys

def main():
    print("🧪 Verifying Cloud SQL Storage Layer...")
    
    # 1. Connection Check
    status, msg = storage.check_db_status()
    print(f"🔌 Connection Status: {status} ({msg})")
    
    if not status:
        print("❌ DB Connection Failed. Please check .streamlit/secrets.toml")
        sys.exit(1)
        
    user_id = "local"
    ticker = "TEST_TICKER"
    
    # 2. Add Trade
    print("📝 Adding Test Trade...")
    try:
        trade = {
            "user_id": user_id,
            "ticker": ticker,
            "datetime": "2024-01-01 12:00:00+00",
            "action": "BUY",
            "shares": 10,
            "price": 150.0,
            "fee": 5.0,
            "note": "Verify Script Test"
        }
        storage.add_trade(trade)
        print("✅ Trade Added.")
    except Exception as e:
        print(f"❌ Failed to Add Trade: {e}")
        sys.exit(1)
        
    # 3. Read Trade
    print("📖 Reading Trades...")
    trades = storage.list_trades(user_id, ticker)
    if len(trades) > 0:
        print(f"✅ Found {len(trades)} trades for {ticker}")
        print(trades[0])
    else:
        print("❌ No trades found (Insert failed?)")
        sys.exit(1)
        
    # 4. Cleanup
    print("🗑️ Cleaning up...")
    try:
        storage.delete_trade(trades[0]['id'], user_id)
        print("✅ Cleanup complete.")
    except Exception as e:
        print(f"⚠️ Cleanup failed: {e}")
        
    print("\n🎉 ALL CHECKS PASSED. Storage Layer is Ready.")

if __name__ == "__main__":
    main()

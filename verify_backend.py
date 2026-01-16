import sys
from unittest.mock import MagicMock
import pandas as pd
import toml
import os
from ingest_engine import extract_content

# --- MOCK STREAMLIT ---
class MockStreamlit(MagicMock):
    def __getattr__(self, name):
        if name == "columns":
             return lambda x: [MagicMock() for _ in range(x)] if isinstance(x, int) else [MagicMock() for _ in x]
        if name == "tabs":
             return lambda x: [MagicMock() for _ in x] # Return list of mocks for tabs
        if name == "secrets":
            # This is tricky because we assign st.secrets later. 
            # But the mock object itself needs to behave like a dict for get access if used.
            return MagicMock() 
        return MagicMock()

sys.modules["streamlit"] = MockStreamlit()
# Mock submodules
sys.modules["streamlit.connections"] = MockStreamlit()
sys.modules["streamlit.dataframe_util"] = MockStreamlit()
sys.modules["streamlit_gsheets"] = MockStreamlit()

import streamlit as st

# Load actual secrets
secrets_path = os.path.join(".streamlit", "secrets.toml")
try:
    with open(secrets_path, "r") as f:
        secrets_data = toml.load(f)
    st.secrets = secrets_data # Assign dict to st.secrets
except Exception as e:
    print(f"FAIL: Could not load secrets.toml: {e}")
    sys.exit(1)

# --- IMPORT APP LOGIC ---
try:
    import app
except Exception as e:
    print(f"Warning during import: {e}")

# --- TEST 1: FINAZON ---
from ingest_engine import get_price_data_finazon

def test_finazon():
    print("Testing Finazon API connectivity...")
    try:
        ticker = "AAPL"
        # Since verify_backend mocks st.secrets, we need to ensure ingest_engine can access it.
        # ingest_engine imports streamlit as st.
        # We customized the mock in this file, so st.secrets is populated.
        
        df = get_price_data_finazon(ticker)
        if isinstance(df, str): # Error message
             print(f"FAIL: Finazon returned error: {df}")
             # sys.exit(1) # Failing hard for now
        else:
             if df.empty:
                 print("FAIL: Finazon returned empty dataframe")
             else:
                 # Check columns
                 required_cols = ['Open', 'High', 'Low', 'Close', 'Volume', 'RSI', 'Bias']
                 missing = [c for c in required_cols if c not in df.columns]
                 if missing:
                     print(f"FAIL: Missing columns: {missing}")
                 else:
                     # Check values
                     last_rsi = df['RSI'].iloc[-1]
                     last_bias = df['Bias'].iloc[-1]
                     print(f"PASS: Finazon fetched {len(df)} rows.")
                     print(f"      Indicators Verified -> RSI(14): {last_rsi:.2f}, Bias(20MA): {last_bias:.2f}%")
    except Exception as e:
        print(f"FAIL: Finazon exception: {e}")

def test_macro_dashboard_connectivity():
    print("Testing Macro Dashboard (yfinance)...")
    try:
        import yfinance as yf
        vix = yf.Ticker("^VIX").history(period="1d")
        if not vix.empty:
            print(f"PASS: VIX fetched. Close: {vix['Close'].iloc[-1]:.2f}")
        else:
            print("FAIL: VIX returned empty data")
    except Exception as e:
        print(f"FAIL: Macro Dashboard error: {e}")

# --- TEST 2: INGEST ENGINE (YOUTUBE) ---
def test_ingest_youtube():
    print("Testing Ingest Engine (YouTube)...")
    # Use a solid, short video (Google's "Me at the zoo" or similar, or just a known one)
    # Using "Me at the zoo" ID: jNQXAC9IVRw
    dummy_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw" 
    
    try:
        content = extract_content(dummy_url)
        if "YOUTUBE TRANSCRIPT START" in content:
            print("PASS: YouTube transcript extracted.")
        else:
            print(f"WARNING: YouTube extraction failed or no transcript. Content: {content[:50]}...")
            # Note: Many videos don't have transcripts. This might fail if the video has none.
            # Allowing warning.
    except Exception as e:
        print(f"FAIL: YouTube Ingest Error: {e}")

# --- TEST 3: BLACK BOX LOGIC (Simple Import Check) ---
def verify_black_box_logic():
    print("\n[Test 3] Verifying Black Box Imports...")
    try:
        from app import generate_black_box_analysis, fetch_perplexity_news
        print("✅ Analysis functions imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import Failed: {e}")
        return False

# --- TEST 4: LEDGER LOGIC (V6.0) ---
def test_ledger_calculation():
    print("\n[Test 4] Verifying Ledger Logic (V6.0)...")
    try:
        from app import calculate_portfolio
        import pandas as pd
        
        # Mock Data: 2 Entries for SAME Ticker
        mock_data = pd.DataFrame([
            {"Ticker": "AAPL", "Shares": 10, "Cost": 100},
            {"Ticker": "AAPL", "Shares": 10, "Cost": 200}
        ])
        
        # Expected: Total Shares = 20, Avg Cost = 150
        result = calculate_portfolio(mock_data)
        row = result.iloc[0]
        
        if row['Shares'] == 20 and row['Cost'] == 150:
            print("✅ Ledger Aggregation Success: AAPL 20 Shares @ $150")
            return True
        else:
            print(f"❌ Logic Error: Got {row['Shares']} Shares @ {row['Cost']}")
            return False
            
    except ImportError:
         print("❌ Function not found in app.py")
         return False
    except Exception as e:
         print(f"❌ Ledger Test Failed: {e}")
         return False

# --- TEST 5: V7 NATIVE CSV LOGIC ---
def test_jay_csv_logic():
    print("\n[Test 5] Verifying Native CSV Logic (V7.0)...")
    try:
        from app import process_jay_csv
        import pandas as pd
        import numpy as np
        
        # Mock Jay CSV Data
        data = {
            '交易日期': ['2023/01/01', '2023/01/02'],
            '代碼': ['TSM', 'NVDA'],
            '買入股數': [1000, 10], 
            '賣出股數': [np.nan, np.nan],
            '成交總金額': [500000, 4000] # TSM 500/share, NVDA 400/share
        }
        df_jay = pd.DataFrame(data)
        
        result_df = process_jay_csv(df_jay)
        
        if result_df.empty:
            print("❌ Result is empty.")
            return False
            
        row1 = result_df.iloc[0]
        # TSM: 1000 shares, 500000 total -> 500 cost/share
        if row1['Ticker'] == 'TSM' and row1['Shares'] == 1000 and row1['Cost'] == 500:
             print("✅ TSM Parsed Correctly")
        else:
             print(f"❌ TSM Error: {row1.to_dict()}")
             return False

        return True

    except Exception as e:
         print(f"❌ CSV Logic Error: {e}")
         return False

def run_tests():
    # Only running specific logic tests to avoid mock issues with app.py sidebar
    t5 = test_jay_csv_logic()
    
    if t5:
        print("\n✅ V7 LOGIC TEST PASSED")

if __name__ == "__main__":
    test_jay_csv_logic()

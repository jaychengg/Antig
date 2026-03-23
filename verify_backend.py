import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import sys
import os
import io

# --- Mock Streamlit Setup ---
# We must mock streamlit before importing app modules that use it
class MockStreamlit:
    def error(self, msg):
        print(f"❌ STREAMLIT ERROR: {msg}")
    def warning(self, msg):
        print(f"⚠️ STREAMLIT WARNING: {msg}")
    def info(self, msg):
        print(f"ℹ️ STREAMLIT INFO: {msg}")
    def cache_data(self, ttl=None):
        def decorator(func):
            return func
        return decorator
    @property
    def secrets(self):
        # returns a dummy dict acting as secrets
        return {"FINAZON_API_KEY": "dummy_key_for_testing"}

sys.modules["streamlit"] = MockStreamlit()

# Attempt to import the engine
try:
    import ingest_engine
    print("✅ Successfully imported ingest_engine")
except ImportError as e:
    print(f"❌ BROKEN: Could not import ingest_engine: {e}")
    sys.exit(1)

class TestBackendLogic(unittest.TestCase):
    
    def test_01_load_portfolio_chinese(self):
        print("\n[Test 1] Verifying Chinese CSV Format Loading...")
        csv_content = """代碼 (Ticker),買入股數 (Shares),平均成本,賣出股數(Shares),成交總金額 (Total Cost)
AAPL,10,150,0,1500
TSLA,5,200,0,1000
"""
        file_buffer = io.StringIO(csv_content)
        df = ingest_engine.load_portfolio(file_buffer)
        
        if df.empty:
            self.fail("❌ Portfolio is empty for valid Chinese CSV")
        
        row = df[df["Ticker"] == "AAPL"].iloc[0]
        self.assertEqual(row["Net Shares"], 10)
        print("✅ Chinese CSV format parsed correctly")

    def test_02_load_portfolio_english(self):
        print("\n[Test 2] Verifying English CSV Format Loading...")
        csv_content = """Ticker,Shares,Price
NVDA,10,400
MSFT,20,300
"""
        file_buffer = io.StringIO(csv_content)
        df = ingest_engine.load_portfolio(file_buffer)
        
        if df.empty:
            self.fail("❌ Portfolio is empty for valid English CSV")
            
        row = df[df["Ticker"] == "NVDA"].iloc[0]
        self.assertEqual(row["Net Shares"], 10)
        print("✅ English CSV format parsed correctly")

    def test_03_finazon_api_structure(self):
        print("\n[Test 3] Verifying Finazon API Data Handling (Mocked)...")
        with patch('ingest_engine.requests.get') as mock_get:
            mock_response = MagicMock()
            # Mocking a valid Finazon response structure
            mock_response.json.return_value = {
                "data": [
                    {"t": 1672531200, "o": 100, "h": 110, "l": 90, "c": 105, "v": 10000},
                    {"t": 1672617600, "o": 105, "h": 115, "l": 100, "c": 110, "v": 12000}
                ]
            }
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            df = ingest_engine.get_price_data_finazon("AAPL")
            self.assertFalse(df.empty)
            self.assertIn("Close", df.columns)
            print("✅ Finazon data structure handled correctly")

    def test_04_market_data_engine(self):
        print("\n[Test 4] Verifying MarketDataEngine Class (V11.3)...")
        from ingest_engine import MarketDataEngine
        engine = MarketDataEngine()
        
        with patch('ingest_engine.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            # V11.3 expects lowercase keys from 't', 'o', etc.
            mock_response.json.return_value = {
                "data": [
                    {"t": 1672531200, "o": 100, "h": 110, "l": 90, "c": 105, "v": 10000},
                    {"t": 1672617600, "o": 105, "h": 115, "l": 100, "c": 110, "v": 12000}
                ]
            }
            mock_get.return_value = mock_response
            
            df = engine.get_price_data("AAPL")
            
            self.assertFalse(df.empty)
            self.assertIn("timestamp", df.columns)
            self.assertIn("close", df.columns)
            self.assertIn("MA20", df.columns)
            self.assertIn("RSI", df.columns)
            print("✅ MarketDataEngine columns & indicators verified")

if __name__ == '__main__':
    unittest.main()

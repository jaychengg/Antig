import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import sys
import io

# Mock streamlit before importing ingest_engine
class MockStreamlit:
    def error(self, msg):
        print(f"ST ERROR: {msg}")
    def warning(self, msg):
        print(f"ST WARNING: {msg}")
    def cache_data(self, ttl=None):
        def decorator(func):
            return func
        return decorator
    @property
    def secrets(self):
        return {"FINAZON_API_KEY": "dummy_key"}

sys.modules["streamlit"] = MockStreamlit()
import ingest_engine

class TestV11(unittest.TestCase):
    def test_load_portfolio_chinese_format(self):
        csv_content = """代碼 (Ticker),買入股數 (Shares),平均成本,賣出股數(Shares),成交總金額 (Total Cost)
AAPL,10,150,0,1500
TSLA,5,200,0,1000
"""
        file_buffer = io.StringIO(csv_content)
        df = ingest_engine.load_portfolio(file_buffer)
        
        self.assertFalse(df.empty, "Portfolio should not be empty for valid Chinese CSV")
        self.assertEqual(len(df), 2)
        self.assertIn("AAPL", df["Ticker"].values)
        self.assertIn("TSLA", df["Ticker"].values)
        # Check calculations
        aapl = df[df["Ticker"] == "AAPL"].iloc[0]
        self.assertEqual(aapl["Net Shares"], 10)
        self.assertEqual(aapl["Avg Cost"], 150.0)

    def test_load_portfolio_english_format(self):
        csv_content = """Ticker,Shares,Price
NVDA,10,400
MSFT,20,300
"""
        file_buffer = io.StringIO(csv_content)
        df = ingest_engine.load_portfolio(file_buffer)
        
        self.assertFalse(df.empty, "Portfolio should not be empty for valid English CSV")
        self.assertEqual(len(df), 2)
        
        nvda = df[df["Ticker"] == "NVDA"].iloc[0]
        self.assertEqual(nvda["Net Shares"], 10)
        self.assertEqual(nvda["Avg Cost"], 400.0)

    def test_load_portfolio_invalid(self):
        csv_content = """Invalid,Column,Names
1,2,3
"""
        file_buffer = io.StringIO(csv_content)
        df = ingest_engine.load_portfolio(file_buffer)
        self.assertTrue(df.empty, "Portfolio should be empty for invalid CSV")

    @patch('ingest_engine.requests.get')
    def test_get_price_data_finazon(self, mock_get):
        # Mock successful response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"t": 1672531200, "o": 100, "h": 110, "l": 90, "c": 105, "v": 10000},
                {"t": 1672617600, "o": 105, "h": 115, "l": 100, "c": 110, "v": 12000}
            ]
        }
        mock_get.return_value = mock_response
        
        df = ingest_engine.get_price_data_finazon("AAPL")
        self.assertFalse(df.empty)
        self.assertIn("Close", df.columns)
        self.assertEqual(len(df), 2)

    @patch('ingest_engine.requests.get')
    def test_get_latest_price_batch(self, mock_get):
        # Mock successful response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"t": 1672617600, "c": 150.5}]
        }
        mock_get.return_value = mock_response
        
        prices = ingest_engine.get_latest_price_batch(["AAPL"])
        self.assertEqual(prices["AAPL"], 150.5)

if __name__ == '__main__':
    unittest.main()

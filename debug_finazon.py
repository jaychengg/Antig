import requests
import sys

API_KEY = "3c2f09a744fa401f8ebb384ff3e69cff4d"
TICKER = "AAPL"

def test_dataset(dataset):
    print(f"Testing dataset: {dataset}...")
    url = f"https://api.finazon.io/latest/time_series"
    params = {
        "dataset": dataset,
        "ticker": TICKER,
        "interval": "1d",
        "apikey": API_KEY,
        "page_size": 1
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            print(f"✅ SUCCESS! Dataset '{dataset}' works.")
            print(f"Response: {response.json()}")
            return True
        else:
            print(f"❌ FAIL: {dataset} -> {response.status_code} ({response.text})")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    datasets_to_try = [
        "us_stocks_essential",
        "us_stocks_sip", 
        "us_stocks_daily_sip",
        "sip_non_pro",
        "us_equities_basic"
    ]
    
    for ds in datasets_to_try:
        if test_dataset(ds):
            break

if __name__ == "__main__":
    main()

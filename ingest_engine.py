import re
import requests
import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from PyPDF2 import PdfReader

# --- HELPER: PERPLEXITY BACKEND ---
def _perplexity_backend_summary(url):
    """
    Uses internal Perplexity API to summarize a URL if direct scraping fails.
    Relies on st.secrets for the key (loaded in app.py, but we can access via st.secrets here if initialized).
    """
    try:
        api_key = st.secrets["PERPLEXITY_API_KEY"]
        endpoint = "https://api.perplexity.ai/chat/completions"
        payload = {
            "model": "sonar-pro",
            "messages": [
                {
                    "role": "system", 
                    "content": "Summarize this URL content for financial analysis. Focus on facts, numbers, and market implications. Output must be in Traditional Chinese (繁體中文)."
                },
                {
                    "role": "user", 
                    "content": f"Summarize: {url}"
                }
            ]
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        response = requests.post(endpoint, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Perplexity Summary Failed: {e}"

# --- CORE EXTRACTION LOGIC ---
def extract_content(source):
    """
    Universal Content Extractor.
    Args:
        source: Can be a URL string, a YouTube link string, an UploadedFile (PDF), or raw text.
    Returns:
        String containing the extracted text content.
    """
    # 1. Handle None/Empty
    if not source:
        return ""

    # 2. Handle Streamlit UploadedFile (PDF)
    if hasattr(source, "read") and hasattr(source, "type"):
        if source.type == "application/pdf":
            try:
                reader = PdfReader(source)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return f"--- PDF CONTENT START ---\n{text}\n--- PDF CONTENT END ---"
            except Exception as e:
                return f"Error reading PDF: {e}"
        else:
             # Fallback for text files
             return str(source.read(), "utf-8")

    # 3. Handle Strings (URLs, YouTube, Text)
    source_str = str(source).strip()
    
    # YouTube
    if "youtube.com" in source_str or "youtu.be" in source_str:
        try:
            video_id = ""
            if "v=" in source_str:
                video_id = source_str.split("v=")[1].split("&")[0]
            elif "youtu.be/" in source_str:
                video_id = source_str.split("youtu.be/")[1].split("?")[0]
            
            if video_id:
                transcript = YouTubeTranscriptApi.get_transcript(video_id)
                text = " ".join([t['text'] for t in transcript])
                return f"--- YOUTUBE TRANSCRIPT START ---\n{text}\n--- YOUTUBE TRANSCRIPT END ---"
        except Exception as e:
            return f"Error fetching YouTube transcript: {e}"

    # General URL (Article) -> Perplexity Summary
    if source_str.startswith("http://") or source_str.startswith("https://"):
        return f"--- WEB SUMMARY (Source: {source_str}) ---\n{_perplexity_backend_summary(source_str)}"

    # Raw Text
    return source_str

# --- FINAZON DATA FEED ---
import pandas as pd
import pandas_ta as ta
import time

def get_price_data_finazon(ticker):
    """
    Fetches daily OHLCV data from Finazon.
    Returns a DataFrame with DateTime index and standard columns: Open, High, Low, Close, Volume.
    Also calculates RSI (14) and Bias (MA20).
    """
    try:
        api_key = st.secrets["FINAZON_API_KEY"]
        
        # Determine dataset (Crypto vs Stocks)
        dataset = "us_stocks_essential"
        if "-" in ticker and "USD" in ticker: 
             dataset = "crypto_daily" # Basic override if needed later
             
        url = f"https://api.finazon.io/latest/time_series"
        params = {
            "dataset": dataset,
            "ticker": ticker.upper(),
            "interval": "1d",
            "apikey": api_key,
            "page_size": 180 # Approx 6 months
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                df = pd.DataFrame(data["data"])
                
                # Rename columns
                rename_map = {'t': 'Date', 'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume'}
                df.rename(columns=rename_map, inplace=True)
                
                # Convert Date
                df['Date'] = pd.to_datetime(df['Date'], unit='s')
                df.set_index('Date', inplace=True)
                df.sort_index(inplace=True)
                
                # --- V3.0 INDICATORS ---
                # RSI (14)
                df['RSI'] = ta.rsi(df['Close'], length=14)
                
                # Bias (20MA) = (Close - MA20) / MA20 * 100
                ma20 = ta.sma(df['Close'], length=20)
                df['MA20'] = ma20 # Store MA20 for plotting
                df['Bias'] = ((df['Close'] - ma20) / ma20) * 100
                
                # MA100 for Charting
                df['MA100'] = ta.sma(df['Close'], length=100)
                
                return df
            else:
                 return f"Finazon Error: No data found for {ticker}"
        else:
            return f"Finazon API Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        return f"Finazon Connection Failed: {e}"

# --- V10.0 SMART PARSER ---
def process_smart_upload(df):
    """
    V10.0 Smart Parser: Auto-detects schema and normalizes to Ledger format.
    Target: ['Ticker', 'Shares', 'Cost']
    """
    # 1. Detect Schema
    cols = df.columns.tolist()
    
    # Schema B (Chinese / Jay)
    if '代碼' in cols and '交易日期' in cols:
        return process_jay_csv_logic(df)
        
    # Schema A (Standard English)
    elif 'Ticker' in cols and 'Shares' in cols:
        return process_standard_csv_logic(df)
        
    else:
        st.error("Unknown CSV Format. Expected 'Ticker/Shares' or '代碼/交易日期'")
        return pd.DataFrame(columns=['Ticker', 'Shares', 'Cost'])

def process_jay_csv_logic(df):
    """Parses Jay Investments Chinese format."""
    processed = []
    # Map: 代碼->Ticker, 買入股數->Buy, 賣出股數->Sell, 成交總金額->TotalCost
    for _, row in df.iterrows():
        try:
            ticker = str(row['代碼']).strip().upper()
            buy = float(row['買入股數']) if pd.notna(row['買入股數']) else 0
            sell = float(row['賣出股數']) if pd.notna(row['賣出股數']) else 0
            cost_total = float(row['成交總金額']) if pd.notna(row['成交總金額']) else 0
            
            # Logic: Add Buy row, Add Sell row (negative)
            if buy > 0:
                cost_per = cost_total / buy
                processed.append({'Ticker': ticker, 'Shares': buy, 'Cost': cost_per})
            if sell > 0:
                processed.append({'Ticker': ticker, 'Shares': -sell, 'Cost': 0}) # Sell acts as reduction
        except:
            continue
    return pd.DataFrame(processed)

def process_standard_csv_logic(df):
    """Parses Text001 English format."""
    # Ensure columns exist
    needed = ['Ticker', 'Shares', 'Cost']
    cols = df.columns.tolist()
    
    # Allow partial if Price exists instead of Cost
    if 'Price' in cols and 'Cost' not in cols:
        df['Cost'] = df['Price']
    
    # Return standard columns
    # Handle missing columns gracefully
    final_cols = [c for c in needed if c in df.columns]
    return df[final_cols].dropna()

# --- V10.0 SNAPSHOT API ---
@st.cache_data(ttl=600, show_spinner=False)
def get_finazon_snapshot(ticker):
    """
    V10.0 Lightweight Snapshot.
    Fetches ONLY the latest price. Cached for 10 minutes.
    """
    if 'finazon_key' not in st.secrets:
        return {'price': 0.0}

    api_key = st.secrets['finazon_key']
    url = "https://api.finazon.io/latest/time_series"
    
    # Lightweight call: 1 minute interval, 1 row
    params = {
        "ticker": ticker,
        "dataset": "us_stocks_essential",
        "interval": "1d", 
        "page_size": 1, 
        "apikey": api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and len(data['data']) > 0:
                last_row = data['data'][0]
                return {'price': last_row['c']}
    except:
        pass
    return {'price': 0.0}

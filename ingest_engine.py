import pandas as pd
import requests
import streamlit as st
from datetime import datetime, timedelta
import pandas_ta as ta
import re
from youtube_transcript_api import YouTubeTranscriptApi
from PyPDF2 import PdfReader

# --- HELPER: PERPLEXITY BACKEND ---
def _perplexity_backend_summary(url):
    """
    Uses internal Perplexity API to summarize a URL if direct scraping fails.
    Relies on st.secrets for the key.
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

# --- V11.0 SMART PARSER ---
def load_portfolio(source):
    """
    V11.0 Smart Parser:
    - Automatically detects if the uploaded CSV/DataFrame is 'Simple English' or 'Jay's Chinese Format'.
    - Normalizes everything into standard columns: ['Ticker', 'Shares', 'Cost'].
    """
    try:
        # Support both file buffer and DataFrame
        if isinstance(source, pd.DataFrame):
            df = source
        else:
            df = pd.read_csv(source)
            
        cols = df.columns.tolist()

        # ---------------------------
        # 模式 A: Jay's Chinese Format (Jay Investments - Record.csv)
        # ---------------------------
        if "代碼 (Ticker)" in cols or "代碼" in cols:
            # 1. Map Columns
            rename_map = {
                "代碼 (Ticker)": "Ticker",
                "代碼": "Ticker",
                "買入股數 (Shares)": "Buys",
                "賣出股數(Shares)": "Sells",
                "賣出股數 (Shares)": "Sells", # Handle slight variation
                "成交總金額 (Total Cost)": "Total Cost"
            }
            df = df.rename(columns=rename_map)
            
            # 2. Clean Data
            df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
            df['Buys'] = pd.to_numeric(df['Buys'], errors='coerce').fillna(0)
            df['Sells'] = pd.to_numeric(df['Sells'], errors='coerce').fillna(0)
            df['Total Cost'] = pd.to_numeric(df['Total Cost'], errors='coerce').fillna(0)

            # 3. Calculate Net Position (Group by Ticker)
            # We need to aggregate all rows for the same ticker
            portfolio = df.groupby('Ticker').agg({
                'Buys': 'sum',
                'Sells': 'sum',
                'Total Cost': 'sum'
            }).reset_index()

            portfolio['Net Shares'] = portfolio['Buys'] - portfolio['Sells']
            # Avoid division by zero
            portfolio['Avg Cost'] = portfolio.apply(
                lambda x: x['Total Cost'] / x['Buys'] if x['Buys'] > 0 else 0, axis=1
            )
            
            # Filter out closed positions or empty tickers
            portfolio = portfolio[portfolio['Net Shares'] > 0]
            portfolio = portfolio[portfolio['Ticker'] != 'NAN']
            
            # Normalize to App Standard: ['Ticker', 'Shares', 'Cost']
            portfolio = portfolio.rename(columns={'Net Shares': 'Shares', 'Avg Cost': 'Cost'})
            return portfolio[['Ticker', 'Shares', 'Cost']]

        # ---------------------------
        # 模式 B: Simple English Format (test001.csv)
        # ---------------------------
        elif "Ticker" in cols and "Price" in cols:
            # 1. Clean Data
            df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
            df['Shares'] = pd.to_numeric(df['Shares'], errors='coerce').fillna(0)
            df['Price'] = pd.to_numeric(df['Price'], errors='coerce').fillna(0)
            
            # 2. Calculate Cost (Assuming Price in CSV is the Buy Price)
            df['Cost Basis'] = df['Shares'] * df['Price']
            
            # 3. Aggregate
            portfolio = df.groupby('Ticker').agg({
                'Shares': 'sum',
                'Cost Basis': 'sum'
            }).reset_index()
            
            portfolio.rename(columns={'Shares': 'Net Shares'}, inplace=True)
            portfolio['Avg Cost'] = portfolio['Cost Basis'] / portfolio['Net Shares']
            
            # Normalize to App Standard
            portfolio = portfolio.rename(columns={'Net Shares': 'Shares', 'Avg Cost': 'Cost'})
            return portfolio[['Ticker', 'Shares', 'Cost']]

        elif "Ticker" in cols and "Shares" in cols and "Cost" in cols:
            # Already in standard format
             return df[['Ticker', 'Shares', 'Cost']]

        else:
            st.error(f"⚠️ 無法識別 CSV 格式。偵測到的欄位: {cols}")
            return pd.DataFrame()

    except Exception as e:
        st.error(f"讀取檔案失敗: {str(e)}")
        return pd.DataFrame()

# --- FINAZON DATA FEED (V11 + INDICATORS) ---
@st.cache_data(ttl=3600)
def get_price_data_finazon(ticker, start_date=None):
    """
    Fetches historical OHLCV data from Finazon.
    Cached for 1 hour.
    Includes technical indicators: RSI(14), Bias(20MA), MA100.
    """
    try:
        api_key = st.secrets["FINAZON_API_KEY"]
        if not start_date:
            # Default to 2 years ago for valid 100MA/200MA
            start_date = int((datetime.now() - timedelta(days=730)).timestamp())
        
        # Determine dataset (Crypto vs Stocks)
        dataset = "us_stocks_daily"
        if "-" in ticker and "USD" in ticker: 
             dataset = "crypto_daily"

        url = "https://api.finazon.io/latest/time_series"
        params = {
            "ticker": ticker.upper(),
            "dataset": dataset,
            "start_at": start_date,
            "apikey": api_key
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'data' not in data:
            return f"Finazon Error: No data found for {ticker}"
            
        df = pd.DataFrame(data['data'])
        # Rename V11 standard
        df = df.rename(columns={
            "t": "Date", "o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"
        })
        
        # Convert Date
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], unit='s')
            df.set_index("Date", inplace=True)
            df.sort_index(inplace=True)
        
        # --- TECHNICAL INDICATORS (RESTORED) ---
        # RSI (14)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        # Bias (20MA) = (Close - MA20) / MA20 * 100
        ma20 = ta.sma(df['Close'], length=20)
        df['MA20'] = ma20 
        df['Bias'] = ((df['Close'] - ma20) / ma20) * 100
        
        # MA100
        df['MA100'] = ta.sma(df['Close'], length=100)
        
        return df

    except Exception as e:
        st.warning(f"Finazon API Error for {ticker}: {e}")
        return f"Error: {e}"

def get_latest_price_batch(tickers):
    """
    V11.0 Feature: Lightweight Snapshot
    Uses Finazon 'snapshot' endpoint to get ONLY the latest price.
    Returns dictionary: {ticker: price}
    """
    updates = {}
    if not tickers:
        return updates
        
    api_key = st.secrets["FINAZON_API_KEY"]
    
    dataset = "us_stocks_daily"
    url = "https://api.finazon.io/latest/time_series"
    
    for t in tickers:
        try:
            # Check for crypto
            this_dataset = "crypto_daily" if "-" in t and "USD" in t else dataset
            
            # Fetch only extremely recent to be fast
            start_at = int((datetime.now() - timedelta(days=5)).timestamp())
            params = {
                "ticker": t.upper(), 
                "dataset": this_dataset, 
                "start_at": start_at, 
                "apikey": api_key,
                "page_size": 1 # Just get last candle
            }
            
            res = requests.get(url, params=params, timeout=3).json()
            if 'data' in res and len(res['data']) > 0:
                last_row = res['data'][-1]
                updates[t] = last_row['c']
            else:
                updates[t] = 0.0
        except:
            updates[t] = 0.0
            
    return updates

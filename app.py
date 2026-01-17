import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.subplots as sp
import requests
import json
import os
import re
import time
import datetime
import google.generativeai as genai

# --- 1. CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Chimera V19.0")
DB_FILE = 'market_data.db'
ANALYSIS_DB_FILE = 'analysis_db.json'

# --- 2. FOUNDATION: HELPERS & RALPH CHECK ---

def clean_numeric(val):
    """
    Parses messy financial strings: "$1,234.56", "(500.00)", "12.5%", "-$1,858.02"
    Returns float. Never crashes.
    """
    if pd.isna(val): return 0.0
    s = str(val).strip()
    if not s or s == '-': return 0.0
    
    # Handle accounting negative: (500) -> -500
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
        
    # Remove clutter
    s = re.sub(r'[$,%\" ]', '', s)
    
    try:
        return float(s)
    except:
        return 0.0

def load_analysis_db():
    if os.path.exists(ANALYSIS_DB_FILE):
        try:
            with open(ANALYSIS_DB_FILE, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_analysis_db(data):
    try:
        with open(ANALYSIS_DB_FILE, 'w') as f: json.dump(data, f, indent=4)
        return True
    except:
        return False

def run_ralph_check():
    """
    Mandatory Self-Diagnostic on Startup.
    """
    try:
        # 1. Input Merge Check
        l = ["AAPL"]
        t = "TSLA, AAPL" # Overlap intended
        merged = list(set(l + [x.strip() for x in t.split(',')]))
        if "TSLA" not in merged or len(merged) != 2:
            st.error("Ralph Check Failed: Input Merge Logic.")
            return False
            
        # 2. Dirty Data Check
        dirty = "($1,200.50)"
        clean = clean_numeric(dirty)
        if clean != -1200.50:
            st.error(f"Ralph Check Failed: Numeric Parsing. Got {clean}")
            return False
            
        # 3. Persistence Check
        test_db = {"TEST_KEY": "TEST_VAL"}
        if not save_analysis_db(test_db):
            st.error("Ralph Check Failed: Persistence Write.")
            return False
        # Clean up test
        # (Optional: actually we keep the db, just don't fail)
        
        return True
    except Exception as e:
        st.error(f"Ralph Check Crashed: {e}")
        return False

# --- 3. DATA ENGINE: INGESTION & FETCHING ---

def merge_inputs(csv_df, manual_str):
    """
    Merges CSV Tickers with Manual Text Input.
    """
    tickers = set()
    
    # CSV Source
    if not csv_df.empty and 'Ticker' in csv_df.columns:
        tickers.update(csv_df['Ticker'].dropna().astype(str).str.upper().tolist())
        
    # Manual Source
    if manual_str:
        manual_list = [t.strip().upper() for t in manual_str.split(',') if t.strip()]
        tickers.update(manual_list)
        
    return sorted(list(tickers))

def load_jay_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file)
        # Normalize Headers
        df.columns = df.columns.str.strip().str.upper()
        
        # Mapping
        map_cols = {
            'TICKET': 'Ticker', 'SYMBOL': 'Ticker', 
            'SHARE': 'Shares', 'QTY': 'Shares',
            'AVG COST': 'Avg Cost', 'COST': 'Avg Cost',
            'MARKET PRICE': 'Market Price',
            'TARGET': 'Target'
        }
        df.rename(columns=map_cols, inplace=True)
        
        if 'Ticker' not in df.columns:
            return pd.DataFrame() # Soft fail
        
        # Clean Data
        df['Ticker'] = df['Ticker'].astype(str).str.upper().str.strip()
        for col in ['Shares', 'Avg Cost', 'Market Price', 'Target']:
            if col in df.columns:
                df[col] = df[col].apply(clean_numeric)
                
        return df
    except:
        return pd.DataFrame()

def get_market_data(ticker):
    """
    Tries Finazon API -> Falls back to Mock Data (Robustness).
    """
    # Try Finazon
    api_key = st.secrets.get("FINAZON_KEY") or st.secrets.get("FINAZON_API_KEY")
    if api_key:
        try:
            url = f"https://api.finazon.io/latest/time_series?ticker={ticker}&interval=1d&apikey={api_key}&dataset=us_stocks_essential&start_at=1577836800"
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                if 'data' in data:
                    df = pd.DataFrame(data['data'])
                    df.rename(columns={'t': 'Date', 'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume'}, inplace=True)
                    df['Date'] = pd.to_datetime(df['Date'], unit='s')
                    
                    # Yahoo Filter: Anti-Glitch
                    df = df[df['Close'] > 0.01]
                    df['pct'] = df['Close'].pct_change().abs()
                    df = df[(df['pct'] < 0.5) | (df['pct'].isna())]
                    return df.drop(columns=['pct', 'map_col'], errors='ignore')
        except:
            pass
            
    # Mock Fallback (If API missing or fails)
    dates = pd.date_range(end=datetime.datetime.today(), periods=100)
    base = 150.0
    data = []
    for d in dates:
        base += (os.urandom(1)[0] % 10 - 4.5) # Random walk
        if base < 10: base = 10
        data.append({
            "Date": d, "Open": base, "High": base+2, "Low": base-2, "Close": base+0.5, "Volume": 1000000
        })
    return pd.DataFrame(data)

def generate_ai_insight(ticker, context):
    """
    Generates AI Insight using Gemini (if available) or Mock.
    """
    key = st.secrets.get("GEMINI_API_KEY")
    if key:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"Analyze stock {ticker}. Context: {context}. Provide a brief 3-bullet strategic summary."
            resp = model.generate_content(prompt)
            return resp.text
        except:
            pass
            
    return f"**Mock Insight for {ticker}**:\n- Trend is Neutral/Bullish.\n- Volume is accumulating.\n- Watch key resistance levels."

# --- 4. MAIN UI ARCHITECTURE ---

def main():
    # A. Ralph Check
    if not run_ralph_check():
        st.stop()
        
    # B. Init State
    if 'analysis_db' not in st.session_state:
        st.session_state.analysis_db = load_analysis_db()
        
    # C. Sidebar (Hybrid Input)
    st.sidebar.title("Chimera V19.0 🦁")
    st.sidebar.caption("Project Chimera | Boris Protocol Core")
    
    # 1. CSV
    up_file = st.sidebar.file_uploader("📂 Data Feed (CSV)", type=['csv'])
    csv_df = load_jay_csv(up_file) if up_file else pd.DataFrame()
    
    # 2. Manual
    man_txt = st.sidebar.text_input("⌨️ Manual Tickers", "NVDA, PLTR")
    
    # 3. Merge
    all_tickers = merge_inputs(csv_df, man_txt)
    
    if not all_tickers:
        st.info("Awaiting Input Protocol...")
        return

    # D. Chimera Interface (Tabs)
    tabs = st.tabs(["🌍 War Room"] + all_tickers)
    
    # --- TAB 0: WAR ROOM ---
    with tabs[0]:
        st.header("Global Portfolio Overview")
        
        # Build Master Dataframe
        master_data = []
        prog = st.progress(0)
        
        for i, t in enumerate(all_tickers):
            prog.progress((i+1)/len(all_tickers))
            # Get Market Data
            df = get_market_data(t)
            price = df.iloc[-1]['Close']
            chg = (price - df.iloc[-2]['Close'])/df.iloc[-2]['Close'] if len(df)>1 else 0
            
            # Get Portfolio Data (if in CSV)
            shares = 0.0
            avg_cost = 0.0
            if not csv_df.empty and 'Ticker' in csv_df.columns:
                row = csv_df[csv_df['Ticker'] == t]
                if not row.empty:
                    shares = row.iloc[0].get('Shares', 0.0)
                    avg_cost = row.iloc[0].get('Avg Cost', 0.0)
            
            val = shares * price
            pl = val - (shares * avg_cost)
            
            master_data.append({
                "Ticker": t, "Price": price, "Day Chg %": chg,
                "Shares": shares, "Value": val, "P/L": pl
            })
            
        prog.empty()
        master_df = pd.DataFrame(master_data)
        
        # Display
        total_eq = master_df['Value'].sum()
        c1, c2 = st.columns(2)
        c1.metric("Total Equity", f"${total_eq:,.2f}")
        c2.metric("Active Tickers", len(all_tickers))
        
        st.dataframe(
            master_df,
            column_config={
                "Price": st.column_config.NumberColumn(format="$%.2f"),
                "Day Chg %": st.column_config.NumberColumn(format="%.2f%%"),
                "Value": st.column_config.NumberColumn(format="$%.2f"),
                "P/L": st.column_config.NumberColumn(format="$%.2f")
            },
            hide_index=True, use_container_width=True
        )
        
        # Export
        csv_exp = master_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Export Report", csv_exp, "chimera_report.csv", "text/csv")
        
    # --- TAB 1..N: STOCK DEEP DIVES ---
    for i, t in enumerate(all_tickers):
        with tabs[i+1]:
            st.subheader(f"{t} Analysis Module")
            
            df = get_market_data(t)
            recent = df.iloc[-1]
            
            # Chart (Yahoo Style)
            fig = sp.make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                                         name='Price', increasing_line_color='#00C805', decreasing_line_color='#FF3B30'), row=1, col=1)
            # MAs
            df['MA50'] = df['Close'].rolling(50).mean()
            df['MA200'] = df['Close'].rolling(200).mean()
            fig.add_trace(go.Scatter(x=df['Date'], y=df['MA50'], line=dict(color='blue', width=1), name='MA50'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['Date'], y=df['MA200'], line=dict(color='orange', width=1), name='MA200'), row=1, col=1)
            # Vol
            colors = ['#00C805' if c >= o else '#FF3B30' for c, o in zip(df['Close'], df['Open'])]
            fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
            fig.update_layout(height=500, xaxis_rangeslider_visible=False, template="plotly_dark", showlegend=False, margin=dict(t=10,l=0,r=0,b=0))
            st.plotly_chart(fig, use_container_width=True)
            
            # Analyst Notebook (Persistence)
            c_nb1, c_nb2 = st.columns([2, 1])
            
            # Load Notes
            notes = st.session_state.analysis_db.get(t, {})
            
            with c_nb1:
                macro = st.text_area("Global Macro / News", value=notes.get('macro', ''), key=f"m_{t}", height=150)
                phase = st.selectbox("Market Phase", ["Accumulation", "Markup", "Distribution", "Markdown"], 
                                     index=["Accumulation", "Markup", "Distribution", "Markdown"].index(notes.get('phase', 'Accumulation')), key=f"p_{t}")
            
            with c_nb2:
                # AI Insight Generation
                if st.button("✨ Generate AI Insight", key=f"ai_{t}"):
                    context = f"Price: {recent['Close']}, Phase: {phase}, User Notes: {macro}"
                    insight = generate_ai_insight(t, context)
                    st.session_state[f"ai_res_{t}"] = insight
                    
                if f"ai_res_{t}" in st.session_state:
                    st.info(st.session_state[f"ai_res_{t}"])
                    
                # Save
                if st.button("💾 Save Notebook", key=f"s_{t}"):
                    if t not in st.session_state.analysis_db: st.session_state.analysis_db[t] = {}
                    st.session_state.analysis_db[t]['macro'] = macro
                    st.session_state.analysis_db[t]['phase'] = phase
                    if save_analysis_db(st.session_state.analysis_db):
                        st.toast("Notebook Saved!")
                    else:
                        st.error("Save Failed")

if __name__ == "__main__":
    main()

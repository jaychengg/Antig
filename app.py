import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from ingest_engine import extract_content, get_price_data_finazon, load_portfolio, get_latest_price_batch
from datetime import datetime, timedelta
import io

# --- CONFIGURATION ---
st.set_page_config(page_title="投資戰情室 V2.0 (Investment War Room)", layout="wide")

# API Keys
try:
    PERPLEXITY_API_KEY = st.secrets["PERPLEXITY_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    # Finazon key is used inside ingest_engine, checked there.
except Exception as e:
    st.error(f"Missing API Keys: {e}")
    st.stop()

# --- BACKEND SERVICES ---
def fetch_market_data(ticker):
    """Fetches OHLCV data via Finazon Engine (includes RSI/Bias)."""
    return get_price_data_finazon(ticker)

def fetch_perplexity_news(ticker):
    """Fetches key news from the last 7 days."""
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "system", 
                "content": "You are a financial news aggregator. Return the most critical headlines and catalysts for the last 7 days. Be concise. Output MUST be in Traditional Chinese (繁體中文)."
            },
            {
                "role": "user", 
                "content": f"News for {ticker} (Last 7 Days)"
            }
        ]
    }
    headers = {"Authorization": f"Bearer {PERPLEXITY_API_KEY}", "Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Error fetching news: {e}"

def generate_black_box_analysis(ticker, market_data, news_context, user_intel, rsi_val, bias_val):
    """
    The Brain: Gemini 1.5 Pro (or 2.0 Flash) synthesizing all data.
    """
    model_name = "gemini-2.0-flash-exp"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    # Convert market data to string summary (last 15 days)
    market_summary = str(market_data.tail(15).to_markdown()) if not isinstance(market_data, str) else market_data
    
    prompt = f"""
    You are the Commander of the Investment War Room (投資戰情室).
    
    TARGET: {ticker}
    
    === TECHNICAL SNAPSHOT ===
    RSI (14): {rsi_val}
    Bias (20MA): {bias_val:.2f}%
    
    === USER INTEL (Zone B) ===
    {user_intel}
    
    === MARKET DATA (Technical Context - Last 15 Days) ===
    {market_summary}
    
    === NEWS WIRE (Last 7 Days) ===
    {news_context}
    
    === MISSION ===
    Perform a Deep Spectrum Analysis in Traditional Chinese (繁體中文).
    
    PART 1: MACRO CONTEXT (宏觀背景)
    - Analyze sector rotation, interest rate impact, and broader market correlation based on the news and data.
    
    PART 2: WYCKOFF SCHEMATICS (威科夫分析)
    - Reference the RSI ({rsi_val}) and Bias ({bias_val:.2f}%) in your analysis.
    - Analyze the price action. 
    - Identify Phase (A, B, C, D, or E).
    - Determine if this is Accumulation (吸籌/累積) or Distribution (派發/出貨).
    - Comment on Volume anomalies (量價異常).
    - Look for Spring (彈簧效應) or Upthrift (上衝回落).
    
    PART 3: TACTICAL ORDER (戰術指令)
    - Verdict: BUY (買入) / SELL (賣出) / HOLD (持有)
    - Risk Level: (1-10)
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Gemini Error ({response.status_code}): {response.text}"
    except Exception as e:
        return f"Connection Error: {e}"

# --- MACRO DASHBOARD ---
def render_macro_dashboard():
    """Renders global macro indicators using yfinance."""
    st.markdown("### 🌍 宏觀戰情看板 (Macro Dashboard)")
    col1, col2, col3 = st.columns(3)
    
    metrics = {
        "VIX 恐慌指數": "^VIX",
        "10年期公債殖利率": "^TNX",
        "WTI 原油價格": "CL=F"
    }
    
    cols = [col1, col2, col3]
    for (label, ticker), col in zip(metrics.items(), cols):
        try:
            data = yf.Ticker(ticker).history(period="2d")
            if len(data) >= 1:
                price = data['Close'].iloc[-1]
                prev_price = data['Close'].iloc[-2] if len(data) > 1 else price
                delta = price - prev_price
                col.metric(label, f"{price:.2f}", f"{delta:.2f}")
            else:
                col.metric(label, "N/A", "0.00")
        except:
            col.metric(label, "Error", "0.00")
    st.divider()

# --- UI COMPONENTS ---
# --- HELPER FUNCTIONS ---
# --- HELPER FUNCTIONS ---
def calculate_portfolio(transactions_df):
    """Calculates weighted average cost and total shares per ticker."""
    if transactions_df.empty:
        return pd.DataFrame(columns=["Ticker", "Shares", "Cost"])
    
    portfolio = []
    
    for ticker, group in transactions_df.groupby("Ticker"):
        buys = group[group['Shares'] > 0]
        total_shares = group['Shares'].sum()
        
        avg_cost = 0.0
        if not buys.empty and total_shares > 0:
            total_invested = (buys['Shares'] * buys['Cost']).sum()
            total_shares_bought = buys['Shares'].sum()
            avg_cost = total_invested / total_shares_bought
            
        if total_shares > 0.01:
            portfolio.append({
                "Ticker": ticker,
                "Shares": total_shares,
                "Cost": avg_cost
            })
        
    return pd.DataFrame(portfolio)

# --- UI: DEEP DIVE ANALYSIS (HEAVY) ---
def render_deep_dive(ticker):
    """Renders the Heavy Analysis View for a SINGLE selected ticker."""
    st.markdown(f"## 🔍 {ticker} 深度分析 (Deep Dive)")
    
    # 1. Fetch Heavy Data (Cached 1hr)
    with st.spinner(f"正在獲取 {ticker} 歷史數據..."):
        market_data = get_price_data_finazon(ticker)
    
    if isinstance(market_data, str):
        st.error(market_data)
        return

    # 2. Indicators Header
    current_price = market_data['Close'].iloc[-1]
    rsi = market_data['RSI'].iloc[-1]
    bias = market_data['Bias'].iloc[-1]
    
    m1, m2, m3 = st.columns(3)
    m1.metric("價格 (Price)", f"${current_price:.2f}")
    m2.metric("RSI (14)", f"{rsi:.1f}")
    m3.metric("Bias (20MA)", f"{bias:.2f}%")
    
    st.divider()
    
    # 3. Chart
    st.subheader("📉 趨勢圖表")
    try:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=market_data.index, open=market_data['Open'], high=market_data['High'], low=market_data['Low'], close=market_data['Close'], name='Price'), row=1, col=1)
        if 'MA20' in market_data.columns: fig.add_trace(go.Scatter(x=market_data.index, y=market_data['MA20'], line=dict(color='orange'), name='MA20'), row=1, col=1)
        if 'MA100' in market_data.columns: fig.add_trace(go.Scatter(x=market_data.index, y=market_data['MA100'], line=dict(color='cyan'), name='MA100'), row=1, col=1)
        fig.add_trace(go.Bar(x=market_data.index, y=market_data['Volume'], name='Vol'), row=2, col=1)
        fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Chart Error: {e}")
        
    # 4. Intelligence (Zone B/C)
    st.subheader("📡 情報與分析")
    c1, c2 = st.columns([3, 1])
    user_note = c1.text_area("筆記/連結", key=f"note_{ticker}")
    if c2.button("🚀 執行黑盒分析", key=f"run_{ticker}"):
        with st.status("分析中...") as s:
            news = fetch_perplexity_news(ticker)
            s.write("新聞獲取完成")
            ai_res = generate_black_box_analysis(ticker, market_data, news, user_note if user_note else "", rsi, bias)
            st.session_state[f"ai_{ticker}"] = ai_res
            s.update(label="完成", state="complete")
            
    if f"ai_{ticker}" in st.session_state:
        st.markdown(st.session_state[f"ai_{ticker}"])

# --- MAIN APP ---
st.title("🛡️ 投資戰情室 V10.0 (Smart Architecture)")
render_macro_dashboard()

# Sidebar
with st.sidebar:
    st.header("系統監控")
    with st.expander("API 狀態"):
         st.caption("Auto-caching active.")
         if st.button("Refresh Cache"):
             st.cache_data.clear()
             st.rerun()

    st.header("管理")
    # Smart Upload
    # Smart Upload
    # (Cleaned up: Import handled at top)
    
    up = st.file_uploader("📂 上傳 (Smart CSV)", type=['csv', 'xlsx'])
    if up:
        try:
            # Load into DF if Excel, else pass buffer
            if up.name.endswith('.xlsx'):
                source = pd.read_excel(up)
            else:
                source = up # Pass file buffer directly for CSV
            
            st.session_state['transactions'] = load_portfolio(source)
            st.success("Smart Upload 成功!")
        except Exception as e:
            st.error(f"Upload Failed: {e}")
            
    # Manual Add (Legacy)
    with st.expander("➕ 手動"):
        with st.form("manual"):
            t = st.text_input("Ticker"); s = st.number_input("Shares"); c = st.number_input("Cost")
            if st.form_submit_button("Add"):
                new = pd.DataFrame([{"Ticker": t.upper(), "Shares": s, "Cost": c}])
                st.session_state['transactions'] = pd.concat([st.session_state.get('transactions', pd.DataFrame()), new], ignore_index=True)
                st.rerun()
                
    # Copy Data
    if 'transactions' in st.session_state:
        with st.expander("匯出數據"):
            st.code(st.session_state['transactions'].to_csv(index=False), language='csv')

# --- DATA ---
if 'transactions' not in st.session_state:
    st.session_state['transactions'] = pd.DataFrame(columns=["Ticker", "Shares", "Cost"])
    
portfolio_df = calculate_portfolio(st.session_state['transactions'])

# --- TABS (SPLIT ARCHITECTURE) ---
t1, t2 = st.tabs(["🏠 總覽 (Dashboard)", "🔍 深度分析 (Deep Dive)"])

# TAB 1: DASHBOARD (LIGHT)
with t1:
    st.subheader("📊 資產總覽")
    if portfolio_df.empty:
        st.info("尚無持倉。")
    else:
        # Fetch Snapshots
        total_val = 0; total_cost = 0;
        rows = []
        
        # Batch Fetch Prices (V11 Optimized)
        tickers = portfolio_df['Ticker'].unique().tolist()
        current_prices = get_latest_price_batch(tickers)

        for _, row in portfolio_df.iterrows():
            tk = row['Ticker']
            sh = row['Shares']
            h_cost = row['Cost']
            
            price = current_prices.get(tk, 0)
            
            val = sh * price
            c_basis = sh * h_cost
            pnl = val - c_basis
            pnl_p = (pnl / c_basis * 100) if c_basis > 0 else 0
            
            total_val += val
            total_cost += c_basis
            
            rows.append({
                "Ticker": tk,
                "Shares": f"{sh:.2f}",
                "AvgCost": f"{h_cost:.2f}",
                "Price": f"{price:.2f}",
                "Value": val,
                "PnL ($)": pnl,
                "PnL (%)": f"{pnl_p:.1f}%"
            })
            
        # Top Metrics
        tot_pnl = total_val - total_cost
        tot_pnl_p = (tot_pnl/total_cost*100) if total_cost>0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("總市值", f"${total_val:,.0f}")
        c2.metric("總成本", f"${total_cost:,.0f}")
        c3.metric("總損益", f"${tot_pnl:,.0f}", f"{tot_pnl_p:.1f}%")
        
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

# TAB 2: DEEP DIVE (HEAVY)
with t2:
    if portfolio_df.empty:
        st.write("No stocks.")
    else:
        # Selectbox to lazy load
        tickers = portfolio_df['Ticker'].unique().tolist()
        watchlist = st.session_state.get('watchlist', [])
        all_opts = sorted(list(set(tickers + watchlist)))
        
        selected = st.selectbox("選擇股票 (Select Stock)", all_opts)
        
        if selected:
            render_deep_dive(selected)

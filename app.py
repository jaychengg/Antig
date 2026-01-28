import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.subplots as sp
import requests
import json
import numpy as np
import yfinance as yf
import re
import io
import time
import google.generativeai as genai
from datetime import datetime, timedelta

# Internal Engines
from governance import gov
from preload_db import preload
from nexus_intelligence import nexus_brain
from chart_engine import chart_engine, ChartContext, Resolution

# ==========================================
# ⚙️ SYSTEM CONFIG (Nexus V30)
# ==========================================
st.set_page_config(
    page_title="反重力戰情室 (Nexus V30)",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="expanded"
)

COLOR_UP = '#00C805'
COLOR_DOWN = '#FF3B30'

# ==========================================
# 🔒 BOOT SEQUENCE
# ==========================================
if 'BOOT_COMPLETE' not in st.session_state:
    nexus_brain.system_boot_check()
    st.session_state['BOOT_COMPLETE'] = True

# ==========================================
# 🛡️ SYSTEM STATUS UI
# ==========================================
def render_sidebar_status():
    # CSS for Compact Status
    st.markdown("""
        <style>
        .st-emotion-cache-16idsys p { font-size: 0.8rem; } /* Streamlit generic adjustment attempt */
        div[data-testid="stMetricValue"] { font-size: 0.9rem !important; }
        .status-label { font-size: 0.75rem; color: #aaa; margin-bottom: -5px; }
        .status-val { font-size: 0.85rem; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        </style>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("### 🔑 System Status")
    
    # Check Ralph Status
    ralph = st.session_state.get('RALPH_STATUS', {})
    gem_ok = ralph.get('gemini_ok', False)
    perp_ok = bool(st.secrets.get("PERPLEXITY_KEY") or st.secrets.get("PERPLEXITY_API_KEY"))
    fin_ok = bool(st.secrets.get("FINAZON_KEY"))
    
    c1, c2, c3 = st.sidebar.columns([1,1,1.2]) # Give Gemini slightly more space
    
    with c1:
        st.markdown('<p class="status-label">Finazon</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="status-val">{"🟢 Active" if fin_ok else "🔴 Missing"}</p>', unsafe_allow_html=True)
        
    with c2:
        st.markdown('<p class="status-label">Perplexity</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="status-val">{"🟢 Active" if perp_ok else "🔴 Missing"}</p>', unsafe_allow_html=True)
        
    with c3:
        model_name = ralph.get('model', 'Blocked').replace('models/', '')
        st.markdown('<p class="status-label">Gemini</p>', unsafe_allow_html=True)
        if gem_ok:
            st.markdown(f'<p class="status-val" title="{model_name}">🟢 {model_name}</p>', unsafe_allow_html=True)
        else:
            st.markdown('<p class="status-val">🔴 Blocked</p>', unsafe_allow_html=True)

    if not gem_ok:
        st.sidebar.error(f"⛔ {ralph.get('reason')}")
    
    st.sidebar.markdown("---")
    
    # Budget Monitor
    status = gov.get_status()
    st.sidebar.subheader("📊 流量預算 (Budget)")
    pct_used = status['used'] / 850.0
    st.sidebar.progress(min(pct_used, 1.0))
    st.sidebar.caption(f"今日: {status['used']}/850 | RPM Token: {status['rpm_tokens']}")
    
    if status['power_save']:
        st.sidebar.warning("⚠️ 省電模式 (Power Save)")
    
    st.sidebar.write("---")
    return st.secrets.get("FINAZON_KEY", "")

# ==========================================
# 🔌 NEXUS DATA ENGINE
# ==========================================
def fetch_finazon_safe(ticker, finazon_key, start_ts=None, end_ts=None):
    allowed, msg = gov.allow_request(ticker)
    if not allowed: return pd.DataFrame(), f"BLOCKED: {msg}"
        
    try:
        url = "https://api.finazon.io/latest/finazon/us_stocks_essential/time_series"
        params = {"ticker": ticker, "interval": "1d", "apikey": finazon_key}
        if start_ts: params['start_at'] = start_ts
        if end_ts: params['end_at'] = end_ts
        if not start_ts and not end_ts: params['page_size'] = 365
        
        res = requests.get(url, params=params, timeout=5)
        if res.status_code == 200:
            data = res.json().get('data', [])
            if data:
                df = pd.DataFrame(data)
                df = df.rename(columns={'t': 'Date', 'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume'})
                df['Date'] = pd.to_datetime(df['Date'], unit='s')
                return df, "Finazon (Pro)"
        elif res.status_code == 429:
             time.sleep(1)
             return pd.DataFrame(), "Rate Limit (429)"
    except Exception as e:
        return pd.DataFrame(), str(e)
    return pd.DataFrame(), "No Data"

# ==========================================
# 📊 METRICS & CSV
# ==========================================
def clean_numeric(value):
    if isinstance(value, (int, float)): return float(value)
    try:
        s_val = str(value).strip().replace(',', '').replace('$', '').replace('%', '')
        if '(' in s_val: s_val = '-' + s_val.replace('(', '').replace(')', '')
        return float(s_val) if s_val else 0.0
    except: return 0.0

def process_accounting_csv(uploaded_file):
    # Load demo if no file
    if not uploaded_file:
         try:
             df = pd.read_csv("Jay Investments - Sheet16.csv")
         except:
             return pd.DataFrame(), {}
    else:
        df = pd.read_csv(uploaded_file)
        
    try:
        # 1. Cleaning Headers
        # Remove unnamed columns
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        # Drop empty columns
        df = df.dropna(axis=1, how='all')
        
        # Canonical Rename Map (User Hard Spec)
        rename_map = {
            'SHARE': 'Shares', 'Share': 'Shares', 
            'AVG COST': 'AvgCost', 'Avg Cost': 'AvgCost', 
            'MARKET PRICE': 'MarketPrice', 'Market Price': 'MarketPrice',
            'Value': 'MarketValue', 'Market Value': 'MarketValue',
            'TOTAL COST': 'TotalCost', 'Total Cost': 'TotalCost',
            'PROFIT': 'PnL', 'Profit': 'PnL',
            'PROFIT%': 'PnLPct', 'Profit%': 'PnLPct'
        }
        df.rename(columns=rename_map, inplace=True)
        
        # Ensure Ticker exists
        if 'Ticker' not in df.columns: return pd.DataFrame(), {}
        
        df = df.dropna(subset=['Ticker'])
        df['Ticker'] = df['Ticker'].astype(str).str.upper().str.strip()
        
        # 2. Convert Numerics STRICT
        num_cols = ['Shares', 'AvgCost', 'MarketPrice', 'MarketValue', 'TotalCost', 'PnL']
        for c in num_cols:
            if c in df.columns:
                df[c] = df[c].apply(clean_numeric)
            else:
                df[c] = 0.0

        # 3. KPI Recalculation (Trust but Verify)
        # TotalCost Strategy: Use provided TotalCost if valid, else fallback
        # User Rule: TotalCost = Σ TotalCost (from CSV)
        
        # Recalculate PnL and ROI based on User Formula, NOT CSV
        # NetPnL = TotalValue - TotalCost
        df['NetPnL'] = df['MarketValue'] - df['TotalCost']
        
        # ROI = NetPnL / TotalCost (Ratio, not %)
        df['ROI'] = df.apply(lambda x: (x['NetPnL'] / x['TotalCost']) if x['TotalCost'] > 0 else 0, axis=1)
        
        # 4. Gate Check (Data Integrity)
        def check_integrity(row):
            tc = row['TotalCost']
            mv = row['MarketValue']
            if mv == 0: return row['ROI']
            
            if tc < (mv * 0.2) or tc > (mv * 5):
                 # Outlier
                 return np.nan 
            return row['ROI']
        
        # 5. Whitelist Columns
        final_cols = ['Ticker', 'Shares', 'AvgCost', 'MarketPrice', 'MarketValue', 'TotalCost', 'NetPnL', 'ROI']
        df_final = df[final_cols].copy()
        df_final.rename(columns={'NetPnL': 'PnL', 'ROI': 'PnLPct'}, inplace=True) 
        
        # 6. Global Metrics
        total_value = df['MarketValue'].sum()
        total_cost = df['TotalCost'].sum()
        net_pnl = total_value - total_cost
        roi = (net_pnl / total_cost * 100) if total_cost > 0 else 0
        
        metrics = {
            "Total Asset": total_value,
            "Total Cost": total_cost,
            "Net Revenue": net_pnl,
            "Rev %": roi
        }
        
        return df_final.sort_values('MarketValue', ascending=False), metrics
    except Exception as e:
        print(f"CSV Error: {e}") 
        return pd.DataFrame(), {}

# ==========================================
# 📝 TRADE TAB LOGIC (LEAF NODE)
# ==========================================
def render_trade_tab(ticker):
    import storage
    import uuid
    
    st.markdown("### 📝 交易紀錄 (Trade Log)")
    
    # 0. Check Storage Status
    db_ok, db_msg = storage.check_db_status()
    user_id = "local" # MVP single user
    
    if db_ok:
        st.caption("🟢 Cloud SQL Online")
        trades = storage.list_trades(user_id, ticker)
    else:
        st.warning(f"⚠️ Data Offline: {db_msg}. Using Volatile Session State.")
        if 'trades_db' not in st.session_state: st.session_state['trades_db'] = []
        trades = [t for t in st.session_state['trades_db'] if t['ticker'] == ticker]
    
    # 1. Summary Metrics
    total_shares = 0
    total_cost = 0
    
    for t in trades:
        act = t['action']
        sh = float(t['shares'])
        pr = float(t['price'])
        fe = float(t['fee']) if t.get('fee') else 0.0
        
        if act in ['BUY', 'ADD']:
            total_shares += sh
            total_cost += (sh * pr) + fe
        elif act in ['SELL', 'REDUCE']:
            total_shares -= sh
            pass

    avg_cost = 0
    if total_shares > 0:
        buys = [t for t in trades if t['action'] in ['BUY', 'ADD']]
        b_shares = sum(float(t['shares']) for t in buys)
        b_cost = sum(float(t['shares']) * float(t['price']) + (float(t.get('fee')) if t.get('fee') else 0.0) for t in buys)
        if b_shares > 0: avg_cost = b_cost / b_shares
    
    c1, c2, c3 = st.columns(3)
    c1.metric("目前持倉 (Shares)", f"{total_shares:,.0f}")
    c2.metric("平均成本 (Avg Cost)", f"${avg_cost:,.2f}")
    c3.metric("交易筆數 (Count)", len(trades))

    st.markdown("---")
    
    # 2. Add New Trade
    with st.expander("➕ 新增交易 (Add Trade)", expanded=False):
        with st.form(key=f"add_trade_{ticker}"):
            c1, c2 = st.columns(2)
            date = c1.date_input("日期 (Date)", value=datetime.utcnow())
            action = c2.selectbox("動作 (Action)", ["BUY", "SELL", "ADD", "REDUCE"])
            
            c3, c4, c5 = st.columns(3)
            shares = c3.number_input("股數 (Shares)", min_value=0.0, step=1.0)
            price = c4.number_input("價格 (Price)", min_value=0.0, step=0.01)
            fee = c5.number_input("手續費 (Fee)", min_value=0.0, step=0.1)
            
            note = st.text_input("備註 (Note)")
            
            if st.form_submit_button("💾 儲存 (Save)"):
                new_trade = {
                    "user_id": user_id,
                    "ticker": ticker,
                    "datetime": str(date),
                    "action": action,
                    "shares": shares,
                    "price": price,
                    "fee": fee,
                    "note": note
                }
                
                try:
                    if db_ok:
                        storage.add_trade(new_trade)
                    else:
                        new_trade['id'] = str(uuid.uuid4())
                        st.session_state['trades_db'].append(new_trade)
                        
                    st.success("已儲存！")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Save Failed: {e}")
    
    # 3. Trade List
    if trades:
        df_trades = pd.DataFrame(trades)
        cols = ['datetime', 'action', 'shares', 'price', 'fee', 'note', 'id']
        show_cols = [c for c in cols if c in df_trades.columns]
        df_trades = df_trades[show_cols]
        if 'datetime' in df_trades.columns:
            df_trades = df_trades.sort_values('datetime', ascending=False)
        
        st.dataframe(df_trades, use_container_width=True, hide_index=True)
        
        del_id = st.text_input("輸入 ID 刪除 (Delete Trace ID)", key=f"del_{ticker}")
        if st.button("🗑️ 刪除 (Delete)", key=f"btn_del_{ticker}"):
             if db_ok:
                 try:
                     storage.delete_trade(del_id, user_id)
                     st.success("已刪除")
                     st.rerun()
                 except Exception as e:
                     st.error(f"Delete Failed: {e}")
             else:
                 st.session_state['trades_db'] = [t for t in st.session_state['trades_db'] if t['id'] != del_id]
                 st.success("已刪除")
                 st.rerun()
    else:
        st.info("尚無交易紀錄 (No Trades)")

# ==========================================
# 🚀 MAIN APP V30
# ==========================================
def main():
    f_key = render_sidebar_status()
    ralph = st.session_state.get('RALPH_STATUS', {})
    
    st.sidebar.markdown("---")
    uploaded_file = st.sidebar.file_uploader("📂 投資組合 CSV (Portfolio)", type=['csv'])
    manual_txt = st.sidebar.text_input("📝 自選代碼 (Manual Tickers)", "NVDA, TSLA")
    
    df_stocks, metrics = process_accounting_csv(uploaded_file)
    
    all_tickers = []
    if not df_stocks.empty: all_tickers = df_stocks['Ticker'].tolist()
    if manual_txt: all_tickers += [x.strip().upper() for x in manual_txt.split(',')]
    all_tickers = sorted(list(set(all_tickers)))
    
    portfolio_ctx = {}
    if not df_stocks.empty:
        for _, row in df_stocks.iterrows():
            portfolio_ctx[row['Ticker']] = {'avg_cost': row['AvgCost']}
    
    tab1, tab2 = st.tabs(["🌍 全球戰情 (Dashboard)", "🛠️ 個股分析 (Workbench)"])
    
    with tab1:
        st.subheader("全球資產情報")
        if metrics:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("總資產", f"${metrics['Total Asset']:,.2f}")
            c2.metric("總成本", f"${metrics['Total Cost']:,.2f}")
            c3.metric("淨損益", f"${metrics['Net Revenue']:,.2f}", delta_color="normal" if metrics['Net Revenue']>0 else "inverse")
            c4.metric("報酬率", f"{metrics['Rev %']:.2f}%", delta=f"{metrics['Rev %']:.2f}%")
        
        if not df_stocks.empty:
            st.dataframe(
                df_stocks, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "AvgCost": st.column_config.NumberColumn("Avg Cost", format="$%.2f"),
                    "MarketPrice": st.column_config.NumberColumn("Market Price", format="$%.2f"),
                    "MarketValue": st.column_config.NumberColumn("Market Value", format="$%.2f"),
                    "TotalCost": st.column_config.NumberColumn("Total Cost", format="$%.2f"),
                    "PnL": st.column_config.NumberColumn("PnL", format="$%.2f"),
                    "PnLPct": st.column_config.NumberColumn("PnL %", format="%.2%")
                }
            )

    with tab2:
        if not all_tickers:
            st.info("請上傳 CSV 或輸入代碼以開始分析")
        else:
            sel_ticker = st.selectbox("選擇資產 (Select Asset)", all_tickers, index=0)
            
            # NESTED TABS for Workbench
            t_chart, t_anal, t_wyck, t_trade = st.tabs(["📈 線圖 (Chart)", "📋 分析報告 (Report)", "🧙‍♂️ 威科夫 (Wyckoff)", "📝 交易紀錄 (Trade Log)"])
            
            # --- TAB 1: CHART ---
            with t_chart:
                 try:
                     period = st.selectbox("時間範圍 (Range)", ["1mo", "3mo", "6mo", "1y", "5y"], index=2, key="chart_period")
                     
                     # Initialize Pipeline with Context
                     ctx = ChartContext(symbol=sel_ticker, interval=Resolution.DAILY, period=period, finazon_key=f_key)
                     result = chart_engine.run(ticker=sel_ticker, interval="1d", period=period, finazon_key=f_key)
                     
                     df_price = result.get('df')
                     coverage = result.get('coverage', 0.0)
                     missing_cnt = result.get('missing_count', 0)
                     source = result.get('source', 'Unknown')
                     reliability = result.get('reliability', True)
                     
                     if not df_price.empty:
                        # Forensic Status Line
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Coverage (信賴度)", f"{coverage:.1%}")
                        c2.metric("Missing (缺口)", f"{missing_cnt} days")
                        c3.caption(f"Source: {source}")
                        
                        if not reliability:
                             st.error("⚠️ 交易日曆不可用 (Calendar Unavailable): Coverage 僅供參考，可能包含非交易日。")
                        
                        if coverage < 0.99 and missing_cnt > 0:
                             st.warning(f"⚠️ 此線圖包含 {missing_cnt} 個遺失交易日 (Missing Trading Days)。")

                        fig = sp.make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7,0.3], vertical_spacing=0.03)
                        
                        # OPTION A: Category Axis (Strict Trading Days)
                        df_price['DateStr'] = df_price.index.strftime('%Y-%m-%d')
                        
                        fig.add_trace(go.Candlestick(
                            x=df_price['DateStr'], open=df_price['Open'], high=df_price['High'],
                            low=df_price['Low'], close=df_price['Close'],
                            name="Price", increasing_line_color=COLOR_UP, decreasing_line_color=COLOR_DOWN
                        ), row=1, col=1)
                        
                        colors = [COLOR_UP if c >= o else COLOR_DOWN for c, o in zip(df_price['Close'], df_price['Open'])]
                        fig.add_trace(go.Bar(x=df_price['DateStr'], y=df_price['Volume'], marker_color=colors, name="Vol", showlegend=False), row=2, col=1)
                        
                        fig.update_layout(height=500, margin=dict(t=10,b=0,l=0,r=0), template="plotly_dark", showlegend=False)
                        fig.update_xaxes(type='category', tickmode='auto', nticks=10, rangeslider_visible=False)
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        ohlcv_summary = df_price.tail(30).to_string()
                     else:
                         st.error(f"❌ No Data Available for {sel_ticker}. (Source: {source})")
                         ohlcv_summary = "No Price Data"
                 except Exception as e:
                     st.error(f"Chart Error: {e}")
                     ohlcv_summary = "Error"

            # Global Block Check
            is_blocked = not ralph.get('gemini_ok')

            # --- TAB 2: ANALYSIS REPORT ---
            with t_anal:
                try:
                    st.subheader("📋 個股分析報告")
                    if is_blocked:
                        st.error(f"⛔ BLOCKED: {ralph.get('reason')}")
                    else:
                        col_btn, _ = st.columns([1,3])
                        if col_btn.button("🚀 執行深度分析", key="btn_anal"):
                             with st.spinner("Processing..."):
                                 ev = nexus_brain.fetch_evidence_pack(sel_ticker)
                                 ctx = portfolio_ctx.get(sel_ticker, {})
                                 rep = nexus_brain.generate_report(sel_ticker, ev['data'], ohlcv_summary, ctx, "STOCK_ANALYSIS")
                                 nexus_brain._set_cache(sel_ticker, "report_anal", rep)
                                 st.rerun()
                                 
                        final_rep = nexus_brain._get_cache_data(sel_ticker, "report_anal") if nexus_brain._is_cache_valid(sel_ticker, "report_anal") else None
                        if final_rep: 
                            st.markdown(final_rep)
                        else: 
                            st.info(f"💡 Ready to Analyze {sel_ticker}")
                except Exception as e:
                    st.error(f"Analysis Error: {e}")

            # --- TAB 3: WYCKOFF ---
            with t_wyck:
                try:
                    st.subheader("📈 威科夫分析")
                    if is_blocked:
                        st.error(f"⛔ BLOCKED: {ralph.get('reason')}")
                    else:
                        col_btn, _ = st.columns([1,3])
                        if col_btn.button("🧙‍♂️ 執行威科夫推演", key="btn_wyck"):
                             with st.spinner("Synthesizing..."):
                                 ev = nexus_brain.fetch_evidence_pack(sel_ticker)
                                 rep = nexus_brain.generate_report(sel_ticker, ev['data'], ohlcv_summary, None, "WYCKOFF")
                                 nexus_brain._set_cache(sel_ticker, "report_wyckoff", rep)
                                 st.rerun()
                                 
                        final_wy = nexus_brain._get_cache_data(sel_ticker, "report_wyckoff") if nexus_brain._is_cache_valid(sel_ticker, "report_wyckoff") else None
                        if final_wy: 
                            st.markdown(final_wy)
                        else: 
                            st.info(f"💡 Ready to Run Wyckoff on {sel_ticker}")
                except Exception as e:
                    st.error(f"Wyckoff Error: {e}")

            # --- TAB 4: TRADES (NEW) ---
            with t_trade:
                render_trade_tab(sel_ticker)

if __name__ == "__main__":
    main()

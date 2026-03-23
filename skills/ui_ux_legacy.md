# Agent Skill: V10 Legacy UI Standard
# Description: Defines the strict visual and interaction standards for the Antigravity War Room on Mac Silicon.

## 1. Layout Philosophy
- **Vertical Flow**: All content must flow vertically. DO NOT use `st.tabs` or horizontal pagination.
- **Expander First**: Individual stock details must be wrapped in `st.expander(label=f"{symbol} Analysis", expanded=True)`.
- **Metrics**: Use `st.columns` only for high-level metrics (Price, Change, Volume) inside the expander.

## 2. Visual Intelligence (Plotly)
- **Chart Type**: Interactive Candlestick (Plotly Graph Objects).
- **Overlays**:
    - MA20: Blue Line (width=1.5)
    - MA100: Orange Line (width=1.5)
- **Configuration**: Disable 'displayModeBar' to keep it clean.

## 3. Error UI
- **Graceful Failure**: If data is missing, display `st.warning("No Data")` instead of crashing.
- **Debug Info**: Show API status codes in `st.expander("Debug Log", expanded=False)` for Engineers.

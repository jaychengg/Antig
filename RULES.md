# Project Constitution: Antigravity War Room (V17.0 Ralph Protocol)

## 1. The "Ralph Check" (Mandatory Self-Correction)
- **Definition**: Before any UI is rendered, the `ralph_check()` function MUST run.
- **Scope**:
    1.  **CSV Integrity**: Verify `Ticker`, `Shares`, `Avg Cost` columns exist and are numeric. If `Ticket` is found, auto-rename to `Ticker`.
    2.  **Schema Validation**: Ensure API DataFrames contain standard columns (`Date`, `Close`, `Volume`) in Title Case.
    3.  **Sanity Check**: If TSLA price is $0 or $5000 (bad data), trigger `st.cache_data.clear()` and retry.
- **Enforcement**: If `ralph_check()` returns `False`, the app MUST STOP and display a specific error code, NOT a traceback.

## 2. Architecture & Tech Stack
- **OS**: MacOS Silicon Optimized.
- **Database**: SQLite (`market_data.db`) for robust caching.
- **Data Source**: Finazon API (Primary).
- **Visualization**: Plotly Graph Objects (Yahoo Finance Style: Green/Red Candles, Separate Volume).

## 3. Data Ingestion Standards (Zero-Crash)
- **Accounting Format**: Must parse `(500.00)`, `$1,200.00`, `12.5%` without error.
- **Schema Guard**: All DataFrames must pass through `normalize_schema(df)` to fix case-sensitivity (`date` -> `Date`) before being accessed.

## 4. Error Handling Protocols
- **No Tracebacks**: Use `try-except` blocks globally.
- **Graceful Degradation**: If one ticker fails, the dashboard must load the others.

## 5. UI/UX
- **Structure**: Vertical flow (No Tabs).
- **Dashboard**: "Rich Table" with Live Price, Market Value, and P/L.

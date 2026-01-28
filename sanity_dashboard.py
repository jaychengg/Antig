
import pandas as pd
import numpy as np
from app import process_accounting_csv, clean_numeric
import sys

# Mock clean_numeric if needed (but we import it)
# We test the logic by running process_accounting_csv(None) which loads the local demo file

def sanity_check():
    print("🧪 Running Dashboard Logic Sanity Check...")
    
    df, metrics = process_accounting_csv(None)
    
    if df.empty:
        print("❌ Data Load Failed")
        sys.exit(1)
        
    print("\n--------------------------------")
    print("📊 Metrics")
    print("--------------------------------")
    for k, v in metrics.items():
        print(f"{k}: {v:,.2f}")
        
    print("\n--------------------------------")
    print("🛑 Gate Check: Total Cost vs Value")
    print("--------------------------------")
    
    tc = metrics['Total Cost']
    ta = metrics['Total Asset']
    
    print(f"Total Cost: ${tc:,.2f}")
    print(f"Total Asset: ${ta:,.2f}")
    
    # Simple magnitude check
    if tc < 10000 or tc > 10000000: # Assuming typical demo port is ~100k-1M
        print("⚠️ Total Cost seems suspicious (Magnitude Check)")
    else:
        print("✅ Total Cost magnitude seems reliable")
        
    # Check Net PnL Math
    pnl = metrics['Net Revenue']
    calc_pnl = ta - tc
    if abs(pnl - calc_pnl) < 0.01:
        print(f"✅ Net PnL is mathematically correct: {pnl:,.2f}")
    else:
        print(f"❌ PnL Mismatch: Reported {pnl}, Calc {calc_pnl}")
        
    print("\n--------------------------------")
    print("⚠️ Outlier Detection")
    print("--------------------------------")
    # Check columns
    print("Cols:", df.columns.tolist())
    
    if any("Unnamed" in c for c in df.columns):
         print("❌ 'Unnamed' columns detected!")
    else:
         print("✅ Columns are clean.")
         
    # Check top row
    print("\nTop 3 Rows:")
    print(df.head(3).to_string())

if __name__ == "__main__":
    sanity_check()

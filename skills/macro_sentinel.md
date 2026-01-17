---
name: macro-sentinel
description: Scans macro data like Fed minutes, CPI, dot-plots, and inter-market correlations to assess portfolio risk.
---

# Agent Skill: Macro Sentinel

## 1. When to Use
- **Trigger**: FOMC meetings, CPI release dates, or anomalous Bond Yield spikes.
- **Context**: Daily "Risk On/Off" determination.

## 2. Analysis Logic (The Brain)
### Phase A: The Fed Whisperer
1. **Sentiment Extraction**: Scan FOMC minutes for keywords ("Transitory", "Sticky", "Hike").
2. **Dot-Plot Mapping**: Compare market expectations (Fed Funds Futures) vs Fed Dot Plot. Gap = Volatility.

### Phase B: Inter-Market Correlations
1. **DXY vs Assets**: 
   - Rising DXY + Rising Yields = **Toxic for Equities/Crypto**.
   - Falling DXY = **Tailwind for Risk Assets**.
2. **Yield Curve**: Check 10Y-2Y spread. Inversion deepening or normalizing (Recession signal)?

### Phase C: Bridgewater Checklist
1. **Bubble Gauge**: Are prices discounting unrealistic growth?
2. **Liquidity Pump**: Is the TGA (Treasury General Account) refilling or draining?

## 3. Required Output
- **Macro Regime**: Inflationary Boom / Deflationary Bust / Stagflation / Goldilocks.
- **Risk Level**: High (Cash is King) / Medium / Low (Leverage Up).

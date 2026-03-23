---
name: fundamental-hunter
description: Analyzes earnings reports, 10-Ks, and call transcripts to extract revenue quality, management guidance tone, and key red flags using structured checklists.
---

# Agent Skill: Fundamental Hunter

## 1. When to Use
- **Trigger**: User uploads a PDF (10-K/10-Q) or queries "analyze earnings" for a specific ticker.
- **Context**: Pre-trade validation or quarterly review.

## 2. Analysis Logic (The Brain)
### Phase A: Document Autopsy
1. **Section Parsing**: Locate MD&A (Item 7) and Risk Factors (Item 1A).
2. **DuPont Breakdown**: 
   - Calculate: Net Profit Margin × Asset Turnover × Equity Multiplier.
   - *Goal*: Identify if ROE is driven by actual efficiency or just higher debt (leverage).

### Phase B: Quality Control
1. **Revenue Reality Check**: Distinguish between "Recurring Revenue" vs "One-time Gains".
2. **Cash Flow Check**: If Net Income > Operating Cash Flow for 2 consecutive quarters -> **RED FLAG** (Aggressive Accounting).

### Phase C: Deception Detection (Tone Analysis)
1. **Linguistic Scan**: Look for hesitation markers ("honestly", "to be clear", "as I said").
2. **Guidance Audit**: Compare previous guidance vs actual results. Did they move the goalposts?

## 3. Required Output
- **Scorecard**: Revenue Quality (High/Med/Low), Tone (Bullish/Defensive), Red Flags (Count).
- **Verdict**: Buy / Hold / Avoid.

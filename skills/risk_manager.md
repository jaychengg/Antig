---
name: risk-manager
description: Validates manual trade inputs against position sizing, Kelly Criterion, and ATR-based stops.
---

# Agent Skill: Risk Manager (The Gatekeeper)

## 1. When to Use
- **Trigger**: User inputs a manual trade via Sidebar "Trade Validator".
- **Context**: Pre-execution validation.

## 2. Analysis Logic (The Brain)
### Phase A: The ATR Shield (Volatility Check)
1. **Stop Loss Validation**: 
   - Calculate distance: `|Entry - Stop|`.
   - If distance < `1.5 * ATR(14)`, REJECT (Stop is too tight, noise will kill you).

### Phase B: Position Sizing (The Kelly Limit)
1. **Risk Per Trade**: 
   - Max Risk = 2% of Total Account Equity.
   - `Risk Amount = Shares * (Entry - Stop)`.
   - If `Risk Amount > Max Risk`, REJECT.

## 3. Required Output
- **Verdict**: PASS / FAIL.
- **Advice**: "Reduce size to X shares" or "Widen stop to $Y".

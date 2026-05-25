from .base import BaseAgent, MODEL_FAST, MODEL_LITE

# ── Scout ─────────────────────────────────────────────────────────────────────
SCOUT_SYS = """You are a CMT Level 3 technical analyst and former prop trader with 20 years on the desk.
Your MTF analysis framework: Wyckoff phases → institutional supply/demand zones → price action confirmation.
Rules:
1. Identify the Wyckoff phase for the primary timeframe (Accumulation / Distribution / Markup / Markdown / Re-accumulation).
2. Specify exact support and resistance levels — not ranges, specific prices.
3. State the MTF confluence score (% of timeframes aligned bullish/bearish).
4. Define the entry trigger condition precisely (e.g. "close above X on volume > Y").
5. Label the setup type: Breakout / Pullback-to-support / Range-fade / Reversal / Continuation.
Never give vague levels like "around support" — give the exact price."""

# ── Trader ────────────────────────────────────────────────────────────────────
TRADER_SYS = """You are a Senior Portfolio Manager at a multi-strategy hedge fund running long/short equity and derivatives.
Your trade recommendations are used for live capital deployment. You produce two-layer recommendations:
  Layer 1 — Directional equity trade with exact entry/exit/risk parameters and R:R
  Layer 2 — Options overlay for asymmetric risk/reward (Bull Call Spread, Put hedge, Straddle, etc.)
Rules:
1. All price levels must be specific numbers, not ranges.
2. State the exact entry trigger condition (not just "buy here").
3. Options layer must specify: structure · strike · expiry · net debit/credit · max profit · max loss.
4. Include a 3-scenario probability matrix.
5. State conviction as a percentage and explain the edge."""

# ── Risk ──────────────────────────────────────────────────────────────────────
RISK_SYS = """You are the Chief Risk Officer at a multi-billion dollar hedge fund.
Your position sizing methodology: modified Kelly Criterion capped at firm risk limits.
Rules:
1. Show all intermediate calculation steps (risk per unit → units → position value → portfolio %).
2. Calculate portfolio impact at each TP and at stop-loss.
3. Compute Expected Value (EV) = (Win% × avg gain) − (Loss% × avg loss). Flag if EV < 0.
4. Assess liquidity: can we exit the full position in 1 trading day without moving the market?
5. Trade Viability Rating: OPTIMAL / ACCEPTABLE / REDUCE SIZE / AVOID — with specific reasoning."""


class Scout(BaseAgent):
    def __init__(self):
        super().__init__("Scout", "🎯", "MTF Market Scanner", MODEL_FAST)

    def scan_mtf(self, ticker: str, technicals: dict, mtf: dict, timeframe: str = "swing") -> str:
        p = technicals.get("current_price", 0)
        confluence = mtf.get("confluence", {})

        tf_order  = ["1mo", "1w", "1d", "4h", "1h", "15m"]
        tf_labels = {
            "1mo": "Monthly", "1w": "Weekly", "1d": "Daily",
            "4h": "4H", "1h": "1H", "15m": "15M",
        }
        rows = []
        for tf in tf_order:
            d = mtf.get(tf, {})
            if not d.get("available", True) or "trend_th" not in d:
                rows.append(f"  [{tf:>3s}] {tf_labels.get(tf,'')}: No data")
                continue
            rsi_str = f"RSI {d['rsi']:.0f}" if d.get("rsi") else "RSI —"
            rows.append(
                f"  [{tf:>3s}] {tf_labels.get(tf,''):7s} | {d.get('trend_en', d.get('trend_th','?')):16s} | "
                f"{rsi_str:8s} {d.get('rsi_zone_en', d.get('rsi_zone_th','')):14s} | "
                f"{d.get('macd_signal_en', d.get('macd_signal_th','?')):22s} | "
                f"{d.get('bias_dot','?')} {d.get('bias_en', d.get('bias_th','?'))}"
            )

        mtf_block   = "\n".join(rows)
        conf_signal = confluence.get("signal_en", confluence.get("signal_th", "?"))
        bull_pct    = confluence.get("bull_pct", 0)
        bear_pct    = confluence.get("bear_pct", 0)

        prompt = f"""Perform a professional top-down MTF technical analysis on {ticker} for {timeframe} trading.

══ MULTI-TIMEFRAME DATA ══
Overall Confluence: {conf_signal}  (Bull {bull_pct:.0f}% / Bear {bear_pct:.0f}%)
Timeframes available: {', '.join(confluence.get('tfs', []))}

{mtf_block}

══ CURRENT PRICE ACTION ══
Price {p} | 1D {technicals.get('change_1d_pct')}% | 5D {technicals.get('change_5d_pct')}%
High {technicals.get('high')} / Low {technicals.get('low')} | 52W High {technicals.get('high_52w')} / Low {technicals.get('low_52w')}
Volume {technicals.get('volume') or 0:,} (×{technicals.get('volume_ratio') or 0:.2f} vs 20D avg)
ATR(14) {technicals.get('atr')} | RSI(14) {technicals.get('rsi')}
SMA20 {technicals.get('sma20')} | SMA50 {technicals.get('sma50')} | SMA200 {technicals.get('sma200')}
BB Upper {technicals.get('bb_upper')} / Lower {technicals.get('bb_lower')}

REQUIRED OUTPUT — use exact headers:

## WYCKOFF PHASE ANALYSIS
Primary trend structure (Monthly/Weekly): [Phase + evidence]
Intermediate structure (Daily/4H): [Phase + evidence, aligned or diverging?]

## INSTITUTIONAL PRICE LEVELS
Key Resistance levels (specify exact prices, explain why each matters):
  R1: ___  |  R2: ___  |  R3: ___
Key Support levels:
  S1: ___  |  S2: ___  |  S3: ___
VWAP / Volume-based level (if applicable): ___

## MTF CONFLUENCE SCORE
{bull_pct:.0f}% bullish / {bear_pct:.0f}% bearish — interpretation:
Highest-confidence timeframe alignment: ___
Conflicting signals (if any): ___

## SETUP CLASSIFICATION
Type: Breakout / Pullback-to-support / Range-fade / Reversal / Continuation
Confidence: HIGH / MEDIUM / LOW
Pattern: [Specific pattern name + location]

## ENTRY TRIGGER (exact conditions, not approximations)
Entry condition: ___
Confirmation required: ___
Entry price zone: ___ – ___

## STOP LOSS PLACEMENT
Stop: ___  |  Logic: [Why this level invalidates the setup]
ATR-based stop (1.5× ATR from entry): ___

## PRICE TARGETS (technical basis)
TP1: ___ (next resistance / measured move)
TP2: ___ (major resistance / 52W range extension)
TP3: ___ (extension target)

## EXECUTION PLAN
Right now the market is: [assessment]
Recommended action: [specific, actionable, immediate]"""

        return self.run(SCOUT_SYS, prompt, max_tokens=1100)

    def scan(self, ticker: str, technicals: dict, timeframe: str = "swing") -> str:
        """Fallback when MTF data is unavailable."""
        p = technicals.get("current_price", 0)
        prompt = f"""Perform a professional technical analysis on {ticker} for {timeframe} trading.
(Note: Multi-timeframe data unavailable — use single-timeframe data below.)

TECHNICAL DATA:
Price {p} | 1D {technicals.get('change_1d_pct')}% | 5D {technicals.get('change_5d_pct')}%
High {technicals.get('high')} / Low {technicals.get('low')}
Volume {technicals.get('volume') or 0:,} (×{technicals.get('volume_ratio') or 0:.2f})
RSI(14) {technicals.get('rsi')} | MACD Hist {technicals.get('macd_hist')}
SMA20 {technicals.get('sma20')} | SMA50 {technicals.get('sma50')} | SMA200 {technicals.get('sma200')}
BB Upper {technicals.get('bb_upper')} / Mid {technicals.get('bb_mid','N/A')} / Lower {technicals.get('bb_lower')}
ATR(14) {technicals.get('atr')} | 52W High {technicals.get('high_52w')} / Low {technicals.get('low_52w')}

## TREND STRUCTURE
Primary trend: [Uptrend / Downtrend / Sideways] | Strength: [Strong / Moderate / Weak]
Evidence: [specific price levels confirming trend]

## KEY LEVELS
Resistance: R1 ___ | R2 ___ | R3 ___
Support:    S1 ___ | S2 ___ | S3 ___

## SETUP & MOMENTUM
Pattern: ___ | RSI status: ___ | Volume confirmation: Y/N
Setup quality: HIGH / MEDIUM / LOW

## ENTRY TRIGGER
Entry condition (exact): ___  |  Entry zone: ___ – ___
Stop: ___  |  TP1: ___ | TP2: ___ | TP3: ___

## EXECUTION PLAN
Recommended action right now: ___"""

        return self.run(SCOUT_SYS, prompt, max_tokens=900)


class Trader(BaseAgent):
    def __init__(self):
        super().__init__("Trader", "📈", "Trade Signal Generator", MODEL_FAST)

    def generate_signal(self, ticker: str, scan: str, research_summary: str, technicals: dict) -> str:
        price = technicals.get("current_price", 0)
        atr   = technicals.get("atr", 0)

        prompt = f"""Generate a professional two-layer trade recommendation for {ticker}.

Current Price: {price} | ATR(14): {atr}

Scout's Technical Analysis:
{scan[:900]}

Fundamental context:
{research_summary[:400]}

━━━ REQUIRED TRADE CARD FORMAT ━━━

## SETUP SUMMARY
Pattern: ___ | Timeframe: ___ | Quality: HIGH / MEDIUM / LOW

─────────────────────────────────────────────────────────
LAYER 1 — DIRECTIONAL EQUITY TRADE
─────────────────────────────────────────────────────────
Direction:  LONG (Buy) / SHORT (Sell)
Entry Zone: ___ – ___
Entry Trigger (exact condition): ___

Stop Loss:  ___ | Distance: -___% from entry | Basis: ATR / Structure
  → 1.5× ATR stop = {price - 1.5*(atr or 0):.2f} (long) / {price + 1.5*(atr or 0):.2f} (short)

TP1: ___  (+___%)  R:R = ___
TP2: ___  (+___%)  R:R = ___
TP3: ___  (+___%)  R:R = ___

Partial profit plan: Take ___% at TP1, trail remainder to ___
Max holding period: ___

─────────────────────────────────────────────────────────
LAYER 2 — OPTIONS OVERLAY
─────────────────────────────────────────────────────────
Strategy: [Bull Call Spread / Long Call / Protective Put / Straddle / etc.]
Structure: Buy ___ / Sell ___  |  Expiry: ___  |  Net Cost: ___
Max Profit: ___ | Max Loss: ___ | Breakeven at expiry: ___
[Write "OPTIONS LAYER: N/A — use equity only" if not appropriate]

─────────────────────────────────────────────────────────
SCENARIO MATRIX
─────────────────────────────────────────────────────────
Bull scenario  (___% prob): price → ___  |  Action: ___
Base scenario  (___% prob): price → ___  |  Action: ___
Bear/Stop      (___% prob): price → ___  |  Action: ___

─────────────────────────────────────────────────────────
TRADE MANAGEMENT
─────────────────────────────────────────────────────────
Invalidation: Trade is CANCELLED if ___
Catalyst to watch: ___

HEDGE FUND CONVICTION
Confidence: ___%
Edge: [1 sentence explaining why this trade has positive expected value]"""

        return self.run(TRADER_SYS, prompt, max_tokens=1000)


class Risk(BaseAgent):
    def __init__(self):
        super().__init__("Risk", "🛡️", "Risk Manager", MODEL_LITE)

    def size_position(self, ticker: str, trade_card: str, portfolio_size: float, risk_pct: float = 2.0) -> str:
        risk_amount = portfolio_size * risk_pct / 100

        prompt = f"""Calculate position sizing for this trade using hedge fund risk management standards.

TRADE CARD:
{trade_card}

PORTFOLIO PARAMETERS:
Portfolio Value: {portfolio_size:,.0f}
Max risk per trade: {risk_pct}% = {risk_amount:,.0f}

━━━ REQUIRED OUTPUT ━━━

## POSITION SIZING CALCULATION
Step 1 — Risk per unit (Entry midpoint − Stop Loss): ___
Step 2 — Units = Max risk ÷ Risk per unit: ___
Step 3 — Position value (Units × Entry price): ___
Step 4 — Portfolio allocation %: ___
Step 5 — Liquidity check: Position size vs avg daily volume — can exit in <1 day? Y/N

## P&L PROJECTION
           | Price  | P&L (___units) | Portfolio impact
TP1 hit    | ___    | +___           | +___% portfolio
TP2 hit    | ___    | +___           | +___% portfolio
TP3 hit    | ___    | +___           | +___% portfolio
Stop hit   | ___    | -___           | -{risk_pct}% portfolio

## EXPECTED VALUE ANALYSIS
Win rate assumption (from Scout confidence): ___%
EV = (Win% × avg TP) − (Loss% × Stop distance) = ___
EV per unit of risk: ___  [Positive = proceed | Negative = DO NOT TRADE]

## KELLY CRITERION
Full Kelly: ___% of portfolio
Suggested (half-Kelly for risk management): ___% → ___units
Comparison to rule-based size (Step 2): [take the smaller of the two]

## TRADE VIABILITY RATING
Rating: OPTIMAL ✅ / ACCEPTABLE ⚠️ / REDUCE SIZE ⚡ / AVOID ❌
Reasoning: [specific justification with numbers]
Final recommended position: ___ units ({risk_pct}% risk budget {'fully' if True else 'partially'} deployed)"""

        return self.run(RISK_SYS, prompt, max_tokens=800)

from .base import BaseAgent, MODEL_FAST, MODEL_LITE

# ── Scout ─────────────────────────────────────────────────────────────────────
SCOUT_SYS = """You are a CMT Level 3 technical analyst and former prop trader with 20 years on the desk.
Your MTF analysis framework: Wyckoff phases → institutional supply/demand zones → price action confirmation.
Rules:
1. Identify the Wyckoff phase for the primary timeframe (Accumulation / Distribution / Markup / Markdown / Re-accumulation).
2. Specify exact support and resistance levels — not ranges, specific prices.
3. State the MTF confluence score (% of timeframes aligned bullish/bearish).
4. Define the entry trigger condition precisely (e.g. "close above X on volume > Y" OR "break below Y on volume > Z").
5. Label the setup type: Breakout / Pullback-to-support / Range-fade / Reversal / Continuation.
6. CRITICAL — Direction is DATA-DRIVEN: If MTF confluence is ≥55% bearish, build a SHORT setup. If ≥55% bullish, build a LONG setup. If 45–54% either way, declare NO TRADE.
7. NEVER default to LONG simply because it is the conventional direction. Price targets for LONG are resistances above entry; price targets for SHORT are supports below entry.
Never give vague levels like "around support" — give the exact price.

SUPPORT / RESISTANCE LABELING RULE (mandatory — applies to ALL levels, Fibonacci or otherwise):
  Level > current_price  →  RESISTANCE only. Never call it support.
  Level < current_price  →  SUPPORT only. Never call it resistance.
  If price is near the 52W Low (within 20% of the range above low): the 52W Low IS the primary support.
  Fibonacci levels above current price are resistance targets, not support levels."""

# ── Trader ────────────────────────────────────────────────────────────────────
TRADER_SYS = """You are a Senior Portfolio Manager at a multi-strategy hedge fund running long/short equity and derivatives.
Your trade recommendations are used for live capital deployment. You produce two-layer recommendations:
  Layer 1 — Directional equity trade with exact entry/exit/risk parameters and R:R
  Layer 2 — Options overlay for asymmetric risk/reward (Bull Call Spread, Put hedge, Straddle, etc.)
Rules:
1. All price levels must be specific numbers, not ranges.
2. State the exact entry trigger condition (not just "buy here" or "sell here").
3. Options layer must specify: structure · strike · expiry · net debit/credit · max profit · max loss.
4. Include a 3-scenario probability matrix.
5. State conviction as a percentage and explain the edge.
6. CRITICAL — FOLLOW SCOUT'S DIRECTION. If Scout says SHORT, your card MUST be SHORT. Do NOT flip to LONG.
7. For LONG trades: Stop = Entry − 1.5×ATR (support-based). For SHORT trades: Stop = Entry + 1.5×ATR (resistance-based). TPs for LONG are above entry; TPs for SHORT are below entry. R:R is always positive.
8. If Scout declares NO TRADE, state "NO TRADE — insufficient edge" and explain why.
9. R:R GATE — before finalising Confidence %:
   Compute TP1 R:R = (TP1 − Entry) ÷ (Entry − Stop)  [LONG]  or  (Entry − TP1) ÷ (Stop − Entry)  [SHORT].
   If TP1 R:R < 1.0: label the trade "⚠️ SUB-OPTIMAL ENTRY" immediately after the setup summary,
   explain why R:R is below 1:1, and CAP your Confidence at 60% maximum.
   If TP1 R:R ≥ 1.0: proceed normally, no cap."""

# ── Risk ──────────────────────────────────────────────────────────────────────
RISK_SYS = """You are the Chief Risk Officer at a multi-billion dollar hedge fund.
Your position sizing methodology: modified Kelly Criterion capped at firm risk limits.
Rules:
1. Show all intermediate calculation steps (risk per unit → units → position value → portfolio %).
   POSITION SIZING FORMULA (mandatory — no substitutions):
     risk_per_unit  = |entry_price − stop_price|  (in dollars/points — NOT a percentage)
     max_risk_$     = portfolio_value × risk_pct / 100
     units          = max_risk_$ ÷ risk_per_unit
   Example: entry=60,000  stop=57,178  →  risk_per_unit=2,822  |  max_risk$=2,000  →  units=0.71
   NEVER write "use max risk per unit instead" or skip the dollar-per-unit step.
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

        # Determine direction label for the prompt
        _dir_hint = (
            "LONG (bullish confluence dominant)"   if bull_pct >= 55 else
            "SHORT (bearish confluence dominant)"  if bear_pct >= 55 else
            "NO TRADE (confluence too mixed for a directional bet)"
        )

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

REQUIRED OUTPUT — use exact headers in this order:

## ① TRADE DIRECTION  ← fill this FIRST before any other section
Confluence verdict: Bull {bull_pct:.0f}% / Bear {bear_pct:.0f}%
Suggested direction: {_dir_hint}
Final direction chosen: LONG / SHORT / NO TRADE  (state your reasoning in 1 sentence)
If NO TRADE → explain what would need to change to generate a valid setup, then skip sections ③–⑥.

## ② WYCKOFF PHASE ANALYSIS
Primary trend structure (Monthly/Weekly): [Phase + evidence]
Intermediate structure (Daily/4H): [Phase + evidence, aligned or diverging?]

## ③ INSTITUTIONAL PRICE LEVELS
Key Resistance levels (exact prices):  R1: ___ | R2: ___ | R3: ___
Key Support levels (exact prices):     S1: ___ | S2: ___ | S3: ___

## ④ SETUP CLASSIFICATION
Type: Breakout / Pullback / Reversal / Continuation / Distribution / Capitulation
Confidence: HIGH / MEDIUM / LOW
Pattern: [Specific pattern name + location]

## ⑤ ENTRY & RISK  (use direction from ①)
[LONG]  Entry zone: ___ – ___ | Trigger: close above ___ on volume > avg
         Stop = structural support or {p - 1.5*(technicals.get('atr') or 0):.4g} (1.5× ATR) — whichever is tighter
         TP1: ___ (next resistance)  TP2: ___  TP3: ___  | R:R at TP1: ___
[SHORT] Entry zone: ___ – ___ | Trigger: close below ___ on volume > avg
         Stop = structural resistance or {p + 1.5*(technicals.get('atr') or 0):.4g} (1.5× ATR) — whichever is tighter
         TP1: ___ (next support)  TP2: ___  TP3: ___  | R:R at TP1: ___
(Fill only the applicable direction from ①)

## ⑥ EXECUTION PLAN
Right now the market is: [assessment]
Recommended action: [specific, actionable, immediate — BUY / SELL SHORT / WAIT]

---
## 🇹🇭 สรุปภาษาไทย — สัญญาณ Technical
**ทิศทาง:** LONG (ซื้อ) / SHORT (ขายชอร์ต) / NO TRADE (รอดู) — [เหตุผล 1 ประโยค]
**Phase Wyckoff:** [สะสม / แจกจ่าย / ขาขึ้น / ขาลง / สะสมใหม่] — [หลักฐานสั้นๆ]
**แนวต้านสำคัญ:** R1 ___ | R2 ___ | R3 ___
**แนวรับสำคัญ:** S1 ___ | S2 ___ | S3 ___
**จุดเข้า:** ___ – ___ | **เงื่อนไข:** ___
**Stop Loss:** ___ | **เป้าหมาย:** TP1 ___ | TP2 ___ | TP3 ___
**แนะนำตอนนี้:** [ซื้อ ณ ___ / ขายชอร์ต ณ ___ / รอสัญญาณยืนยัน — ระบุราคาชัดเจน]"""

        return self.run(SCOUT_SYS, prompt, max_tokens=1300)

    def scan(self, ticker: str, technicals: dict, timeframe: str = "swing") -> str:
        """Fallback when MTF data is unavailable."""
        p = technicals.get("current_price", 0)
        # Infer direction from single-timeframe indicators
        _rsi   = technicals.get("rsi") or 50
        _above200 = technicals.get("above_sma200")
        _macd_h = technicals.get("macd_hist") or 0
        _single_bias = "bullish" if (_above200 and _macd_h > 0 and _rsi > 50) else \
                       "bearish" if (not _above200 and _macd_h < 0 and _rsi < 50) else "mixed"
        _dir_hint2 = (
            "LONG"     if _single_bias == "bullish" else
            "SHORT"    if _single_bias == "bearish" else
            "NO TRADE"
        )

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

REQUIRED OUTPUT — use exact headers:

## ① TRADE DIRECTION  ← fill this FIRST
Indicator alignment: {_single_bias.upper()} bias (RSI {_rsi:.0f}, MACD {'positive' if _macd_h > 0 else 'negative'}, {'above' if _above200 else 'below'} SMA200)
Suggested direction: {_dir_hint2}
Final direction: LONG / SHORT / NO TRADE (state your 1-sentence reasoning)
If NO TRADE → explain what change would create a valid setup, then skip ③–④.

## ② TREND STRUCTURE
Primary trend: [Uptrend / Downtrend / Sideways] | Strength: [Strong / Moderate / Weak]
Evidence: [specific price levels confirming trend]

## ③ KEY LEVELS & SETUP
Resistance: R1 ___ | R2 ___ | R3 ___
Support:    S1 ___ | S2 ___ | S3 ___
Pattern: ___ | Setup quality: HIGH / MEDIUM / LOW

## ④ ENTRY & RISK  (direction-matched)
[LONG]  Entry: ___ – ___ | Trigger: ___ | Stop: ___ | TP1: ___ | TP2: ___ | R:R: ___
[SHORT] Entry: ___ – ___ | Trigger: ___ | Stop: ___ | TP1: ___ | TP2: ___ | R:R: ___
(Fill only the applicable direction from ①)

## ⑤ EXECUTION PLAN
Recommended action right now: [BUY / SELL SHORT / WAIT — be specific]

---
## 🇹🇭 สรุปภาษาไทย — สัญญาณ Technical
**ทิศทาง:** LONG (ซื้อ) / SHORT (ขายชอร์ต) / NO TRADE (รอดู) — [เหตุผล 1 ประโยค]
**แนวโน้ม:** [ขาขึ้น/ขาลง/Sideways] ความแข็งแกร่ง: [แรง/กลาง/อ่อน]
**แนวต้าน:** R1 ___ | R2 ___ &nbsp; **แนวรับ:** S1 ___ | S2 ___
**จุดเข้า:** ___ – ___ | **Stop:** ___ | **TP1:** ___ | **TP2:** ___
**แนะนำตอนนี้:** [ซื้อ / ขายชอร์ต / รอ — ระบุราคาชัดเจน]"""

        return self.run(SCOUT_SYS, prompt, max_tokens=1100)


class Trader(BaseAgent):
    def __init__(self):
        super().__init__("Trader", "📈", "Trade Signal Generator", MODEL_FAST)

    def generate_signal(self, ticker: str, scan: str, research_summary: str, technicals: dict) -> str:
        price = technicals.get("current_price", 0)
        atr   = technicals.get("atr", 0)

        long_stop  = round(price - 1.5 * (atr or 0), 4)
        short_stop = round(price + 1.5 * (atr or 0), 4)

        prompt = f"""Generate a professional two-layer trade recommendation for {ticker}.
IMPORTANT: Read Scout's direction from section ① of the analysis below and FOLLOW IT exactly.
If Scout says SHORT → your trade card MUST be SHORT. If NO TRADE → state that and stop.

Current Price: {price} | ATR(14): {atr}
ATR reference stops: LONG stop = {long_stop} (entry − 1.5×ATR) | SHORT stop = {short_stop} (entry + 1.5×ATR)

Scout's Technical Analysis (direction is stated in section ①):
{scan[:1000]}

Fundamental context:
{research_summary[:400]}

━━━ REQUIRED TRADE CARD FORMAT ━━━

## SETUP SUMMARY
Direction: [LONG / SHORT / NO TRADE — copied from Scout's section ①]
Pattern: ___ | Timeframe: ___ | Quality: HIGH / MEDIUM / LOW

─────────────────────────────────────────────────────────
LAYER 1 — DIRECTIONAL EQUITY TRADE
─────────────────────────────────────────────────────────
Direction:  LONG (Buy) / SHORT (Sell to open)   ← must match Scout
Entry Zone: ___ – ___
Entry Trigger (exact condition): ___

Stop Loss:  ___
  Basis: [structure level / ATR — cite specific price and logic]
  Distance from entry: ___% | Max acceptable loss per unit: ___

TP1: ___  (___% from entry)  R:R = ___    ← TPs ABOVE entry if LONG; BELOW entry if SHORT
TP2: ___  (___% from entry)  R:R = ___
TP3: ___  (___% from entry)  R:R = ___

Partial profit plan: Take ___% at TP1, trail remainder to ___
Max holding period: ___

─────────────────────────────────────────────────────────
LAYER 2 — OPTIONS OVERLAY
─────────────────────────────────────────────────────────
Strategy: [Bull Call Spread / Bear Put Spread / Long Put / Straddle / etc. — match direction]
Structure: Buy ___ / Sell ___  |  Expiry: ___  |  Net Cost: ___
Max Profit: ___ | Max Loss: ___ | Breakeven: ___
[Write "OPTIONS LAYER: N/A — use equity only" if options not appropriate]

─────────────────────────────────────────────────────────
SCENARIO MATRIX
─────────────────────────────────────────────────────────
Bull scenario  (___% prob): price → ___  |  Action: ___
Base scenario  (___% prob): price → ___  |  Action: ___
Bear scenario  (___% prob): price → ___  |  Action: ___

─────────────────────────────────────────────────────────
TRADE MANAGEMENT
─────────────────────────────────────────────────────────
Invalidation: Trade is CANCELLED if ___
Catalyst to watch: ___

HEDGE FUND CONVICTION
Confidence: ___%
Edge: [1 sentence — why does this trade have a positive expected value?]

---
## 🇹🇭 Trade Card ภาษาไทย
**ทิศทาง:** LONG ซื้อ / SHORT ขายชอร์ต | **คุณภาพ Setup:** สูง/กลาง/ต่ำ
**โซนเข้า:** ___ – ___ | **เงื่อนไขเข้า:** ___
**Stop Loss:** ___ (-___% จากจุดเข้า) | **เหตุผล Stop:** ___
**เป้าหมายกำไร:**
  • TP1: ___ (+___%) R:R = ___ → รับกำไร ___% ที่นี่
  • TP2: ___ (+___%) R:R = ___
  • TP3: ___ (+___%) R:R = ___
**Options:** [กลยุทธ์ภาษาไทย หรือ "ใช้ Equity อย่างเดียว"]
**สถานการณ์:** 📈 ดี (___%) → ___ | ➡️ พื้นฐาน (___%) → ___ | 📉 เลวร้าย (___%) → ___
**ความเชื่อมั่น:** ___% — [เหตุผล 1 ประโยค ว่าทำไม trade นี้มี edge]
**ยกเลิก Trade หาก:** ___"""

        return self.run(TRADER_SYS, prompt, max_tokens=1250)


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
Step 1 — risk_per_unit = |entry_price − stop_price| in dollars/points (NOT a %).
          Extract the exact entry and stop from the trade card above. Subtract. Show the arithmetic.
          Example format: risk_per_unit = |60,000 − 57,178| = 2,822
Step 2 — max_risk_$ = {risk_amount:,.0f}  (given above)
Step 3 — units = max_risk_$ ÷ risk_per_unit = {risk_amount:,.0f} ÷ [Step 1 result] = ___
Step 4 — Position value = units × entry_price: ___
Step 5 — Portfolio allocation %: ___
Step 6 — Liquidity check: Position size vs avg daily volume — can exit in <1 day? Y/N

## P&L PROJECTION
           | Price  | P&L (___units) | Portfolio impact
TP1 hit    | ___    | +___           | +___% portfolio
TP2 hit    | ___    | +___           | +___% portfolio
TP3 hit    | ___    | +___           | +___% portfolio
Stop hit   | ___    | -___           | -{risk_pct}% portfolio

## EXPECTED VALUE ANALYSIS
Use the 3-scenario matrix from the Trade Card above. EV = Σ(probability × return_per_scenario).
Direction note: for LONG, profit = TP − Entry (positive when price rises).
               For SHORT, profit = Entry − TP (positive when price FALLS).
               Loss scenario: always negative (stop hit).

Show all three lines:
  Bull  (___% prob): return = ___ per unit  →  contribution = ___% × ___ = ___
  Base  (___% prob): return = ___ per unit  →  contribution = ___% × ___ = ___
  Bear  (___% prob): return = ___ per unit  →  contribution = ___% × ___ = ___
  EV per unit = sum of three contributions = ___
[Positive EV → proceed | Zero/Negative → DO NOT TRADE]
Do NOT use (win% × TP) × 2 or any shortcut. Show the full three-line calculation above.

## KELLY CRITERION
Full Kelly: ___% of portfolio
Suggested (half-Kelly for risk management): ___% → ___units
Comparison to rule-based size (Step 2): [take the smaller of the two]

## TRADE VIABILITY RATING
Rating: OPTIMAL ✅ / ACCEPTABLE ⚠️ / REDUCE SIZE ⚡ / AVOID ❌
Reasoning: [specific justification with numbers]
Final recommended position: ___ units ({risk_pct}% risk budget deployed)"""

        return self.run(RISK_SYS, prompt, max_tokens=800)

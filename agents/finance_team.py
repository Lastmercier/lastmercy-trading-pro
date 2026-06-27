import json
from .base import BaseAgent, MODEL_FAST, MODEL_LITE

# ── Wizard ────────────────────────────────────────────────────────────────────
REESE_SYS = """You are a Managing Director at a bulge-bracket bank (Goldman Sachs / Morgan Stanley calibre) with 20 years covering equities.
You write institutional research notes that portfolio managers stake real capital on.
Non-negotiable rules:
1. Every claim must cite a specific number from the data provided.
2. Structure output with clear headers — no prose walls.
3. Include a Scenario Table (Bull/Base/Bear) with explicit price targets AND probabilities.
4. Quantify all risks (likelihood H/M/L × magnitude H/M/L).
5. End with a single clear Recommendation line (rating · target · conviction).
Output must read like an initiation note, not a summary.

MANDATORY THRESHOLDS (override any shorthand you use elsewhere):
• RSI OVERSOLD = RSI < 30 ONLY. RSI 37 = "approaching oversold / weak momentum" — NEVER write "oversold".
  RSI OVERBOUGHT = RSI > 70 ONLY. Use the exact RSI value from the DATA BLOCK above.
• ATR is in the same price units as the asset. ATR ÷ Price should be 0.5–12%.
  If a volatility or VaR figure implies > 15% daily move, flag it as implausible.
• 52W High/Low come from the DATA BLOCK — use verbatim, never invent or adjust."""

# ── Sage ──────────────────────────────────────────────────────────────────────
MAX_SYS = """You are a Partner at a top activist short-selling hedge fund (Muddy Waters / Hindenburg calibre).
Your trade thesis has to survive a partner meeting and a compliance review.
Non-negotiable rules:
1. Open with one deadly-specific primary short thesis sentence.
2. Enumerate exactly 3 bear cases — each with probability %, downside magnitude %, and the exact catalyst that triggers it.
3. Identify at least one financial red flag with the precise metric and threshold that concerns you.
4. Name the single biggest flaw in the bull thesis.
5. Provide an explicit bear-case price target with a step-by-step path to reach it.
Never write "there could be risks" — name the risk, size it, and date it."""

# ── Priest ────────────────────────────────────────────────────────────────────
VERA_SYS = """You are a Senior Research Integrity Officer at a Tier-1 asset manager.
Your job: forensically audit every number and claim before the note goes to the portfolio committee.
Rules:
1. Cross-reference every cited metric against the raw data block.
2. Flag mismatches as: [CORRECTION: stated X → actual Y].
3. Score Data Confidence 1–10; deduct 1 point per unsupported claim or arithmetic error, explain each deduction.
4. List any critical data gaps that would change the analysis.
5. Final line: CLEARED FOR COMMITTEE / REQUIRES REVISION.

CRITICAL AUDIT PROTOCOLS — an audit layer that introduces errors is worse than no audit:

RULE A — SHOW WORKING BEFORE ANY CORRECTION (mandatory):
Before writing any [CORRECTION], you MUST first show your recomputation:
  Format: [recompute: <numerator> / <denominator> = <result>]
  Example: [recompute: 2,056.74 / 60,049 = 0.03424 = 3.42%]
  If recompute confirms the stated value → write "verified ✓" and DO NOT flag a correction.
  Flagging a correction without recompute working is prohibited.

RULE B — DECIMAL-SHIFT SANITY CHECK (stop and re-verify):
If the value you plan to "correct TO" is exactly 10× or 0.1× the value you are "correcting FROM":
  STOP — this is the signature of a decimal-place error in YOUR OWN calculation, not the analyst's.
  Re-verify by a different method (e.g., check the plausibility range) before proceeding.
  Classic example of this error: analyst states ATR% = 3.42%; you "correct" to 0.34%.
  3.42% × 0.1 = 0.342% — that is YOUR decimal shift. The analyst was correct. Do not flag it.

RULE C — ATR% PLAUSIBILITY RANGE:
ATR ÷ Price should be 0.5%–12% for any liquid financial asset.
If the stated or computed ATR% is within this range, it is NOT an error.
If your computed ATR% is OUTSIDE this range, you likely have a unit error yourself.
The AUTHORITY DATA REFERENCE includes a pre-computed ATR% — use it directly rather than recomputing."""


class Reese(BaseAgent):
    def __init__(self):
        super().__init__("Wizard", "🔍", "Research Analyst", MODEL_FAST)

    def research(self, ticker: str, info: dict, technicals: dict, news: list) -> str:
        news_lines = "\n".join(f"  • {n['title']} — {n['publisher']}" for n in news[:5])
        _mcap = info.get('market_cap')
        mcap_str = f"{_mcap:,}" if isinstance(_mcap, (int, float)) else "N/A"

        # Helper to format pct values
        # NOTE: info dict stores margins/ROE already in percent form via _pct()
        # e.g. roe=15.5 means 15.5%, do NOT multiply by 100 again.
        def _p(v):
            if v is None: return "N/A"
            try: return f"{float(v):.1f}%"
            except: return str(v)

        prompt = f"""Write an institutional equity research brief on {ticker} ({info.get('company', ticker)}).

━━━ DATA BLOCK ━━━
PRICE & MARKET:
  Price {info.get('current_price')} {info.get('currency','USD')} | MCap {mcap_str}
  Sector: {info.get('sector')} | Industry: {info.get('industry')}
  52W High {info.get('52w_high')} / Low {info.get('52w_low')} | Beta {info.get('beta')}
  Analyst Target {info.get('analyst_target')} ({info.get('recommendation','N/A')})

VALUATION:
  P/E {info.get('pe_ratio')} | Fwd P/E {info.get('forward_pe')} | P/B {info.get('pb_ratio')}
  EV/EBITDA {info.get('ev_ebitda','N/A')} | PEG {info.get('peg_ratio','N/A')}

QUALITY & GROWTH:
  ROE {_p(info.get('roe'))} | Net Margin {_p(info.get('net_margin'))} | Op Margin {_p(info.get('operating_margin','N/A'))}
  Revenue Growth {_p(info.get('revenue_growth'))} | Earnings Growth {_p(info.get('earnings_growth'))}
  Debt/Equity {info.get('debt_equity')} | FCF {info.get('free_cashflow','N/A')}

TECHNICALS:
  RSI(14) {technicals.get('rsi')} | MACD Hist {technicals.get('macd_hist')} | ATR {technicals.get('atr')}
  SMA20 {technicals.get('sma20')} | SMA50 {technicals.get('sma50')} | SMA200 {technicals.get('sma200')}
  Volume {technicals.get('volume') or 0:,} vs 20D avg {technicals.get('avg_volume_20d') or 0:,} (×{technicals.get('volume_ratio')})
  1D {technicals.get('change_1d_pct')}% | 5D {technicals.get('change_5d_pct')}%
  BB Upper {technicals.get('bb_upper')} / Lower {technicals.get('bb_lower')}

NEWS (last 5):
{news_lines}
━━━ END DATA ━━━

REQUIRED OUTPUT — use these exact headers:

## INVESTMENT THESIS
Three specific, number-backed reasons to own or avoid this stock:
1.
2.
3.

## VALUATION
- P/E {info.get('pe_ratio')} context: vs historical / sector peers → CHEAP / FAIR / EXPENSIVE
- Implied upside to analyst target {info.get('analyst_target')}: ____%
- Most important valuation risk: [1 sentence]

## SCENARIO ANALYSIS
Bull  (prob __%)  Target ___  |  Key catalyst:  |  Timeline:
Base  (prob __%)  Target ___  |  Key catalyst:  |  Timeline:
Bear  (prob __%)  Target ___  |  Key catalyst:  |  Timeline:

## FINANCIAL QUALITY SCORECARD  (rate 1–5, give 1-line rationale)
Revenue Growth ({_p(info.get('revenue_growth'))}):   __/5
Profitability  ({_p(info.get('net_margin'))} margin): __/5
Balance Sheet  (D/E {info.get('debt_equity')}):       __/5
Capital Return (ROE {_p(info.get('roe'))}):           __/5

## UPCOMING CATALYSTS  (next 60–90 days, 2–3 items)
-
-

## TOP 3 RISKS
1. Risk | Likelihood: H/M/L | Impact: H/M/L | Mitigant:
2. Risk | Likelihood: H/M/L | Impact: H/M/L | Mitigant:
3. Risk | Likelihood: H/M/L | Impact: H/M/L | Mitigant:

## RECOMMENDATION
Rating: STRONG BUY / BUY / HOLD / SELL / STRONG SELL
12-Month Price Target: ___ {info.get('currency','USD')}  (____% upside/downside from {info.get('current_price')})
Conviction: HIGH / MEDIUM / LOW
Key monitor: [The one metric to watch most closely]

---
## 🇹🇭 สรุปภาษาไทย
**ภาพรวม:** [2 ประโยค — บริษัท/สินทรัพย์นี้ทำอะไร และสถานะทางการเงินปัจจุบันเป็นอย่างไร]
**คำแนะนำ:** [STRONG BUY ซื้อแรง / BUY ซื้อ / HOLD ถือ / SELL ขาย / STRONG SELL ขายแรง] — เป้าหมาย ___ (upside/downside ___%) ความเชื่อมั่น: สูง/กลาง/ต่ำ
**เหตุผลหลัก:** [2-3 ข้อที่สนับสนุนคำแนะนำนี้ โดยอ้างตัวเลขจริงจากข้อมูล]
**ความเสี่ยงสำคัญ:** 1.___ 2.___ 3.___
**สิ่งที่ต้องติดตาม:** [ตัวชี้วัดหรือเหตุการณ์ที่สำคัญที่สุด]"""

        return self.run(REESE_SYS, prompt, max_tokens=1800)


class Max(BaseAgent):
    def __init__(self):
        super().__init__("Sage", "⚔️", "Contrarian Critic", MODEL_LITE)

    def critique(self, ticker: str, research: str) -> str:
        prompt = f"""Wizard's research on {ticker}:
{research[:1200]}

Construct the most rigorous bear thesis possible using this framework:

## PRIMARY SHORT THESIS
[One sentence. Be specific. Include a number.]

## BEAR CASE 1 — [Name this risk]
Probability: __%  |  Downside if triggered: -__%  |  Trigger event: ___
Supporting evidence (specific metrics): ___

## BEAR CASE 2 — [Name this risk]
Probability: __%  |  Downside if triggered: -__%  |  Trigger event: ___
Supporting evidence: ___

## BEAR CASE 3 — [Name this risk]
Probability: __%  |  Downside if triggered: -__%  |  Trigger event: ___
Supporting evidence: ___

## FINANCIAL RED FLAGS
List the specific metrics that concern you most (cite exact numbers from Wizard's data):
-
-

## BULL THESIS VULNERABILITY
What single assumption in Wizard's thesis is most likely to be wrong, and why?

## BEAR PRICE TARGET
Target: ___  |  Path: [2-step explanation with specific price levels]

## SHORT SQUEEZE RISK (what kills the short thesis)
Metric or event that would force covering: ___

---
## 🇹🇭 สรุปภาษาไทย — มุมมองขาลง
**ทฤษฎีขาลงหลัก:** [1 ประโยค — เหตุผลหลักที่เป็นความเสี่ยงสูงสุด พร้อมตัวเลข]
**ความเสี่ยง 3 อันดับแรก:** 1. ___ (โอกาส ___%, ลงได้ -___%) 2. ___ 3. ___
**ราคาเป้าหมายกรณีแย่:** ___ — เส้นทางลง: [2 ขั้นตอน]
**สิ่งที่จะทำให้วิเคราะห์นี้ผิด:** [เงื่อนไขที่จะพลิกกลับเป็นขาขึ้น]"""

        return self.run(MAX_SYS, prompt, max_tokens=1100)


class Vera(BaseAgent):
    def __init__(self):
        super().__init__("Priest", "✅", "Fact Auditor", MODEL_LITE)

    def fact_check(self, ticker: str, research: str, critique: str, info: dict, technicals: dict) -> str:
        # Pre-compute ATR% so Priest doesn't need to derive it (prevents decimal-shift errors)
        _atr   = technicals.get('atr')
        _price = info.get('current_price') or technicals.get('current_price')
        try:
            _atr_pct = f"{float(_atr) / float(_price) * 100:.2f}%" if _atr and _price else "N/A"
        except Exception:
            _atr_pct = "N/A"

        prompt = f"""Audit the research and critique for {ticker}.

RESEARCH (excerpt):
{research[:900]}

CRITIQUE (excerpt):
{critique[:500]}

AUTHORITATIVE DATA REFERENCE (pre-verified — use these values directly):
Price {info.get('current_price')} | P/E {info.get('pe_ratio')} | P/B {info.get('pb_ratio')} | MCap {info.get('market_cap')}
RSI {technicals.get('rsi')} | SMA200 {technicals.get('sma200')}
ATR {technicals.get('atr')} | ATR% (pre-computed: ATR÷Price) = {_atr_pct}  ← use this directly, do NOT recompute ATR%
52W High {info.get('52w_high')} | 52W Low {info.get('52w_low')}
ROE {info.get('roe')} | Net Margin {info.get('net_margin')} | D/E {info.get('debt_equity')}
Analyst Target {info.get('analyst_target')} | Revenue Growth {info.get('revenue_growth')}

AUDIT OUTPUT — use exact headers:

## VERIFIED CLAIMS
List claims that are numerically accurate (cite data point). For each numeric claim you verify,
show: [recompute: A / B = C] if applicable, then write "verified ✓".
-
-

## CORRECTIONS REQUIRED
MANDATORY FORMAT: Before each correction, show your recompute working.
  [recompute: <A> / <B> = <C>]  → only then → [CORRECTION: stated X → actual Y] + explanation
If recompute confirms the stated value → write "verified ✓, no correction needed" instead.
Decimal-shift check: if your corrected value is 10× or 0.1× the stated value, STOP and re-verify.
-
-

## UNSUPPORTED ASSERTIONS
Claims made without data backing (flag as [UNSUPPORTED]):
-

## CRITICAL DATA GAPS
What important data was missing that would strengthen or overturn the thesis?
-

## DATA CONFIDENCE SCORE
Score: __/10
Deductions: [list each deduction and reason]

## VERDICT
CLEARED FOR COMMITTEE / REQUIRES REVISION — [1-sentence rationale]

---
## 🇹🇭 ผลตรวจสอบความถูกต้อง
**คะแนนความน่าเชื่อถือ:** ___/10 [เหตุผลการหักคะแนน ถ้ามี]
**ประเด็นที่แก้ไขแล้ว:** [รายการ หรือ "ไม่มี"]
**ช่องว่างข้อมูลสำคัญ:** [ข้อมูลที่ขาดซึ่งอาจเปลี่ยนผลวิเคราะห์]
**สรุป:** [ผ่านการตรวจสอบ ✅ / ต้องแก้ไข ⚠️] — [เหตุผล 1 ประโยค]"""

        return self.run(VERA_SYS, prompt, max_tokens=850)

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional
from .base import BaseAgent, MODEL_FAST, MODEL_DEEP, MODEL_LITE

# Prepended to every voting IC agent's system prompt.
# IMPORTANT: vote goes on the FIRST LINE so Groq token truncation never cuts it off.
_VOTE_INSTRUCTION = (
    "\n\nSTRUCTURE YOUR RESPONSE EXACTLY AS FOLLOWS:\n"
    "• Line 1 (mandatory): [VOTE: BUY] or [VOTE: HOLD] or [VOTE: SELL]  ← pick exactly ONE, nothing else on this line\n"
    "• Lines 2 onward: your full analysis.\n"
    "The [VOTE:] tag MUST be the very first line of your output — no preamble, no header before it."
)

IC_ROSTER = [
    {
        "name": "CIS",
        "emoji": "🎯",
        "title": "Chief Investment Strategist (Bridgewater)",
        "system": (
            "You are the Chief Investment Strategist at Bridgewater Associates, applying Ray Dalio's All Weather framework.\n"
            "Your output must include ALL of the following:\n"
            "1. MACRO REGIME: Classify current regime (Rising/Falling Growth × Rising/Falling Inflation) with supporting evidence.\n"
            "2. ASSET POSITIONING: How does this regime favor or punish this specific asset class?\n"
            "3. TOP 2 MACRO THEMES: Name them, size their potential impact (+/-X%), give 3-month horizon.\n"
            "4. STRATEGIC CALL: Overweight / Neutral / Underweight with conviction HIGH/MED/LOW.\n"
            "5. RISK SCENARIO: The one macro event that would most forcefully reverse your call.\n"
            "Be specific with numbers. Under 300 words."
            + _VOTE_INSTRUCTION
        ),
        "votes": True,
    },
    {
        "name": "QuantRisk",
        "emoji": "📊",
        "title": "Quantitative Risk Manager (Citadel)",
        "system": (
            "You are the Head of Quantitative Risk at Citadel Securities.\n"
            "Your output must include ALL of the following:\n"
            "1. VOLATILITY REGIME: Current vol vs historical average — Low / Normal / Elevated / Extreme.\n"
            "2. DRAWDOWN ESTIMATE: Expected max drawdown in a 1-sigma adverse scenario (cite Beta and sector vol).\n"
            "3. CORRELATION RISK: How correlated is this to SPX / broad market? Diversification benefit?\n"
            "4. POSITION LIMIT: Maximum % of portfolio warranted given risk metrics (cite specific reason).\n"
            "5. VAR ESTIMATE: Rough 1-day 95% VaR as % of position value.\n"
            "6. TAIL RISK: Identify one non-linear risk (gap risk, liquidity crisis, binary event).\n"
            "All estimates must include your assumptions. Under 300 words."
            + _VOTE_INSTRUCTION
        ),
        "votes": True,
    },
    {
        "name": "Fundamental",
        "emoji": "📚",
        "title": "Fundamental Analyst (Berkshire/Buffett)",
        "system": (
            "You are a Senior Fundamental Analyst trained in the Berkshire Hathaway tradition (Buffett/Munger/Klarman).\n"
            "Your output must include ALL of the following:\n"
            "1. MOAT ASSESSMENT: Rate the competitive moat (Wide / Narrow / None) with specific evidence.\n"
            "2. INTRINSIC VALUE ESTIMATE: Use P/E-based or earnings power value method. Show your math.\n"
            "3. MARGIN OF SAFETY: (Intrinsic Value − Current Price) / Intrinsic Value = X%. Adequate (>30%) / Thin / Negative.\n"
            "4. MANAGEMENT QUALITY: Capital allocation track record — ROIC trend, buyback vs dilution history.\n"
            "5. EARNINGS QUALITY: Are earnings backed by FCF? Flag any accruals concern.\n"
            "6. BUFFETT TEST: Would Buffett buy this at today's price? Yes / No / Maybe — with specific reasoning.\n"
            "Under 300 words."
            + _VOTE_INSTRUCTION
        ),
        "votes": True,
    },
    {
        "name": "Macro",
        "emoji": "🌍",
        "title": "Global Macro Analyst (Soros/Druckenmiller)",
        "system": (
            "You are a Global Macro Partner at a Soros/Druckenmiller-style macro fund.\n"
            "Your output must include ALL of the following:\n"
            "1. MACRO THESIS: State the dominant macro force affecting this asset in 1 sentence.\n"
            "2. RATE/CURRENCY SENSITIVITY: How does this asset react to USD strength, rate moves (cite Beta to each)?\n"
            "3. GEOPOLITICAL RISK: Flag any specific geopolitical exposure (supply chains, sanctions, elections).\n"
            "4. SECTOR FLOW: Is institutional money flowing INTO or OUT OF this sector? Evidence?\n"
            "5. REFLEXIVITY CHECK (Soros): Is there a self-reinforcing narrative building? Positive or negative?\n"
            "6. MACRO CONVICTION: HIGH / MED / LOW — and the single data point you're watching most closely.\n"
            "Under 300 words."
            + _VOTE_INSTRUCTION
        ),
        "votes": True,
    },
    {
        "name": "PortfolioConstructor",
        "emoji": "⚖️",
        "title": "Portfolio Construction Specialist (Yale Endowment)",
        "system": (
            "You are the Head of Portfolio Construction at the Yale Endowment (Swensen framework).\n"
            "Your output must include ALL of the following:\n"
            "1. FACTOR EXPOSURE: Identify the dominant factors (Value, Growth, Momentum, Quality, Low-Vol). Rate each 1–5.\n"
            "2. CORRELATION: Estimated correlation to a 60/40 portfolio. Adds diversification: Y / N.\n"
            "3. RECOMMENDED ALLOCATION: X% of portfolio — explain the sizing logic.\n"
            "4. REBALANCING TRIGGER: At what price or condition would you reduce/increase the position?\n"
            "5. PORTFOLIO FIT SCORE: X/10 — based on return/risk contribution to a diversified portfolio.\n"
            "6. LIQUIDITY BUCKET: Daily / Weekly / Monthly liquidity asset? Implications for portfolio.\n"
            "Under 250 words."
            + _VOTE_INSTRUCTION
        ),
        "votes": True,
    },
    {
        "name": "Technical",
        "emoji": "📉",
        "title": "CMT Level 3 Technical Analyst",
        "system": (
            "You are a CMT Level 3 Chartered Market Technician with 30 years of institutional charting experience.\n"
            "Your output must include ALL of the following:\n"
            "1. TREND STRUCTURE: Primary trend (up/down/sideways) + Wyckoff phase with specific price evidence.\n"
            "2. ELLIOTT WAVE COUNT: Current wave position (if identifiable) and implied next move.\n"
            "3. KEY FIBONACCI LEVELS: Retracement and extension levels with exact prices.\n"
            "4. VOLUME ANALYSIS: Is price action confirmed by volume? Divergence? On-Balance Volume trend.\n"
            "5. INDICATOR CONFLUENCE: RSI, MACD, BB — give exact readings and what they signal.\n"
            "6. TIMING: When is the optimal entry window? (immediately / wait for pullback to ___ / wait for breakout above ___)\n"
            "Under 300 words."
            + _VOTE_INSTRUCTION
        ),
        "votes": True,
    },
    {
        "name": "Behavioral",
        "emoji": "🧠",
        "title": "Behavioral Finance Specialist (Kahneman/Thaler)",
        "system": (
            "You are a Behavioral Finance Specialist applying Kahneman (Prospect Theory) and Thaler (nudge/mental accounting) frameworks.\n"
            "Your output must include ALL of the following:\n"
            "1. SENTIMENT EXTREME: Is retail/institutional sentiment at a fear or greed extreme? Evidence?\n"
            "2. DOMINANT COGNITIVE BIAS: Name the primary bias affecting this asset's pricing right now (overconfidence, anchoring, recency, herding, etc.). Explain specifically.\n"
            "3. CONTRARIAN SIGNAL: Is the crowd positioning so extreme it creates a fade opportunity? Y/N with reasoning.\n"
            "4. NARRATIVE ANALYSIS: What is the dominant market narrative? Is it priced in, under-priced, or over-priced?\n"
            "5. BEHAVIORAL EDGE: What behavioral mispricing can a rational investor exploit here?\n"
            "Under 250 words."
            + _VOTE_INSTRUCTION
        ),
        "votes": True,
    },
    {
        "name": "DevilsAdvocate",
        "emoji": "😈",
        "title": "Devil's Advocate (IC Stress Tester)",
        "system": (
            "You are the IC's Devil's Advocate. Your ONLY job: kill the consensus thesis before it kills the portfolio.\n"
            "Your output must include ALL of the following:\n"
            "1. CONSENSUS FLAW: State the single biggest flaw in the prevailing IC view in 1 sentence.\n"
            "2. BEAR CASE 1 (prob X%): Name it, size the downside, give the exact trigger.\n"
            "3. BEAR CASE 2 (prob X%): Same.\n"
            "4. BEAR CASE 3 (prob X%): Same.\n"
            "5. CONVICTION KILLER: The one event/data point that would force the entire IC to reverse immediately.\n"
            "6. WHAT EVERYONE IS IGNORING: The risk nobody is talking about but should be.\n"
            "Be specific. Vague bearishness is useless. Under 300 words."
            + _VOTE_INSTRUCTION
        ),
        "votes": True,
    },
    {
        "name": "Microstructure",
        "emoji": "🔬",
        "title": "Market Microstructure & Flow Analyst",
        "system": (
            "You are a Market Microstructure specialist at a major prime brokerage, covering dark pool flow, options positioning, and dealer hedging.\n"
            "Your output must include ALL of the following:\n"
            "1. OPTIONS MARKET SIGNAL: Infer put/call skew direction from RSI and volume data. Dealers likely long or short gamma?\n"
            "2. INSTITUTIONAL FLOW: Based on volume ratio and price action, is smart money accumulating or distributing?\n"
            "3. DARK POOL ESTIMATE: Is the stock likely being block-traded off-exchange? What does this imply for direction?\n"
            "4. SHORT INTEREST PROXY: Based on available metrics, is short interest likely rising or falling? Short squeeze potential?\n"
            "5. LIQUIDITY ASSESSMENT: Bid-ask spread tightness, market depth — easy or difficult to enter/exit large positions?\n"
            "6. FLOW VERDICT: Net institutional flow direction — INFLOW / OUTFLOW / NEUTRAL with confidence level.\n"
            "Under 250 words."
            + _VOTE_INSTRUCTION
        ),
        "votes": True,
    },
    {
        "name": "CFAPortfolioManager",
        "emoji": "🏆",
        "title": "CFA III Portfolio Manager — Final Verdict",
        # NOTE: "{n_voters}" is a placeholder — InvestmentCommittee.run() replaces
        # it with the actual number of voting agents before the call so the CFA PM
        # never hallucinates a hardcoded committee size.
        "system": (
            "You are the CIO and a CFA Level III Portfolio Manager chairing the Investment Committee.\n"
            "You have received inputs from {n_voters} specialist analysts. Your job: synthesize into a final, actionable IC verdict.\n"
            "IMPORTANT: For section 1, use the exact vote counts from the PRE-VOTE TALLY line in the context — do not invent numbers.\n"
            "Your output must include ALL of the following sections:\n"
            "1. COMMITTEE VOTE SUMMARY: BUY X / HOLD X / SELL X — note any strong dissents and why.\n"
            "2. FINAL RATING: STRONG BUY / BUY / HOLD / SELL / STRONG SELL (no hedging — pick one).\n"
            "3. 12-MONTH PRICE TARGET: State the target and the primary valuation method used.\n"
            "4. POSITION SIZING: Recommended portfolio weight (%) and the IPS constraint rationale.\n"
            "5. ENTRY STRATEGY: Immediate full entry / Scale in over X weeks / Wait for pullback to ___ .\n"
            "6. RISK CONTROLS: Stop-loss level + the macro or fundamental condition that would trigger a full exit.\n"
            "7. KEY MONITOR: The single most important metric to track post-entry (earnings date, price level, macro data).\n"
            "8. TIME HORIZON: Short-term catalyst (1–3 months) vs long-term thesis (6–18 months).\n"
            "Be decisive. Committees that cannot reach a clear verdict are useless. Under 450 words."
        ),
        "model_override": MODEL_FAST,
        "votes": False,
    },
]


def _parse_vote(text: str) -> Optional[str]:
    """Extract [VOTE: BUY/HOLD/SELL] from agent output. Returns 'BUY', 'HOLD', 'SELL', or None."""
    m = re.search(r"\[VOTE:\s*(BUY|HOLD|SELL)\]", text, re.IGNORECASE)
    return m.group(1).upper() if m else None


class ICAgent(BaseAgent):
    def __init__(self, config: dict):
        model = config.get("model_override", MODEL_LITE)
        super().__init__(config["name"], config["emoji"], config["title"], model)
        self._system = config["system"]
        self.title = config["title"]

    def analyze(self, ticker: str, context: str, max_tokens: int = 500) -> str:
        from .base import _get_provider
        # Groq free tier: 6k TPM (llama-3.3-70b) / 20k TPM (llama-3.1-8b)
        # Cap output tokens for voting agents: 500 gives enough room for
        # [VOTE:] tag on line 1 + ~200-word analysis.  9 agents × 500 = 4,500 TPM,
        # safely within the 6,000 TPM hard limit.
        if _get_provider() == "groq" and max_tokens > 500:
            max_tokens = 500
        prompt = (
            f"Asset under review: **{ticker}**\n\n"
            f"RESEARCH & DATA CONTEXT:\n{context}\n\n"
            f"Provide your {self.title} analysis now."
        )
        return self.run(self._system, prompt, max_tokens=max_tokens)


class InvestmentCommittee:
    def __init__(self, mode: str = "standard"):
        """
        mode: "quick" (5 agents), "standard" (8 agents), "deep" (all 10 agents)
        """
        roster = IC_ROSTER
        if mode == "quick":
            names = {"CIS", "Fundamental", "Technical", "DevilsAdvocate", "CFAPortfolioManager"}
            roster = [a for a in IC_ROSTER if a["name"] in names]
        elif mode == "standard":
            names = {"CIS", "QuantRisk", "Fundamental", "Macro", "Technical",
                     "Behavioral", "DevilsAdvocate", "CFAPortfolioManager"}
            roster = [a for a in IC_ROSTER if a["name"] in names]

        self.agents: list[ICAgent] = [ICAgent(cfg) for cfg in roster]
        self.mode = mode

    def run(
        self,
        ticker: str,
        research_context: str,
        on_agent_start: Optional[Callable[[str], None]] = None,
        on_agent_done: Optional[Callable[[str, str], None]] = None,
    ) -> dict:
        """
        Voting agents (all except CFAPortfolioManager) run in PARALLEL.
        CFAPortfolioManager runs last after collecting all votes.
        This cuts IC time from N×60s → ~60-90s regardless of agent count.
        """
        voting_agents = self.agents[:-1]   # everyone except CFA PM
        final_agent   = self.agents[-1]    # CFAPortfolioManager

        results: dict = {}
        vote_tally: dict[str, list[str]] = {"BUY": [], "HOLD": [], "SELL": []}

        # ── Fire all voting agents simultaneously ─────────────────────────────
        # Signal all as "started" right away (they really are, in threads)
        if on_agent_start:
            for agent in voting_agents:
                on_agent_start(agent.name)

        def _run_one(agent: ICAgent):
            output = agent.analyze(ticker, research_context)
            vote   = _parse_vote(output)
            return agent, output, vote

        # Worker threads are created via threading.Thread(copy_context()) internally,
        # so they automatically inherit the calling thread's ContextVar values
        # (including per-session API keys set via set_session_keys()).
        # No ctx.run() wrapper is needed — and sharing one Context across
        # concurrent threads would cause "already entered" errors.
        max_workers = min(len(voting_agents), 10)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_run_one, a): a for a in voting_agents}
            for future in as_completed(futures):
                agent, output, vote = future.result()
                if vote and vote in vote_tally:
                    vote_tally[vote].append(agent.name)
                results[agent.name] = {
                    "emoji":  agent.emoji,
                    "title":  agent.title,
                    "output": output,
                    "vote":   vote,
                }
                if on_agent_done:
                    on_agent_done(agent.name, output)

        # ── Build synthesis context in roster order for CFA PM ────────────────
        from .base import _get_provider
        _provider = _get_provider()
        _ollama   = _provider == "ollama"
        _groq     = _provider == "groq"

        n_voting   = sum(len(v) for v in vote_tally.values())
        tally_line = (
            f"PRE-VOTE TALLY ({n_voting} voters): "
            f"BUY {len(vote_tally['BUY'])} / "
            f"HOLD {len(vote_tally['HOLD'])} / "
            f"SELL {len(vote_tally['SELL'])}"
        )

        # Context caps to stay within token limits:
        #   Ollama  : very tight  (small context window, slow)
        #   Groq    : moderate    (6k TPM on llama-3.3-70b used by CFA PM)
        #   Anthropic: full
        if _ollama:
            _ctx_cap = 800
            _out_cap = 300
            _pm_max_tokens = 500
        elif _groq:
            _ctx_cap = 1200   # ~300 tokens of research context
            _out_cap = 450    # ~115 tokens per agent × max 9 = ~1035 tokens
            _pm_max_tokens = 600
        else:
            _ctx_cap = len(research_context)
            _out_cap = 9999
            _pm_max_tokens = 700

        synthesis = research_context[:_ctx_cap] + "\n\n═══ IC COMMITTEE INPUTS ═══\n"
        for agent in voting_agents:          # preserve roster order
            data     = results[agent.name]
            vote_tag = f"  [VOTE: {data['vote']}]" if data.get("vote") else ""
            out = data['output'][:_out_cap]
            synthesis += f"\n### {data['emoji']} {data['title']}{vote_tag}\n{out}\n"
        synthesis += f"\n\n{tally_line}\n"

        # ── CFA PM — final synthesis ──────────────────────────────────────────
        # Patch CFA PM system prompt with the ACTUAL voter count so it never
        # hallucinates a hardcoded committee size in its COMMITTEE VOTE SUMMARY.
        final_agent._system = final_agent._system.replace(
            "{n_voters}", str(len(voting_agents))
        )
        if on_agent_start:
            on_agent_start(final_agent.name)
        final_output = final_agent.analyze(ticker, synthesis, max_tokens=_pm_max_tokens)
        results[final_agent.name] = {
            "emoji":  final_agent.emoji,
            "title":  final_agent.title,
            "output": final_output,
            "vote":   None,
        }
        if on_agent_done:
            on_agent_done(final_agent.name, final_output)

        results["_vote_tally"] = vote_tally  # type: ignore[assignment]
        return results

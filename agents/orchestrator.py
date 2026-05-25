import json
import re
from .base import BaseAgent, MODEL_LITE
from tools.ticker_resolver import resolve, asset_class_label

SYSTEM = """You are Joey, orchestrator of an investment analysis system.
Given a user-provided ticker or asset name, extract parameters and respond ONLY with valid JSON."""

PROMPT = """
Input: "{user_input}"
Pre-resolved: ticker="{ticker}", asset_class="{asset_class}", market="{market}"
Requested mode: "{mode}"

Return JSON with these exact keys:
{{
  "ticker":       "{ticker}",
  "asset_class":  "{asset_class}",
  "market":       "{market}",
  "analysis_type": "{mode}",
  "timeframe_short": "swing",
  "routing_note": "<one sentence on what to focus>"
}}
Only change timeframe_short if you have a strong reason (scalp/intraday/swing/position).
"""


class Joey(BaseAgent):
    def __init__(self):
        super().__init__("Joey", "☁️", "Orchestrator — routes work, never does it", MODEL_LITE)

    def classify(self, user_input: str, mode: str = "both") -> dict:
        # Step 1: deterministic resolver (no LLM needed)
        resolved = resolve(user_input)

        # Step 2: quick LLM pass to add routing_note (cheap)
        try:
            raw = self.run(
                SYSTEM,
                PROMPT.format(
                    user_input=user_input,
                    ticker=resolved["ticker"],
                    asset_class=resolved["asset_class"],
                    market=resolved["market"],
                    mode=mode,
                ),
                max_tokens=200,
            )
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                result = json.loads(match.group())
                # Always trust the deterministic resolver for ticker/class/market
                result["ticker"]      = resolved["ticker"]
                result["asset_class"] = resolved["asset_class"]
                result["market"]      = resolved["market"]
                result["display"]     = resolved["display"]
                result["uncertain"]   = resolved.get("uncertain", False)
                return result
        except Exception:
            pass

        return {
            "ticker":          resolved["ticker"],
            "asset_class":     resolved["asset_class"],
            "market":          resolved["market"],
            "display":         resolved["display"],
            "uncertain":       resolved.get("uncertain", False),
            "analysis_type":   mode,
            "timeframe_short": "swing",
            "routing_note":    f"Analyze {resolved['ticker']} ({resolved['asset_class']})",
        }

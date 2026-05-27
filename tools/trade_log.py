"""
Trade Log — persistent trade journal backed by st.session_state + server cache.

• Session state   : in-memory during the current Streamlit session
• Server cache    : st.cache_resource dict keyed by user UID (see persistence.py)
• JSON export/import : long-term backup across server restarts
"""

from __future__ import annotations

import json
import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import concurrent.futures

import streamlit as st
import yfinance as yf


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class TradeRecord:
    id: str                        # short uuid (8 chars)
    ticker: str
    company: str
    action: str                    # "BUY" | "SELL"
    entry_price: float
    currency: str                  # "THB" | "USD" | …
    ic_verdict: str                # human-readable label, e.g. "STRONG SELL ⚡"
    logged_at: str                 # "YYYY-MM-DD HH:MM"
    current_price: Optional[float] = None
    last_refreshed: Optional[str]  = None
    note: str                      = ""

    # ── P&L helpers ──────────────────────────────────────────────────────────
    def pnl_pct(self) -> Optional[float]:
        """Return profit/loss % from entry.  BUY: gain if price rises.
        SELL (short): gain if price falls."""
        if self.current_price is None or self.entry_price == 0:
            return None
        if self.action == "BUY":
            return (self.current_price - self.entry_price) / self.entry_price * 100
        return (self.entry_price - self.current_price) / self.entry_price * 100

    def pnl_abs(self) -> Optional[float]:
        if self.current_price is None:
            return None
        if self.action == "BUY":
            return self.current_price - self.entry_price
        return self.entry_price - self.current_price


# ── Session-state CRUD ────────────────────────────────────────────────────────

_SS_KEY = "trade_log"


def get_trades() -> list[TradeRecord]:
    """Return the current trade list from session state (always a list)."""
    if _SS_KEY not in st.session_state:
        st.session_state[_SS_KEY] = []
    return st.session_state[_SS_KEY]


def add_trade(record: TradeRecord) -> None:
    """Prepend a trade; silently skip exact duplicates (same ticker + logged_at)."""
    trades = get_trades()
    for t in trades:
        if t.ticker == record.ticker and t.logged_at == record.logged_at:
            return
    trades.insert(0, record)
    st.session_state[_SS_KEY] = trades


def delete_trade(trade_id: str) -> None:
    st.session_state[_SS_KEY] = [t for t in get_trades() if t.id != trade_id]


def clear_trades() -> None:
    st.session_state[_SS_KEY] = []


def update_prices(price_map: dict[str, Optional[float]]) -> None:
    """Bulk-update current_price for every trade whose ticker appears in price_map."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for t in get_trades():
        if t.ticker in price_map and price_map[t.ticker] is not None:
            t.current_price = price_map[t.ticker]
            t.last_refreshed = now


# ── Serialization ─────────────────────────────────────────────────────────────

def trades_to_json(trades: list[TradeRecord]) -> str:
    return json.dumps([dataclasses.asdict(t) for t in trades], ensure_ascii=False)


def trades_from_json(json_str: str) -> list[TradeRecord]:
    try:
        records = json.loads(json_str)
        if not isinstance(records, list):
            return []
        result = []
        for r in records:
            if not isinstance(r, dict):
                continue
            # Drop unknown keys so old exports still load cleanly
            known = {f.name for f in dataclasses.fields(TradeRecord)}
            clean = {k: v for k, v in r.items() if k in known}
            try:
                result.append(TradeRecord(**clean))
            except Exception:
                continue
        return result
    except Exception:
        return []


# ── Server-side persistence ───────────────────────────────────────────────────
#
# Replaces the unreliable localStorage / streamlit-javascript approach.
# All writes go to a st.cache_resource dict keyed by user UID.
# See tools/persistence.py for architecture details.
#
_PERSIST_KEY = "trade_log"


def write_localstorage(trades: list[TradeRecord]) -> None:
    """
    Persist trades to the server-side cache for this user.

    Name kept for backward compatibility with all call-sites in app.py.
    No longer writes to browser localStorage — uses st.cache_resource instead.
    """
    try:
        from tools.persistence import get_uid, save
        save(get_uid(), _PERSIST_KEY, trades_to_json(trades))
    except Exception:
        pass   # never crash the UI over a persistence failure


def ensure_loaded() -> bool:
    """
    Load trades from server-side cache into session_state exactly once per session.

    Always returns True (no first-render delay unlike st_javascript).
    Callers that checked 'if not ensure_loaded(): st.rerun()' are safe —
    that branch is simply never entered.
    """
    if st.session_state.get("_tl_loaded"):
        return True

    try:
        from tools.persistence import get_uid, load
        raw = load(get_uid(), _PERSIST_KEY)
    except Exception:
        raw = "[]"

    loaded = trades_from_json(raw)
    current = st.session_state.get(_SS_KEY) or []
    if loaded:
        current_ids = {t.id for t in current}
        merged = current + [t for t in loaded if t.id not in current_ids]
        st.session_state[_SS_KEY] = merged
    else:
        st.session_state.setdefault(_SS_KEY, [])

    st.session_state["_tl_loaded"] = True
    return True


# ── Price refresh ─────────────────────────────────────────────────────────────

def fetch_prices_parallel(tickers: list[str]) -> dict[str, Optional[float]]:
    """Fetch current prices for multiple tickers simultaneously using yfinance."""
    if not tickers:
        return {}

    def _one(ticker: str) -> tuple[str, Optional[float]]:
        try:
            fi = yf.Ticker(ticker).fast_info
            price = (getattr(fi, "last_price", None) or
                     getattr(fi, "regular_market_price", None))
            return ticker, float(price) if price else None
        except Exception:
            return ticker, None

    workers = min(len(tickers), 10)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(pool.map(_one, tickers))

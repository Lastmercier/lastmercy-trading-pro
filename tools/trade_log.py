"""
Trade Log — persistent trade journal backed by st.session_state + browser localStorage.

• Session state   : in-memory during a Streamlit session
• localStorage    : persists across browser sessions (requires streamlit-javascript)
• WRITE path      : st.components.v1.html(<script>) — no extra package, zero height
• READ  path      : streamlit_javascript.st_javascript() — returns None on first
                    render; we set a flag so we only wait once.
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
        return [TradeRecord(**r) for r in records if isinstance(r, dict)]
    except Exception:
        return []


# ── localStorage bridge ───────────────────────────────────────────────────────

_LS_KEY = "lastmercy_trades"


def write_localstorage(trades: list[TradeRecord]) -> None:
    """Write trades to browser localStorage via a zero-height iframe script."""
    data = trades_to_json(trades)
    st.components.v1.html(
        f"""<script>
        try {{
            localStorage.setItem({json.dumps(_LS_KEY)}, {json.dumps(data)});
        }} catch(e) {{
            console.warn('[TradeLog] localStorage write failed:', e);
        }}
        </script>""",
        height=0,
        scrolling=False,
    )


def read_localstorage() -> Optional[str]:
    """
    Read the raw JSON string from localStorage via streamlit-javascript.
    Returns None on the very first render (JS not yet executed).
    Returns "[]" or a JSON array string on subsequent renders.
    Falls back to "[]" if the package is not installed.
    """
    try:
        from streamlit_javascript import st_javascript
        return st_javascript(
            f'localStorage.getItem({json.dumps(_LS_KEY)}) || "[]"',
            key="tl_ls_read",
        )
    except ImportError:
        return "[]"


def ensure_loaded() -> bool:
    """
    Load trades from localStorage into session_state exactly once per session.
    Returns True when loading is complete (or if already done).
    Returns False on the very first render — caller should st.rerun().
    """
    if st.session_state.get("_tl_loaded"):
        return True  # already loaded this session

    raw = read_localstorage()
    if raw is None:
        return False  # first render — JS hasn't responded yet

    loaded = trades_from_json(raw)
    if loaded:
        # Only overwrite if session_state is empty (don't clobber a just-logged trade)
        if not st.session_state.get(_SS_KEY):
            st.session_state[_SS_KEY] = loaded
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

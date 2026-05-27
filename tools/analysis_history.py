"""
Analysis History — stores a rich summary of every analysis run.

Persistence strategy (same as trade_log.py):
  • Session state  : in-memory, current Streamlit session
  • localStorage   : browser-side, survives page refresh/close
    - WRITE via st.components.v1.html(<script>)  — zero height
    - READ  via streamlit_javascript.st_javascript()
      (returns None on first render; caller must handle via ensure_loaded)

Size budget: ~4–5 KB per entry, ~1,000 entries fit in a 5 MB localStorage slot.
"""

from __future__ import annotations

import json
import dataclasses
from dataclasses import dataclass
from typing import Optional

import streamlit as st


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class HistoryRecord:
    # Identity
    id:           str
    ticker:       str
    company:      str
    sector:       str
    market:       str
    asset_class:  str
    mode:         str        # "short" | "long" | "both"
    ic_mode:      str        # "quick" | "standard" | "deep" | ""
    run_at:       str        # "YYYY-MM-DD HH:MM"

    # Price & key metrics
    price:           float
    currency:        str
    pe_ratio:        Optional[float]
    market_cap:      Optional[float]
    analyst_target:  Optional[float]

    # IC summary
    ic_verdict:    str        # "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL" | ""
    ic_votes_buy:  int
    ic_votes_hold: int
    ic_votes_sell: int
    ic_final_text: str        # first 1200 chars of CFA PM output

    # Research outputs (truncated)
    research_text:   str      # first 800 chars of Wizard output
    trade_card_text: str      # first 600 chars of trade card
    trade_direction: str      # "LONG" | "SHORT" | ""


# ── Session-state CRUD ────────────────────────────────────────────────────────

_SS_KEY = "analysis_history"


def get_history() -> list[HistoryRecord]:
    if _SS_KEY not in st.session_state:
        st.session_state[_SS_KEY] = []
    return st.session_state[_SS_KEY]


def add_history_record(record: HistoryRecord) -> None:
    """Prepend record; silently skip if same id already exists."""
    history = get_history()
    existing_ids = {r.id for r in history}
    if record.id in existing_ids:
        return
    history.insert(0, record)
    # Cap at 200 entries to stay well within localStorage limits
    st.session_state[_SS_KEY] = history[:200]


def delete_history_record(record_id: str) -> None:
    st.session_state[_SS_KEY] = [r for r in get_history() if r.id != record_id]


def clear_history() -> None:
    st.session_state[_SS_KEY] = []


# ── Serialization ─────────────────────────────────────────────────────────────

def history_to_json(history: list[HistoryRecord]) -> str:
    return json.dumps([dataclasses.asdict(r) for r in history], ensure_ascii=False)


def history_from_json(json_str: str) -> list[HistoryRecord]:
    try:
        records = json.loads(json_str)
        return [HistoryRecord(**r) for r in records if isinstance(r, dict)]
    except Exception:
        return []


# ── localStorage bridge ───────────────────────────────────────────────────────

_LS_KEY = "lastmercy_history"


def write_history_localstorage(history: list[HistoryRecord]) -> None:
    """
    Write history to localStorage.

    Same approach as trade_log.write_localstorage — uses st_javascript
    instead of st.components.v1.html(height=0).  Zero-height iframes are
    silently skipped by most browsers, so scripts inside them never run.
    st_javascript renders a proper (but invisible) Streamlit component
    that reliably executes JavaScript.

    Hash-based key: new component (→ JS re-runs) only when data changes.
    """
    import hashlib
    data  = history_to_json(history)
    _key  = "hist_w_" + hashlib.md5(data.encode()).hexdigest()[:8]
    try:
        from streamlit_javascript import st_javascript
        st_javascript(
            f"(()=>{{try{{localStorage.setItem({json.dumps(_LS_KEY)},{json.dumps(data)});}}catch(e){{console.warn('[Hist write]',e);}}return 1;}})()",
            key=_key,
        )
    except ImportError:
        st.components.v1.html(
            f"<script>try{{localStorage.setItem({json.dumps(_LS_KEY)},{json.dumps(data)});}}catch(e){{console.warn(e);}}</script>",
            height=30,
        )


def read_history_localstorage() -> Optional[str]:
    """Read history JSON string from localStorage (None on first render)."""
    try:
        from streamlit_javascript import st_javascript
        return st_javascript(
            f'localStorage.getItem({json.dumps(_LS_KEY)}) || "[]"',
            key="hist_ls_read",
        )
    except ImportError:
        return "[]"


def ensure_history_loaded() -> bool:
    """
    Load history from localStorage into session_state exactly once per session.
    Returns True when done, False on first render (JS not yet executed).
    """
    if st.session_state.get("_hist_loaded"):
        return True

    raw = read_history_localstorage()
    if raw is None:
        return False  # first render — wait

    loaded = history_from_json(raw)
    current = st.session_state.get(_SS_KEY) or []
    if loaded:
        # Merge: keep current-session records AND historical records (by id)
        current_ids = {r.id for r in current}
        merged = current + [r for r in loaded if r.id not in current_ids]
        st.session_state[_SS_KEY] = merged[:200]
    else:
        st.session_state.setdefault(_SS_KEY, [])

    st.session_state["_hist_loaded"] = True
    return True

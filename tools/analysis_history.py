"""
Analysis History — stores a rich summary of every analysis run.

• Session state   : in-memory during the current Streamlit session
• Server cache    : st.cache_resource dict keyed by user UID (see persistence.py)
• JSON export/import : long-term backup across server restarts

Cap: 200 entries per user (well within cache memory budget).
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
    # Cap at 200 entries
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
        if not isinstance(records, list):
            return []
        result = []
        for r in records:
            if not isinstance(r, dict):
                continue
            # Drop unknown keys so old exports still load cleanly
            known = {f.name for f in dataclasses.fields(HistoryRecord)}
            clean = {k: v for k, v in r.items() if k in known}
            try:
                result.append(HistoryRecord(**clean))
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
_PERSIST_KEY = "analysis_history"


def write_history_localstorage(history: list[HistoryRecord]) -> None:
    """
    Persist history to the server-side cache for this user.

    Name kept for backward compatibility with all call-sites in app.py.
    No longer writes to browser localStorage — uses st.cache_resource instead.
    """
    try:
        from tools.persistence import get_uid, save
        save(get_uid(), _PERSIST_KEY, history_to_json(history))
    except Exception:
        pass   # never crash the UI over a persistence failure


def read_history_localstorage() -> Optional[str]:
    """
    Read history JSON string from server-side cache.
    Kept for backward compatibility; always returns immediately (no JS delay).
    """
    try:
        from tools.persistence import get_uid, load
        return load(get_uid(), _PERSIST_KEY)
    except Exception:
        return "[]"


def ensure_history_loaded() -> bool:
    """
    Load history from server-side cache into session_state exactly once per session.

    Always returns True (no first-render delay unlike st_javascript).
    Callers that checked 'if not ensure_history_loaded(): st.rerun()' are safe —
    that branch is simply never entered.
    """
    if st.session_state.get("_hist_loaded"):
        return True

    try:
        from tools.persistence import get_uid, load
        raw = load(get_uid(), _PERSIST_KEY)
    except Exception:
        raw = "[]"

    loaded = history_from_json(raw)
    current = st.session_state.get(_SS_KEY) or []
    if loaded:
        current_ids = {r.id for r in current}
        merged = current + [r for r in loaded if r.id not in current_ids]
        st.session_state[_SS_KEY] = merged[:200]
    else:
        st.session_state.setdefault(_SS_KEY, [])

    st.session_state["_hist_loaded"] = True
    return True

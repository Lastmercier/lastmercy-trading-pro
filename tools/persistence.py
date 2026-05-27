"""
Server-side persistence for Trade Log and Analysis History.

Why this replaces localStorage / streamlit-javascript
──────────────────────────────────────────────────────
• st.components.v1.html(height=0)  — zero-height iframes are silently
  skipped by modern browsers; scripts inside them never execute.
• streamlit-javascript st_javascript() — unreliable on Streamlit
  Community Cloud (component not registered on cold boots, returns None
  indefinitely, or crashes on large payloads).

New architecture
────────────────
  st.cache_resource  — Python dict, lives in the server process.
                       Survives WebSocket disconnections and browser
                       close+reopen as long as the server process runs.
                       Cleared only on server restart (deploy / idle
                       shutdown on Community Cloud ~every 24-48 h).

  ?uid=<id> in URL   — 12-char hex UUID.  Only written to the URL when
                       the user explicitly clicks the "Get my data URL"
                       button in the sidebar.  No automatic st.query_params
                       writes → no unwanted reruns → no spinner loops.

  JSON export/import — true long-term backup across server restarts.

Flow on first visit
───────────────────
  1. get_uid() generates a new UID, stores it in st.session_state only.
  2. ensure_loaded() loads "[]" (empty) — nothing saved yet.
  3. After analysis / logging, save() writes data for that UID.
  4. User clicks "Get my data URL" in the sidebar → browser navigates
     to ?uid=<id>.  From that point the URL contains the UID.

Flow on return visit (bookmarked ?uid=<id> URL)
───────────────────────────────────────────────
  1. get_uid() reads UID from st.query_params (no session_state write
     needed, query_params read is always safe).
  2. ensure_loaded() reads stored JSON from cache → data appears.
"""

from __future__ import annotations
import uuid as _uuid
import streamlit as st


# ── Global server-side store ──────────────────────────────────────────────────

@st.cache_resource
def _global_store() -> dict:
    """
    Single Python dict shared across ALL user sessions on this server.
    Keyed by UID → { persist_key → json_str }.
    Lives for the lifetime of the server process.
    """
    return {}


# ── User identity ─────────────────────────────────────────────────────────────

def get_uid() -> str:
    """
    Return (and create if needed) this browser session's user UID.

    Priority:
      1. st.session_state["_uid"]  — cached within the session (fastest)
      2. st.query_params["uid"]    — user returned via bookmarked URL
      3. Generate new UID, store in session_state only

    NEVER writes to st.query_params here — that would trigger a Streamlit
    rerun and can cause an infinite spinner loop on Community Cloud.
    The UID reaches the URL only when the user clicks the sidebar button.
    """
    if "_uid" in st.session_state:
        return st.session_state["_uid"]

    uid: str = ""
    try:
        uid = st.query_params.get("uid") or ""
    except Exception:
        pass

    if not uid:
        uid = _uuid.uuid4().hex[:12]

    st.session_state["_uid"] = uid
    return uid


# ── Read / write ──────────────────────────────────────────────────────────────

def save(uid: str, key: str, json_str: str) -> None:
    """Persist a JSON string for this user + key."""
    store = _global_store()
    if uid not in store:
        store[uid] = {}
    store[uid][key] = json_str


def load(uid: str, key: str) -> str:
    """Load a JSON string for this user + key.  Returns '[]' if not found."""
    return _global_store().get(uid, {}).get(key, "[]")

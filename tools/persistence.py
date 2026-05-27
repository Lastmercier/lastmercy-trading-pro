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

  st.query_params["uid"] — 12-char hex UUID written to the browser URL.
                           Survives browser close + reopen IF the user
                           returns via a bookmark or browser history.
                           On a new device / incognito, a fresh UID is
                           generated automatically.

  JSON export / import   — true long-term backup across server restarts.
                           Users should download their JSON and re-import
                           after a server restart.

Flow on first visit
───────────────────
  1. get_uid() generates a new UID, writes ?uid=<uid> to the URL.
  2. ensure_loaded() / ensure_history_loaded() load "[]" (empty) from
     the cache (first visit → nothing there yet).
  3. After analysis / logging, save() writes data for that UID.

Flow on return visit (same server process)
──────────────────────────────────────────
  1. Browser reopens the bookmarked URL → ?uid=<uid> is in the URL.
  2. get_uid() reads the UID from st.query_params, no new UID generated.
  3. ensure_loaded() reads the stored JSON from the cache → data appears.
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
      1. st.session_state["_uid"]  — fastest; cached within the session
      2. st.query_params["uid"]    — user returned via a bookmarked URL
      3. Generate new UID and store in session_state only

    NOTE: We intentionally do NOT write back to st.query_params here.
    Setting st.query_params triggers a full Streamlit rerun, which can
    cause a rerun loop if called during early script execution.
    The UID is written to the URL lazily via _write_uid_to_url() which
    should only be called from safe locations (e.g. sidebar button handlers
    or after the first successful persistence write).
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


def write_uid_to_url(uid: str) -> None:
    """
    Write the UID into the browser URL (st.query_params).

    ONLY call this from a safe context — e.g. after the sidebar has fully
    rendered, or inside an 'if st.button(...)' block.  Writing to
    st.query_params triggers a rerun; calling it mid-render can loop.
    """
    try:
        existing = st.query_params.get("uid") or ""
        if existing != uid:
            st.query_params["uid"] = uid
    except Exception:
        pass


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

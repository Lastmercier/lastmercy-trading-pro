"""
Persistence layer for Trade Log and Analysis History.

Storage tiers (best → worst durability)
─────────────────────────────────────────
  Tier 1 — Supabase PostgreSQL   (configured via SUPABASE_URL + SUPABASE_KEY)
            Survives server restarts, server migration, re-deploys.
            Set up once; all subsequent visits restore data automatically.

  Tier 2 — st.cache_resource     (in-memory, always active)
            Survives browser close/reopen within the same server process.
            Cleared when Streamlit Community Cloud restarts (~24-48 h idle).

  Tier 3 — JSON export/import    (manual, lives in user's file system)
            Survives everything.  User downloads a backup and re-imports.

How UID works
─────────────
  • First visit  : a 12-char hex UID is generated and stored in session_state.
  • After "Lock Data to URL" : UID is written to st.query_params → URL updates
    to ?uid=xxx → user bookmarks that URL.
  • Return visit : UID is read from st.query_params → correct data loaded.

Supabase setup (one-time, ~5 min)
──────────────────────────────────
  1. Create free account at https://supabase.com
  2. New project → SQL Editor → run:

       CREATE TABLE IF NOT EXISTS user_data (
           uid  TEXT NOT NULL,
           key  TEXT NOT NULL,
           val  TEXT NOT NULL DEFAULT '[]',
           ts   TIMESTAMPTZ DEFAULT NOW(),
           PRIMARY KEY (uid, key)
       );
       ALTER TABLE user_data DISABLE ROW LEVEL SECURITY;

  3. Settings → API → copy "Project URL" and "anon public" key.
  4. In Streamlit Cloud → app settings → Secrets → add:

       SUPABASE_URL = "https://xxxx.supabase.co"
       SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5c..."
"""

from __future__ import annotations
import os
import uuid as _uuid
import concurrent.futures as _cf

import streamlit as st


# ── Background writer (non-blocking Supabase writes) ─────────────────────────
_bg_pool = _cf.ThreadPoolExecutor(max_workers=2, thread_name_prefix="sb_write")


# ── Global in-memory store (Tier 2) ──────────────────────────────────────────

@st.cache_resource
def _mem_store() -> dict:
    """
    Server-side dict, keyed uid → {persist_key → json_str}.
    Lives for the lifetime of the server process.
    """
    return {}


# ── Supabase config ───────────────────────────────────────────────────────────

def _sb_config() -> tuple[str, str]:
    """Return (supabase_url, api_key) or ("", "") if not configured."""
    url, key = "", ""
    try:
        url = st.secrets.get("SUPABASE_URL", "") or ""
        key = st.secrets.get("SUPABASE_KEY", "") or ""
    except Exception:
        pass
    url = url or os.environ.get("SUPABASE_URL", "")
    key = key or os.environ.get("SUPABASE_KEY", "")
    return url.rstrip("/"), key


def supabase_configured() -> bool:
    """True when Supabase credentials are present."""
    u, k = _sb_config()
    return bool(u and k)


# ── Supabase I/O (Tier 1) ─────────────────────────────────────────────────────

def _sb_upsert(uid: str, key: str, val: str, url: str, api_key: str) -> None:
    """Write (uid, key, val) row to Supabase — called in background thread."""
    try:
        import requests as _req
        _req.post(
            f"{url}/rest/v1/user_data",
            headers={
                "apikey": api_key,
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates",
            },
            json={"uid": uid, "key": key, "val": val},
            timeout=8,
        )
    except Exception:
        pass


def _sb_fetch(uid: str, key: str, url: str, api_key: str) -> str:
    """Read val for (uid, key) from Supabase. Returns '[]' on miss/error."""
    try:
        import requests as _req
        resp = _req.get(
            f"{url}/rest/v1/user_data",
            headers={
                "apikey": api_key,
                "Authorization": f"Bearer {api_key}",
            },
            params={"uid": f"eq.{uid}", "key": f"eq.{key}", "select": "val"},
            timeout=8,
        )
        if resp.status_code == 200:
            rows = resp.json()
            if rows:
                return rows[0].get("val", "[]") or "[]"
    except Exception:
        pass
    return "[]"


# ── Public API ────────────────────────────────────────────────────────────────

def save(uid: str, key: str, json_str: str) -> None:
    """
    Write data for this user+key.

    • Writes to in-memory cache immediately (fast, for current session).
    • Writes to Supabase in a background thread if configured
      (non-blocking — UI stays snappy even on slow connections).
    """
    # Tier 2: in-memory
    store = _mem_store()
    if uid not in store:
        store[uid] = {}
    store[uid][key] = json_str

    # Tier 1: Supabase (background, fire-and-forget)
    sb_url, sb_key = _sb_config()
    if sb_url and sb_key:
        _bg_pool.submit(_sb_upsert, uid, key, json_str, sb_url, sb_key)


def load(uid: str, key: str) -> str:
    """
    Read data for this user+key.

    • First checks in-memory cache (O(1), handles normal session re-renders).
    • Falls back to Supabase on first load after a server restart
      (one HTTP round-trip per key per session, then cached in memory).
    """
    # Tier 2: in-memory
    val = _mem_store().get(uid, {}).get(key, "")
    if val:
        return val

    # Tier 1: Supabase
    sb_url, sb_key = _sb_config()
    if sb_url and sb_key:
        sb_val = _sb_fetch(uid, key, sb_url, sb_key)
        if sb_val and sb_val != "[]":
            # Populate in-memory cache for the rest of this session
            store = _mem_store()
            if uid not in store:
                store[uid] = {}
            store[uid][key] = sb_val
            return sb_val

    return "[]"


# ── User identity ─────────────────────────────────────────────────────────────

def get_uid() -> str:
    """
    Return (and create if needed) this browser session's user UID.

    Priority:
      1. st.session_state["_uid"]  — cached within the session (fastest)
      2. st.query_params["uid"]    — user returned via bookmarked URL
      3. Generate new UID, store in session_state only

    Never writes to st.query_params here — that would trigger a Streamlit
    rerun loop.  The UID reaches the URL via the "Lock Data to URL" button.
    """
    if "_uid" in st.session_state:
        return st.session_state["_uid"]

    uid = ""
    try:
        uid = st.query_params.get("uid") or ""
    except Exception:
        pass

    if not uid:
        uid = _uuid.uuid4().hex[:12]

    st.session_state["_uid"] = uid
    return uid

import os
import sys
import json
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv()

# ── Ticker resolver — loaded at module level (needed for sidebar + dashboard) ─
from tools.ticker_resolver import (
    asset_class_label, fuzzy_suggest, to_tradingview_symbol,
    get_etf_holdings, get_thai_fund_info, THAI_FUNDS,
)

# ── Streamlit Cloud: load secrets into env vars ───────────────────────────────
# On Streamlit Community Cloud, secrets are in st.secrets (not .env).
# This bridge makes the rest of the code work unchanged.
try:
    if "ANTHROPIC_API_KEY" in st.secrets and not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    if "GROQ_API_KEY" in st.secrets and not os.environ.get("GROQ_API_KEY"):
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except Exception:
    pass  # st.secrets not available in local dev — fine, .env is used instead

# ── Detect deployment environment ─────────────────────────────────────────────
# Streamlit Community Cloud sets IS_STREAMLIT_CLOUD or runs on Linux without Ollama.
_IS_CLOUD = (
    os.environ.get("STREAMLIT_SHARING_MODE") == "true"        # legacy flag
    or os.environ.get("IS_STREAMLIT_CLOUD", "").lower() == "true"
    or not os.path.exists("/usr/local/bin/ollama")             # heuristic: no Ollama binary
    and sys.platform.startswith("linux")                       # running on Linux (cloud)
)

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Lastmercy Trading Pro",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
/* ── Global layout ─────────────────────────────────────────────────────── */
[data-testid="stAppViewContainer"] { background: #f0f4f8; }
[data-testid="stSidebar"] {
    background: #ffffff;
    box-shadow: 2px 0 16px rgba(0,0,0,0.07);
}
[data-testid="stSidebar"] section { padding-top: 1rem; }

/* ── Hero banner ───────────────────────────────────────────────────────── */
.hero {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 55%, #a855f7 100%);
    border-radius: 16px;
    padding: 28px 36px;
    margin-bottom: 28px;
    box-shadow: 0 6px 28px rgba(79,70,229,0.28);
}
.hero h1 {
    margin: 0; font-size: 1.9rem; color: #fff;
    font-weight: 800; letter-spacing: -0.5px;
}
.hero p { margin: 6px 0 0; color: rgba(255,255,255,0.78); font-size: 0.92rem; }
.hero-badges { margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap; }
.hero-badge {
    display: inline-block;
    background: rgba(255,255,255,0.18);
    color: rgba(255,255,255,0.95);
    border-radius: 20px; padding: 3px 13px;
    font-size: 0.73rem; font-weight: 600; letter-spacing: 0.8px;
    border: 1px solid rgba(255,255,255,0.3);
}

/* ── Section pipeline columns ──────────────────────────────────────────── */
.team-header {
    font-size: 0.78rem; font-weight: 700; letter-spacing: 1.2px;
    text-transform: uppercase; padding-bottom: 8px;
    margin-bottom: 4px; margin-top: 4px;
    display: flex; align-items: center; gap: 6px;
}
.th-finance { color: #1d4ed8; border-bottom: 2px solid #bfdbfe; }
.th-trading { color: #047857; border-bottom: 2px solid #6ee7b7; }
.th-ic      { color: #6d28d9; border-bottom: 2px solid #ddd6fe; }

/* ── Agent cards ───────────────────────────────────────────────────────── */
.agent-card {
    background: #fff;
    border-left: 3px solid #e2e8f0;
    border-radius: 8px;
    padding: 9px 13px;
    margin: 4px 0;
    font-size: 0.82rem;
    color: #64748b;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    display: flex; align-items: center; gap: 6px;
}
.agent-card b { color: #334155; }
.ac-finance  { border-left-color: #93c5fd; }
.ac-trading  { border-left-color: #6ee7b7; }
.ac-ic       { border-left-color: #c4b5fd; }
.ac-running  {
    border-left-color: #f59e0b; background: #fffbeb;
    color: #92400e; box-shadow: 0 0 0 2px #fde68a44;
    animation: pulse-amber 1.4s ease-in-out infinite;
}
.ac-running b { color: #78350f; }
.ac-done    { border-left-color: #10b981; background: #f0fdf4; color: #065f46; }
.ac-done b  { color: #064e3b; }

@keyframes pulse-amber {
    0%,100% { box-shadow: 0 0 0 2px #fde68a44; }
    50%      { box-shadow: 0 0 0 4px #fde68a88; }
}

/* ── Metric strip ──────────────────────────────────────────────────────── */
div[data-testid="stMetric"] {
    background: #fff;
    border-radius: 12px;
    padding: 14px 18px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    border: 1px solid #e2e8f0;
}
div[data-testid="stMetricLabel"]  { font-size: 0.78rem; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
div[data-testid="stMetricValue"]  { font-size: 1.45rem; font-weight: 800; color: #1e293b; }
div[data-testid="stMetricDelta"]  { font-size: 0.82rem; }

/* ── Trade card ────────────────────────────────────────────────────────── */
.tc {
    background: #fff;
    border-radius: 14px;
    padding: 0 0 20px 0;
    margin-bottom: 16px;
    box-shadow: 0 3px 14px rgba(0,0,0,0.09);
    overflow: hidden;
}
.tc-header {
    padding: 14px 22px;
    margin-bottom: 16px;
    font-size: 1.05rem; font-weight: 800; letter-spacing: 0.5px;
}
.tc-long  .tc-header { background: linear-gradient(90deg,#d1fae5,#a7f3d0); color: #064e3b; border-bottom: 2px solid #10b981; }
.tc-short .tc-header { background: linear-gradient(90deg,#fee2e2,#fecaca); color: #7f1d1d; border-bottom: 2px solid #ef4444; }
.tc-body { padding: 0 22px; }

/* ── IC verdict banner ─────────────────────────────────────────────────── */
.verdict-banner {
    border-radius: 14px; padding: 20px 32px;
    text-align: center; margin-bottom: 24px;
    font-size: 1.7rem; font-weight: 900;
    letter-spacing: 4px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
}
.vb-sbuy  { background: linear-gradient(135deg,#d1fae5,#a7f3d0); border:2px solid #10b981; color:#065f46; }
.vb-buy   { background: linear-gradient(135deg,#dbeafe,#bfdbfe); border:2px solid #3b82f6; color:#1e40af; }
.vb-hold  { background: linear-gradient(135deg,#fef9c3,#fde68a); border:2px solid #eab308; color:#713f12; }
.vb-sell  { background: linear-gradient(135deg,#fee2e2,#fecaca); border:2px solid #ef4444; color:#991b1b; }
.vb-ssell { background: linear-gradient(135deg,#fce7f3,#fbcfe8); border:2px solid #ec4899; color:#831843; }

/* ── White section cards ───────────────────────────────────────────────── */
.section-card {
    background: #fff; border-radius: 12px;
    padding: 20px 24px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.06);
    border: 1px solid #e2e8f0;
    margin-bottom: 16px;
}

/* ── Tabs ──────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: #fff; border-radius: 12px;
    padding: 5px 6px; gap: 4px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.07);
    border: 1px solid #e2e8f0;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px; padding: 8px 20px;
    font-weight: 600; font-size: 0.87rem; color: #64748b;
}
.stTabs [aria-selected="true"] {
    background: #4f46e5 !important;
    color: #fff !important;
}

/* ── Sidebar typography ────────────────────────────────────────────────── */
[data-testid="stSidebar"] h2 { color: #1e293b !important; }
[data-testid="stSidebar"] h3 {
    font-size: 0.72rem !important; font-weight: 700 !important;
    text-transform: uppercase; letter-spacing: 1px;
    color: #94a3b8 !important; margin-top: 1.2rem !important;
}
[data-testid="stSidebar"] label { color: #374151 !important; font-weight: 500; }
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
    border: none !important;
    font-weight: 700 !important; font-size: 1rem !important;
    padding: 0.65rem !important;
    box-shadow: 0 4px 14px rgba(79,70,229,0.4) !important;
    border-radius: 10px !important;
}

/* ── Expanders (IC agents) ─────────────────────────────────────────────── */
details {
    background: #fff; border-radius: 10px;
    border: 1px solid #e2e8f0 !important;
    margin-bottom: 6px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
details summary {
    padding: 12px 16px; font-weight: 700;
    color: #334155; font-size: 0.88rem;
}
details[open] summary { color: #4f46e5; }

/* ── Dividers ──────────────────────────────────────────────────────────── */
hr { border-color: #e2e8f0 !important; }

/* ── Status boxes ──────────────────────────────────────────────────────── */
[data-testid="stStatusWidget"] { border-radius: 10px; border: 1px solid #e2e8f0; }

/* ── Ticker guide card ─────────────────────────────────────────────────── */
.tg-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px 14px;
    margin-top: 6px;
    font-size: 0.78rem;
}
.tg-row { margin-bottom: 10px; }
.tg-row:last-child { margin-bottom: 0; }
.tg-label {
    display: flex; align-items: center; gap: 5px;
    font-size: 0.7rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.6px;
    color: #64748b; margin-bottom: 5px;
}
.tg-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.tg-chip {
    display: inline-block;
    font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
    font-size: 0.72rem; font-weight: 700;
    padding: 2px 7px; border-radius: 5px;
    border: 1px solid; cursor: default;
    letter-spacing: 0.2px;
}
/* per-class chip colours */
.tg-set  { background:#eff6ff; border-color:#bfdbfe; color:#1d4ed8; }
.tg-us   { background:#f0fdf4; border-color:#bbf7d0; color:#15803d; }
.tg-cry  { background:#fdf4ff; border-color:#e9d5ff; color:#7e22ce; }
.tg-com  { background:#fffbeb; border-color:#fde68a; color:#92400e; }
.tg-hk   { background:#fff1f2; border-color:#fecdd3; color:#be123c; }
.tg-tw   { background:#f0f9ff; border-color:#bae6fd; color:#075985; }
.tg-fx   { background:#f9fafb; border-color:#d1d5db; color:#374151; }
.tg-note {
    font-size: 0.68rem; color: #94a3b8;
    margin-top: 3px; font-style: italic;
}

/* ── MTF grid ──────────────────────────────────────────────────────────── */
.mtf-wrap {
    background: #fff; border-radius: 14px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    margin-bottom: 20px; overflow: hidden;
}
.mtf-header {
    background: linear-gradient(90deg, #1e293b 0%, #334155 100%);
    padding: 14px 20px;
    display: flex; justify-content: space-between; align-items: center;
}
.mtf-title { color: #fff; font-weight: 800; font-size: 0.95rem; }
.mtf-conf  { font-size: 1.15rem; font-weight: 900; letter-spacing: 1px; }
.mtf-conf-buy  { color: #34d399; }
.mtf-conf-sell { color: #f87171; }
.mtf-conf-neu  { color: #fbbf24; }
.mtf-bar-wrap {
    padding: 8px 20px 12px 20px;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
}
.mtf-bar-label { font-size: 0.72rem; color: #64748b; font-weight: 600; margin-bottom: 4px; }
.mtf-bar { height: 8px; border-radius: 99px; background: #e2e8f0; overflow: hidden; }
.mtf-bar-fill { height: 100%; border-radius: 99px; transition: width 0.4s; }
.mtf-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.mtf-table th {
    padding: 7px 12px; text-align: left;
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.8px;
    text-transform: uppercase; color: #94a3b8;
    background: #f8fafc; border-bottom: 1px solid #e2e8f0;
}
.mtf-table td {
    padding: 8px 12px; border-bottom: 1px solid #f1f5f9;
    color: #334155;
}
.mtf-table tr:last-child td { border-bottom: none; }
.mtf-table tr:hover td { background: #f8fafc; }
.tf-badge {
    display: inline-block;
    font-family: 'SF Mono','Monaco','Consolas',monospace;
    font-size: 0.75rem; font-weight: 700;
    padding: 2px 8px; border-radius: 5px;
    background: #1e293b; color: #e2e8f0;
}
.bias-buy  { color: #065f46; font-weight: 700; }
.bias-sell { color: #7f1d1d; font-weight: 700; }
.bias-neu  { color: #713f12; font-weight: 700; }
.na-row td { color: #cbd5e1 !important; font-style: italic; }
</style>
""",
    unsafe_allow_html=True,
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def api_key_ok() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

def groq_key_ok() -> bool:
    return bool(os.environ.get("GROQ_API_KEY", "").strip())


def ollama_running(url: str = "http://localhost:11434") -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(url, timeout=2)
        return True
    except Exception:
        return False


def ollama_models(url: str = "http://localhost:11434") -> list:
    try:
        import urllib.request, json
        with urllib.request.urlopen(f"{url}/api/tags", timeout=3) as r:
            data = json.loads(r.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def fmt_number(n):
    if n is None:
        return "N/A"
    if isinstance(n, (int, float)):
        if abs(n) >= 1e12:
            return f"{n/1e12:.2f}T"
        if abs(n) >= 1e9:
            return f"{n/1e9:.2f}B"
        if abs(n) >= 1e6:
            return f"{n/1e6:.2f}M"
        return f"{n:,.2f}"
    return str(n)


def pct(v):
    """Format a value that is already stored in percent form (e.g. 15.5 → '15.5%').
    Values come from _pct() in market_data.py which already multiplies by 100."""
    if v is None:
        return "N/A"
    return f"{float(v):.1f}%"


def _parse_final_rating(text: str) -> str | None:
    """
    Extract the CFA PM's structured FINAL RATING line.
    Looks for patterns like:
      "2. FINAL RATING: STRONG BUY"
      "**FINAL RATING:** BUY"
      "FINAL RATING: SELL"
    Returns one of: STRONG BUY | BUY | HOLD | SELL | STRONG SELL  or None.
    """
    import re as _re
    # Primary: match labelled "FINAL RATING" line
    m = _re.search(
        r'FINAL\s+RATING\s*[:\-–—]\s*(STRONG\s+BUY|STRONG\s+SELL|BUY|SELL|HOLD)',
        text, _re.IGNORECASE,
    )
    if m:
        return m.group(1).upper().strip()

    # Secondary: other labelled verdict lines
    m2 = _re.search(
        r'(?:^|\n)\s*(?:\d+\.)?\s*\*{0,2}(?:RATING|VERDICT|RECOMMENDATION|FINAL\s+CALL)\s*\*{0,2}\s*[:\-–—]\s*(STRONG\s+BUY|STRONG\s+SELL|BUY|SELL|HOLD)',
        text, _re.IGNORECASE | _re.MULTILINE,
    )
    if m2:
        return m2.group(1).upper().strip()

    return None


def _verdict_from_tally(tally: dict) -> str:
    """
    Derive a verdict string from the raw vote tally dict when CFA PM text
    parsing fails.  Returns one of: STRONG BUY | BUY | HOLD | SELL | STRONG SELL.
    """
    n_buy  = len(tally.get("BUY",  []))
    n_hold = len(tally.get("HOLD", []))
    n_sell = len(tally.get("SELL", []))
    n_total = n_buy + n_hold + n_sell
    if n_total == 0:
        return "HOLD"

    if n_buy > n_sell and n_buy > n_hold:
        return "STRONG BUY" if n_buy / n_total >= 0.625 else "BUY"
    if n_sell > n_buy and n_sell > n_hold:
        return "STRONG SELL" if n_sell / n_total >= 0.625 else "SELL"
    return "HOLD"


def _rating_to_css(rating: str) -> tuple[str, str]:
    """Map a clean rating string → (css_class, display_label)."""
    r = rating.upper().strip()
    if "STRONG BUY" in r:
        return "vb-sbuy",  "STRONG BUY ⚡"
    if "STRONG SELL" in r:
        return "vb-ssell", "STRONG SELL ⚡"
    if r == "BUY":
        return "vb-buy",   "BUY 📈"
    if r == "SELL":
        return "vb-sell",  "SELL 📉"
    return "vb-hold", "HOLD / รอดู"


def verdict_css(text: str, tally: dict | None = None) -> tuple[str, str]:
    """
    Return (css_class, display_label) for the IC verdict banner.
    Priority:
      1. Structured FINAL RATING line in CFA PM output  (most reliable)
      2. Vote majority tally                            (if parsing fails)
      3. Legacy keyword scan                            (last resort)
    """
    # 1. Parse structured line
    rating = _parse_final_rating(text)
    if rating:
        return _rating_to_css(rating)

    # 2. Derive from actual vote tally
    if tally:
        return _rating_to_css(_verdict_from_tally(tally))

    # 3. Legacy keyword scan (fallback only — less reliable)
    t = text.upper()
    if "STRONG BUY"  in t: return "vb-sbuy",  "STRONG BUY ⚡"
    if "STRONG SELL" in t: return "vb-ssell", "STRONG SELL ⚡"
    if "BUY"  in t:        return "vb-buy",   "BUY 📈"
    if "SELL" in t:        return "vb-sell",  "SELL 📉"
    return "vb-hold", "HOLD / รอดู"


def _mtf_conf_class(signal: str) -> str:
    s = signal.upper()
    if "BUY" in s or "ซื้อ" in s:
        return "mtf-conf-buy"
    if "SELL" in s or "ขาย" in s:
        return "mtf-conf-sell"
    return "mtf-conf-neu"


def render_mtf_grid(mtf_data: dict):
    """Render the 6-timeframe analysis grid as HTML."""
    conf       = mtf_data.get("confluence", {})
    signal_th  = conf.get("signal_th", "เป็นกลาง")
    dot        = conf.get("dot", "🟡")
    bull_pct   = conf.get("bull_pct", 50)
    bear_pct   = conf.get("bear_pct", 50)
    conf_cls   = _mtf_conf_class(signal_th)

    # Bull bar fill color
    if "ซื้อ" in signal_th:
        fill_color = "#10b981"
    elif "ขาย" in signal_th:
        fill_color = "#ef4444"
    else:
        fill_color = "#f59e0b"

    TF_ORDER = ["1mo", "1w", "1d", "4h", "1h", "15m"]
    TF_TH    = {
        "1mo": "รายเดือน",
        "1w":  "รายสัปดาห์",
        "1d":  "รายวัน",
        "4h":  "4 ชั่วโมง",
        "1h":  "1 ชั่วโมง",
        "15m": "15 นาที",
    }

    rows_html = ""
    for tf in TF_ORDER:
        d = mtf_data.get(tf, {})
        tf_name = TF_TH.get(tf, tf)
        if not d.get("available", True) or "trend_th" not in d:
            rows_html += (
                f'<tr class="na-row">'
                f'<td><span class="tf-badge">{tf}</span></td>'
                f'<td>{tf_name}</td>'
                f'<td colspan="4">ไม่มีข้อมูลเพียงพอ</td>'
                f'</tr>'
            )
            continue

        rsi_val  = d.get("rsi")
        rsi_str  = f'{rsi_val:.1f}' if rsi_val is not None else "—"
        rsi_zone = d.get("rsi_zone_th", "—")
        bias_th  = d.get("bias_th", "—")
        bias_dot = d.get("bias_dot", "🟡")
        bias     = d.get("bias", "NEUTRAL")
        b_cls    = "bias-buy" if bias == "BUY" else "bias-sell" if bias == "SELL" else "bias-neu"

        rows_html += (
            f'<tr>'
            f'<td><span class="tf-badge">{tf}</span></td>'
            f'<td>{tf_name}</td>'
            f'<td>{d.get("trend_th","—")}</td>'
            f'<td>{rsi_str} <span style="font-size:0.72rem;color:#94a3b8">{rsi_zone}</span></td>'
            f'<td>{d.get("macd_signal_th","—")}</td>'
            f'<td class="{b_cls}">{bias_dot} {bias_th}</td>'
            f'</tr>'
        )

    html = f"""
<div class="mtf-wrap">
  <div class="mtf-header">
    <span class="mtf-title">📊 Multi-Timeframe Analysis</span>
    <span class="mtf-conf {conf_cls}">{dot} {signal_th}</span>
  </div>
  <div class="mtf-bar-wrap">
    <div class="mtf-bar-label">Bull {bull_pct}% &nbsp;/&nbsp; Bear {bear_pct}%
      &nbsp;·&nbsp; {len(conf.get('tfs',[]))} timeframes available</div>
    <div class="mtf-bar">
      <div class="mtf-bar-fill" style="width:{bull_pct}%;background:{fill_color}"></div>
    </div>
  </div>
  <table class="mtf-table">
    <thead>
      <tr>
        <th>TF</th>
        <th>ชื่อ</th>
        <th>แนวโน้ม</th>
        <th>RSI</th>
        <th>MACD</th>
        <th>สัญญาณ</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</div>"""
    st.markdown(html, unsafe_allow_html=True)


def render_price_chart(A: dict):
    """Render a Plotly OHLCV candlestick chart from stored chart_records."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    records = A.get("chart_records", [])
    if not records:
        return

    df = pd.DataFrame(records)
    if df.empty or "Close" not in df.columns:
        return

    df["Date"] = pd.to_datetime(df["Date"])
    n = len(df)
    close = df["Close"]

    # SMA overlays
    sma20 = close.rolling(min(20, n)).mean() if n >= 10 else None
    sma50 = close.rolling(min(50, n)).mean() if n >= 30 else None

    has_volume = "Volume" in df.columns and df["Volume"].sum() > 0
    rows = 2 if has_volume else 1
    row_h = [0.75, 0.25] if has_volume else [1.0]

    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        row_heights=row_h,
        vertical_spacing=0.04,
    )

    # ── Candlestick ──────────────────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df["Date"],
        open=df["Open"], high=df["High"],
        low=df["Low"],   close=df["Close"],
        name="Price",
        increasing=dict(line=dict(color="#10b981"), fillcolor="#10b981"),
        decreasing=dict(line=dict(color="#ef4444"), fillcolor="#ef4444"),
    ), row=1, col=1)

    # ── SMA 20 ───────────────────────────────────────────────────────────────
    if sma20 is not None:
        fig.add_trace(go.Scatter(
            x=df["Date"], y=sma20,
            name="SMA 20", line=dict(color="#3b82f6", width=1.3, dash="dot"),
            opacity=0.8,
        ), row=1, col=1)

    # ── SMA 50 ───────────────────────────────────────────────────────────────
    if sma50 is not None:
        fig.add_trace(go.Scatter(
            x=df["Date"], y=sma50,
            name="SMA 50", line=dict(color="#f59e0b", width=1.3, dash="dash"),
            opacity=0.8,
        ), row=1, col=1)

    # ── Volume ───────────────────────────────────────────────────────────────
    if has_volume:
        bar_colors = [
            "#10b981" if c >= o else "#ef4444"
            for c, o in zip(df["Close"], df["Open"])
        ]
        fig.add_trace(go.Bar(
            x=df["Date"], y=df["Volume"],
            name="Volume", marker_color=bar_colors, opacity=0.5,
        ), row=2, col=1)

    ticker  = A.get("ticker", "")
    company = A.get("company", ticker)

    fig.update_layout(
        height=460,
        margin=dict(l=8, r=8, t=36, b=8),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f8fafc",
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01, x=0,
            font=dict(size=11),
        ),
        font=dict(size=11, color="#334155"),
        title=dict(
            text=f"<b>{ticker}</b> — {company}",
            font=dict(size=13, color="#334155"), x=0.01,
        ),
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor="#e2e8f0", showgrid=True, zeroline=False)
    fig.update_yaxes(gridcolor="#e2e8f0", showgrid=True, zeroline=False)

    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False})


def render_etf_holdings(ticker: str):
    """Fetch and display ETF top holdings table."""
    with st.spinner("กำลังโหลด holdings..."):
        holdings = get_etf_holdings(ticker)
    if not holdings:
        st.caption("ℹ️ Holdings data not available for this ticker (works best for US ETFs like SPY, QQQ, VTI)")
        return
    df = pd.DataFrame(holdings)
    df.columns = ["Symbol", "Name", "Weight (%)"]
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_trade_log():
    """Render the Trade Log page (📓 tab)."""
    import time as _time
    import uuid as _uuid
    from tools.trade_log import (
        TradeRecord, get_trades, delete_trade, clear_trades,
        update_prices, write_localstorage, ensure_loaded,
        fetch_prices_parallel, trades_to_json, trades_from_json,
    )

    # ── Load from localStorage on first visit ──────────────────────────────
    if not ensure_loaded():
        # First render: st_javascript hasn't resolved yet — rerun once.
        st.markdown(
            '<div style="color:#94a3b8;font-size:0.8rem;padding:8px">⌛ Loading trade log…</div>',
            unsafe_allow_html=True,
        )
        _time.sleep(0.15)
        st.rerun()

    trades = get_trades()

    # ── Header ─────────────────────────────────────────────────────────────
    st.markdown("## 📓 Trade Log")

    n_buy  = sum(1 for t in trades if t.action == "BUY")
    n_sell = sum(1 for t in trades if t.action == "SELL")

    badge_html = (
        f'<div style="display:flex;gap:10px;align-items:center;margin-bottom:16px">'
        f'<span style="background:#dcfce7;color:#15803d;border-radius:20px;'
        f'padding:3px 12px;font-size:0.8rem;font-weight:700">🟢 BUY: {n_buy}</span>'
        f'<span style="background:#fee2e2;color:#b91c1c;border-radius:20px;'
        f'padding:3px 12px;font-size:0.8rem;font-weight:700">🔴 SELL: {n_sell}</span>'
        f'<span style="background:#f1f5f9;color:#475569;border-radius:20px;'
        f'padding:3px 12px;font-size:0.8rem;font-weight:700">📋 Total: {len(trades)}</span>'
        f'</div>'
    )
    st.markdown(badge_html, unsafe_allow_html=True)

    # ── Action bar ─────────────────────────────────────────────────────────
    btn_col1, btn_col2, btn_col3, btn_col4 = st.columns([2, 1.3, 1.2, 1])
    with btn_col2:
        do_refresh = st.button(
            "🔄 Refresh All Prices",
            use_container_width=True,
            disabled=len(trades) == 0,
            help="Fetches current price for every ticker simultaneously",
        )
    with btn_col3:
        # Download as JSON
        if trades:
            st.download_button(
                "⬇️ Export JSON",
                data=trades_to_json(trades),
                file_name="trade_log.json",
                mime="application/json",
                use_container_width=True,
            )
        else:
            st.button("⬇️ Export JSON", disabled=True, use_container_width=True)
    with btn_col4:
        do_clear = st.button(
            "🗑️ Clear All",
            use_container_width=True,
            disabled=len(trades) == 0,
            type="secondary",
        )

    # ── Import from JSON ────────────────────────────────────────────────────
    with st.expander("📂 Import / Restore trade log from JSON", expanded=False):
        uploaded = st.file_uploader("Upload trade_log.json", type="json",
                                    label_visibility="collapsed")
        if uploaded:
            try:
                imported = trades_from_json(uploaded.read().decode())
                if imported:
                    # Merge: add only records not already in log (by id)
                    existing_ids = {t.id for t in get_trades()}
                    new_ones = [r for r in imported if r.id not in existing_ids]
                    for r in new_ones:
                        get_trades().insert(0, r)
                    st.session_state["trade_log"] = get_trades()
                    write_localstorage(get_trades())
                    st.success(f"✅ Imported {len(new_ones)} new trades")
                    st.rerun()
                else:
                    st.error("❌ File is empty or invalid")
            except Exception as _e:
                st.error(f"❌ Import failed: {_e}")

    st.markdown("---")

    # ── Refresh prices ──────────────────────────────────────────────────────
    if do_refresh and trades:
        tickers = list({t.ticker for t in trades})
        with st.spinner(f"🔄 Fetching prices for {len(tickers)} tickers…"):
            price_map = fetch_prices_parallel(tickers)
        update_prices(price_map)
        write_localstorage(get_trades())
        ok_count = sum(1 for v in price_map.values() if v is not None)
        st.success(f"✅ Updated {ok_count}/{len(tickers)} prices", icon="🔄")
        st.rerun()

    # ── Clear all ───────────────────────────────────────────────────────────
    if do_clear:
        clear_trades()
        write_localstorage([])
        st.rerun()

    # ── Trade table ─────────────────────────────────────────────────────────
    if not trades:
        st.info(
            "📭 No trades logged yet.\n\n"
            "Run an analysis, then click **📓 Log Trade** in the IC Verdict tab.",
            icon="💡",
        )
        return

    # Column headers
    hdr = st.columns([1.1, 0.85, 0.65, 0.9, 0.9, 1.0, 1.0, 1.6, 0.45])
    _header_style = "font-size:0.72rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.5px"
    for col, label in zip(hdr, ["Date", "Ticker", "Action", "Entry", "Current", "P&L %", "P&L Abs", "IC Verdict", "Del"]):
        col.markdown(f'<div style="{_header_style}">{label}</div>', unsafe_allow_html=True)

    st.markdown('<hr style="margin:4px 0 8px;border-color:#e2e8f0">', unsafe_allow_html=True)

    for trade in trades:
        pnl_pct = trade.pnl_pct()
        pnl_abs = trade.pnl_abs()

        # Row background tint based on P&L
        if pnl_pct is None:
            _row_bg = "#f8fafc"
        elif pnl_pct >= 0:
            _row_bg = "#f0fdf4"   # light green
        else:
            _row_bg = "#fff1f2"   # light red

        # P&L display strings
        if pnl_pct is not None:
            _pct_color = "#16a34a" if pnl_pct >= 0 else "#dc2626"
            _sign = "+" if pnl_pct >= 0 else ""
            _pct_str  = f'<span style="color:{_pct_color};font-weight:700">{_sign}{pnl_pct:.2f}%</span>'
            _abs_sign = "+" if pnl_abs and pnl_abs >= 0 else ""
            _abs_str  = f'<span style="color:{_pct_color}">{_abs_sign}{pnl_abs:.2f}</span>' if pnl_abs is not None else "—"
        else:
            _pct_str = '<span style="color:#94a3b8">—</span>'
            _abs_str = '<span style="color:#94a3b8">—</span>'

        # Current price display
        _cur_str = (
            f'<span style="font-weight:600">{trade.current_price:.2f}</span>'
            if trade.current_price is not None
            else '<span style="color:#94a3b8">—</span>'
        )

        # Action badge
        if trade.action == "BUY":
            _act_html = '<span style="background:#dcfce7;color:#15803d;border-radius:4px;padding:1px 7px;font-size:0.78rem;font-weight:700">BUY</span>'
        else:
            _act_html = '<span style="background:#fee2e2;color:#b91c1c;border-radius:4px;padding:1px 7px;font-size:0.78rem;font-weight:700">SELL</span>'

        # Truncate long verdict label
        _verdict = trade.ic_verdict[:20] + ("…" if len(trade.ic_verdict) > 20 else "")

        row = st.columns([1.1, 0.85, 0.65, 0.9, 0.9, 1.0, 1.0, 1.6, 0.45])
        row[0].markdown(
            f'<div style="font-size:0.82rem;color:#475569">{trade.logged_at[:16]}</div>',
            unsafe_allow_html=True,
        )
        row[1].markdown(
            f'<div style="font-weight:700;color:#1e293b">{trade.ticker}</div>'
            f'<div style="font-size:0.72rem;color:#94a3b8">{trade.currency}</div>',
            unsafe_allow_html=True,
        )
        row[2].markdown(_act_html, unsafe_allow_html=True)
        row[3].markdown(
            f'<div style="font-size:0.85rem">{trade.entry_price:.2f}</div>',
            unsafe_allow_html=True,
        )
        row[4].markdown(_cur_str, unsafe_allow_html=True)
        row[5].markdown(_pct_str, unsafe_allow_html=True)
        row[6].markdown(_abs_str, unsafe_allow_html=True)
        row[7].markdown(
            f'<div style="font-size:0.78rem;color:#475569" title="{trade.ic_verdict}">{_verdict}</div>'
            f'<div style="font-size:0.7rem;color:#94a3b8">{trade.company[:18]}</div>',
            unsafe_allow_html=True,
        )
        if row[8].button("🗑", key=f"del_{trade.id}", help="Delete this trade"):
            delete_trade(trade.id)
            write_localstorage(get_trades())
            st.rerun()

        st.markdown(
            f'<hr style="margin:3px 0;border-color:{_row_bg if _row_bg != "#f8fafc" else "#f1f5f9"}">',
            unsafe_allow_html=True,
        )

    if trades and trades[0].last_refreshed:
        st.caption(f"🕐 Last price refresh: {trades[0].last_refreshed}")

    # ── Sync localStorage on every render of this page ──────────────────────
    # (keeps localStorage consistent even after deletes / imports)
    write_localstorage(get_trades())


def render_dashboard(A: dict):
    """
    Render the full results dashboard (metrics, MTF grid, PDF download, tabs)
    from a stored analysis dict. Reads ONLY from `A` so it can repaint on any
    rerun (e.g. after a PDF-download click) without re-running the AI pipeline.
    """
    ticker            = A["ticker"]
    company           = A["company"]
    asset_class       = A["asset_class"]
    market            = A.get("market", "")      # needed for TradingView link
    info              = A["info"]
    technicals        = A["technicals"]
    news              = A["news"]
    mtf_data          = A["mtf_data"]
    price             = A["price"]
    mode              = A["mode"]
    ic_mode           = A["ic_mode"]
    research_output   = A["research_output"]
    critique_output   = A["critique_output"]
    fact_check_output = A["fact_check_output"]
    trade_card_text   = A["trade_card_text"]
    risk_output       = A["risk_output"]
    ic_results        = A["ic_results"]

    # ── Data date badge ───────────────────────────────────────────────────────
    from datetime import datetime
    last_bar  = technicals.get("last_bar_date") or "—"
    run_at    = A.get("run_at") or datetime.now().strftime("%Y-%m-%d %H:%M")
    st.markdown(
        f'<div style="display:flex;gap:16px;align-items:center;'
        f'font-size:0.75rem;color:#64748b;margin-bottom:8px">'
        f'<span>📅 <b>Data as of:</b> {last_bar}</span>'
        f'<span>🕐 <b>Analysis run:</b> {run_at}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Metric strip ──────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    _curr = info.get("currency", "")
    _price_str = (f"{price:,.4g} {_curr}".strip() if price and _curr
                  else f"{price:,.4g}" if price else "N/A")
    change_val = technicals.get("change_1d_pct") or 0
    _delta_str = f"{change_val:+.2f}%" if change_val else None
    m1.metric("Price", _price_str, delta=_delta_str)
    m2.metric("RSI(14)", technicals.get("rsi") or "—")
    if asset_class == "crypto":
        m3.metric("MC Rank",  f"#{info.get('market_cap_rank','—')}")
        m5.metric("ATH",      fmt_number(info.get("ath")))
    else:
        _pe = info.get("pe_ratio")
        m3.metric("P/E", f"{_pe:.1f}" if isinstance(_pe, float) else "—")
        _52h = technicals.get("high_52w") or info.get("52w_high")
        m5.metric("52W High", f"{_52h:,.4g}" if _52h else "—")
    m4.metric("Market Cap", fmt_number(info.get("market_cap")))

    st.markdown("---")

    # ── MTF grid ──────────────────────────────────────────────────────────────
    if mtf_data:
        render_mtf_grid(mtf_data)

    # ── PDF download ──────────────────────────────────────────────────────────
    dl_col, _ = st.columns([1, 2])
    with dl_col:
        try:
            from tools.pdf_export import build_pdf
            from datetime import date
            pdf_bytes = build_pdf(A)
            st.download_button(
                "📥 Download PDF Report",
                data=pdf_bytes,
                file_name=f"{ticker}_Lastmercy_{date.today().isoformat()}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.warning(f"PDF generation failed: {e}", icon="⚠️")

    # ── Results ───────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:0.75rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;'
        'color:#94a3b8;margin:14px 0 12px">📋 ANALYSIS RESULTS</div>',
        unsafe_allow_html=True,
    )

    tabs_to_show = ["📊 Overview"]
    if mode in ("short", "both") and trade_card_text:
        tabs_to_show.append("🎯 Trade Card")
    if mode in ("long", "both") and ic_results:
        tabs_to_show.append("🏛️ IC Verdict")
    tabs_to_show += ["📊 MTF Detail", "🔍 Research", "📰 Market Data"]

    tabs    = st.tabs(tabs_to_show)
    tab_map = {name: tab for name, tab in zip(tabs_to_show, tabs)}

    # ── Overview tab ─────────────────────────────────────────────────────────
    with tab_map["📊 Overview"]:
        # ── Price Chart (Plotly OHLCV) ────────────────────────────────────
        render_price_chart(A)
        # TradingView full chart link (opens in new tab)
        _tv_sym = to_tradingview_symbol(ticker, asset_class, market)
        _tv_url = f"https://www.tradingview.com/chart/?symbol={_tv_sym}"
        _lc, _ = st.columns([1, 3])
        with _lc:
            st.link_button("📈 Full Chart on TradingView ↗", url=_tv_url,
                           use_container_width=True)
        st.markdown("---")

        scol, rcol = st.columns([1, 1])
        with scol:
            st.markdown(f"### {company}")
            st.markdown(f"**Ticker:** `{ticker}` | **Sector:** {info.get('sector','N/A')} | **Industry:** {info.get('industry','N/A')}")
            desc = info.get("description", "")
            if desc:
                st.markdown(desc[:300] + ("…" if len(desc) > 300 else ""))

            # Thai fund info
            if asset_class == "fund":
                fund_info = get_thai_fund_info(ticker)
                if fund_info:
                    st.info(
                        f"🏦 **{fund_info['name']}**\n\n"
                        f"ข้อมูลกองทุนไทยไม่ได้อยู่บน Yahoo Finance — "
                        f"ดูข้อมูล NAV และ holdings ได้ที่:\n"
                        f"[{fund_info['url']}]({fund_info['url']}) "
                        f"หรือ [SEC Thailand](https://www.sec.or.th)",
                        icon="🏦",
                    )

        with rcol:
            st.markdown("#### Key Metrics")
            _curr = info.get("currency", "")
            _price_label = (f"{price:,.4g} {_curr}" if price and _curr
                            else f"{price:,.4g}" if price else "N/A")
            kdf = {
                "Current Price":   _price_label,
                "Market Cap":      fmt_number(info.get("market_cap")),
                "P/E Ratio":       info.get("pe_ratio") or "N/A",
                "P/B Ratio":       info.get("pb_ratio") or "N/A",
                "ROE":             pct(info.get("roe")),
                "Net Margin":      pct(info.get("net_margin")),
                "52W High":        technicals.get("high_52w") or info.get("52w_high") or "N/A",
                "52W Low":         technicals.get("low_52w") or info.get("52w_low") or "N/A",
                "Beta":            info.get("beta") or "N/A",
                "Analyst Target":  info.get("analyst_target") or "N/A",
                "Dividend Yield":  pct(info.get("dividend_yield")) if info.get("dividend_yield") else "N/A",
            }
            st.dataframe(
                pd.DataFrame(list(kdf.items()), columns=["Metric", "Value"]),
                use_container_width=True,
                hide_index=True,
            )

        # ── ETF Holdings ──────────────────────────────────────────────────
        if asset_class in ("etf", "stock") and not ticker.endswith(".BK"):
            with st.expander("🗂 ETF / Fund Holdings (top 15)", expanded=False):
                render_etf_holdings(ticker)

        if news:
            st.markdown("#### Latest News")
            for n in news[:5]:
                title = n.get("title", "").strip()
                link  = n.get("link", "").strip()
                pub   = n.get("publisher", "").strip()
                if title and link:
                    st.markdown(f"- [{title}]({link}) — *{pub}*")
                elif title:
                    st.markdown(f"- {title} — *{pub}*")

    # ── Trade Card tab ──────────────────────────────────────────────────────
    if "🎯 Trade Card" in tab_map:
        with tab_map["🎯 Trade Card"]:
            direction = "LONG" if "LONG" in trade_card_text.upper() else "SHORT"
            css_cls   = "tc-long"  if direction == "LONG" else "tc-short"
            dir_icon  = "▲ LONG (Buy)" if direction == "LONG" else "▼ SHORT (Sell)"

            st.markdown(
                f'<div class="tc {css_cls}">'
                f'<div class="tc-header">{dir_icon} &nbsp; {ticker} &nbsp;·&nbsp; Trade Signal</div>'
                f'<div class="tc-body"></div></div>',
                unsafe_allow_html=True,
            )

            tc_col, rs_col = st.columns([1, 1])
            with tc_col:
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.markdown("**📋 Signal Details**")
                st.markdown(trade_card_text)
                st.markdown('</div>', unsafe_allow_html=True)
            with rs_col:
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.markdown("**🛡️ Position Management**")
                st.markdown(risk_output)
                st.markdown('</div>', unsafe_allow_html=True)

    # ── IC Verdict tab ──────────────────────────────────────────────────────
    if "🏛️ IC Verdict" in tab_map:
        with tab_map["🏛️ IC Verdict"]:
            # ── Vote Tally — read first so verdict banner can use it ─────────
            tally = ic_results.get("_vote_tally", {})

            if "CFAPortfolioManager" in ic_results:
                final_text = ic_results["CFAPortfolioManager"]["output"]
                # Pass tally so verdict_css uses structured parsing → tally fallback
                css, label = verdict_css(final_text, tally=tally or None)

                # Show parsed source so user can trust the label
                _rating_src = "CFA PM" if _parse_final_rating(final_text) else "Vote Majority"
                st.markdown(
                    f'<div class="verdict-banner {css}">{label}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(f"📌 Verdict derived from: **{_rating_src}**")

                # ── Log Trade button ─────────────────────────────────────────
                _lbl_clean = label.replace("⚡", "").replace("📈", "").replace("📉", "").strip()
                _log_action = (
                    "BUY"  if "BUY"  in _lbl_clean else
                    "SELL" if "SELL" in _lbl_clean else
                    None
                )
                if _log_action:
                    _btn_color = "#16a34a" if _log_action == "BUY" else "#dc2626"
                    _log_key   = f"log_trade_{ticker}_{A.get('run_at','')}"
                    st.markdown(
                        f'<style>div[data-testid="stButton"] button[kind="secondary"]'
                        f'{{border-color:{_btn_color};color:{_btn_color}}}</style>',
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        f"📓 Log Trade — {_log_action} {ticker}",
                        key=_log_key,
                        type="secondary",
                        help="Save this trade to your Trade Log for P&L tracking",
                    ):
                        import uuid as _uuid
                        from tools.trade_log import TradeRecord, add_trade, write_localstorage, get_trades
                        from datetime import datetime as _dt2
                        _rec = TradeRecord(
                            id          = _uuid.uuid4().hex[:8],
                            ticker      = ticker,
                            company     = company,
                            action      = _log_action,
                            entry_price = float(price or 0),
                            currency    = info.get("currency", "USD"),
                            ic_verdict  = _lbl_clean,
                            logged_at   = A.get("run_at") or _dt2.now().strftime("%Y-%m-%d %H:%M"),
                        )
                        add_trade(_rec)
                        write_localstorage(get_trades())
                        st.success(
                            f"✅ Logged: **{_log_action} {ticker}** @ {price} {info.get('currency','USD')}  "
                            f"→ go to **📓 Trade Log** tab to track P&L",
                            icon="📓",
                        )

                st.markdown("### IC Final Verdict")
                st.markdown(final_text)
                st.markdown("---")
            if tally:
                n_buy  = len(tally.get("BUY",  []))
                n_hold = len(tally.get("HOLD", []))
                n_sell = len(tally.get("SELL", []))
                n_total = n_buy + n_hold + n_sell
                buy_pct  = round(n_buy  / n_total * 100) if n_total else 0
                hold_pct = round(n_hold / n_total * 100) if n_total else 0
                sell_pct = 100 - buy_pct - hold_pct if n_total else 0
                buy_voters  = ", ".join(tally.get("BUY",  [])) or "—"
                hold_voters = ", ".join(tally.get("HOLD", [])) or "—"
                sell_voters = ", ".join(tally.get("SELL", [])) or "—"

                # Check if CFA PM verdict differs from vote majority
                _majority = _verdict_from_tally(tally)
                _pm_rating = (_parse_final_rating(ic_results.get("CFAPortfolioManager", {}).get("output", ""))
                              if "CFAPortfolioManager" in ic_results else None)
                _override_note = ""
                if _pm_rating and _majority:
                    _maj_side  = "BUY"  if "BUY"  in _majority  else "SELL" if "SELL"  in _majority  else "HOLD"
                    _pm_side   = "BUY"  if "BUY"  in _pm_rating else "SELL" if "SELL"  in _pm_rating else "HOLD"
                    if _maj_side != _pm_side:
                        _override_note = (
                            f'<div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;'
                            f'padding:8px 14px;margin-top:10px;font-size:0.8rem;color:#92400e">'
                            f'⚠️ CFA PM overrode majority: Vote = <b>{_majority}</b> → PM = <b>{_pm_rating}</b>'
                            f'</div>'
                        )

                st.markdown("### 🗳️ IC Vote Summary")
                st.markdown(
                    f"""
<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px 20px;margin-bottom:16px">
  <div style="display:flex;gap:12px;margin-bottom:10px">
    <div style="flex:1;background:#dcfce7;border-radius:8px;padding:10px 14px;text-align:center">
      <div style="font-size:1.5rem;font-weight:800;color:#16a34a">{n_buy}</div>
      <div style="font-size:0.8rem;font-weight:600;color:#15803d">BUY</div>
    </div>
    <div style="flex:1;background:#fef9c3;border-radius:8px;padding:10px 14px;text-align:center">
      <div style="font-size:1.5rem;font-weight:800;color:#ca8a04">{n_hold}</div>
      <div style="font-size:0.8rem;font-weight:600;color:#a16207">HOLD</div>
    </div>
    <div style="flex:1;background:#fee2e2;border-radius:8px;padding:10px 14px;text-align:center">
      <div style="font-size:1.5rem;font-weight:800;color:#dc2626">{n_sell}</div>
      <div style="font-size:0.8rem;font-weight:600;color:#b91c1c">SELL</div>
    </div>
    <div style="flex:1;background:#f1f5f9;border-radius:8px;padding:10px 14px;text-align:center">
      <div style="font-size:1.5rem;font-weight:800;color:#475569">{n_total}</div>
      <div style="font-size:0.8rem;font-weight:600;color:#64748b">Total</div>
    </div>
  </div>
  <div style="height:12px;border-radius:6px;overflow:hidden;display:flex;background:#e2e8f0">
    <div style="width:{buy_pct}%;background:#22c55e;transition:width 0.4s"></div>
    <div style="width:{hold_pct}%;background:#eab308;transition:width 0.4s"></div>
    <div style="width:{sell_pct}%;background:#ef4444;transition:width 0.4s"></div>
  </div>
  <div style="display:flex;justify-content:space-between;font-size:0.72rem;color:#64748b;margin-top:5px">
    <span>BUY {buy_pct}%</span><span>HOLD {hold_pct}%</span><span>SELL {sell_pct}%</span>
  </div>
  <div style="margin-top:10px;font-size:0.8rem;color:#475569;line-height:1.7">
    <span style="color:#15803d">BUY:</span> {buy_voters}<br>
    <span style="color:#a16207">HOLD:</span> {hold_voters}<br>
    <span style="color:#b91c1c">SELL:</span> {sell_voters}
  </div>
  {_override_note}
</div>""",
                    unsafe_allow_html=True,
                )
                st.markdown("---")

            st.markdown("### Individual Agent Views")
            for name, data in ic_results.items():
                if name in ("CFAPortfolioManager", "_vote_tally"):
                    continue
                vote     = data.get("vote")
                vote_tag = (
                    " 🟢 BUY" if vote == "BUY" else
                    " 🟡 HOLD" if vote == "HOLD" else
                    " 🔴 SELL" if vote == "SELL" else ""
                )
                with st.expander(f"{data['emoji']} {data['title']}{vote_tag}"):
                    st.markdown(data["output"])

    # ── MTF Detail tab ──────────────────────────────────────────────────────
    with tab_map["📊 MTF Detail"]:
        if mtf_data:
            st.markdown("### 📊 Multi-Timeframe Analysis — Detail")
            render_mtf_grid(mtf_data)

            st.markdown("#### Per-Timeframe Breakdown")
            TF_ORDER = ["1mo", "1w", "1d", "4h", "1h", "15m"]
            TF_LABEL = {
                "1mo": "Monthly", "1w": "Weekly", "1d": "Daily",
                "4h":  "4-Hour",  "1h": "1-Hour", "15m": "15-Min",
            }
            for tf in TF_ORDER:
                d = mtf_data.get(tf, {})
                label = f"**{tf}** · {TF_LABEL.get(tf,'')}"
                if not d.get("available", True) or "trend_th" not in d:
                    with st.expander(f"{label} — No data"):
                        st.caption("Insufficient data for this timeframe")
                    continue
                bias_dot = d.get("bias_dot", "🟡")
                bias_en  = d.get("bias_en", d.get("bias_th", "Neutral"))
                trend_en = d.get("trend_en", d.get("trend_th", "?"))
                with st.expander(f"{label} · {bias_dot} {bias_en}  |  {trend_en}  |  RSI {d.get('rsi','—')}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Price",  d.get("price", "—"))
                        st.metric("Change", f"{d.get('change_pct','—')}%")
                    with col2:
                        st.metric("Resistance", d.get("resistance", "—"))
                        st.metric("Support",    d.get("support", "—"))
                    with col3:
                        st.metric("RSI",   d.get("rsi", "—"))
                        st.metric("SMA20", d.get("sma20", "—"))
                        st.metric("SMA50", d.get("sma50", "—"))
        else:
            st.info("No MTF data available for this asset.", icon="📊")

    # ── Research tab ─────────────────────────────────────────────────────────
    with tab_map["🔍 Research"]:
        r1, r2, r3 = st.tabs(["🔍 Wizard — Research", "⚔️ Sage — Critique", "✅ Priest — Fact-Check"])
        with r1:
            st.markdown(research_output)
        with r2:
            st.markdown(critique_output)
        with r3:
            st.markdown(fact_check_output)

    # ── Market Data tab ───────────────────────────────────────────────────────
    with tab_map["📰 Market Data"]:
        d1, d2 = st.columns(2)
        with d1:
            st.markdown("#### Technical Indicators")
            tech_display = {k: v for k, v in technicals.items() if v is not None and not isinstance(v, bool)}
            st.json(tech_display)
        with d2:
            st.markdown("#### Fundamentals")
            fund_display = {k: v for k, v in info.items() if v is not None and k not in ("description", "error")}
            st.json(fund_display)

    st.markdown("---")
    st.caption(
        f"Analysis complete: **{ticker}** | Mode: **{mode.upper()}** | IC Depth: **{ic_mode}** | "
        f"MTF: **{len(mtf_data.get('confluence',{}).get('tfs',[]))} timeframes**"
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="font-size:1.25rem;font-weight:800;color:#1e293b;padding:4px 0 2px">💎 Lastmercy Trading Pro</div>'
        '<div style="font-size:0.75rem;color:#94a3b8;margin-bottom:12px">multi-agent AI · multi-provider</div>',
        unsafe_allow_html=True,
    )

    # ── Page navigation ───────────────────────────────────────────────────────
    _page = st.radio(
        "Navigate",
        ["📊 Analysis", "📓 Trade Log"],
        horizontal=True,
        label_visibility="collapsed",
        key="page_nav",
    )
    st.markdown('<hr style="margin:10px 0 14px;border-color:#e2e8f0">', unsafe_allow_html=True)

    # ── Provider selection ────────────────────────────────────────────────────
    st.markdown("### 🤖 AI Provider")
    if _IS_CLOUD:
        _provider_options = [
            "⚡ Groq (Free · Fast)",
            "☁️ Anthropic Claude (API Key)",
        ]
        provider_choice = st.radio(
            "Select AI Engine", _provider_options, index=0,
            help="Groq is free and very fast. Anthropic gives the highest quality output.",
        )
        use_ollama = False
    else:
        _provider_options = [
            "🦙 Ollama (Local · Free)",
            "⚡ Groq (Cloud · Free)",
            "☁️ Anthropic Claude (API Key)",
        ]
        provider_choice = st.radio(
            "Select AI Engine", _provider_options, index=0,
            help="Ollama = local/free · Groq = cloud/free · Anthropic = best quality",
        )
        use_ollama = provider_choice.startswith("🦙")

    use_groq = provider_choice.startswith("⚡")

    if use_ollama:
        os.environ["AI_PROVIDER"] = "ollama"

        ollama_ok = ollama_running()
        if ollama_ok:
            available_models = ollama_models()
            if available_models:
                preferred = ["qwen2.5:14b", "qwen2.5:7b", "llama3.1:8b",
                             "llama3.2:latest", "llama3.2:3b", "mistral:latest",
                             "gemma2:9b", "deepseek-r1:8b"]
                default_model = next(
                    (m for m in preferred if any(m in am for am in available_models)),
                    available_models[0]
                )
                selected_model = st.selectbox(
                    "Model",
                    available_models,
                    index=available_models.index(default_model) if default_model in available_models else 0,
                    help="Models already pulled on your machine.",
                )
                os.environ["OLLAMA_MODEL"] = selected_model
                st.success(f"Ollama ready — {len(available_models)} model(s)", icon="✅")
                st.info(
                    "⏱️ **Ollama speed tips:**\n"
                    "- ใช้ **quick IC (5 agents)** เร็วที่สุด\n"
                    "- M1/M2 Mac ~2-4 min · CPU only ~8-12 min\n"
                    "- เร็วขึ้น 4× ถ้าเปลี่ยนไปใช้ Anthropic API",
                    icon="💡",
                )
            else:
                st.warning("Ollama is running but no models found.", icon="⚠️")
                st.markdown(
                    "Pull a model first:\n"
                    "```bash\nollama pull qwen2.5:7b\n```"
                )
                os.environ["OLLAMA_MODEL"] = "qwen2.5:7b"
        else:
            st.error("Ollama is not running.", icon="❌")
            with st.expander("📥 How to install Ollama", expanded=True):
                st.markdown("""
**Step 1 — Install Ollama**
```bash
# macOS
brew install ollama
# or download at:
# https://ollama.com/download
```

**Step 2 — Start Ollama**
```bash
ollama serve
```

**Step 3 — Pull a model**
```bash
# Recommended for investment analysis:
ollama pull qwen2.5:7b    # RAM ~5GB ✅
ollama pull qwen2.5:14b   # RAM ~10GB ⚡ (better)
ollama pull llama3.1:8b   # alternative
```

**Step 4 — Reload this page**
                """)

    if use_groq:
        os.environ["AI_PROVIDER"] = "groq"
        if not groq_key_ok():
            groq_key_input = st.text_input(
                "🔑 Groq API Key",
                type="password",
                placeholder="gsk_...",
                help="สมัครฟรีที่ console.groq.com — ไม่ต้องใส่บัตรเครดิต",
            )
            if groq_key_input:
                os.environ["GROQ_API_KEY"] = groq_key_input.strip()
        else:
            st.success("Groq API Key loaded ✓", icon="⚡")
        st.caption("Model: llama-3.3-70b · llama-3.1-8b-instant (fast tasks)")
        st.info(
            "⚠️ **Groq Free Tier limits:**\n"
            "- 30 req/min · 6k tokens/min\n"
            "- IC Committee ใช้ tokens เยอะ → แนะนำ **quick (5 agents)**\n"
            "- ถ้า error ให้รอ 2-3 นาทีแล้วลองใหม่",
            icon="⚡",
        )

    elif not use_groq and not use_ollama:
        os.environ["AI_PROVIDER"] = "anthropic"
        if not api_key_ok():
            api_key_input = st.text_input(
                "🔑 Anthropic API Key",
                type="password",
                placeholder="sk-ant-...",
                help="Get your key at console.anthropic.com · or set in .env",
            )
            if api_key_input:
                os.environ["ANTHROPIC_API_KEY"] = api_key_input.strip()
        else:
            st.success("API Key loaded ✓", icon="🔑")

    # ── Asset input ───────────────────────────────────────────────────────────
    st.markdown("### 📌 Asset")
    ticker_input = st.text_input(
        "Ticker Symbol",
        placeholder="AAPL · PTT · BTC · GOLD · 9988.HK · 7203.T",
        help="Type any ticker, name, or pair — fuzzy search finds it even with typos.",
    )

    # ── Fuzzy search suggestions ──────────────────────────────────────────────
    if ticker_input and len(ticker_input.strip()) >= 2:
        _raw = ticker_input.strip()
        _suggestions = fuzzy_suggest(_raw, n=5)
        # Only show suggestions if the top hit looks different from raw input
        _top_sym = _suggestions[0]["ticker"] if _suggestions else ""
        _show = (
            len(_suggestions) > 0
            and _raw.upper() not in {s["ticker"].replace(".BK","").replace("-USD","") for s in _suggestions}
        )
        if _show and len(_suggestions) > 1:
            st.markdown(
                '<div style="font-size:0.72rem;color:#64748b;margin-bottom:3px">'
                '🔍 Did you mean?</div>',
                unsafe_allow_html=True,
            )
            for s in _suggestions[:4]:
                _disp = s["display"][:45]
                _sym  = s["ticker"]
                st.markdown(
                    f'<div style="font-size:0.73rem;padding:2px 0;color:#4f46e5">'
                    f'<code style="font-size:0.72rem">{_sym}</code> — {_disp}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── Ticker format reference card ──────────────────────────────────────────
    with st.expander("📖 Ticker format guide by country / asset class", expanded=False):
        st.markdown(
            """
<div class="tg-card">

<div class="tg-row">
  <div class="tg-label">🇹🇭 Thai Stocks (SET / MAI) — 450+ tickers</div>
  <div class="tg-chips">
    <span class="tg-chip tg-set">PTT</span>
    <span class="tg-chip tg-set">GPSC</span>
    <span class="tg-chip tg-set">KBANK</span>
    <span class="tg-chip tg-set">AOT</span>
    <span class="tg-chip tg-set">DELTA</span>
    <span class="tg-chip tg-set">ADVANC</span>
    <span class="tg-chip tg-set">CPALL</span>
    <span class="tg-chip tg-set">GULF</span>
    <span class="tg-chip tg-set">MINT</span>
    <span class="tg-chip tg-set">IVL</span>
  </div>
  <div class="tg-note">พิมพ์ symbol ตรงๆ → ระบบเติม .BK อัตโนมัติ · ใส่ fuzzy search พิมพ์ผิดนิดหน่อยก็ได้<br>ถ้าไม่เจอ ลองเพิ่ม .BK ต่อท้าย เช่น <b>GULF.BK</b></div>
</div>

<div class="tg-row">
  <div class="tg-label">🇺🇸 US Stocks / ETFs</div>
  <div class="tg-chips">
    <span class="tg-chip tg-us">AAPL</span>
    <span class="tg-chip tg-us">NVDA</span>
    <span class="tg-chip tg-us">TSLA</span>
    <span class="tg-chip tg-us">SPY</span>
    <span class="tg-chip tg-us">QQQ</span>
    <span class="tg-chip tg-us">VTI</span>
    <span class="tg-chip tg-us">ARKK</span>
  </div>
  <div class="tg-note">Type the ticker directly — no suffix needed · ETF holdings shown in Overview tab</div>
</div>

<div class="tg-row">
  <div class="tg-label">₿ Crypto — top 100</div>
  <div class="tg-chips">
    <span class="tg-chip tg-cry">BTC</span>
    <span class="tg-chip tg-cry">ETH</span>
    <span class="tg-chip tg-cry">SOL</span>
    <span class="tg-chip tg-cry">BNB</span>
    <span class="tg-chip tg-cry">XRP</span>
    <span class="tg-chip tg-cry">DOGE</span>
    <span class="tg-chip tg-cry">AVAX</span>
    <span class="tg-chip tg-cry">PEPE</span>
    <span class="tg-chip tg-cry">SUI</span>
    <span class="tg-chip tg-cry">TON</span>
  </div>
  <div class="tg-note">Binance format ก็ได้ → <b>BTCUSDT</b>, <b>ETHUSDT</b> · Full name: <b>bitcoin</b>, <b>solana</b></div>
</div>

<div class="tg-row">
  <div class="tg-label">🥇 Commodities</div>
  <div class="tg-chips">
    <span class="tg-chip tg-com">GOLD</span>
    <span class="tg-chip tg-com">SILVER</span>
    <span class="tg-chip tg-com">OIL</span>
    <span class="tg-chip tg-com">BRENT</span>
    <span class="tg-chip tg-com">NATGAS</span>
    <span class="tg-chip tg-com">COPPER</span>
    <span class="tg-chip tg-com">WHEAT</span>
    <span class="tg-chip tg-com">PLATINUM</span>
  </div>
  <div class="tg-note">Type the English name → system maps to futures symbol</div>
</div>

<div class="tg-row">
  <div class="tg-label">💱 Forex — 35+ pairs</div>
  <div class="tg-chips">
    <span class="tg-chip tg-fx">EURUSD</span>
    <span class="tg-chip tg-fx">GBPUSD</span>
    <span class="tg-chip tg-fx">USDJPY</span>
    <span class="tg-chip tg-fx">USDTHB</span>
    <span class="tg-chip tg-fx">AUDUSD</span>
    <span class="tg-chip tg-fx">USDSGD</span>
    <span class="tg-chip tg-fx">USDCNY</span>
    <span class="tg-chip tg-fx">EURGBP</span>
  </div>
  <div class="tg-note">พิมพ์คู่เงิน 6 ตัวอักษร · รองรับ slash ด้วย: <b>EUR/USD</b>, <b>USD/THB</b></div>
</div>

<div class="tg-row">
  <div class="tg-label">🇭🇰 Hong Kong · 🇹🇼 Taiwan · 🇨🇳 China</div>
  <div class="tg-chips">
    <span class="tg-chip tg-hk">9988.HK</span>
    <span class="tg-chip tg-hk">0700.HK</span>
    <span class="tg-chip tg-tw">2330.TW</span>
    <span class="tg-chip tg-tw">2454.TW</span>
    <span class="tg-chip tg-hk">601318.SS</span>
    <span class="tg-chip tg-hk">000858.SZ</span>
  </div>
  <div class="tg-note">ใส่ suffix ตามตลาด: <b>.HK</b> · <b>.TW</b> · <b>.SS</b> (Shanghai) · <b>.SZ</b> (Shenzhen)</div>
</div>

<div class="tg-row">
  <div class="tg-label">🇯🇵 Japan · 🇰🇷 Korea · 🇸🇬 Singapore</div>
  <div class="tg-chips">
    <span class="tg-chip tg-fx">7203.T</span>
    <span class="tg-chip tg-fx">9984.T</span>
    <span class="tg-chip tg-fx">005930.KS</span>
    <span class="tg-chip tg-fx">035420.KS</span>
    <span class="tg-chip tg-fx">D05.SI</span>
    <span class="tg-chip tg-fx">Z74.SI</span>
  </div>
  <div class="tg-note">Japan <b>.T</b> · Korea <b>.KS</b> · Singapore <b>.SI</b> · พิมพ์แค่ตัวเลข 4 หลัก → ระบบลอง .T อัตโนมัติ</div>
</div>

<div class="tg-row">
  <div class="tg-label">🇩🇪 Europe · 🇬🇧 UK · 🇦🇺 Australia</div>
  <div class="tg-chips">
    <span class="tg-chip tg-fx">SAP.DE</span>
    <span class="tg-chip tg-fx">BAS.DE</span>
    <span class="tg-chip tg-fx">SHEL.L</span>
    <span class="tg-chip tg-fx">HSBA.L</span>
    <span class="tg-chip tg-fx">BHP.AX</span>
    <span class="tg-chip tg-fx">CBA.AX</span>
  </div>
  <div class="tg-note">Germany <b>.DE</b> · London <b>.L</b> · Australia <b>.AX</b></div>
</div>

<div class="tg-row">
  <div class="tg-label">📊 Market Indices · 🏦 Thai Funds</div>
  <div class="tg-chips">
    <span class="tg-chip tg-com">SP500</span>
    <span class="tg-chip tg-com">NASDAQ</span>
    <span class="tg-chip tg-com">NIKKEI</span>
    <span class="tg-chip tg-com">KOSPI</span>
    <span class="tg-chip tg-com">VIX</span>
    <span class="tg-chip tg-set">KF-CHINA</span>
    <span class="tg-chip tg-set">SCBTHAI</span>
  </div>
  <div class="tg-note">กองทุนไทย พิมพ์ fund code เช่น <b>KF-CHINA</b>, <b>SCBTHAI</b>, <b>BBLPLUS</b></div>
</div>

</div>
""",
            unsafe_allow_html=True,
        )

    pdf_file = st.file_uploader(
        "📎 Upload PDF report (optional)",
        type=["pdf"],
        help="Annual report, analyst report, or any PDF to add context for the AI.",
    )

    st.markdown("### ⚙️ Analysis Mode")
    analysis_type = st.radio(
        "What type of analysis?",
        options=["🔀 Both (Short + Long term)", "⚡ Trade Signals (Short term)", "📊 Investment Committee (Long term)"],
        index=0,
    )
    mode_map = {
        "🔀 Both (Short + Long term)":       "both",
        "⚡ Trade Signals (Short term)":      "short",
        "📊 Investment Committee (Long term)": "long",
    }
    mode = mode_map[analysis_type]

    if mode in ("short", "both"):
        tf_label = st.selectbox(
            "Trading Timeframe",
            ["swing", "intraday", "scalp"],
            help="swing = days–weeks, intraday = within a day, scalp = minutes",
        )
    else:
        tf_label = "swing"

    if mode in ("long", "both"):
        ic_depth = st.selectbox(
            "IC Committee Depth",
            ["standard (8 agents)", "deep (all 10 agents)", "quick (5 agents)"],
            index=0,
        )
        ic_mode = ic_depth.split(" ")[0]
    else:
        ic_mode = "standard"

    st.markdown("### 💼 Portfolio")
    portfolio_size = st.number_input(
        "Portfolio Value (฿ / $)",
        min_value=1,
        max_value=100_000_000,
        value=100_000,
        step=1_000,
        format="%d",
    )
    risk_pct = st.slider(
        "Max risk per trade",
        0.5, 5.0, 2.0, 0.5,
        format="%.1f%%",
        help="2% = standard · higher = larger position size",
    )

    st.markdown("---")

    ready = bool(ticker_input.strip() or pdf_file)
    if use_ollama:
        ready = ready and ollama_running() and bool(ollama_models())
    elif use_groq:
        ready = ready and groq_key_ok()
    else:
        ready = ready and api_key_ok()

    run_button = st.button(
        "🚀 Run Analysis",
        use_container_width=True,
        type="primary",
        disabled=not ready,
    )
    if not ready:
        if use_ollama and not ollama_running():
            st.caption("⬆️ Start Ollama first, then enter a ticker")
        elif use_groq and not groq_key_ok():
            st.caption("⬆️ Enter your Groq API key above")
        elif not (ticker_input.strip() or pdf_file):
            st.caption("⬆️ Enter a ticker to get started")


# ── Main ──────────────────────────────────────────────────────────────────────
if use_ollama:
    _provider_badge = f"🦙 Ollama · {os.environ.get('OLLAMA_MODEL', 'local')}"
elif use_groq:
    _provider_badge = "⚡ Groq · Llama 3.3 70B"
else:
    _provider_badge = "☁️ Claude Sonnet & Haiku"
# Dynamic agent count: Joey(1) + Finance(3) + Trading(3) + IC(5/8/10)
_ic_count  = {"quick": 5, "standard": 8, "deep": 10}.get(ic_mode, 8)
_total_agents = 7 + _ic_count  # 12 / 15 / 17
st.markdown(
    f"""<div class="hero">
    <h1>💎 Lastmercy Trading Pro</h1>
    <p>One Orchestrator · 3 Teams · {_total_agents} Agents · Trade Signals + Investment Committee · Multi-Timeframe Analysis</p>
    <div class="hero-badges">
        <span class="hero-badge">☁️ Joey Orchestrator</span>
        <span class="hero-badge">💰 Finance Team</span>
        <span class="hero-badge">📈 Trading Team</span>
        <span class="hero-badge">🏛️ Investment Committee</span>
        <span class="hero-badge">📊 MTF 15m→1mo</span>
        <span class="hero-badge">{_provider_badge}</span>
    </div>
</div>""",
    unsafe_allow_html=True,
)

# ── Trade Log page — always handled before analysis routing ───────────────────
if _page == "📓 Trade Log":
    render_trade_log()
    st.stop()

# ── Cached render ─────────────────────────────────────────────────────────────
# If the user isn't launching a new run but a previous analysis exists (e.g. the
# page reran because they clicked the PDF download button), repaint the dashboard
# straight from session_state — no AI calls, no lost results.
if not run_button and "analysis" in st.session_state:
    render_dashboard(st.session_state["analysis"])
    st.stop()

if not run_button:
    # Landing state
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="team-header th-finance">💰 Finance Team</div>', unsafe_allow_html=True)
        for a in [("🔍", "Wizard", "Research Analyst"), ("⚔️", "Sage", "Contrarian Critic"), ("✅", "Priest", "Fact Auditor")]:
            st.markdown(f'<div class="agent-card ac-finance">{a[0]} <b>{a[1]}</b> — {a[2]}</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="team-header th-trading">📈 Trading Team</div>', unsafe_allow_html=True)
        for a in [("🎯", "Scout", "MTF Market Scanner"), ("📈", "Trader", "Signal Generator"), ("🛡️", "Risk", "Risk Manager")]:
            st.markdown(f'<div class="agent-card ac-trading">{a[0]} <b>{a[1]}</b> — {a[2]}</div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="team-header th-ic">🏛️ Investment Committee</div>', unsafe_allow_html=True)
        for a in [
            ("🎯", "CIS",        "Chief Investment Strategist"),
            ("📊", "QuantRisk",  "Quant Risk Manager"),
            ("📚", "Fundamental","Fundamental Analyst"),
            ("🌍", "Macro",      "Global Macro Analyst"),
            ("⚖️", "Portfolio",  "Portfolio Constructor"),
            ("📉", "Technical",  "CMT Technical Analyst"),
            ("🧠", "Behavioral", "Behavioral Finance"),
            ("😈", "Devil",      "Devil's Advocate"),
            ("🔬", "Micro",      "Microstructure Analyst"),
            ("🏆", "CFA PM",     "Final Verdict"),
        ]:
            st.markdown(f'<div class="agent-card ac-ic">{a[0]} <b>{a[1]}</b> — {a[2]}</div>', unsafe_allow_html=True)

    st.info("Enter a ticker in the sidebar and click **🚀 Run Analysis** to start the pipeline.", icon="💡")
    st.stop()

# ── Guard: provider readiness ─────────────────────────────────────────────────
if use_ollama:
    if not ollama_running():
        st.error("Ollama is not running. Please run `ollama serve` then reload.", icon="❌")
        st.stop()
    if not ollama_models():
        st.error("No Ollama models found. Please run `ollama pull qwen2.5:7b` then reload.", icon="❌")
        st.stop()
elif use_groq:
    if not groq_key_ok():
        st.error("Groq API Key required. Please enter it in the sidebar.", icon="⚡")
        st.stop()
else:
    if not api_key_ok():
        st.error("Anthropic API Key required. Please enter it in the sidebar.", icon="🔑")
        st.stop()

# ── Import agents (lazy to avoid import-time errors) ─────────────────────────
from agents.orchestrator import Joey
from agents.finance_team import Reese, Max, Vera
from agents.trading_team import Scout, Trader, Risk as RiskAgent
from agents.ic_team import InvestmentCommittee
from tools.market_data import MarketData
from tools.pdf_reader import extract_text

# ── Pipeline execution ────────────────────────────────────────────────────────
ticker_raw = ticker_input.strip()

_ic_agent_count = {"quick": 5, "standard": 8, "deep": 10}.get(ic_mode, 8)
if use_ollama:
    _est_min, _est_max = 3 + _ic_agent_count, 8 + _ic_agent_count * 2
    _provider_tag = "Ollama · local model"
elif use_groq:
    _est_min, _est_max = 1, 3
    _provider_tag = "Groq · Llama 3.3 70B · parallel"
else:
    _est_min, _est_max = 1, 2
    _provider_tag = "Anthropic API · parallel"
st.markdown(
    f'<div style="font-size:0.75rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;'
    f'color:#94a3b8;margin-bottom:4px">🔄 ANALYSIS PIPELINE</div>'
    f'<div style="font-size:0.75rem;color:#64748b;margin-bottom:12px">'
    f'⏱️ Est. {_est_min}–{_est_max} min &nbsp;·&nbsp; {_provider_tag} &nbsp;·&nbsp; {_ic_agent_count + 7} agents'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Step 0: Orchestrator ──────────────────────────────────────────────────────
with st.status("☁️ Joey — routing request...", expanded=False) as cloudy_status:
    cloudy = Joey()
    classification = cloudy.classify(ticker_raw, mode)
    ticker      = classification.get("ticker", ticker_raw.upper())
    asset_class = classification.get("asset_class", "stock")
    market      = classification.get("market", "US")
    uncertain   = classification.get("uncertain", False)
    ac_label    = asset_class_label(asset_class)

    cloudy_status.update(
        label=(
            f"☁️ Joey — **{ticker}** · {ac_label} · {market} · "
            f"**{classification.get('analysis_type','both').upper()}** mode"
        ),
        state="complete",
        expanded=False,
    )

if uncertain:
    st.info(
        f"⚠️ **{ticker_raw.upper()}** — กำลังลอง `{ticker}` · "
        f"ถ้าข้อมูลไม่ขึ้น ลองเพิ่ม suffix (.BK / .T / .KS / .SI) หรือตรวจสอบที่ "
        f"[Yahoo Finance](https://finance.yahoo.com)",
        icon="🔍",
    )
    # Show fuzzy alternatives
    _alts = fuzzy_suggest(ticker_raw, n=4)
    if _alts:
        _alt_str = "  |  ".join(
            f"`{a['ticker']}` ({a['display'][:30]})" for a in _alts[:3]
        )
        st.caption(f"🔍 ผลค้นหาที่ใกล้เคียง: {_alt_str}")

# ── Step 1: Market data ───────────────────────────────────────────────────────
with st.status(f"📡 Fetching {ac_label} data for {ticker}...", expanded=False) as data_status:
    md   = MarketData()
    data = md.get_all(ticker, asset_class)
    info          = data["info"]
    technicals    = data["technicals"]
    news          = data["news"]
    chart_records = data.get("chart_records", [])

    company = info.get("company", ticker)
    price   = info.get("current_price") or technicals.get("current_price") or 0
    bars    = technicals.get("bars_available", 0)
    src     = info.get("_source", "yfinance")

    if technicals.get("_error") == "no_price_data":
        data_status.update(
            label=f"⚠️ No price data found for {ticker} — agents will analyze from fundamentals + PDF only",
            state="error", expanded=False,
        )
    else:
        _curr_label = info.get("currency", "")
        _price_disp = f"{price:,.4g} {_curr_label}".strip() if price else "N/A"
        data_status.update(
            label=(
                f"📡 {company} @ {_price_disp}"
                f"· {bars} bars · source: {src}"
            ),
            state="complete", expanded=False,
        )

# ── Step 2: Multi-Timeframe data ──────────────────────────────────────────────
mtf_data = {}
with st.status(f"📊 Computing Multi-Timeframe data for {ticker}...", expanded=False) as mtf_status:
    try:
        mtf_data   = md.get_multi_timeframe(ticker)
        confluence = mtf_data.get("confluence", {})
        avail_tfs  = confluence.get("tfs", [])
        mtf_status.update(
            label=(
                f"📊 MTF Confluence: **{confluence.get('signal_th','?')}** "
                f"{confluence.get('dot','')}  "
                f"· Bull {confluence.get('bull_pct',0):.0f}% / Bear {confluence.get('bear_pct',0):.0f}%"
                f"  · {len(avail_tfs)} TF available ({', '.join(avail_tfs)})"
            ),
            state="complete", expanded=False,
        )
    except Exception as e:
        mtf_data = {}
        mtf_status.update(label=f"⚠️ MTF calculation failed: {e}", state="error", expanded=False)

# ── PDF context ────────────────────────────────────────────────────────────────
pdf_context = ""
if pdf_file:
    with st.status("📄 Reading PDF...", expanded=False) as pdf_status:
        pdf_context = extract_text(pdf_file)
        pdf_status.update(label=f"📄 PDF loaded — {len(pdf_context):,} characters", state="complete")

# ── Three-column pipeline ──────────────────────────────────────────────────────
from concurrent.futures import ThreadPoolExecutor as _TPE

fin_col, trade_col, ic_col = st.columns(3)

# ── Progress card helpers (ALL Streamlit calls stay in main thread) ────────────
def _ph_waiting(ph, emoji, name, css="ac-finance"):
    ph.markdown(
        f'<div class="agent-card {css}">{emoji} <b>{name}</b>'
        f'<span style="color:#94a3b8;font-size:0.78rem"> — waiting</span></div>',
        unsafe_allow_html=True,
    )

def _ph_running(ph, emoji, name):
    ph.markdown(
        f'<div class="agent-card ac-running">{emoji} <b>{name}</b>'
        f'<span style="font-size:0.78rem"> — analyzing…</span></div>',
        unsafe_allow_html=True,
    )

def _ph_done(ph, emoji, name):
    ph.markdown(
        f'<div class="agent-card ac-done">{emoji} <b>{name}</b> ✓</div>',
        unsafe_allow_html=True,
    )

# ── Pre-create all placeholders in main thread ────────────────────────────────
with fin_col:
    st.markdown('<div class="team-header th-finance">💰 Finance Team</div>', unsafe_allow_html=True)
    ph_wizard = st.empty()
    ph_sage   = st.empty()
    ph_priest = st.empty()

with trade_col:
    st.markdown('<div class="team-header th-trading">📈 Trading Team</div>', unsafe_allow_html=True)
    if mode in ("short", "both"):
        ph_scout  = st.empty()
        ph_trader = st.empty()
        ph_risk   = st.empty()
    else:
        st.info("Trading Team skipped (long-term mode selected)", icon="⏭️")
        ph_scout = ph_trader = ph_risk = None

# Initial waiting state
_ph_waiting(ph_wizard, "🔍", "Wizard", "ac-finance")
_ph_waiting(ph_sage,   "⚔️", "Sage",   "ac-finance")
_ph_waiting(ph_priest, "✅", "Priest", "ac-finance")
if ph_scout:
    _ph_waiting(ph_scout,  "🎯", "Scout",  "ac-trading")
    _ph_waiting(ph_trader, "📈", "Trader", "ac-trading")
    _ph_waiting(ph_risk,   "🛡️", "Risk",   "ac-trading")

# ── Result accumulators ────────────────────────────────────────────────────────
research_output   = ""
critique_output   = ""
fact_check_output = ""
scan_output       = ""
trade_card_text   = ""
risk_output       = ""

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Wizard + Scout  (parallel — both are data-independent)
# ══════════════════════════════════════════════════════════════════════════════
_ph_running(ph_wizard, "🔍", "Wizard")
if ph_scout:
    _ph_running(ph_scout, "🎯", "Scout")

def _run_wizard():
    r = Reese()
    out = r.research(ticker, info, technicals, news)
    if pdf_context:
        out += f"\n\nPDF CONTEXT:\n{pdf_context[:2000]}"
    return out

def _run_scout():
    s = Scout()
    return (s.scan_mtf(ticker, technicals, mtf_data, tf_label) if mtf_data
            else s.scan(ticker, technicals, tf_label))

with _TPE(max_workers=2) as _pool:
    _fw = _pool.submit(_run_wizard)
    _fs = _pool.submit(_run_scout) if ph_scout else None
    try:
        research_output = _fw.result(timeout=150)
    except Exception as _wiz_err:
        research_output = (
            f"⚠️ **Wizard analysis incomplete** ({type(_wiz_err).__name__})\n\n"
            f"Groq อาจ rate-limited หรือ timeout — รายละเอียด: {_wiz_err}\n\n"
            f"**วิธีแก้:** รอ 1-2 นาทีแล้ว Run Analysis ใหม่ หรือเปลี่ยนเป็น Anthropic API"
        )
        _ph_done(ph_wizard, "🔍", "Wizard")
    try:
        if _fs:
            scan_output = _fs.result(timeout=120)
    except Exception:
        scan_output = ""

_ph_done(ph_wizard, "🔍", "Wizard")
if ph_scout:
    _ph_done(ph_scout, "🎯", "Scout")

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — Sage + Trader  (parallel — both need Wizard output)
# ══════════════════════════════════════════════════════════════════════════════
_ph_running(ph_sage, "⚔️", "Sage")
if ph_trader:
    _ph_running(ph_trader, "📈", "Trader")

def _run_sage():
    return Max().critique(ticker, research_output)

def _run_trader():
    return Trader().generate_signal(ticker, scan_output, research_output, technicals)

with _TPE(max_workers=2) as _pool:
    _fsage   = _pool.submit(_run_sage)
    _ftrader = _pool.submit(_run_trader) if ph_trader else None
    try:
        critique_output = _fsage.result(timeout=120)
    except Exception as _e:
        critique_output = f"⚠️ Sage timeout/error ({type(_e).__name__}): {_e}"
    try:
        if _ftrader:
            trade_card_text = _ftrader.result(timeout=120)
    except Exception as _e:
        trade_card_text = f"⚠️ Trader timeout/error: {_e}"

_ph_done(ph_sage, "⚔️", "Sage")
if ph_trader:
    _ph_done(ph_trader, "📈", "Trader")

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — Priest + Risk  (parallel — Priest needs Sage, Risk needs Trader)
# ══════════════════════════════════════════════════════════════════════════════
_ph_running(ph_priest, "✅", "Priest")
if ph_risk:
    _ph_running(ph_risk, "🛡️", "Risk")

def _run_priest():
    return Vera().fact_check(ticker, research_output, critique_output, info, technicals)

def _run_risk():
    return RiskAgent().size_position(ticker, trade_card_text, portfolio_size, risk_pct)

with _TPE(max_workers=2) as _pool:
    _fpriest = _pool.submit(_run_priest)
    _frisk   = _pool.submit(_run_risk) if ph_risk else None
    try:
        fact_check_output = _fpriest.result(timeout=120)
    except Exception as _e:
        fact_check_output = f"⚠️ Priest timeout/error ({type(_e).__name__}): {_e}"
    try:
        if _frisk:
            risk_output = _frisk.result(timeout=120)
    except Exception as _e:
        risk_output = f"⚠️ Risk agent timeout/error: {_e}"

_ph_done(ph_priest, "✅", "Priest")
if ph_risk:
    _ph_done(ph_risk, "🛡️", "Risk")

# ═══════════════════════════════════════════════════════════
# INVESTMENT COMMITTEE
# ═══════════════════════════════════════════════════════════
ic_results = {}

with ic_col:
    st.markdown('<div class="team-header th-ic">🏛️ Investment Committee</div>', unsafe_allow_html=True)

    if mode in ("long", "both"):
        ic = InvestmentCommittee(mode=ic_mode)

        # Build IC context — asset-class aware
        conf = mtf_data.get("confluence", {}) if mtf_data else {}
        mtf_summary = (
            f"MTF CONFLUENCE: {conf.get('signal_th','?')} {conf.get('dot','')} "
            f"(Bull {conf.get('bull_pct',0)}% / Bear {conf.get('bear_pct',0)}%)\n"
        ) if conf else ""

        if asset_class == "crypto":
            ic_context = (
                f"ASSET: {ticker} ({company}) | CLASS: Cryptocurrency | MARKET: {market}\n"
                f"PRICE: {price} USD | Market Cap: {fmt_number(info.get('market_cap'))} | Rank: #{info.get('market_cap_rank','?')}\n"
                f"24H: {info.get('price_change_24h_pct','?')}% | 7D: {info.get('price_change_7d_pct','?')}% | 30D: {info.get('price_change_30d_pct','?')}%\n"
                f"ATH: {info.get('ath','?')} ({info.get('ath_change_pct','?')}% from ATH)\n"
                f"Circulating Supply: {fmt_number(info.get('circulating_supply'))} | Total Supply: {fmt_number(info.get('total_supply'))}\n"
                f"RSI: {technicals.get('rsi')} | Volume 24H: {fmt_number(info.get('total_volume_usd'))}\n"
                f"Above SMA50: {technicals.get('above_sma50')} | Above SMA200: {technicals.get('above_sma200')}\n"
                f"{mtf_summary}\n"
                f"RESEARCH SUMMARY:\n{research_output[:1200]}\n\n"
                f"CONTRARIAN CRITIQUE:\n{critique_output[:600]}\n"
            )
        else:
            ic_context = (
                f"TICKER: {ticker} | COMPANY: {company} | CLASS: {asset_class} | MARKET: {market}\n"
                f"PRICE: {price} {info.get('currency','USD')} | Market Cap: {fmt_number(info.get('market_cap'))}\n"
                f"P/E: {info.get('pe_ratio')} | P/B: {info.get('pb_ratio')} | ROE: {pct(info.get('roe'))}\n"
                f"Revenue Growth: {pct(info.get('revenue_growth'))} | Net Margin: {pct(info.get('net_margin'))}\n"
                f"RSI: {technicals.get('rsi')} | Above SMA200: {technicals.get('above_sma200')}\n"
                f"Beta: {info.get('beta')} | Analyst Target: {info.get('analyst_target')}\n"
                f"{mtf_summary}\n"
                f"RESEARCH ANALYST SUMMARY:\n{research_output[:1200]}\n\n"
                f"CONTRARIAN CRITIQUE:\n{critique_output[:600]}\n"
            )
        if pdf_context:
            ic_context += f"\nFILING/REPORT CONTEXT:\n{pdf_context[:2000]}"

        agent_placeholders = {}
        for agent in ic.agents:
            ph = st.empty()
            ph.markdown(
                f'<div class="agent-card ac-ic">{agent.emoji} <b>{agent.name}</b> '
                f'<span style="color:#94a3b8;font-size:0.78rem">— waiting</span></div>',
                unsafe_allow_html=True,
            )
            agent_placeholders[agent.name] = ph

        def on_start(name):
            if name in agent_placeholders:
                a = next(a for a in ic.agents if a.name == name)
                agent_placeholders[name].markdown(
                    f'<div class="agent-card ac-running">{a.emoji} <b>{name}</b> '
                    f'<span style="font-size:0.78rem">— analyzing…</span></div>',
                    unsafe_allow_html=True,
                )

        def on_done(name, output):
            if name in agent_placeholders:
                a = next(a for a in ic.agents if a.name == name)
                agent_placeholders[name].markdown(
                    f'<div class="agent-card ac-done">{a.emoji} <b>{name}</b> ✓</div>',
                    unsafe_allow_html=True,
                )

        try:
            ic_results = ic.run(ticker, ic_context, on_agent_start=on_start, on_agent_done=on_done)
        except Exception as _ic_err:
            _err_str = str(_ic_err)
            if "RateLimit" in _err_str or "rate_limit" in _err_str.lower() or "429" in _err_str:
                st.error(
                    "⚡ **Groq Rate Limit**  IC Committee ถูก throttle\n\n"
                    "วิธีแก้: เปลี่ยน IC Depth → **quick (5 agents)** หรือรอ 2 นาทีแล้วลองใหม่",
                    icon="⚡",
                )
            else:
                st.error(f"IC Committee error: {_ic_err}", icon="❌")
            ic_results = {}
    else:
        st.info("IC Committee skipped (short-term mode selected)", icon="⏭️")

# ── "Report ready" banner — always shown so user knows to scroll down ─────────
_ic_ok = bool(ic_results) if mode in ("long", "both") else True
if _ic_ok:
    st.success("✅ **Analysis complete** — Report พร้อมแล้ว  ↓ scroll ลงด้านล่าง", icon="📋")
else:
    st.warning(
        "⚠️ **Report พร้อมแล้ว** (ไม่มี IC Verdict เพราะ rate limit)  "
        "↓ scroll ลงด้านล่างเพื่อดู Overview / Research / MTF",
        icon="📋",
    )

# ── Persist results + render dashboard ────────────────────────────────────────
# Store everything so a later rerun (e.g. PDF download click) can repaint the
# dashboard without re-running any AI agents.
from datetime import datetime as _dt
st.session_state["analysis"] = {
    "ticker":            ticker,
    "company":           company,
    "asset_class":       asset_class,
    "market":            market,
    "ac_label":          ac_label,
    "price":             price,
    "info":              info,
    "technicals":        technicals,
    "news":              news,
    "mtf_data":          mtf_data,
    "chart_records":     chart_records,
    "research_output":   research_output,
    "critique_output":   critique_output,
    "fact_check_output": fact_check_output,
    "trade_card_text":   trade_card_text,
    "risk_output":       risk_output,
    "ic_results":        ic_results,
    "mode":              mode,
    "ic_mode":           ic_mode,
    "run_at":            _dt.now().strftime("%Y-%m-%d %H:%M"),
}

render_dashboard(st.session_state["analysis"])

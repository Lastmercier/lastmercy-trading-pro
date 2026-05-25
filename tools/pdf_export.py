"""
PDF report generator for Lastmercy Trading Pro.

Renders the full analysis (MTF, Trade Card, IC Verdict, Research) into a
clean Thai-language PDF using fpdf2 + a Thai TrueType font.

The font is resolved from a candidate list so the app keeps working even if
the primary macOS system font is unavailable.
"""

from __future__ import annotations

import os
import re
from datetime import datetime

from fpdf import FPDF

# ── Thai font resolution (first existing wins) ────────────────────────────────
# Bundled font (committed to repo) → works on Streamlit Cloud and local
_BUNDLED_FONT = os.path.join(os.path.dirname(__file__), "..", "fonts", "NotoSansThai.ttf")

_FONT_CANDIDATES = [
    os.path.normpath(_BUNDLED_FONT),                                    # repo font (cloud-safe)
    "/System/Library/Fonts/Supplemental/Ayuthaya.ttf",                 # macOS
    "/Library/Fonts/Ayuthaya.ttf",
    "/System/Library/Fonts/Supplemental/Krungthep.ttf",
    "/System/Library/Fonts/Supplemental/Silom.ttf",
    "/usr/share/fonts/truetype/tlwg/Sarabun.ttf",                      # Linux
    "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansThai[wdth,wght].ttf",
]


def _find_font():
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


# ── Text cleaning (strip glyphs the Thai font cannot render) ───────────────────
_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # emoji / pictographs / symbols
    "\U00002600-\U000027BF"   # misc symbols + dingbats
    "\U00002190-\U000021FF"   # arrows  (↔ ↑ ↓ etc.)
    "\U00002B00-\U00002BFF"   # misc symbols & arrows
    "\U00002500-\U0000257F"   # box drawing (─ ═ etc.)
    "\U0000FE00-\U0000FE0F"   # variation selectors
    "\U00002000-\U0000206F"   # general punctuation extras (zero-width etc.)
    "\U0000200D"              # zero-width joiner
    "]+",
    flags=re.UNICODE,
)

_MD_RE = re.compile(r"(\*\*|__|`|#+\s?)")


def _clean(text) -> str:
    """Remove emojis / box-glyphs / light markdown so the Thai font renders cleanly."""
    if text is None:
        return ""
    s = str(text)
    s = _EMOJI_RE.sub("", s)
    s = _MD_RE.sub("", s)
    s = s.replace("•", "- ")
    # collapse runs of whitespace but keep line breaks
    s = "\n".join(re.sub(r"[ \t]{2,}", " ", ln).rstrip() for ln in s.splitlines())
    return s.strip()


def _fmt(n):
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


# ── PDF document ───────────────────────────────────────────────────────────────
class _Report(FPDF):
    def __init__(self, font_path: str, meta_line: str = ""):
        super().__init__(format="A4")
        self.font_path = font_path
        self.meta_line = meta_line
        self.set_auto_page_break(auto=True, margin=18)
        self.add_font("Thai", "", font_path)
        self.set_margins(15, 15, 15)

    # Header on every page
    def header(self):
        self.set_font("Thai", "", 9)
        self.set_text_color(148, 163, 184)
        self.cell(0, 6, "Lastmercy Trading Pro", align="L")
        self.cell(0, 6, self.meta_line, align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(226, 232, 240)
        self.line(self.l_margin, self.get_y() + 1,
                  self.w - self.r_margin, self.get_y() + 1)
        self.ln(4)

    def footer(self):
        self.set_y(-14)
        self.set_font("Thai", "", 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 6,
                  "รายงานนี้สร้างโดย AI เพื่อการศึกษาเท่านั้น ไม่ใช่คำแนะนำการลงทุน  -  "
                  f"หน้า {self.page_no()}",
                  align="C")

    # ── Building blocks ───────────────────────────────────────────────────────
    def section(self, title: str, rgb=(79, 70, 229)):
        if self.get_y() > self.h - 40:
            self.add_page()
        self.ln(2)
        self.set_fill_color(*rgb)
        self.set_text_color(255, 255, 255)
        self.set_font("Thai", "", 12)
        self.multi_cell(0, 9, _clean(title), fill=True,
                        new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(30, 41, 59)
        self.ln(2)

    def kv(self, key: str, value):
        self.set_font("Thai", "", 10)
        self.set_text_color(100, 116, 139)
        self.cell(52, 7, _clean(key))
        self.set_text_color(30, 41, 59)
        self.multi_cell(0, 7, _clean(str(value)),
                        new_x="LMARGIN", new_y="NEXT")

    def body(self, text: str, size: int = 10):
        self.set_font("Thai", "", size)
        self.set_text_color(30, 41, 59)
        cleaned = _clean(text)
        if not cleaned:
            cleaned = "(ไม่มีข้อมูล)"
        self.multi_cell(0, 6, cleaned, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)


# ── MTF table ──────────────────────────────────────────────────────────────────
_TF_ORDER = ["1mo", "1w", "1d", "4h", "1h", "15m"]
_TF_TH = {
    "1mo": "รายเดือน", "1w": "รายสัปดาห์", "1d": "รายวัน",
    "4h": "4 ชั่วโมง", "1h": "1 ชั่วโมง", "15m": "15 นาที",
}
_COLS = [16, 26, 34, 24, 42, 38]   # widths (sum ~180mm)


def _mtf_table(pdf: _Report, mtf: dict):
    headers = ["TF", "ชื่อ", "แนวโน้ม", "RSI", "MACD", "สัญญาณ"]
    pdf.set_font("Thai", "", 9)
    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    for w, h in zip(_COLS, headers):
        pdf.cell(w, 8, _clean(h), border=0, fill=True, align="L")
    pdf.ln()

    pdf.set_text_color(30, 41, 59)
    for i, tf in enumerate(_TF_ORDER):
        d = mtf.get(tf, {})
        fill = i % 2 == 0
        pdf.set_fill_color(248, 250, 252)
        if not d.get("available", True) or "trend_th" not in d:
            cells = [tf, _TF_TH.get(tf, tf), "ไม่มีข้อมูล", "-", "-", "-"]
        else:
            rsi = d.get("rsi")
            cells = [
                tf,
                _TF_TH.get(tf, tf),
                d.get("trend_th", "-"),
                f"{rsi:.0f}" if rsi is not None else "-",
                d.get("macd_signal_th", "-"),
                f"{d.get('bias_th', '-')}",
            ]
        for w, c in zip(_COLS, cells):
            pdf.cell(w, 7, _clean(c)[:24], border=0, fill=fill, align="L")
        pdf.ln()
    pdf.ln(3)


# ── Public entry point ─────────────────────────────────────────────────────────
def build_pdf(A: dict) -> bytes:
    """
    Build a PDF report from the analysis dict stored in session_state.
    Returns raw PDF bytes (ready for st.download_button).
    Raises RuntimeError if no Thai-capable font is available.
    """
    font_path = _find_font()
    if not font_path:
        raise RuntimeError(
            "ไม่พบฟอนต์ภาษาไทยในระบบ — ติดตั้งฟอนต์ เช่น Sarabun หรือ Noto Sans Thai"
        )

    ticker  = A.get("ticker", "?")
    company = A.get("company", ticker)
    when    = datetime.now().strftime("%Y-%m-%d %H:%M")
    meta    = f"{ticker}  -  {when}"

    pdf = _Report(font_path, meta_line=meta)
    pdf.add_page()

    # ── Title block ───────────────────────────────────────────────────────────
    pdf.set_font("Thai", "", 20)
    pdf.set_text_color(30, 41, 59)
    pdf.multi_cell(0, 11, _clean(f"รายงานวิเคราะห์: {company}"),
                   new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Thai", "", 11)
    pdf.set_text_color(100, 116, 139)
    info = A.get("info", {})
    pdf.multi_cell(
        0, 7,
        _clean(
            f"Ticker: {ticker}  |  ประเภท: {A.get('ac_label','')}  |  "
            f"ตลาด: {A.get('market','')}  |  โหมด: {str(A.get('mode','')).upper()}"
        ),
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(3)

    # ── Key metrics ───────────────────────────────────────────────────────────
    pdf.section("ตัวชี้วัดสำคัญ")
    tech  = A.get("technicals", {})
    price = A.get("price", 0)
    pdf.kv("ราคาปัจจุบัน", f"{price:,}" if price else "N/A")
    pdf.kv("Market Cap", _fmt(info.get("market_cap")))
    if A.get("asset_class") == "crypto":
        pdf.kv("อันดับ Market Cap", f"#{info.get('market_cap_rank', '-')}")
        pdf.kv("ATH", _fmt(info.get("ath")))
        pdf.kv("เปลี่ยน 24H / 7D / 30D",
               f"{info.get('price_change_24h_pct','?')}% / "
               f"{info.get('price_change_7d_pct','?')}% / "
               f"{info.get('price_change_30d_pct','?')}%")
    else:
        pdf.kv("P/E Ratio", info.get("pe_ratio", "N/A"))
        pdf.kv("P/B Ratio", info.get("pb_ratio", "N/A"))
        pdf.kv("52W สูงสุด / ต่ำสุด",
               f"{tech.get('high_52w','N/A')} / {tech.get('low_52w','N/A')}")
    pdf.kv("RSI(14)", tech.get("rsi", "N/A"))

    # ── MTF ───────────────────────────────────────────────────────────────────
    mtf = A.get("mtf_data", {})
    if mtf:
        conf = mtf.get("confluence", {})
        pdf.section(
            f"Multi-Timeframe Analysis  -  สัญญาณรวม: {conf.get('signal_th','?')}  "
            f"(Bull {conf.get('bull_pct',0)}% / Bear {conf.get('bear_pct',0)}%)"
        )
        _mtf_table(pdf, mtf)

    # ── Trade Card + Risk ─────────────────────────────────────────────────────
    if A.get("trade_card_text"):
        pdf.section("Trade Card (สัญญาณซื้อขาย)", rgb=(4, 120, 87))
        pdf.body(A["trade_card_text"])
        if A.get("risk_output"):
            pdf.section("การบริหาร Position", rgb=(4, 120, 87))
            pdf.body(A["risk_output"])

    # ── IC Verdict ────────────────────────────────────────────────────────────
    ic = A.get("ic_results", {})
    if ic:
        final = ic.get("CFAPortfolioManager", {})
        if final:
            pdf.section("คำตัดสินคณะกรรมการลงทุน (IC Verdict)", rgb=(109, 40, 217))
            pdf.body(final.get("output", ""))
        # vote tally summary
        tally = ic.get("_vote_tally", {})
        if tally:
            n_buy  = len(tally.get("BUY",  []))
            n_hold = len(tally.get("HOLD", []))
            n_sell = len(tally.get("SELL", []))
            n_total = n_buy + n_hold + n_sell
            pdf.section("สรุปผลโหวต IC Committee", rgb=(109, 40, 217))
            pdf.kv("BUY",  f"{n_buy}/{n_total}  ({', '.join(tally.get('BUY',[])) or '-'})")
            pdf.kv("HOLD", f"{n_hold}/{n_total}  ({', '.join(tally.get('HOLD',[])) or '-'})")
            pdf.kv("SELL", f"{n_sell}/{n_total}  ({', '.join(tally.get('SELL',[])) or '-'})")

        # per-agent (compact) — skip the internal vote tally dict
        others = [(n, d) for n, d in ic.items()
                  if n not in ("CFAPortfolioManager", "_vote_tally")]
        if others:
            pdf.section("ความเห็นกรรมการแต่ละท่าน", rgb=(109, 40, 217))
            for name, d in others:
                pdf.set_font("Thai", "", 11)
                pdf.set_text_color(109, 40, 217)
                pdf.multi_cell(0, 7, _clean(d.get("title", name)),
                               new_x="LMARGIN", new_y="NEXT")
                pdf.body(d.get("output", ""), size=9)

    # ── Research ──────────────────────────────────────────────────────────────
    pdf.section("งานวิจัย (Finance Team)", rgb=(29, 78, 216))
    if A.get("research_output"):
        pdf.set_font("Thai", "", 11)
        pdf.set_text_color(29, 78, 216)
        pdf.multi_cell(0, 7, "Wizard - Research Analyst",
                       new_x="LMARGIN", new_y="NEXT")
        pdf.body(A["research_output"])
    if A.get("critique_output"):
        pdf.set_font("Thai", "", 11)
        pdf.set_text_color(29, 78, 216)
        pdf.multi_cell(0, 7, "Sage - Contrarian Critic",
                       new_x="LMARGIN", new_y="NEXT")
        pdf.body(A["critique_output"])
    if A.get("fact_check_output"):
        pdf.set_font("Thai", "", 11)
        pdf.set_text_color(29, 78, 216)
        pdf.multi_cell(0, 7, "Priest - Fact Auditor",
                       new_x="LMARGIN", new_y="NEXT")
        pdf.body(A["fact_check_output"])

    return bytes(pdf.output())

"""
Smart ticker resolver — normalizes user input to exchange-qualified symbols
and detects asset class + market automatically.

Examples
--------
  "GPSC"      → GPSC.BK  (SET stock)
  "ptт"       → PTT.BK   (SET stock, case-insensitive)
  "BTC"       → BTC-USD  (crypto)
  "bitcoin"   → BTC-USD  (crypto by name)
  "AAPL"      → AAPL     (US stock)
  "SPY"       → SPY      (US ETF)
  "Gold"      → GC=F     (commodity)
"""

from __future__ import annotations

# ── SET (Thailand) tickers ────────────────────────────────────────────────────
# Major & liquid SET-listed stocks / REITs / ETFs
SET_TICKERS: set[str] = {
    # Energy & Utilities
    "PTT", "PTTEP", "PTTGC", "GPSC", "GULF", "BGRIM", "RATCH", "EGCO",
    "EA", "STGT", "SPCG", "TPIPP", "GLOW", "IRPC",
    # Banking & Finance
    "SCB", "KBANK", "BBL", "KTB", "TMB", "TISCO", "TCAP", "KKP",
    "AEONTS", "SAWAD", "MTC", "TIDLOR", "THCOM", "LHFG",
    # Property & REITs
    "LH", "SIRI", "AP", "SC", "PSH", "SPALI", "QH", "ORI",
    "CPNREIT", "DREIT", "WHART", "FTREIT", "BKDREIT",
    # Retail & Consumer
    "CPALL", "MAKRO", "CRC", "BJC", "HMPRO", "COM7", "GLOBAL",
    "BEAUTY", "OSP", "SAPPE",
    # Telecom & Tech
    "ADVANC", "TRUE", "INTUCH", "SYNEX", "INET",
    # Industrial & Materials
    "SCC", "SCCC", "TPIPL", "TPCH", "KSL",
    # Healthcare
    "BCH", "BDMS", "BH", "CHG", "VIBHA", "PR9", "NTV",
    # Agri & Food
    "CPF", "TFG", "GFPT", "NRF", "ICHI", "MALEE",
    # Airlines & Transport
    "AOT", "AAV", "NOK", "THAI", "BTS", "BTSGIF",
    # Media & Entertainment
    "MAJOR", "RS", "VGI", "MCOT",
    # Insurance
    "BLA", "THREL", "TQM",
    # Electronics & Auto
    "DELTA", "KCE", "SVI", "HANA", "STANLY",
    # Hospitality
    "MINT", "ERW", "CENTEL", "SHATEL",
    # Others
    "AWC", "DTAC", "JMART", "JMT", "WHA",
    "BANPU", "GLAND", "LPN", "PRUKSA", "NOBLE",
    "BCPG", "CKP", "RATCH", "SUPER",
}

# ── Crypto tickers ────────────────────────────────────────────────────────────
CRYPTO_MAP: dict[str, str] = {
    # Major
    "BTC": "BTC-USD", "BITCOIN": "BTC-USD",
    "ETH": "ETH-USD", "ETHEREUM": "ETH-USD",
    "BNB": "BNB-USD", "BINANCE": "BNB-USD",
    "SOL": "SOL-USD", "SOLANA": "SOL-USD",
    "XRP": "XRP-USD", "RIPPLE": "XRP-USD",
    "ADA": "ADA-USD", "CARDANO": "ADA-USD",
    "DOGE": "DOGE-USD", "DOGECOIN": "DOGE-USD",
    "TRX": "TRX-USD", "TRON": "TRX-USD",
    "AVAX": "AVAX-USD", "AVALANCHE": "AVAX-USD",
    "SHIB": "SHIB-USD", "SHIBA": "SHIB-USD",
    # Layer 2 / DeFi
    "MATIC": "MATIC-USD", "POLYGON": "MATIC-USD",
    "DOT": "DOT-USD", "POLKADOT": "DOT-USD",
    "LINK": "LINK-USD", "CHAINLINK": "LINK-USD",
    "UNI": "UNI-USD", "UNISWAP": "UNI-USD",
    "ARB": "ARB-USD", "ARBITRUM": "ARB-USD",
    "OP": "OP-USD", "OPTIMISM": "OP-USD",
    "ATOM": "ATOM-USD", "COSMOS": "ATOM-USD",
    "NEAR": "NEAR-USD",
    "APT": "APT-USD", "APTOS": "APT-USD",
    "SUI": "SUI-USD",
    # Stablecoin proxies / others
    "LTC": "LTC-USD", "LITECOIN": "LTC-USD",
    "BCH": "BCH-USD", "BITCOINCASH": "BCH-USD",
    "FIL": "FIL-USD", "FILECOIN": "FIL-USD",
    "SAND": "SAND-USD",  "MANA": "MANA-USD",
    "INJ": "INJ-USD", "SEI": "SEI-USD",
    "TON": "TON11419-USD", "TONCOIN": "TON11419-USD",
    # Thai exchange popular (Bitkub)
    "KUB": "KUB-USD",
}

# CoinGecko IDs for crypto (free API, no key)
COINGECKO_IDS: dict[str, str] = {
    "BTC-USD": "bitcoin",
    "ETH-USD": "ethereum",
    "BNB-USD": "binancecoin",
    "SOL-USD": "solana",
    "XRP-USD": "ripple",
    "ADA-USD": "cardano",
    "DOGE-USD": "dogecoin",
    "TRX-USD": "tron",
    "AVAX-USD": "avalanche-2",
    "SHIB-USD": "shiba-inu",
    "MATIC-USD": "matic-network",
    "DOT-USD": "polkadot",
    "LINK-USD": "chainlink",
    "UNI-USD": "uniswap",
    "ARB-USD": "arbitrum",
    "OP-USD": "optimism",
    "ATOM-USD": "cosmos",
    "NEAR-USD": "near",
    "APT-USD": "aptos",
    "SUI-USD": "sui",
    "LTC-USD": "litecoin",
    "BCH-USD": "bitcoin-cash",
    "FIL-USD": "filecoin",
    "SAND-USD": "the-sandbox",
    "MANA-USD": "decentraland",
    "INJ-USD": "injective-protocol",
}

# ── Commodity / Index / Forex shortcuts ──────────────────────────────────────
COMMODITY_MAP: dict[str, str] = {
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "OIL": "CL=F",
    "CRUDE": "CL=F",
    "BRENT": "BZ=F",
    "NATGAS": "NG=F",
    "COPPER": "HG=F",
    "WHEAT": "ZW=F",
    "CORN": "ZC=F",
    "SP500": "^GSPC",
    "SPX": "^GSPC",
    "NASDAQ": "^IXIC",
    "DJI": "^DJI",
    "SET50": "0P00000X0X.BK",   # SET50 Index ETF proxy
    "BITCOIN": "BTC-USD",
}

FOREX_PAIRS: set[str] = {
    "EURUSD", "GBPUSD", "USDJPY", "USDTHB", "AUDUSD",
    "NZDUSD", "USDCAD", "USDCHF", "EURGBP",
}


# ── Main resolver ─────────────────────────────────────────────────────────────
def resolve(raw: str) -> dict:
    """
    Normalize a user-typed ticker/name and return a classification dict.

    Returns
    -------
    {
        "ticker":      str,   # exchange-qualified Yahoo Finance symbol
        "asset_class": str,   # stock | crypto | etf | commodity | forex | fund
        "market":      str,   # SET | US | HKEX | crypto | commodity | forex
        "display":     str,   # human-readable label
        "uncertain":   bool,  # True if we guessed and need to verify
    }
    """
    t = raw.strip().upper().replace(" ", "").replace("/", "")

    # ── Binance-style pairs (BTCUSDT, ETHUSDT, SOLUSDT) ──────────────────────
    if t.endswith("USDT") and len(t) > 4:
        base_sym = t[:-4]          # strip USDT
        yf_ticker = CRYPTO_MAP.get(base_sym, f"{base_sym}-USD")
        return _make(yf_ticker, "crypto", "crypto", f"{base_sym} (Crypto)")
    if t.endswith("BUSD") and len(t) > 4:
        base_sym = t[:-4]
        yf_ticker = CRYPTO_MAP.get(base_sym, f"{base_sym}-USD")
        return _make(yf_ticker, "crypto", "crypto", f"{base_sym} (Crypto)")

    # ── Already fully qualified ───────────────────────────────────────────────
    if ".BK" in t:
        return _make(t, "stock", "SET", t)
    if t.endswith("-USD") or t.endswith("-USDT") or t.endswith("-BTC"):
        normalized = t.replace("-USDT", "-USD")
        return _make(normalized, "crypto", "crypto", normalized)
    if t.endswith(".HK"):
        return _make(t, "stock", "HKEX", t)
    if t.endswith(".TW"):
        return _make(t, "stock", "TWSE", t)
    if t.endswith(".SS") or t.endswith(".SZ"):
        return _make(t, "stock", "China", t)

    # ── Commodity / index shortcuts ───────────────────────────────────────────
    if t in COMMODITY_MAP:
        yf = COMMODITY_MAP[t]
        ac = "crypto" if "-USD" in yf else "commodity" if "=F" in yf else "index"
        return _make(yf, ac, ac, t)

    # ── Forex ─────────────────────────────────────────────────────────────────
    if t in FOREX_PAIRS:
        return _make(f"{t}=X", "forex", "forex", t)

    # ── Crypto (known symbol or name) ─────────────────────────────────────────
    if t in CRYPTO_MAP:
        yf = CRYPTO_MAP[t]
        return _make(yf, "crypto", "crypto", f"{t} (Crypto)")

    # ── Known Thai SET ticker ─────────────────────────────────────────────────
    if t in SET_TICKERS:
        return _make(f"{t}.BK", "stock", "SET", f"{t} (SET)")

    # ── US ticker / ETF / everything else (default) ──────────────────────────
    # Unknown short alpha tickers: user must add .BK manually for Thai stocks
    # not in the SET_TICKERS list above.
    return _make(t, "stock", "US", t)


def _make(ticker, asset_class, market, display, uncertain=False):
    return {
        "ticker":      ticker,
        "asset_class": asset_class,
        "market":      market,
        "display":     display,
        "uncertain":   uncertain,
    }


def asset_class_label(ac: str) -> str:
    return {
        "stock":     "📈 Stock",
        "crypto":    "₿ Crypto",
        "etf":       "🗂 ETF",
        "commodity": "🥇 Commodity",
        "forex":     "💱 Forex",
        "index":     "📊 Index",
        "fund":      "🏦 Fund",
    }.get(ac, "📈 Asset")

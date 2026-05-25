"""
Smart ticker resolver — comprehensive coverage:

- Thai SET / MAI:  ~450 tickers + dynamic .BK suffix fallback
- Crypto:          top 100 by market cap (static list)
- Forex:           35+ major / minor / exotic pairs
- JP / KR / SG / DE / L  auto-detection by suffix or numeric pattern
- Fuzzy search:    difflib-powered typo-tolerant suggestions
- ETF holdings:    yfinance lookup helper
- Thai funds:      popular fund families index
- TradingView:     symbol converter for widget embedding
"""

from __future__ import annotations

import difflib
import re
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Thai SET / MAI tickers  (~450 stocks, all sectors)
# ─────────────────────────────────────────────────────────────────────────────
SET_TICKERS: set[str] = {
    # ── Energy & Utilities ────────────────────────────────────────────────────
    "PTT", "PTTEP", "PTTGC", "TOP", "IRPC", "ESSO", "SPRC",
    "GPSC", "GULF", "BGRIM", "RATCH", "EGCO", "EA", "STGT",
    "SPCG", "TPIPP", "GLOW", "BCPG", "CKP", "SUPER", "DEMCO",
    "GUNKUL", "ENE", "SOLAR", "TSE", "WP", "ACE", "BANPU",
    "LANNA", "COAL", "AEC", "BIGC", "BCP",
    # ── Banking & Finance ─────────────────────────────────────────────────────
    "SCB", "KBANK", "BBL", "KTB", "TTB", "BAY", "TISCO", "TCAP",
    "KKP", "AEONTS", "SAWAD", "MTC", "TIDLOR", "LHFG",
    "ASK", "MFC", "KIATNAKIN", "TSF", "THRE", "BAM",
    "JFIN", "SINGER", "SELIC", "TBANK", "UOBT", "TQM",
    "BLA", "THREL", "TVI", "TIC", "KLIFE", "SMK",
    # ── Property & Real Estate ────────────────────────────────────────────────
    "LH", "SIRI", "AP", "SC", "PSH", "SPALI", "QH", "ORI",
    "PRUKSA", "NOBLE", "LPN", "WHA", "GLAND", "AMATA", "AMATAV",
    "CK", "CH", "MJD", "LALIN", "RICHY", "SUPALAI", "COUNTRY",
    "PLAT", "ASSET", "ANANDA", "DCON", "PLUS", "SANSIRI",
    "ANAN", "NPARK", "PRIN", "BLAND", "PACE", "GRAND",
    # ── REITs / Infrastructure Funds ──────────────────────────────────────────
    "CPNREIT", "DREIT", "WHART", "FTREIT", "BKDREIT", "IMPACT",
    "SIRIP", "MIPF", "PROSPECT", "SF", "LHHOTEL", "SHR",
    "TRUEIF", "DTCFUND", "TFUND", "FFTF", "AMATAR",
    # ── Retail & Consumer ─────────────────────────────────────────────────────
    "CPALL", "MAKRO", "CRC", "BJC", "HMPRO", "COM7", "GLOBAL",
    "BEAUTY", "OSP", "SAPPE", "DOHOME", "CPN", "DCC",
    "TASCO", "MONO", "OISHI", "COL", "BFIT",
    # ── Telecom & Technology ──────────────────────────────────────────────────
    "ADVANC", "TRUE", "INTUCH", "SYNEX", "INET", "DTAC", "THCOM",
    "JTS", "CSL", "HUMAN", "NETBAY", "ARROW", "ITEL", "INOX",
    "FNS", "SMIT", "SVOA", "DIGI", "AIT", "INSET",
    # ── Industrial & Materials ────────────────────────────────────────────────
    "SCC", "SCCC", "TPIPL", "TPCH", "KSL", "CHEMMAN", "DRT",
    "EPA", "SAT", "VNT", "TPAC", "BSM", "MDX", "TTW",
    "NFC", "IVL", "HMC", "TPT", "SCGP", "PPM",
    # ── Construction & Infrastructure ────────────────────────────────────────
    "ITD", "SEAFCO", "NWR", "PWC", "TRC", "STEC", "UNIQ",
    "CKP", "TPCH", "CEN", "PYLON",
    # ── Healthcare ────────────────────────────────────────────────────────────
    "BCH", "BDMS", "BH", "CHG", "VIBHA", "PR9", "NTV",
    "RJH", "SKR", "PRINC", "RAM", "NRF", "BPH", "LPH",
    "CHEWA", "CPMC", "MASTER", "UKEM",
    # ── Agri & Food ──────────────────────────────────────────────────────────
    "CPF", "TFG", "GFPT", "ICHI", "MALEE", "TU", "CBG",
    "SNP", "BTG", "COMAN", "KASET", "TIW", "KSL", "KTIS",
    "THIP", "LSGH", "NFC", "CFRESH", "CGD",
    # ── Airlines & Transport ─────────────────────────────────────────────────
    "AOT", "AAV", "NOK", "THAI", "BTS", "BTSGIF", "NAVI",
    "TOA", "VNET", "RCL",
    # ── Media & Entertainment ─────────────────────────────────────────────────
    "MAJOR", "RS", "VGI", "MCOT", "PLANB", "WORK",
    "GRAMMY", "JKN", "TNN", "MONO",
    # ── Electronics & Auto Parts ──────────────────────────────────────────────
    "DELTA", "KCE", "SVI", "HANA", "STANLY", "PCSGH",
    "AH", "TCR", "YUASA", "AAPICO", "SAA",
    # ── Hospitality & Tourism ─────────────────────────────────────────────────
    "MINT", "ERW", "CENTEL", "SHATEL", "DUSIT", "AWC",
    "ONYX", "TGRAND", "CHO", "MBK",
    # ── Chemicals & Polymers ──────────────────────────────────────────────────
    "IVL", "HMC", "TPT", "CHEMMAN",
    # ── Agriculture / Sugar ───────────────────────────────────────────────────
    "KSL", "KTIS", "THIP", "LSGH",
    # ── Various MAI & Smaller Cap ─────────────────────────────────────────────
    "JMART", "JMT", "ACE", "AFC", "SANKO", "PP", "GOLD",
    "NC", "MEGA", "SPA", "SALEE", "SE", "SEA",
    "SGF", "SGP", "SIC", "SISB", "SKE", "SKYT",
    "SLP", "SLS", "SM", "SNC", "SNNP", "SOG",
    "SPG", "SPS", "SQ", "SR", "SSL", "SST",
    "STONE", "SUC", "SVH", "SWC", "SYS",
    "TAPAC", "TC", "TCC", "TEAM", "TEAMG",
    "TGPRO", "TGS", "THANA", "THMUI", "THNEL",
    "TIPH", "TLUXE", "TMC", "TMILL", "TMT",
    "TNC", "TNITY", "TR", "TRIG", "TRIM",
    "TROP", "TRPC", "TTL",
    "UAC", "UBE", "UEC", "UH",
    "UOBKH", "UVAN", "UV",
    "WACOAL", "WG", "WHM",
    "ZEN",
    # ── Well-known SET100 additions ───────────────────────────────────────────
    "BDMS", "MINT", "HMPRO", "MAKRO", "PTG", "PTZ",
    "AMATA", "WHA", "DTAC", "TRUE",
}

# Human-readable names (used for fuzzy search on name)
SET_NAMES: dict[str, str] = {
    "PTT":     "ปตท - PTT Public Company",
    "PTTEP":   "ปตท.สผ - PTT Exploration",
    "PTTGC":   "พีทีทีจีซี - PTT Global Chemical",
    "KBANK":   "กสิกรไทย - Kasikorn Bank",
    "SCB":     "ไทยพาณิชย์ - Siam Commercial Bank",
    "BBL":     "กรุงเทพ - Bangkok Bank",
    "KTB":     "กรุงไทย - Krungthai Bank",
    "TTB":     "ทีเอ็มบีธนชาต - TMBThanachart Bank",
    "BAY":     "กรุงศรี - Krungsri Bank of Ayudhya",
    "CPALL":   "ซีพีออลล์ - CP All 7-Eleven",
    "MAKRO":   "แม็คโคร - Siam Makro",
    "CRC":     "เซ็นทรัล รีเทล - Central Retail",
    "AOT":     "ท่าอากาศยาน - Airports of Thailand",
    "ADVANC":  "เอไอเอส - Advanced Info Service",
    "TRUE":    "ทรู - True Corporation",
    "SCC":     "ปูนซิเมนต์ - SCG Cement",
    "DELTA":   "เดลต้า - Delta Electronics Thailand",
    "GULF":    "กัลฟ์ - Gulf Energy Development",
    "BGRIM":   "บี.กริม - B.Grimm Power",
    "MINT":    "ไมเนอร์ - Minor International",
    "BDMS":    "กรุงเทพดุสิตเวชการ - Bangkok Dusit Medical",
    "BH":      "โรงพยาบาลบำรุงราษฎร์ - Bumrungrad Hospital",
    "CPF":     "เจริญโภคภัณฑ์อาหาร - Charoen Pokphand Foods",
    "HMPRO":   "โฮมโปร - Home Product Center",
    "EGCO":    "ผลิตไฟฟ้า - Electricity Generating",
    "RATCH":   "ราช กรุ๊ป - Ratch Group",
    "LH":      "แลนด์ แอนด์ เฮ้าส์ - Land and Houses",
    "BTS":     "บีทีเอส - BTS Group Holdings",
    "HANA":    "ฮาน่า ไมโครฯ - Hana Microelectronics",
}


# ─────────────────────────────────────────────────────────────────────────────
# Crypto top ~100 (symbol → Yahoo Finance ticker)
# ─────────────────────────────────────────────────────────────────────────────
CRYPTO_MAP: dict[str, str] = {
    # ── Top 10 ────────────────────────────────────────────────────────────────
    "BTC":       "BTC-USD",   "BITCOIN":     "BTC-USD",
    "ETH":       "ETH-USD",   "ETHEREUM":    "ETH-USD",
    "BNB":       "BNB-USD",   "BINANCE":     "BNB-USD",
    "SOL":       "SOL-USD",   "SOLANA":      "SOL-USD",
    "XRP":       "XRP-USD",   "RIPPLE":      "XRP-USD",
    "ADA":       "ADA-USD",   "CARDANO":     "ADA-USD",
    "DOGE":      "DOGE-USD",  "DOGECOIN":    "DOGE-USD",
    "TRX":       "TRX-USD",   "TRON":        "TRX-USD",
    "TON":       "TON11419-USD", "TONCOIN":  "TON11419-USD",
    "AVAX":      "AVAX-USD",  "AVALANCHE":   "AVAX-USD",
    # ── 11-30 ─────────────────────────────────────────────────────────────────
    "SHIB":      "SHIB-USD",  "SHIBAINU":    "SHIB-USD",
    "LINK":      "LINK-USD",  "CHAINLINK":   "LINK-USD",
    "DOT":       "DOT-USD",   "POLKADOT":    "DOT-USD",
    "MATIC":     "MATIC-USD", "POLYGON":     "MATIC-USD",
    "POL":       "POL-USD",
    "LTC":       "LTC-USD",   "LITECOIN":    "LTC-USD",
    "BCH":       "BCH-USD",   "BITCOINCASH": "BCH-USD",
    "UNI":       "UNI-USD",   "UNISWAP":     "UNI-USD",
    "NEAR":      "NEAR-USD",  "NEARPROTOCOL":"NEAR-USD",
    "ICP":       "ICP-USD",   "INTERNETCOMPUTER":"ICP-USD",
    "APT":       "APT-USD",   "APTOS":       "APT-USD",
    "SUI":       "SUI-USD",
    "ARB":       "ARB-USD",   "ARBITRUM":    "ARB-USD",
    "OP":        "OP-USD",    "OPTIMISM":    "OP-USD",
    "ATOM":      "ATOM-USD",  "COSMOS":      "ATOM-USD",
    "STX":       "STX-USD",   "STACKS":      "STX-USD",
    # ── 31-60 ─────────────────────────────────────────────────────────────────
    "FIL":       "FIL-USD",   "FILECOIN":    "FIL-USD",
    "VET":       "VET-USD",   "VECHAIN":     "VET-USD",
    "HBAR":      "HBAR-USD",  "HEDERA":      "HBAR-USD",
    "MKR":       "MKR-USD",   "MAKER":       "MKR-USD",
    "RNDR":      "RNDR-USD",  "RENDER":      "RNDR-USD",
    "INJ":       "INJ-USD",   "INJECTIVE":   "INJ-USD",
    "THETA":     "THETA-USD",
    "XLM":       "XLM-USD",   "STELLAR":     "XLM-USD",
    "ALGO":      "ALGO-USD",  "ALGORAND":    "ALGO-USD",
    "ETC":       "ETC-USD",   "ETHEREUMCLASSIC":"ETC-USD",
    "GRT":       "GRT-USD",   "THEGRAPH":    "GRT-USD",
    "SAND":      "SAND-USD",  "SANDBOX":     "SAND-USD",
    "MANA":      "MANA-USD",  "DECENTRALAND":"MANA-USD",
    "CHZ":       "CHZ-USD",   "CHILIZ":      "CHZ-USD",
    "EGLD":      "EGLD-USD",  "MULTIVERSX":  "EGLD-USD",
    "FLOW":      "FLOW-USD",
    "XMR":       "XMR-USD",   "MONERO":      "XMR-USD",
    "AXS":       "AXS-USD",   "AXIEINFINITY":"AXS-USD",
    "RUNE":      "RUNE-USD",  "THORCHAIN":   "RUNE-USD",
    "FTM":       "FTM-USD",   "FANTOM":      "FTM-USD",
    "CRV":       "CRV-USD",   "CURVE":       "CRV-USD",
    "AAVE":      "AAVE-USD",
    "LDO":       "LDO-USD",   "LIDO":        "LDO-USD",
    "QNT":       "QNT-USD",   "QUANT":       "QNT-USD",
    "SEI":       "SEI-USD",
    # ── 61-100 ────────────────────────────────────────────────────────────────
    "TIA":       "TIA-USD",   "CELESTIA":    "TIA-USD",
    "PEPE":      "PEPE-USD",
    "WIF":       "WIF-USD",   "DOGWIFHAT":   "WIF-USD",
    "BONK":      "BONK-USD",
    "FLOKI":     "FLOKI-USD",
    "IMX":       "IMX-USD",   "IMMUTABLEX":  "IMX-USD",
    "OSMO":      "OSMO-USD",  "OSMOSIS":     "OSMO-USD",
    "SNX":       "SNX-USD",   "SYNTHETIX":   "SNX-USD",
    "KAVA":      "KAVA-USD",
    "EOS":       "EOS-USD",
    "DASH":      "DASH-USD",
    "ZEC":       "ZEC-USD",   "ZCASH":       "ZEC-USD",
    "XTZ":       "XTZ-USD",   "TEZOS":       "XTZ-USD",
    "COMP":      "COMP-USD",  "COMPOUND":    "COMP-USD",
    "ZIL":       "ZIL-USD",   "ZILLIQA":     "ZIL-USD",
    "ONE":       "ONE-USD",   "HARMONY":     "ONE-USD",
    "ENJ":       "ENJ-USD",   "ENJIN":       "ENJ-USD",
    "GALA":      "GALA-USD",
    "AUDIO":     "AUDIO-USD", "AUDIUS":      "AUDIO-USD",
    "CELO":      "CGLD-USD",  "CGLD":        "CGLD-USD",
    "1INCH":     "1INCH-USD",
    "SUSHI":     "SUSHI-USD", "SUSHISWAP":   "SUSHI-USD",
    "BAL":       "BAL-USD",   "BALANCER":    "BAL-USD",
    "LRC":       "LRC-USD",   "LOOPRING":    "LRC-USD",
    "STORJ":     "STORJ-USD",
    "SKL":       "SKL-USD",   "SKALE":       "SKL-USD",
    "ANKR":      "ANKR-USD",
    "OCEAN":     "OCEAN-USD",
    "REN":       "REN-USD",
    "BAND":      "BAND-USD",  "BANDPROTOCOL":"BAND-USD",
    "KSM":       "KSM-USD",   "KUSAMA":      "KSM-USD",
    "IOTA":      "MIOTA-USD", "MIOTA":       "MIOTA-USD",
    "JASMY":     "JASMY-USD",
    "HOT":       "HOT-USD",   "HOLO":        "HOT-USD",
    "RSR":       "RSR-USD",   "RESERVE":     "RSR-USD",
    "CELR":      "CELR-USD",  "CELER":       "CELR-USD",
    "IOST":      "IOST-USD",
    # ── Thai exchange (Bitkub) ────────────────────────────────────────────────
    "KUB":       "KUB-USD",
}

# CoinGecko IDs for crypto (free API, no key needed)
COINGECKO_IDS: dict[str, str] = {
    "BTC-USD":    "bitcoin",
    "ETH-USD":    "ethereum",
    "BNB-USD":    "binancecoin",
    "SOL-USD":    "solana",
    "XRP-USD":    "ripple",
    "ADA-USD":    "cardano",
    "DOGE-USD":   "dogecoin",
    "TRX-USD":    "tron",
    "TON11419-USD":"the-open-network",
    "AVAX-USD":   "avalanche-2",
    "SHIB-USD":   "shiba-inu",
    "LINK-USD":   "chainlink",
    "DOT-USD":    "polkadot",
    "MATIC-USD":  "matic-network",
    "POL-USD":    "matic-network",
    "LTC-USD":    "litecoin",
    "BCH-USD":    "bitcoin-cash",
    "UNI-USD":    "uniswap",
    "NEAR-USD":   "near",
    "ICP-USD":    "internet-computer",
    "APT-USD":    "aptos",
    "SUI-USD":    "sui",
    "ARB-USD":    "arbitrum",
    "OP-USD":     "optimism",
    "ATOM-USD":   "cosmos",
    "STX-USD":    "blockstack",
    "FIL-USD":    "filecoin",
    "VET-USD":    "vechain",
    "HBAR-USD":   "hedera-hashgraph",
    "MKR-USD":    "maker",
    "RNDR-USD":   "render-token",
    "INJ-USD":    "injective-protocol",
    "THETA-USD":  "theta-token",
    "XLM-USD":    "stellar",
    "ALGO-USD":   "algorand",
    "ETC-USD":    "ethereum-classic",
    "GRT-USD":    "the-graph",
    "SAND-USD":   "the-sandbox",
    "MANA-USD":   "decentraland",
    "CHZ-USD":    "chiliz",
    "EGLD-USD":   "elrond-erd-2",
    "FLOW-USD":   "flow",
    "XMR-USD":    "monero",
    "AXS-USD":    "axie-infinity",
    "RUNE-USD":   "thorchain",
    "FTM-USD":    "fantom",
    "CRV-USD":    "curve-dao-token",
    "AAVE-USD":   "aave",
    "LDO-USD":    "lido-dao",
    "QNT-USD":    "quant-network",
    "SEI-USD":    "sei-network",
    "TIA-USD":    "celestia",
    "PEPE-USD":   "pepe",
    "WIF-USD":    "dogwifcoin",
    "BONK-USD":   "bonk",
    "FLOKI-USD":  "floki",
    "IMX-USD":    "immutable-x",
    "OSMO-USD":   "osmosis",
    "SNX-USD":    "havven",
    "KAVA-USD":   "kava",
    "EOS-USD":    "eos",
}


# ─────────────────────────────────────────────────────────────────────────────
# Commodity / Index shortcuts
# ─────────────────────────────────────────────────────────────────────────────
COMMODITY_MAP: dict[str, str] = {
    "GOLD":      "GC=F",
    "SILVER":    "SI=F",
    "OIL":       "CL=F",
    "CRUDE":     "CL=F",
    "WTICRUD":   "CL=F",
    "BRENT":     "BZ=F",
    "NATGAS":    "NG=F",
    "GAS":       "NG=F",
    "COPPER":    "HG=F",
    "WHEAT":     "ZW=F",
    "CORN":      "ZC=F",
    "SOYBEAN":   "ZS=F",
    "PLATINUM":  "PL=F",
    "PALLADIUM": "PA=F",
    # Indices
    "SP500":     "^GSPC",
    "SPX":       "^GSPC",
    "S&P500":    "^GSPC",
    "NASDAQ":    "^IXIC",
    "NDX":       "^NDX",
    "QQQ":       "QQQ",
    "DJI":       "^DJI",
    "DOW":       "^DJI",
    "VIX":       "^VIX",
    "SET50":     "0P00000X0X.BK",
    "NIKKEI":    "^N225",
    "N225":      "^N225",
    "HSI":       "^HSI",
    "HANGSENG":  "^HSI",
    "DAX":       "^GDAXI",
    "FTSE":      "^FTSE",
    "KOSPI":     "^KS11",
    "STI":       "^STI",
    # Crypto shortcut for COMMODITY_MAP fallthrough
    "BITCOIN":   "BTC-USD",
}


# ─────────────────────────────────────────────────────────────────────────────
# Forex pairs — 35+ major / minor / exotic
# Format: "EURUSD" → "EURUSD=X"
# ─────────────────────────────────────────────────────────────────────────────
FOREX_PAIRS: dict[str, str] = {
    # Major pairs (USD base)
    "EURUSD":  "EURUSD=X",
    "GBPUSD":  "GBPUSD=X",
    "USDJPY":  "JPY=X",
    "USDCHF":  "CHF=X",
    "USDCAD":  "CAD=X",
    "AUDUSD":  "AUDUSD=X",
    "NZDUSD":  "NZDUSD=X",
    "USDCNY":  "CNY=X",
    "USDHKD":  "HKD=X",
    "USDTHB":  "THB=X",
    "USDSGD":  "SGD=X",
    "USDKRW":  "KRW=X",
    "USDINR":  "INR=X",
    "USDBRL":  "BRL=X",
    "USDMXN":  "MXN=X",
    "USDZAR":  "ZAR=X",
    "USDTRY":  "TRY=X",
    "USDSEK":  "SEK=X",
    "USDNOK":  "NOK=X",
    "USDDKK":  "DKK=X",
    "USDPLN":  "PLN=X",
    "USDIDR":  "IDR=X",
    "USDPHP":  "PHP=X",
    "USDMYR":  "MYR=X",
    "USDVND":  "VND=X",
    # Cross pairs (no USD)
    "EURGBP":  "EURGBP=X",
    "EURJPY":  "EURJPY=X",
    "EURCHF":  "EURCHF=X",
    "EURCAD":  "EURCAD=X",
    "EURAUD":  "EURAUD=X",
    "GBPJPY":  "GBPJPY=X",
    "GBPCHF":  "GBPCHF=X",
    "GBPAUD":  "GBPAUD=X",
    "AUDJPY":  "AUDJPY=X",
    "CADJPY":  "CADJPY=X",
    "CHFJPY":  "CHFJPY=X",
    "NZDJPY":  "NZDJPY=X",
    "AUDCAD":  "AUDCAD=X",
    "AUDNZD":  "AUDNZD=X",
    # Shorthand aliases
    "EURUSD/": "EURUSD=X",
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "JPY=X",
    "USD/THB": "THB=X",
}

# Forex display labels
FOREX_LABELS: dict[str, str] = {
    "EURUSD":  "EUR/USD — Euro vs Dollar",
    "GBPUSD":  "GBP/USD — Cable",
    "USDJPY":  "USD/JPY — Dollar vs Yen",
    "USDTHB":  "USD/THB — Dollar vs Baht",
    "AUDUSD":  "AUD/USD — Aussie Dollar",
    "NZDUSD":  "NZD/USD — Kiwi Dollar",
    "USDCAD":  "USD/CAD — Loonie",
    "USDCHF":  "USD/CHF — Swissie",
    "EURGBP":  "EUR/GBP — Euro vs Pound",
    "USDSGD":  "USD/SGD — Dollar vs Singapore Dollar",
    "USDCNY":  "USD/CNY — Dollar vs Renminbi",
    "USDKRW":  "USD/KRW — Dollar vs Korean Won",
}


# ─────────────────────────────────────────────────────────────────────────────
# Thai Mutual Funds — popular fund families
# These are not tradeable on yfinance; included for search + info display
# ─────────────────────────────────────────────────────────────────────────────
THAI_FUNDS: dict[str, dict] = {
    # Kasikorn (K-Fund)
    "KF-CHINA":    {"name": "KF-CHINA — กองทุนหุ้นจีน Kasikorn", "url": "https://www.kasikornasset.com"},
    "KF-US":       {"name": "KF-US — กองทุนหุ้นสหรัฐ Kasikorn",  "url": "https://www.kasikornasset.com"},
    "KF-GLOBAL":   {"name": "KF-GLOBAL — กองทุนหุ้นโลก Kasikorn", "url": "https://www.kasikornasset.com"},
    "KF-INDIA":    {"name": "KF-INDIA — กองทุนหุ้นอินเดีย Kasikorn", "url": "https://www.kasikornasset.com"},
    "KFLTFDIV":    {"name": "KFLTFDIV — กองทุน LTF ปันผล", "url": "https://www.kasikornasset.com"},
    # SCB (SCBAM)
    "SCBTHAI":     {"name": "SCBTHAI — หุ้นไทย SCB Asset Management",  "url": "https://www.scbam.com"},
    "SCBDV":       {"name": "SCBDV — หุ้นปันผล SCB",     "url": "https://www.scbam.com"},
    "SCBEQTG":     {"name": "SCBEQTG — หุ้นทั่วโลก SCB", "url": "https://www.scbam.com"},
    "SCBSMART":    {"name": "SCBSMART — Smart Income SCB", "url": "https://www.scbam.com"},
    # Krungsri (KF / BAY)
    "KFSDIV":      {"name": "KFSDIV — หุ้นปันผล Krungsri", "url": "https://www.krungsriasset.com"},
    "KFSMART":     {"name": "KFSMART — Smart Balance", "url": "https://www.krungsriasset.com"},
    # MFC
    "MFCF":        {"name": "MFCF — MFC Flexible Fund",    "url": "https://www.mfcfund.com"},
    # TMBAM Eastspring
    "TMBPIPF":     {"name": "TMBPIPF — Thai Property Fund", "url": "https://www.eastspring.co.th"},
    # One Asset
    "ONE-UGG-RA":  {"name": "ONE-UGG-RA — One Asset Global",  "url": "https://www.one-asset.com"},
    # บัวหลวง (Bangkok Bank)
    "BBLPLUS":     {"name": "BBLPLUS — Bualuang Plus Fund",  "url": "https://www.bualuangfund.com"},
    "BBL-THAICG":  {"name": "BBL-THAICG — หุ้นไทย CG",       "url": "https://www.bualuangfund.com"},
}

# Fuzzy-searchable name aliases for Thai funds
_THAI_FUND_ALIASES: dict[str, str] = {
    "กองทุนจีน":        "KF-CHINA",
    "กองทุนสหรัฐ":      "KF-US",
    "กองทุนอินเดีย":    "KF-INDIA",
    "กองทุนโลก":        "KF-GLOBAL",
    "กองทุนหุ้นไทย":   "SCBTHAI",
    "กองทุนปันผล":      "SCBDV",
    "บัวหลวง":          "BBLPLUS",
    "กสิกร":            "KF-CHINA",
    "กรุงศรี":          "KFSDIV",
}


# ─────────────────────────────────────────────────────────────────────────────
# Internal: master lookup for fuzzy search
# ─────────────────────────────────────────────────────────────────────────────
def _build_search_corpus() -> dict[str, dict]:
    """Build a flat {key: result_dict} for fuzzy matching."""
    corpus: dict[str, dict] = {}

    for sym in SET_TICKERS:
        corpus[sym] = _make(f"{sym}.BK", "stock", "SET", f"{sym} (SET)")
    for sym, name in SET_NAMES.items():
        corpus[name.upper()] = _make(f"{sym}.BK", "stock", "SET", f"{sym} (SET) — {name}")

    for sym, yf in CRYPTO_MAP.items():
        corpus[sym] = _make(yf, "crypto", "crypto", f"{sym} (Crypto)")

    for pair in FOREX_PAIRS:
        corpus[pair] = _make(FOREX_PAIRS[pair], "forex", "forex", FOREX_LABELS.get(pair, pair))

    for name, yf in COMMODITY_MAP.items():
        ac = "crypto" if "-USD" in yf else "commodity" if "=F" in yf else "index"
        corpus[name] = _make(yf, ac, ac, name)

    for code, info in THAI_FUNDS.items():
        corpus[code] = _make(code, "fund", "TH-Fund", info["name"])
    for alias, code in _THAI_FUND_ALIASES.items():
        if code in THAI_FUNDS:
            corpus[alias] = _make(code, "fund", "TH-Fund", THAI_FUNDS[code]["name"])

    return corpus


_SEARCH_CORPUS: dict[str, dict] | None = None


def _get_corpus() -> dict[str, dict]:
    global _SEARCH_CORPUS
    if _SEARCH_CORPUS is None:
        _SEARCH_CORPUS = _build_search_corpus()
    return _SEARCH_CORPUS


# ─────────────────────────────────────────────────────────────────────────────
# Main resolver
# ─────────────────────────────────────────────────────────────────────────────
def resolve(raw: str) -> dict:
    """
    Normalize a user-typed ticker/name and return a classification dict.

    Returns
    -------
    {
        "ticker":      str,   # exchange-qualified Yahoo Finance symbol
        "asset_class": str,   # stock | crypto | etf | commodity | forex | fund
        "market":      str,   # SET | US | HKEX | Japan | Korea | Singapore | ...
        "display":     str,   # human-readable label
        "uncertain":   bool,  # True if we guessed and need to verify
    }
    """
    t = raw.strip().upper().replace(" ", "").replace("/", "")

    # ── Strip Binance-style pairs (BTCUSDT / BTCBUSD) ─────────────────────────
    if t.endswith("USDT") and len(t) > 4:
        base = t[:-4]
        return _make(CRYPTO_MAP.get(base, f"{base}-USD"), "crypto", "crypto", f"{base} (Crypto)")
    if t.endswith("BUSD") and len(t) > 4:
        base = t[:-4]
        return _make(CRYPTO_MAP.get(base, f"{base}-USD"), "crypto", "crypto", f"{base} (Crypto)")

    # ── Already qualified ─────────────────────────────────────────────────────
    if ".BK" in t:
        sym = t.split(".BK")[0]
        return _make(t, "stock", "SET", f"{sym} (SET)")
    if t.endswith("-USD") or t.endswith("-USDT") or t.endswith("-BTC"):
        normalized = t.replace("-USDT", "-USD")
        return _make(normalized, "crypto", "crypto", normalized)
    if t.endswith(".HK"):
        return _make(t, "stock", "HKEX", f"{t} (Hong Kong)")
    if t.endswith(".TW"):
        return _make(t, "stock", "TWSE", f"{t} (Taiwan)")
    if t.endswith(".SS") or t.endswith(".SZ"):
        return _make(t, "stock", "China", f"{t} (China)")
    if t.endswith(".T"):
        return _make(t, "stock", "Japan", f"{t} (Tokyo)")
    if t.endswith(".KS") or t.endswith(".KQ"):
        return _make(t, "stock", "Korea", f"{t} (Korea)")
    if t.endswith(".SI"):
        return _make(t, "stock", "Singapore", f"{t} (Singapore)")
    if t.endswith(".DE"):
        return _make(t, "stock", "Germany", f"{t} (Frankfurt)")
    if t.endswith(".L"):
        return _make(t, "stock", "UK", f"{t} (London)")
    if t.endswith(".AX"):
        return _make(t, "stock", "Australia", f"{t} (ASX)")

    # ── Numeric code auto-detection ───────────────────────────────────────────
    # 4-digit number → likely Japan (e.g. 7203 → 7203.T)
    if re.fullmatch(r"\d{4}", t):
        return _make(f"{t}.T", "stock", "Japan", f"{t}.T (Tokyo)", uncertain=True)
    # 5–6 digit number → likely Korea (e.g. 005930 → 005930.KS)
    if re.fullmatch(r"\d{5,6}", t):
        return _make(f"{t}.KS", "stock", "Korea", f"{t}.KS (Korea)", uncertain=True)

    # ── Commodity / index shortcuts ───────────────────────────────────────────
    if t in COMMODITY_MAP:
        yf = COMMODITY_MAP[t]
        if "-USD" in yf:
            return _make(yf, "crypto", "crypto", t)
        if "=F" in yf:
            return _make(yf, "commodity", "commodity", f"{t} Futures")
        return _make(yf, "index", "index", f"{t} Index")

    # ── Forex ─────────────────────────────────────────────────────────────────
    # Handle "EURUSD", "EUR/USD", "eurusd" etc.
    t_noslash = t.replace("/", "")
    if t_noslash in FOREX_PAIRS:
        yf = FOREX_PAIRS[t_noslash]
        label = FOREX_LABELS.get(t_noslash, t_noslash)
        return _make(yf, "forex", "forex", label)

    # ── Crypto (known symbol or full name) ────────────────────────────────────
    if t in CRYPTO_MAP:
        yf = CRYPTO_MAP[t]
        return _make(yf, "crypto", "crypto", f"{t} (Crypto)")

    # ── Known Thai SET ticker ─────────────────────────────────────────────────
    if t in SET_TICKERS:
        return _make(f"{t}.BK", "stock", "SET", f"{t} (SET)")

    # ── Thai mutual fund ──────────────────────────────────────────────────────
    if t in THAI_FUNDS:
        return _make(t, "fund", "TH-Fund", THAI_FUNDS[t]["name"])

    # ── Fallback: treat as US stock ───────────────────────────────────────────
    return _make(t, "stock", "US", t)


# ─────────────────────────────────────────────────────────────────────────────
# Fuzzy search — returns up to n close matches from the full corpus
# ─────────────────────────────────────────────────────────────────────────────
def fuzzy_suggest(raw: str, n: int = 6) -> list[dict]:
    """
    Typo-tolerant search across all known tickers and names.

    Returns a list of result dicts (same shape as resolve()) sorted by
    match quality, limited to `n` results.
    """
    q = raw.strip().upper()
    corpus = _get_corpus()

    # Exact match first
    if q in corpus:
        return [corpus[q]]

    keys = list(corpus.keys())
    matches = difflib.get_close_matches(q, keys, n=n, cutoff=0.5)

    # Also include prefix matches (useful for partial typing)
    prefix_hits = [k for k in keys if k.startswith(q) and k not in matches]
    combined = (matches + prefix_hits[:max(0, n - len(matches))])[:n]

    return [corpus[k] for k in combined]


# ─────────────────────────────────────────────────────────────────────────────
# ETF / Fund holdings lookup via yfinance
# ─────────────────────────────────────────────────────────────────────────────
def get_etf_holdings(ticker: str) -> list[dict]:
    """
    Fetch top holdings for a US ETF via yfinance.
    Returns a list of {symbol, holdingName, holdingPercent} dicts.
    Returns [] if not an ETF or data unavailable.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        holdings = info.get("holdings") or []
        if holdings:
            return [
                {
                    "symbol":  h.get("symbol", "?"),
                    "name":    h.get("holdingName", h.get("symbol", "?")),
                    "weight":  round(float(h.get("holdingPercent", 0)) * 100, 2),
                }
                for h in holdings[:15]  # top 15 holdings
            ]
        # Some ETFs use a different key
        for key in ("topHoldings", "fund_holdings"):
            alt = info.get(key, [])
            if alt:
                return [{"symbol": h.get("symbol", "?"), "name": h.get("holdingName", "?"),
                         "weight": round(float(h.get("holdingPercent", 0)) * 100, 2)}
                        for h in alt[:15]]
        return []
    except Exception:
        return []


def get_thai_fund_info(code: str) -> dict | None:
    """Return basic info dict for a Thai mutual fund code, or None."""
    return THAI_FUNDS.get(code.upper())


# ─────────────────────────────────────────────────────────────────────────────
# TradingView symbol converter
# ─────────────────────────────────────────────────────────────────────────────
def to_tradingview_symbol(ticker: str, asset_class: str, market: str) -> str:
    """
    Convert a Yahoo Finance ticker to a TradingView symbol string for the
    Advanced Chart Widget.

    Examples:
        "PTT.BK"     → "SET:PTT"
        "BTC-USD"    → "BINANCE:BTCUSDT"
        "AAPL"       → "NASDAQ:AAPL"
        "EURUSD=X"   → "FX:EURUSD"
        "GC=F"       → "COMEX:GC1!"
        "7203.T"     → "TSE:7203"
        "005930.KS"  → "KRX:005930"
    """
    if asset_class == "crypto":
        base = (ticker
                .replace("-USD", "")
                .replace("-USDT", "")
                .replace("-BTC", ""))
        return f"BINANCE:{base}USDT"

    if market == "SET":
        sym = ticker.replace(".BK", "")
        return f"SET:{sym}"

    if market == "HKEX":
        # 9988.HK → HKEX:9988
        sym = ticker.replace(".HK", "").lstrip("0")
        return f"HKEX:{sym}"

    if market == "Japan":
        sym = ticker.replace(".T", "")
        return f"TSE:{sym}"

    if market == "Korea":
        sym = ticker.replace(".KS", "").replace(".KQ", "")
        return f"KRX:{sym}"

    if market == "Singapore":
        sym = ticker.replace(".SI", "")
        return f"SGX:{sym}"

    if market == "Germany":
        sym = ticker.replace(".DE", "")
        return f"XETR:{sym}"

    if market == "UK":
        sym = ticker.replace(".L", "")
        return f"LSE:{sym}"

    if market == "Australia":
        sym = ticker.replace(".AX", "")
        return f"ASX:{sym}"

    if market == "TWSE":
        sym = ticker.replace(".TW", "")
        return f"TWSE:{sym}"

    if market == "China":
        sym = ticker.replace(".SS", "").replace(".SZ", "")
        exchange = "SSE" if ticker.endswith(".SS") else "SZSE"
        return f"{exchange}:{sym}"

    if asset_class == "forex":
        sym = ticker.replace("=X", "")
        return f"FX:{sym}"

    if asset_class == "commodity":
        commodity_tv: dict[str, str] = {
            "GC=F":  "COMEX:GC1!",
            "SI=F":  "COMEX:SI1!",
            "CL=F":  "NYMEX:CL1!",
            "BZ=F":  "NYMEX:BB1!",
            "NG=F":  "NYMEX:NG1!",
            "HG=F":  "COMEX:HG1!",
            "ZW=F":  "CBOT:ZW1!",
            "ZC=F":  "CBOT:ZC1!",
            "ZS=F":  "CBOT:ZS1!",
            "PL=F":  "NYMEX:PL1!",
            "PA=F":  "NYMEX:PA1!",
        }
        return commodity_tv.get(ticker, f"TVC:{ticker.replace('=F','1!')}")

    if asset_class == "index":
        index_tv: dict[str, str] = {
            "^GSPC":  "SP:SPX",
            "^IXIC":  "NASDAQ:COMP",
            "^NDX":   "NASDAQ:NDX",
            "^DJI":   "DJ:DJI",
            "^VIX":   "CBOE:VIX",
            "^N225":  "TVC:NI225",
            "^HSI":   "TVC:HSI",
            "^GDAXI": "XETR:DAX",
            "^FTSE":  "TVC:UKX",
            "^KS11":  "KRX:KOSPI",
            "^STI":   "SGX:STI",
        }
        return index_tv.get(ticker, f"TVC:{ticker.lstrip('^')}")

    # US stock — TradingView accepts bare symbol (auto-detects exchange)
    return ticker


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _make(ticker: str, asset_class: str, market: str,
          display: str, uncertain: bool = False) -> dict:
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

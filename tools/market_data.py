"""
Multi-source market data pipeline.

Source priority
---------------
Stocks  → Yahoo Finance (yfinance)  ← primary
Crypto  → Yahoo Finance + CoinGecko  ← CoinGecko for richer fundamentals
Thin data fallback: shorter period → weekly interval → best-effort indicators
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

from tools.ticker_resolver import COINGECKO_IDS


# ── Helpers ───────────────────────────────────────────────────────────────────
def _v(x, decimals: int = 4) -> Optional[float]:
    """Return rounded float or None if NaN/None."""
    if x is None:
        return None
    try:
        f = float(x)
        return None if np.isnan(f) else round(f, decimals)
    except (TypeError, ValueError):
        return None


def _safe_int(x) -> int:
    try:
        return int(x) if x and not np.isnan(float(x)) else 0
    except Exception:
        return 0


def _pct(x) -> Optional[float]:
    v = _v(x)
    return round(v * 100, 2) if v is not None else None


# ── CoinGecko (free, no key) ──────────────────────────────────────────────────
def _coingecko_info(yf_ticker: str) -> dict:
    coin_id = COINGECKO_IDS.get(yf_ticker)
    if not coin_id:
        return {}
    try:
        url = (
            f"https://api.coingecko.com/api/v3/coins/{coin_id}"
            "?localization=false&tickers=false&community_data=false&developer_data=false"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            d = json.loads(resp.read())

        market = d.get("market_data", {})
        return {
            "company":           d.get("name", yf_ticker),
            "description":       (d.get("description", {}).get("en", "") or "")[:600],
            "sector":            "Cryptocurrency",
            "industry":          d.get("categories", ["Crypto"])[0] if d.get("categories") else "Crypto",
            "current_price":     market.get("current_price", {}).get("usd"),
            "market_cap":        market.get("market_cap", {}).get("usd"),
            "currency":          "USD",
            "pe_ratio":          None,
            "pb_ratio":          None,
            "dividend_yield":    None,
            "52w_high":          market.get("high_24h", {}).get("usd"),  # use ath instead if needed
            "52w_low":           market.get("low_24h", {}).get("usd"),
            "beta":              None,
            "analyst_target":    None,
            "recommendation":    None,
            # Crypto-specific extras
            "circulating_supply":    market.get("circulating_supply"),
            "total_supply":          market.get("total_supply"),
            "market_cap_rank":       d.get("market_cap_rank"),
            "price_change_24h_pct":  _v(market.get("price_change_percentage_24h")),
            "price_change_7d_pct":   _v(market.get("price_change_percentage_7d")),
            "price_change_30d_pct":  _v(market.get("price_change_percentage_30d")),
            "ath":               market.get("ath", {}).get("usd"),
            "ath_change_pct":    _v(market.get("ath_change_percentage", {}).get("usd")),
            "atl":               market.get("atl", {}).get("usd"),
            "total_volume_usd":  market.get("total_volume", {}).get("usd"),
            "_source":           "coingecko",
        }
    except Exception:
        return {}


def _infer_currency(ticker: str) -> str:
    """Guess the trading currency from the ticker suffix."""
    t = ticker.upper()
    if t.endswith(".BK"):  return "THB"
    if t.endswith(".HK"):  return "HKD"
    if t.endswith(".T"):   return "JPY"
    if t.endswith(".KS") or t.endswith(".KQ"): return "KRW"
    if t.endswith(".SI"):  return "SGD"
    if t.endswith(".TW"):  return "TWD"
    if t.endswith(".L"):   return "GBP"
    if t.endswith(".DE") or t.endswith(".PA") or t.endswith(".AS"): return "EUR"
    if t.endswith(".AX"):  return "AUD"
    if t.endswith(".SS") or t.endswith(".SZ"): return "CNY"
    if "-USD" in t:        return "USD"
    return "USD"


# ── Main class ────────────────────────────────────────────────────────────────
class MarketData:

    # ── Info / fundamentals ───────────────────────────────────────────────────
    def get_info(self, ticker: str, asset_class: str = "stock") -> dict:
        """
        Fetch fundamental/descriptive info.
        Two-pass strategy:
          1. yfinance .info  (full fundamentals — may return stub on Cloud)
          2. yfinance .fast_info  (always works: price, market_cap, currency, 52W)
        The fast_info pass fills gaps left by .info so we never show None when
        data is actually available.
        """
        # Crypto: try CoinGecko first for richer data
        if asset_class == "crypto":
            cg = _coingecko_info(ticker)
            if cg:
                return cg
            # fallback to yfinance below

        stock = yf.Ticker(ticker)

        # ── Pass 1: full .info ────────────────────────────────────────────────
        base: dict = {}
        try:
            info = stock.info or {}

            _raw_price = (info.get("currentPrice")
                          or info.get("regularMarketPrice")
                          or info.get("previousClose")
                          or info.get("navPrice"))
            _has_data = bool(
                info.get("symbol") or info.get("shortName") or info.get("longName")
                or _raw_price or info.get("marketCap") or info.get("quoteType")
            )

            if _has_data:
                base = {
                    "ticker":           ticker,
                    "company":          (info.get("longName") or info.get("shortName")
                                         or info.get("displayName") or ticker),
                    "sector":           info.get("sector") or "N/A",
                    "industry":         info.get("industry") or "N/A",
                    "market_cap":       info.get("marketCap"),
                    "current_price":    _raw_price,
                    "currency":         info.get("currency") or _infer_currency(ticker),
                    "pe_ratio":         _v(info.get("trailingPE")),
                    "forward_pe":       _v(info.get("forwardPE")),
                    "pb_ratio":         _v(info.get("priceToBook")),
                    "ps_ratio":         _v(info.get("priceToSalesTrailing12Months")),
                    "dividend_yield":   _pct(info.get("dividendYield")),
                    "roe":              _pct(info.get("returnOnEquity")),
                    "roa":              _pct(info.get("returnOnAssets")),
                    "debt_equity":      _v(info.get("debtToEquity")),
                    "current_ratio":    _v(info.get("currentRatio")),
                    "gross_margin":     _pct(info.get("grossMargins")),
                    "net_margin":       _pct(info.get("profitMargins")),
                    "operating_margin": _pct(info.get("operatingMargins")),
                    "revenue_growth":   _pct(info.get("revenueGrowth")),
                    "earnings_growth":  _pct(info.get("earningsGrowth")),
                    "52w_high":         _v(info.get("fiftyTwoWeekHigh")),
                    "52w_low":          _v(info.get("fiftyTwoWeekLow")),
                    "avg_volume_10d":   _safe_int(info.get("averageVolume10days")),
                    "beta":             _v(info.get("beta")),
                    "short_ratio":      _v(info.get("shortRatio")),
                    "analyst_target":   _v(info.get("targetMeanPrice")),
                    "recommendation":   info.get("recommendationKey") or "N/A",
                    "description":      (info.get("longBusinessSummary") or "")[:600],
                    "_source":          "yfinance",
                }
                if asset_class == "crypto":
                    base.update({
                        "sector":             "Cryptocurrency",
                        "circulating_supply": info.get("circulatingSupply"),
                        "total_supply":       info.get("totalSupply"),
                    })
        except Exception:
            pass   # will be filled by fast_info below

        # ── Pass 2: fast_info — fills gaps (always fast, rarely rate-limited) ─
        try:
            fi = stock.fast_info
            fi_price   = _v(getattr(fi, "last_price",      None) or
                            getattr(fi, "previous_close",  None))
            fi_mc      = getattr(fi, "market_cap",   None)
            fi_curr    = getattr(fi, "currency",     None)
            fi_yh      = _v(getattr(fi, "year_high", None))
            fi_yl      = _v(getattr(fi, "year_low",  None))

            if not base:
                # .info was empty — build a base from fast_info
                base = self._minimal_info(ticker, asset_class)
                base["_source"] = "yfinance_fast"

            # Patch in any missing / better values from fast_info
            if not base.get("current_price") and fi_price:
                base["current_price"] = fi_price
            if not base.get("market_cap") and fi_mc:
                base["market_cap"] = int(fi_mc)
            if fi_curr:                              # currency from fast_info is authoritative
                base["currency"] = fi_curr
            if not base.get("52w_high") and fi_yh:
                base["52w_high"] = fi_yh
            if not base.get("52w_low") and fi_yl:
                base["52w_low"] = fi_yl
            if base.get("company") == ticker:       # name still unknown
                exch = getattr(fi, "exchange", "")
                if exch:
                    base["company"] = f"{ticker} ({exch})"
        except Exception:
            pass

        # ── Pass 3: Financial statements — derive ratios when .info stub fails ──
        # Targets: pe_ratio, pb_ratio, roe, net_margin, gross_margin
        # Uses income_stmt + balance_sheet which are usually available even when
        # .info returns a near-empty dict (common for Thai / Asian stocks on Cloud).
        try:
            needs = {
                "pe_ratio":    not base.get("pe_ratio"),
                "pb_ratio":    not base.get("pb_ratio"),
                "roe":         not base.get("roe"),
                "net_margin":  not base.get("net_margin"),
                "gross_margin":not base.get("gross_margin"),
            }
            if any(needs.values()) and base:
                mc = base.get("market_cap")   # provided by fast_info (Pass 2)
                net_income_val: Optional[float] = None

                # ── Income statement ─────────────────────────────────────────
                if needs["pe_ratio"] or needs["roe"] or needs["net_margin"] or needs["gross_margin"]:
                    try:
                        inc = stock.income_stmt          # rows=items, cols=dates (newest first)
                        if inc is not None and not inc.empty:
                            col = inc.columns[0]          # most recent annual period

                            def _row(df: pd.DataFrame, *names) -> Optional[float]:
                                for n in names:
                                    if n in df.index:
                                        v = df.loc[n, col]
                                        if pd.notna(v):
                                            return float(v)
                                return None

                            net_income_val = _row(inc,
                                "Net Income", "Net Income Common Stockholders",
                                "NetIncome", "Net Income Applicable To Common Shares")
                            revenue_val    = _row(inc,
                                "Total Revenue", "Revenue", "TotalRevenue",
                                "Revenues")
                            gross_val      = _row(inc,
                                "Gross Profit", "GrossProfit")

                            if needs["pe_ratio"] and mc and net_income_val and net_income_val > 0:
                                base["pe_ratio"] = _v(mc / net_income_val, 2)

                            if needs["net_margin"] and net_income_val is not None and revenue_val:
                                if revenue_val != 0:
                                    base["net_margin"] = _v(net_income_val / revenue_val * 100, 2)

                            if needs["gross_margin"] and gross_val is not None and revenue_val:
                                if revenue_val != 0:
                                    base["gross_margin"] = _v(gross_val / revenue_val * 100, 2)
                    except Exception:
                        pass

                # ── Balance sheet ────────────────────────────────────────────
                if needs["pb_ratio"] or needs["roe"]:
                    try:
                        bs = stock.balance_sheet
                        if bs is not None and not bs.empty:
                            col_bs = bs.columns[0]

                            def _bs_row(*names) -> Optional[float]:
                                for n in names:
                                    if n in bs.index:
                                        v = bs.loc[n, col_bs]
                                        if pd.notna(v):
                                            return float(v)
                                return None

                            equity_val = _bs_row(
                                "Stockholders Equity",
                                "Total Stockholders Equity",
                                "Common Stock Equity",
                                "StockholdersEquity",
                                "Total Equity Gross Minority Interest",
                            )

                            if equity_val and equity_val > 0:
                                if needs["pb_ratio"] and mc:
                                    base["pb_ratio"] = _v(mc / equity_val, 2)
                                if needs["roe"] and net_income_val is not None:
                                    base["roe"] = _v(net_income_val / equity_val * 100, 2)
                    except Exception:
                        pass
        except Exception:
            pass

        return base if base else self._minimal_info(ticker, asset_class)

    def _minimal_info(self, ticker: str, asset_class: str = "stock",
                      error: str = "") -> dict:
        """Skeleton info when all sources fail."""
        return {
            "ticker": ticker, "company": ticker,
            "sector": asset_class.capitalize(), "industry": "N/A",
            "market_cap": None, "current_price": None,
            "currency": _infer_currency(ticker),
            "pe_ratio": None, "pb_ratio": None, "dividend_yield": None,
            "roe": None, "roa": None, "net_margin": None,
            "52w_high": None, "52w_low": None, "beta": None,
            "analyst_target": None, "recommendation": "N/A",
            "description": "", "_source": "none", "_error": error,
        }

    # ── OHLCV with multi-period fallback ──────────────────────────────────────
    def get_ohlcv(self, ticker: str, period: str = "1y",
                  interval: str = "1d") -> pd.DataFrame:
        try:
            df = yf.Ticker(ticker).history(period=period, interval=interval)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass
        return pd.DataFrame()

    def get_ohlcv_best_effort(self, ticker: str) -> tuple[pd.DataFrame, str]:
        """
        Try progressively shorter periods until we have ≥10 bars.
        Returns (DataFrame, period_used).
        """
        attempts = [
            ("2y",  "1d"),
            ("1y",  "1d"),
            ("6mo", "1d"),
            ("3mo", "1d"),
            ("1mo", "1d"),
            ("3mo", "1wk"),
            ("1y",  "1wk"),
        ]
        for period, interval in attempts:
            df = self.get_ohlcv(ticker, period, interval)
            if len(df) >= 10:
                return df, f"{period}/{interval}"
        return pd.DataFrame(), "none"

    # ── Technical indicators with graceful degradation ────────────────────────
    def get_technicals(self, ticker: str) -> dict:
        df, period_used = self.get_ohlcv_best_effort(ticker)

        base = {"ticker": ticker, "_period_used": period_used}

        if df.empty:
            base["_error"] = "no_price_data"
            return base

        n = len(df)
        close  = df["Close"]
        volume = df["Volume"] if "Volume" in df.columns else pd.Series(dtype=float)

        # ── Use last VALID (non-zero, non-NaN) bars ───────────────────────────
        # yfinance sometimes returns 0 or NaN for the most recent bar (Thai stocks
        # in off-hours, partial session, or API quirks). Skip bad tail rows.
        valid_mask = close.notna() & (close > 0)
        if valid_mask.any():
            valid_df = df[valid_mask]
        else:
            valid_df = df  # fallback: use as-is

        last  = valid_df.iloc[-1]
        prev  = valid_df.iloc[-2]  if len(valid_df) >= 2 else valid_df.iloc[-1]
        prev5 = valid_df.iloc[-5]  if len(valid_df) >= 5 else valid_df.iloc[0]

        # Last trading session date (strip timezone for clean display)
        try:
            last_bar_dt = df.index[-1]
            if hasattr(last_bar_dt, "date"):
                last_bar_date = str(last_bar_dt.date())
            else:
                last_bar_date = str(last_bar_dt)[:10]
        except Exception:
            last_bar_date = None

        base.update({
            "current_price":  _v(last["Close"], 4),
            "open":           _v(last["Open"], 4),
            "high":           _v(last["High"], 4),
            "low":            _v(last["Low"], 4),
            "change_1d_pct":  _v((last["Close"] - prev["Close"]) / prev["Close"] * 100, 2),
            "change_5d_pct":  _v((last["Close"] - prev5["Close"]) / prev5["Close"] * 100, 2),
            "last_bar_date":  last_bar_date,
        })

        # Volume
        if not volume.empty:
            base["volume"]         = _safe_int(last["Volume"])
            base["avg_volume_20d"] = _safe_int(volume.rolling(min(20, n)).mean().iloc[-1])
            base["volume_ratio"]   = _v(last["Volume"] / volume.rolling(min(20, n)).mean().iloc[-1])

        # Moving averages (only if enough bars)
        for span, key in [(20, "sma20"), (50, "sma50"), (200, "sma200")]:
            if n >= span:
                val = _v(close.rolling(span).mean().iloc[-1])
                base[key] = val
                base[f"above_{key}"] = bool(last["Close"] > val) if val else None

        base["ema20"] = _v(close.ewm(span=min(20, n), adjust=False).mean().iloc[-1])

        # RSI (needs ≥15)
        if n >= 15:
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs   = gain / loss
            rsi  = 100 - (100 / (1 + rs))
            base["rsi"] = _v(rsi.iloc[-1], 1)

        # MACD (needs ≥27)
        if n >= 27:
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd  = ema12 - ema26
            sig   = macd.ewm(span=9, adjust=False).mean()
            base["macd"]        = _v(macd.iloc[-1])
            base["macd_signal"] = _v(sig.iloc[-1])
            base["macd_hist"]   = _v((macd - sig).iloc[-1])

        # Bollinger Bands (needs ≥20)
        if n >= 20:
            mid  = close.rolling(20).mean()
            std  = close.rolling(20).std()
            base["bb_upper"] = _v((mid + 2 * std).iloc[-1])
            base["bb_mid"]   = _v(mid.iloc[-1])
            base["bb_lower"] = _v((mid - 2 * std).iloc[-1])

        # ATR (needs ≥15)
        if n >= 15 and "High" in df.columns:
            atr_df = pd.concat([
                df["High"] - df["Low"],
                (df["High"] - df["Close"].shift()).abs(),
                (df["Low"]  - df["Close"].shift()).abs(),
            ], axis=1).max(axis=1)
            base["atr"] = _v(atr_df.rolling(14).mean().iloc[-1])

        # 52W high / low (use available range)
        base["high_52w"] = _v(close.max())
        base["low_52w"]  = _v(close.min())

        base["bars_available"] = n

        return base

    # ── Multi-Timeframe Engine ───────────────────────────────────────────────
    def get_multi_timeframe(self, ticker: str) -> dict:
        """
        Fetch OHLCV and compute indicators for 6 timeframes:
        15m, 1h, 4h (resampled), 1d, 1w, 1mo
        Returns per-TF summary + weighted confluence signal.
        """
        configs = [
            ("15m", "5d",   "15m",  False),
            ("1h",  "60d",  "1h",   False),
            ("4h",  "60d",  "1h",   True),   # resample 1h→4h
            ("1d",  "2y",   "1d",   False),
            ("1w",  "5y",   "1wk",  False),
            ("1mo", "10y",  "1mo",  False),
        ]
        result: dict = {}
        for label, period, interval, resample in configs:
            df = self.get_ohlcv(ticker, period, interval)
            if resample and not df.empty:
                df = (df.resample("4h")
                        .agg({"Open": "first", "High": "max",
                              "Low": "min", "Close": "last", "Volume": "sum"})
                        .dropna(subset=["Close"]))
            result[label] = (self._tf_summary(df, label)
                             if not df.empty and len(df) >= 5
                             else {"available": False, "tf": label})

        result["confluence"] = self._confluence(result)
        return result

    def _tf_summary(self, df: pd.DataFrame, tf: str) -> dict:
        n      = len(df)
        close  = df["Close"]
        last   = df.iloc[-1]
        prev   = df.iloc[-2] if n > 1 else last

        out: dict = {
            "available":    True,
            "tf":           tf,
            "bars":         n,
            "price":        _v(last["Close"], 4),
            "change_pct":   _v((last["Close"] - prev["Close"]) / prev["Close"] * 100, 2),
            "high":         _v(last["High"], 4),
            "low":          _v(last["Low"], 4),
        }

        # ── Trend (via SMA) ──────────────────────────────────────────────────
        sma20 = _v(close.rolling(min(20, n)).mean().iloc[-1])
        sma50 = _v(close.rolling(min(50, n)).mean().iloc[-1]) if n >= 20 else None
        out["sma20"] = sma20
        out["sma50"] = sma50
        p = float(last["Close"])
        if sma50:
            if p > sma20 and p > sma50:
                out["trend"], out["trend_th"] = "BULLISH", "ขาขึ้น 📈"
            elif p < sma20 and p < sma50:
                out["trend"], out["trend_th"] = "BEARISH", "ขาลง 📉"
            else:
                out["trend"], out["trend_th"] = "SIDEWAYS", "Sideways ↔️"
        else:
            if sma20 and p > sma20:
                out["trend"], out["trend_th"] = "BULLISH", "ขาขึ้น 📈"
            elif sma20 and p < sma20:
                out["trend"], out["trend_th"] = "BEARISH", "ขาลง 📉"
            else:
                out["trend"], out["trend_th"] = "SIDEWAYS", "Sideways ↔️"

        # ── RSI ──────────────────────────────────────────────────────────────
        if n >= 15:
            d     = close.diff()
            gain  = d.where(d > 0, 0).rolling(14).mean()
            loss  = (-d.where(d < 0, 0)).rolling(14).mean()
            rsi   = 100 - (100 / (1 + gain / loss))
            rv    = _v(rsi.iloc[-1], 1)
            out["rsi"] = rv
            if rv and rv >= 70:
                out["rsi_zone"] = "overbought"; out["rsi_zone_th"] = "Overbought 🔴"
            elif rv and rv <= 30:
                out["rsi_zone"] = "oversold";   out["rsi_zone_th"] = "Oversold 🟢"
            else:
                out["rsi_zone"] = "neutral";    out["rsi_zone_th"] = "Neutral ⚪"

        # ── MACD ─────────────────────────────────────────────────────────────
        if n >= 27:
            ema12  = close.ewm(span=12, adjust=False).mean()
            ema26  = close.ewm(span=26, adjust=False).mean()
            macd   = ema12 - ema26
            sig    = macd.ewm(span=9, adjust=False).mean()
            hist   = macd - sig
            hv     = _v(hist.iloc[-1])
            hv_prev= _v(hist.iloc[-2]) if n >= 28 else 0
            out["macd_hist"] = hv
            if hv and hv > 0 and (hv_prev or 0) <= 0:
                out["macd_signal_th"] = "Golden Cross ✅"
            elif hv and hv < 0 and (hv_prev or 0) >= 0:
                out["macd_signal_th"] = "Death Cross ❌"
            elif hv and hv > 0:
                out["macd_signal_th"] = "Bullish ↑"
            else:
                out["macd_signal_th"] = "Bearish ↓"

        # ── Support / Resistance ──────────────────────────────────────────────
        lb = min(20, n)
        out["resistance"] = _v(close.rolling(lb).max().iloc[-1])
        out["support"]    = _v(close.rolling(lb).min().iloc[-1])

        # ── Volume ────────────────────────────────────────────────────────────
        if "Volume" in df.columns:
            avg = df["Volume"].rolling(min(20, n)).mean().iloc[-1]
            if avg and avg > 0:
                out["vol_ratio"] = _v(float(last["Volume"]) / float(avg))

        # ── Bias score ────────────────────────────────────────────────────────
        bull = 0; bear = 0
        if out.get("trend") == "BULLISH":   bull += 2
        elif out.get("trend") == "BEARISH": bear += 2
        rv = out.get("rsi")
        if rv:
            if rv > 55: bull += 1
            elif rv < 45: bear += 1
        mh = out.get("macd_hist")
        if mh:
            if mh > 0: bull += 1
            else:       bear += 1

        if bull > bear + 1:
            out["bias"] = "BUY";     out["bias_th"] = "ซื้อ";    out["bias_dot"] = "🟢"
        elif bear > bull + 1:
            out["bias"] = "SELL";    out["bias_th"] = "ขาย";   out["bias_dot"] = "🔴"
        else:
            out["bias"] = "NEUTRAL"; out["bias_th"] = "รอดู";  out["bias_dot"] = "🟡"

        return out

    def _confluence(self, mtf: dict) -> dict:
        weights = {"1mo": 3.0, "1w": 2.5, "1d": 2.0, "4h": 1.5, "1h": 1.0, "15m": 0.5}
        bull_w = bear_w = 0.0
        available_tfs = []
        for tf, w in weights.items():
            d = mtf.get(tf, {})
            if not d.get("available"):
                continue
            available_tfs.append(tf)
            b = d.get("bias", "NEUTRAL")
            if b == "BUY":     bull_w += w
            elif b == "SELL":  bear_w += w

        total = bull_w + bear_w
        if total == 0:
            return {"signal": "NEUTRAL", "signal_th": "เป็นกลาง", "bull_pct": 50, "bear_pct": 50, "tfs": available_tfs}

        bp = round(bull_w / total * 100)
        if bp >= 75:    sig, sig_th, dot = "STRONG BUY",  "ซื้อแรง ⚡",  "🟢"
        elif bp >= 55:  sig, sig_th, dot = "BUY",         "ซื้อ",         "🟢"
        elif bp <= 25:  sig, sig_th, dot = "STRONG SELL", "ขายแรง ⚡",  "🔴"
        elif bp <= 45:  sig, sig_th, dot = "SELL",        "ขาย",          "🔴"
        else:           sig, sig_th, dot = "NEUTRAL",     "รอดู",          "🟡"

        return {"signal": sig, "signal_th": sig_th, "dot": dot,
                "bull_pct": bp, "bear_pct": 100 - bp, "tfs": available_tfs}

    # ── News ──────────────────────────────────────────────────────────────────
    def get_news(self, ticker: str, asset_class: str = "stock",
                 limit: int = 8) -> list[dict]:
        results = []

        # yfinance news — handle both old ({title, publisher, link})
        # and new ({id, content: {title, provider, canonicalUrl}}) formats
        try:
            news = yf.Ticker(ticker).news or []
            for n in news[:limit]:
                c = n.get("content", {})
                if c:  # new format
                    title     = c.get("title", "")
                    publisher = c.get("provider", {}).get("displayName", "")
                    link      = (c.get("clickThroughUrl") or c.get("canonicalUrl") or {}).get("url", "")
                else:  # old format
                    title     = n.get("title", "")
                    publisher = n.get("publisher", "")
                    link      = n.get("link", "")
                if title:
                    results.append({
                        "title":     title,
                        "publisher": publisher,
                        "link":      link,
                        "source":    "yfinance",
                    })
        except Exception:
            pass

        # Google News RSS fallback (free, no key)
        if len(results) < 4:
            clean = ticker.replace(".BK", "").replace("-USD", "").replace("=F", "")
            results += _google_news_rss(clean, limit=limit - len(results))

        return results[:limit]

    # ── All-in-one ────────────────────────────────────────────────────────────
    def get_all(self, ticker: str, asset_class: str = "stock") -> dict:
        info        = self.get_info(ticker, asset_class)
        technicals  = self.get_technicals(ticker)
        news        = self.get_news(ticker, asset_class)

        # Sync price: prefer technicals (live bar) over info (may be delayed)
        if not info.get("current_price") and technicals.get("current_price"):
            info["current_price"] = technicals["current_price"]
        if not technicals.get("current_price") and info.get("current_price"):
            technicals["current_price"] = info["current_price"]

        # OHLCV records for price chart (last 180 bars, JSON-safe)
        chart_records: list = []
        try:
            ohlcv_df, _ = self.get_ohlcv_best_effort(ticker)
            if not ohlcv_df.empty:
                _cdf = ohlcv_df.copy().tail(180).reset_index()
                # Normalise the date column name (yfinance 0.2+ uses "Date" or "Datetime")
                date_col = "Date" if "Date" in _cdf.columns else _cdf.columns[0]
                _cdf[date_col] = _cdf[date_col].astype(str).str[:10]
                cols = [date_col, "Open", "High", "Low", "Close"]
                if "Volume" in _cdf.columns:
                    cols.append("Volume")
                _cdf = _cdf[cols].rename(columns={date_col: "Date"})
                # Drop any row where Close is 0 or NaN
                _cdf = _cdf[_cdf["Close"].notna() & (_cdf["Close"] > 0)]
                chart_records = _cdf.to_dict("records")
        except Exception:
            chart_records = []

        return {
            "info":          info,
            "technicals":    technicals,
            "news":          news,
            "chart_records": chart_records,
        }


# ── Google News RSS (no API key) ──────────────────────────────────────────────
def _google_news_rss(query: str, limit: int = 5) -> list[dict]:
    try:
        import feedparser
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        results = []
        for entry in feed.entries[:limit]:
            results.append({
                "title":     entry.get("title", ""),
                "publisher": entry.get("source", {}).get("title", "Google News"),
                "link":      entry.get("link", ""),
                "source":    "google_news",
            })
        return results
    except Exception:
        return []


# Make urllib.parse available
import urllib.parse

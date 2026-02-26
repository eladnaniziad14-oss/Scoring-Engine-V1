# market_data.py
from __future__ import annotations

from typing import Dict
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf
import ta
from binance.client import Client

from asset_registry import resolve_asset
from utils import parse_timestamp


# -----------------------------
# Helpers
# -----------------------------
def _as_1d_series(x) -> pd.Series:
    """Ensure x is a clean 1D float Series."""
    if x is None:
        return pd.Series(dtype=float)

    if isinstance(x, pd.DataFrame):
        if "close" in x.columns:
            x = x["close"]
        else:
            x = x.iloc[:, 0]

    # If it's still 2D-like, take first column
    if hasattr(x, "ndim") and getattr(x, "ndim", 1) > 1:
        x = x.iloc[:, 0]

    s = pd.Series(x).copy()
    s = pd.to_numeric(s, errors="coerce").dropna()
    return s


def _ensure_utc_index(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    return df


def _slice_until(df: pd.DataFrame, ts_utc: datetime) -> pd.DataFrame:
    df = _ensure_utc_index(df)
    if df.empty:
        return df
    return df.loc[df.index <= ts_utc].copy()


def _momentum(series: pd.Series, bars: int) -> float:
    series = _as_1d_series(series)
    if len(series) < bars + 1:
        return 0.0
    a = float(series.iloc[-1])
    b = float(series.iloc[-(bars + 1)])
    if b == 0:
        return 0.0
    return float((a - b) / b)


def _binance_symbol_from_canonical(canonical: str) -> str:
    s = (canonical or "").upper().replace("/", "").replace("-", "").replace(" ", "")
    if s.endswith("USDT"):
        return s
    return f"{s}USDT"


def _fetch_binance_ohlcv(binance_client, symbol: str, interval: str, limit: int) -> pd.DataFrame:
    klines = binance_client.get_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(
        klines,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "num_trades",
            "taker_buy_base", "taker_buy_quote", "ignore",
        ],
    )

    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df.set_index("open_time")
    df = df.dropna(subset=["close"])
    return df[["open", "high", "low", "close", "volume"]]


def _safe_yahoo_ohlcv(yahoo_symbol: str, period: str, interval: str) -> pd.DataFrame:
    """Safer history pull; returns empty df if Yahoo fails."""
    try:
        t = yf.Ticker(yahoo_symbol)
        df = t.history(period=period, interval=interval)
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
        ).dropna()

        df = _ensure_utc_index(df)

        for c in ["open", "high", "low", "close"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
        else:
            df["volume"] = 0.0

        df = df.dropna(subset=["close"])
        return df[["open", "high", "low", "close", "volume"]]
    except Exception:
        return pd.DataFrame()


def _atr_from_daily(df_1d: pd.DataFrame, window: int = 14) -> float:
    """Simple ATR using daily candles (manual, safe fallback)."""
    if df_1d is None or df_1d.empty or len(df_1d) < window + 2:
        return 0.0

    h = pd.to_numeric(df_1d["high"], errors="coerce")
    l = pd.to_numeric(df_1d["low"], errors="coerce")
    c = pd.to_numeric(df_1d["close"], errors="coerce")

    prev_c = c.shift(1)
    tr = np.maximum(h - l, np.maximum((h - prev_c).abs(), (l - prev_c).abs()))
    atr = tr.rolling(window).mean().iloc[-1]
    if not np.isfinite(atr):
        return 0.0
    return float(atr)


# -----------------------------
# Public: compute momentums + weighted_momentum
# -----------------------------
def get_momentums(user_input: dict, *, binance_client=None) -> Dict:
    """
    Returns dict:
    {
      "momentums": {...},
      "weighted_momentum": float
    }
    """
    canonical, asset_data = resolve_asset(user_input)
    if not asset_data:
        return {"momentums": {}, "weighted_momentum": 0.0}

    ts = parse_timestamp(user_input.get("timestamp"))
    asset_type = asset_data.get("type", "other")

    # ----------------- Crypto (Binance) -----------------
    if asset_type == "crypto":
        if binance_client is None:
            raise ValueError("binance_client is required for crypto momentums")

        symbol = _binance_symbol_from_canonical(canonical)

        df_1h = _fetch_binance_ohlcv(binance_client, symbol=symbol, interval=Client.KLINE_INTERVAL_1HOUR, limit=1000)
        df_1d = _fetch_binance_ohlcv(binance_client, symbol=symbol, interval=Client.KLINE_INTERVAL_1DAY, limit=400)

        df_1h = _slice_until(df_1h, ts)
        df_1d = _slice_until(df_1d, ts)

        close_1h = _as_1d_series(df_1h["close"]) if not df_1h.empty else pd.Series(dtype=float)
        close_1d = _as_1d_series(df_1d["close"]) if not df_1d.empty else pd.Series(dtype=float)

    # ----------------- Non-crypto (Yahoo) -----------------
    else:
        yahoo_symbol = asset_data.get("yahoo")
        if not yahoo_symbol:
            return {"momentums": {}, "weighted_momentum": 0.0}

        df_1h = _safe_yahoo_ohlcv(yahoo_symbol, period="90d", interval="1h")
        df_1d = _safe_yahoo_ohlcv(yahoo_symbol, period="2y", interval="1d")

        df_1h = _slice_until(df_1h, ts)
        df_1d = _slice_until(df_1d, ts)

        close_1h = _as_1d_series(df_1h["close"]) if not df_1h.empty else pd.Series(dtype=float)
        close_1d = _as_1d_series(df_1d["close"]) if not df_1d.empty else pd.Series(dtype=float)

    momentums = {
        "momentum_5h": _momentum(close_1h, 5),
        "momentum_10h": _momentum(close_1h, 10),
        "momentum_20h": _momentum(close_1h, 20),
        "momentum_5d": _momentum(close_1d, 5),
        "momentum_20d": _momentum(close_1d, 20),
        "momentum_40d": _momentum(close_1d, 40),
        "momentum_60d": _momentum(close_1d, 60),
    }

    weighted_momentum = (
        0.30 * momentums["momentum_5h"] +
        0.20 * momentums["momentum_10h"] +
        0.10 * momentums["momentum_20h"] +
        0.20 * momentums["momentum_5d"] +
        0.10 * momentums["momentum_20d"] +
        0.05 * momentums["momentum_40d"] +
        0.05 * momentums["momentum_60d"]
    )

    return {"momentums": momentums, "weighted_momentum": float(weighted_momentum)}


# -----------------------------
# Entry-quality inputs
# -----------------------------
def get_entry_inputs(user_input: dict, *, binance_client=None) -> dict:
    """
    Returns everything entry_quality.py needs:
    {
      "df_1h": pd.DataFrame,
      "closes_1h": pd.Series,
      "spot": float,
      "atr_daily": float,
      "binance_symbol": str|None
    }
    """
    canonical, asset_data = resolve_asset(user_input)
    if not asset_data:
        return {
            "df_1h": pd.DataFrame(),
            "closes_1h": pd.Series(dtype=float),
            "spot": np.nan,
            "atr_daily": np.nan,
            "binance_symbol": None,
        }

    ts = parse_timestamp(user_input.get("timestamp"))
    asset_type = asset_data.get("type", "other")

    # ----------------- Crypto (Binance) -----------------
    if asset_type == "crypto":
        if binance_client is None:
            raise ValueError("binance_client is required for crypto entry inputs")

        symbol = _binance_symbol_from_canonical(canonical)
        df_1h = _fetch_binance_ohlcv(binance_client, symbol=symbol, interval=Client.KLINE_INTERVAL_1HOUR, limit=1000)
        df_1d = _fetch_binance_ohlcv(binance_client, symbol=symbol, interval=Client.KLINE_INTERVAL_1DAY, limit=400)

        df_1h = _slice_until(df_1h, ts)
        df_1d = _slice_until(df_1d, ts)

        closes_1h = _as_1d_series(df_1h["close"]) if not df_1h.empty else pd.Series(dtype=float)

        # spot (live)
        try:
            spot = float(binance_client.get_symbol_ticker(symbol=symbol)["price"])
        except Exception:
            spot = float(closes_1h.iloc[-1]) if len(closes_1h) else np.nan

        # ATR daily (prefer ta, fallback manual)
        atr_daily = np.nan
        if df_1d is not None and not df_1d.empty and len(df_1d) >= 30:
            try:
                atr_series = ta.volatility.AverageTrueRange(
                    high=df_1d["high"], low=df_1d["low"], close=df_1d["close"], window=14
                ).average_true_range()
                atr_daily = float(atr_series.iloc[-1]) if len(atr_series) else np.nan
            except Exception:
                atr_daily = np.nan

        if not np.isfinite(atr_daily):
            atr_daily = _atr_from_daily(df_1d)

        return {
            "df_1h": df_1h,
            "closes_1h": closes_1h,
            "spot": spot,
            "atr_daily": atr_daily,
            "binance_symbol": symbol,
        }

    # ----------------- Non-crypto (Yahoo) -----------------
    yahoo_symbol = asset_data.get("yahoo")
    if not yahoo_symbol:
        return {
            "df_1h": pd.DataFrame(),
            "closes_1h": pd.Series(dtype=float),
            "spot": np.nan,
            "atr_daily": np.nan,
            "binance_symbol": None,
        }

    df_1h = _safe_yahoo_ohlcv(yahoo_symbol, period="90d", interval="1h")
    df_1d = _safe_yahoo_ohlcv(yahoo_symbol, period="2y", interval="1d")

    df_1h = _slice_until(df_1h, ts)
    df_1d = _slice_until(df_1d, ts)

    closes_1h = _as_1d_series(df_1h["close"]) if not df_1h.empty else pd.Series(dtype=float)
    spot = float(df_1d["close"].iloc[-1]) if df_1d is not None and not df_1d.empty else np.nan

    atr_daily = np.nan
    if df_1d is not None and not df_1d.empty and len(df_1d) >= 30:
        try:
            atr_series = ta.volatility.AverageTrueRange(
                high=df_1d["high"], low=df_1d["low"], close=df_1d["close"], window=14
            ).average_true_range()
            atr_daily = float(atr_series.iloc[-1]) if len(atr_series) else np.nan
        except Exception:
            atr_daily = np.nan

    if not np.isfinite(atr_daily):
        atr_daily = _atr_from_daily(df_1d)

    return {
        "df_1h": df_1h,
        "closes_1h": closes_1h,
        "spot": spot,
        "atr_daily": atr_daily,
        "binance_symbol": None,  # no depth provider yet for non-crypto
    }
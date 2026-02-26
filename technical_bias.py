# technical_bias.py

from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf
import ta
from datetime import datetime, timezone

from asset_registry import resolve_asset


# -----------------------------
# Time helpers
# -----------------------------
def _to_utc_datetime(ts: str) -> datetime:
    if not ts:
        return datetime.now(timezone.utc)
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def _slice_until_timestamp(df: pd.DataFrame, ts_utc: datetime) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    # index should already be tz-aware UTC
    return df.loc[df.index <= ts_utc].copy()


# -----------------------------
# Data fetching
#   - Binance for crypto
#   - Yahoo for everything else
# -----------------------------
def _binance_symbol_from_canonical(canonical: str) -> str:
    a = (canonical or "").upper().replace("-", "").replace("/", "").replace(" ", "")
    if a.endswith("USDT"):
        return a
    return f"{a}USDT"


def _fetch_binance_ohlcv(binance_client, symbol: str, interval: str, limit: int) -> pd.DataFrame:
    """
    interval examples: "1h", "1d", "1w"
    """
    klines = binance_client.get_klines(symbol=symbol, interval=interval, limit=limit)

    df = pd.DataFrame(
        klines,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "num_trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ],
    )

    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df.set_index("open_time")
    df = df.dropna(subset=["close"])

    return df[["open", "high", "low", "close", "volume"]]


def _fetch_binance_spot_price(binance_client, symbol: str) -> float | None:
    """Live spot price from Binance ticker endpoint."""
    try:
        t = binance_client.get_symbol_ticker(symbol=symbol)
        return float(t["price"])
    except Exception:
        return None


def _fetch_yahoo_ohlcv(yahoo_symbol: str, period: str, interval: str) -> pd.DataFrame:
    """
    interval: "1h", "1d", "1wk"
    Uses yf.Ticker().history (more stable than yf.download)
    """
    try:
        t = yf.Ticker(yahoo_symbol)
        df = t.history(period=period, interval=interval)
    except Exception:
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    df = df.dropna(subset=["close"])

    # Ensure UTC index
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
    else:
        df["volume"] = 0.0

    df = df.dropna(subset=["close"])
    return df[["open", "high", "low", "close", "volume"]]


# -----------------------------
# Core bias calc (ATR-normalized)
# -----------------------------
def _compute_trend_bias(df: pd.DataFrame) -> tuple[float, dict]:
    """
    Returns:
      bias in [-1, +1]
      breakdown dict
    """
    if df is None or df.empty or len(df) < 80:
        return 0.0, {"reason": "insufficient_bars", "bars": int(len(df) if df is not None else 0)}

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    # Indicators
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()

    macd_obj = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
    macd = macd_obj.macd()
    macd_sig = macd_obj.macd_signal()

    sma20 = ta.trend.SMAIndicator(close, window=20).sma_indicator()
    sma50 = ta.trend.SMAIndicator(close, window=50).sma_indicator()

    ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator()
    ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator()

    adx = ta.trend.ADXIndicator(high, low, close, window=14).adx()
    atr = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()

    latest_close = float(close.iloc[-1])
    atr_val = float(atr.iloc[-1]) if np.isfinite(atr.iloc[-1]) else 0.0
    atr_safe = max(atr_val, 1e-9)

    # Bias components
    rsi_bias = float(np.clip((float(rsi.iloc[-1]) - 50.0) / 50.0, -1, 1))

    macd_hist = float(macd.iloc[-1]) - float(macd_sig.iloc[-1])
    macd_bias = float(np.tanh(macd_hist * 5.0))

    # ATR-normalized structure distances
    sma_bias = float(np.tanh(((float(sma20.iloc[-1]) - float(sma50.iloc[-1])) / atr_safe) * 0.8))
    ema_bias = float(np.tanh(((float(ema20.iloc[-1]) - float(ema50.iloc[-1])) / atr_safe) * 0.8))
    price_structure = float(np.tanh(((latest_close - float(sma50.iloc[-1])) / atr_safe) * 0.6))

    # Light breakout confirmation (Donchian)
    breakout_bias = 0.0
    if len(df) >= 22:
        donch_high = high.rolling(20).max()
        donch_low = low.rolling(20).min()
        if latest_close > float(donch_high.iloc[-2]):
            breakout_bias = 1.0
        elif latest_close < float(donch_low.iloc[-2]):
            breakout_bias = -1.0

    raw_bias = (
        0.10 * rsi_bias +
        0.30 * macd_bias +
        0.20 * sma_bias +
        0.20 * ema_bias +
        0.10 * price_structure +
        0.10 * breakout_bias
    )
    raw_bias = float(np.clip(raw_bias, -1, 1))

    # Trend strength amplifier (ADX)
    adx_val = float(adx.iloc[-1]) if np.isfinite(adx.iloc[-1]) else 0.0
    adx_strength = float(np.clip(adx_val / 40.0, 0, 1))
    strength_factor = 0.4 + 0.6 * adx_strength

    bias = float(np.clip(raw_bias * strength_factor, -1, 1))

    breakdown = {
        "rsi_bias": rsi_bias,
        "macd_bias": macd_bias,
        "sma_bias": sma_bias,
        "ema_bias": ema_bias,
        "price_structure": price_structure,
        "breakout_bias": breakout_bias,
        "raw_bias": raw_bias,
        "adx": adx_val,
        "atr": atr_val,
        "strength_factor": strength_factor,
        "bars_used": int(len(df)),
    }
    return bias, breakdown


# -----------------------------
# Volatility regime factor (ATR% + BB width)
# -----------------------------
def _volatility_regime_factor(df: pd.DataFrame) -> tuple[float, dict]:
    """
    Returns damping factor in [0.55..1.00]
    Lower => reduce bias magnitude (choppy / low signal)
    Higher => keep bias magnitude (clean trend)
    """
    if df is None or df.empty or len(df) < 60:
        return 0.85, {"reason": "insufficient_bars"}

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    atr = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)

    latest_close = float(close.iloc[-1])
    atr_val = float(atr.iloc[-1]) if np.isfinite(atr.iloc[-1]) else 0.0
    atrp = atr_val / max(abs(latest_close), 1e-9)

    bb_high = float(bb.bollinger_hband().iloc[-1])
    bb_low = float(bb.bollinger_lband().iloc[-1])
    bbw = (bb_high - bb_low) / max(abs(latest_close), 1e-9)

    atrp_q = float(np.clip((atrp - 0.001) / 0.010, 0, 1))
    bbw_q = float(np.clip((bbw - 0.002) / 0.020, 0, 1))

    quality = 0.5 * atrp_q + 0.5 * bbw_q
    factor = 0.55 + 0.45 * quality

    return float(np.clip(factor, 0.55, 1.0)), {
        "atr_percent": atrp,
        "bb_width_percent": bbw,
        "quality": quality,
        "factor": factor,
    }


# -----------------------------
# Support/Resistance proximity factor
# -----------------------------
def _sr_proximity_factor(df: pd.DataFrame, bias: float, lookback: int = 60) -> tuple[float, dict]:
    """
    Damp bias magnitude when price is too close to opposing level:
    - If bias > 0: near resistance => damp
    - If bias < 0: near support => damp
    Factor in [0.60..1.00]
    """
    if df is None or df.empty or len(df) < lookback + 5:
        return 1.0, {"reason": "insufficient_bars"}

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    atr = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
    atr_val = float(atr.iloc[-1]) if np.isfinite(atr.iloc[-1]) else 0.0
    atr_safe = max(atr_val, 1e-9)

    recent_high = float(high.tail(lookback).max())
    recent_low = float(low.tail(lookback).min())
    last = float(close.iloc[-1])

    dist_to_res = (recent_high - last) / atr_safe
    dist_to_sup = (last - recent_low) / atr_safe

    def proximity_penalty(dist_atr: float) -> float:
        if dist_atr <= 0:
            return 0.40
        return float(np.clip(0.40 * (1 - min(dist_atr, 2.0) / 2.0), 0.0, 0.40))

    penalty = 0.0
    if bias > 0:
        penalty = proximity_penalty(dist_to_res)
    elif bias < 0:
        penalty = proximity_penalty(dist_to_sup)

    factor = 1.0 - penalty
    factor = float(np.clip(factor, 0.60, 1.0))

    return factor, {
        "lookback": lookback,
        "recent_high": recent_high,
        "recent_low": recent_low,
        "last_close": last,
        "atr": atr_val,
        "dist_to_res_atr": float(dist_to_res),
        "dist_to_sup_atr": float(dist_to_sup),
        "penalty": float(penalty),
        "factor": factor,
    }


# -----------------------------
# Public function
# -----------------------------
def get_technical_bias(user_input: dict, binance_client=None) -> dict:
    canonical, asset_data = resolve_asset(user_input)
    if not asset_data:
        return {"technical_bias": 0.0, "canonical": canonical, "reason": "unresolved_asset"}

    ts = _to_utc_datetime(user_input.get("timestamp", ""))
    asset_type = asset_data.get("type", "other")
    yahoo_symbol = asset_data.get("yahoo")

    # ---- Fetch 1h / 1d / 1w
    spot_price: float | None = None
    price_source: str = "unknown"

    if asset_type == "crypto":
        if binance_client is None:
            return {"technical_bias": 0.0, "canonical": canonical, "reason": "missing_binance_client"}

        bsymbol = _binance_symbol_from_canonical(canonical)

        spot_price = _fetch_binance_spot_price(binance_client, bsymbol)
        price_source = "binance"

        df_1h = _fetch_binance_ohlcv(binance_client, symbol=bsymbol, interval="1h", limit=1000)
        df_1d = _fetch_binance_ohlcv(binance_client, symbol=bsymbol, interval="1d", limit=400)
        df_1w = _fetch_binance_ohlcv(binance_client, symbol=bsymbol, interval="1w", limit=260)

        df_1h = _slice_until_timestamp(df_1h, ts)
        df_1d = _slice_until_timestamp(df_1d, ts)
        df_1w = _slice_until_timestamp(df_1w, ts)

    else:
        if not yahoo_symbol:
            return {"technical_bias": 0.0, "canonical": canonical, "reason": "missing_yahoo_symbol"}

        df_1h = _fetch_yahoo_ohlcv(yahoo_symbol, period="90d", interval="1h")
        df_1d = _fetch_yahoo_ohlcv(yahoo_symbol, period="2y", interval="1d")
        df_1w = _fetch_yahoo_ohlcv(yahoo_symbol, period="5y", interval="1wk")

        df_1h = _slice_until_timestamp(df_1h, ts)
        df_1d = _slice_until_timestamp(df_1d, ts)
        df_1w = _slice_until_timestamp(df_1w, ts)

        if df_1d is not None and not df_1d.empty:
            spot_price = float(df_1d["close"].iloc[-1])
        elif df_1h is not None and not df_1h.empty:
            spot_price = float(df_1h["close"].iloc[-1])
        else:
            spot_price = None

        price_source = "yahoo"

    # If no market data at all
    if (df_1d is None or df_1d.empty) and (df_1h is None or df_1h.empty) and (df_1w is None or df_1w.empty):
        return {
            "canonical": canonical,
            "type": asset_type,
            "price_source": price_source,
            "last_price": spot_price,
            "technical_bias": 0.0,
            "reason": "no_market_data",
        }

    # ---- Bias per timeframe
    hourly_bias, hourly_breakdown = _compute_trend_bias(df_1h)
    daily_bias, daily_breakdown = _compute_trend_bias(df_1d)
    weekly_bias, weekly_breakdown = _compute_trend_bias(df_1w)

    # ---- Combine (daily matters most)
    w_daily = 0.60
    w_hourly = 0.25
    w_weekly = 0.15
    combined_bias = float(np.clip(w_daily * daily_bias + w_hourly * hourly_bias + w_weekly * weekly_bias, -1, 1))

    # ---- Filters based on DAILY
    regime_factor, regime_dbg = _volatility_regime_factor(df_1d)
    sr_factor, sr_dbg = _sr_proximity_factor(df_1d, combined_bias, lookback=60)

    final_bias = float(np.sign(combined_bias) * min(abs(combined_bias) * regime_factor * sr_factor, 1.0))
    final_bias = float(np.clip(final_bias, -1, 1))

    # Optional: label daily bias direction for convenience
    if daily_bias > 0.10:
        daily_label = "bullish"
    elif daily_bias < -0.10:
        daily_label = "bearish"
    else:
        daily_label = "neutral"

    return {
        "canonical": canonical,
        "type": asset_type,

        "price_source": price_source,
        "last_price": spot_price,

        "technical_bias": final_bias,

        "daily_direction": daily_label,  # "bullish" / "bearish" / "neutral"

        "components": {
            "hourly_bias": float(hourly_bias),
            "daily_bias": float(daily_bias),
            "weekly_bias": float(weekly_bias),
            "weights": {"daily": w_daily, "hourly": w_hourly, "weekly": w_weekly},
            "combined_pre_filters": float(combined_bias),
        },

        "filters": {
            "volatility_regime_factor": float(regime_factor),
            "sr_proximity_factor": float(sr_factor),
        },

        "breakdown": {
            "hourly": hourly_breakdown,
            "daily": daily_breakdown,
            "weekly": weekly_breakdown,
            "regime": regime_dbg,
            "support_resistance": sr_dbg,
        },
    }
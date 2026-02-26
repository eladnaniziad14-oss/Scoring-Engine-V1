# entry_quality.py
# Adds support for "predicted move %" (move_pct) -> implied target
# Scores both ENTRY feasibility + TARGET feasibility + move realism + liquidity
#
# âœ… Refinement added:
# - Target feasibility is now "entry-aware" but still pre-trade (NOT conditional on entry fill):
#     p_reach_target = 0.60 * P(reach target from spot) + 0.40 * P(reach target from entry)
#
# Outputs:
# - p_touch_entry (0..1)
# - p_reach_target_from_spot (0..1)
# - p_reach_target_from_entry (0..1)
# - p_reach_target (blended) (0..1)
# - entry_precision_score (0..1)
# - target_precision_score (0..1)
# - move_realism_score (0..1)
# - liquidity_score (0..1)
# - final_entry_score (0..1)
#
# Notes:
# - Crypto liquidity uses Binance depth
# - For non-crypto, liquidity returns neutral 0.5 (until you add a provider)

from __future__ import annotations

import math
import numpy as np
import pandas as pd


# -----------------------------
# Helpers
# -----------------------------
def _safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _norm01(x: float) -> float:
    return float(np.clip(x, 0.0, 1.0))


def _direction_norm(direction: str) -> str:
    d = (direction or "").strip().upper()
    return "long" if d in ("BUY", "LONG") else "short"


def implied_target_price(entry_price: float, move_pct: float, direction: str) -> float | None:
    """
    move_pct example: 0.004 for 0.4%
    BUY:  target = entry*(1+move_pct)
    SELL: target = entry*(1-move_pct)
    """
    entry = _safe_float(entry_price, np.nan)
    mp = _safe_float(move_pct, np.nan)
    if not (np.isfinite(entry) and np.isfinite(mp)):
        return None
    mp = abs(mp)

    direction = _direction_norm(direction)
    if direction == "long":
        return float(entry * (1.0 + mp))
    return float(entry * (1.0 - mp))


# -----------------------------
# Bootstrap engine (shared)
# -----------------------------
def _bootstrap_paths(
    closes_1h: pd.Series,
    start_price: float,
    horizon_hours: int,
    n_sims: int,
    lookback_hours: int,
) -> np.ndarray | None:
    """
    Build bootstrap price paths starting from start_price.
    Returns ndarray shape (n_sims, horizon_hours) or None.
    """
    if closes_1h is None:
        return None

    close = closes_1h.dropna()
    if len(close) < max(lookback_hours, horizon_hours) + 5:
        return None

    close = close.astype(float)
    ret = close.pct_change().dropna().tail(lookback_hours)
    if len(ret) < 50:
        return None

    s0 = _safe_float(start_price, np.nan)
    if not np.isfinite(s0) or s0 <= 0:
        return None

    draws = np.random.choice(ret.values, size=(n_sims, horizon_hours), replace=True)
    paths = s0 * np.cumprod(1.0 + draws, axis=1)
    return paths


# -----------------------------
# 1) Bootstrap: touch ENTRY
# -----------------------------
def p_touch_bootstrap(
    closes_1h: pd.Series,
    entry_price: float,
    horizon_hours: int,
    direction: str,
    n_sims: int = 2000,
    lookback_hours: int = 240,  # last 10 days of 1h returns
) -> float:
    """
    Probability that price touches entry within horizon_hours.
    Uses bootstrap resampling of recent hourly returns.

    Touch rules:
    - BUY:  if entry <= spot => touch when path_min <= entry
            else            => touch when path_max >= entry
    - SELL: if entry >= spot => touch when path_max >= entry
            else            => touch when path_min <= entry
    """
    direction = _direction_norm(direction)
    entry_price = _safe_float(entry_price, np.nan)
    if not np.isfinite(entry_price):
        return 0.5

    # Spot is last close in series
    close = closes_1h.dropna() if closes_1h is not None else None
    if close is None or len(close) < 5:
        return 0.5
    spot = float(close.astype(float).iloc[-1])

    paths = _bootstrap_paths(
        closes_1h=closes_1h,
        start_price=spot,
        horizon_hours=int(max(1, horizon_hours)),
        n_sims=n_sims,
        lookback_hours=lookback_hours,
    )
    if paths is None:
        return 0.5

    path_min = paths.min(axis=1)
    path_max = paths.max(axis=1)

    if direction == "long":
        touched = (path_min <= entry_price) if entry_price <= spot else (path_max >= entry_price)
    else:
        touched = (path_max >= entry_price) if entry_price >= spot else (path_min <= entry_price)

    return float(np.mean(touched))


# -----------------------------
# 1b) Bootstrap: reach TARGET (now supports start_price)
# -----------------------------
def p_reach_target_bootstrap(
    closes_1h: pd.Series,
    target_price: float,
    horizon_hours: int,
    direction: str,
    *,
    start_price: float | None = None,  # âœ… NEW
    n_sims: int = 2000,
    lookback_hours: int = 240,
) -> float:
    """
    Probability that price reaches target within horizon_hours.
    - BUY:  path_max >= target
    - SELL: path_min <= target

    start_price:
    - If None: uses latest close as start (spot-based)
    - If provided: simulates from that level (entry-based check)
    """
    direction = _direction_norm(direction)
    target_price = _safe_float(target_price, np.nan)
    if not np.isfinite(target_price):
        return 0.5

    close = closes_1h.dropna() if closes_1h is not None else None
    if close is None or len(close) < 5:
        return 0.5

    spot = float(close.astype(float).iloc[-1])
    s0 = spot if start_price is None else _safe_float(start_price, np.nan)

    paths = _bootstrap_paths(
        closes_1h=closes_1h,
        start_price=s0,
        horizon_hours=int(max(1, horizon_hours)),
        n_sims=n_sims,
        lookback_hours=lookback_hours,
    )
    if paths is None:
        return 0.5

    if direction == "long":
        reached = paths.max(axis=1) >= target_price
    else:
        reached = paths.min(axis=1) <= target_price

    return float(np.mean(reached))


# -----------------------------
# 2) VWAP + precision scoring (ATR + VWAP)
# -----------------------------
def compute_vwap(df_1h: pd.DataFrame, window: int = 24) -> float:
    """Rolling VWAP over last 'window' hours (default: 24h)."""
    if df_1h is None or df_1h.empty or len(df_1h) < window:
        return np.nan

    d = df_1h.tail(window).copy()
    tp = (d["high"] + d["low"] + d["close"]) / 3.0
    vol = d.get("volume", pd.Series([0] * len(d), index=d.index)).astype(float)

    if vol.sum() <= 0:
        return float(tp.mean())
    return float((tp * vol).sum() / vol.sum())


def entry_precision_score(
    spot: float,
    entry: float,
    atr: float,
    vwap: float | None,
    direction: str,
) -> float:
    """
    Score 0..1, best when entry is realistic and not 'chasing'.
    Uses ATR distance and optional VWAP anchoring.
    """
    direction = _direction_norm(direction)

    spot = _safe_float(spot, np.nan)
    entry = _safe_float(entry, np.nan)
    atr = max(_safe_float(atr, 0.0), 1e-9)

    if not (np.isfinite(spot) and np.isfinite(entry)):
        return 0.5

    z = abs(entry - spot) / atr

    z0 = 0.6
    k = 1.8
    base = np.exp(-k * (z - z0) ** 2)

    chasing = (direction == "long" and entry > spot) or (direction == "short" and entry < spot)
    if chasing:
        base *= 0.6

    if vwap is not None and np.isfinite(vwap):
        vw_z = abs(entry - vwap) / atr
        vwap_bonus = float(np.exp(-1.2 * (vw_z ** 2)))
        base = 0.75 * base + 0.25 * vwap_bonus

    return _norm01(base)


def target_precision_score(
    entry: float,
    target: float,
    atr: float,
    vwap: float | None,
    direction: str,
) -> float:
    """
    Target realism relative to ENTRY (not spot).
    - BUY: target must be above entry
    - SELL: target must be below entry
    Score penalizes targets that are too small or too large in ATR terms.
    """
    direction = _direction_norm(direction)

    entry = _safe_float(entry, np.nan)
    target = _safe_float(target, np.nan)
    atr = max(_safe_float(atr, 0.0), 1e-9)

    if not (np.isfinite(entry) and np.isfinite(target)):
        return 0.5

    # directional distance measured from ENTRY
    if direction == "long":
        dz = (target - entry) / atr
    else:
        dz = (entry - target) / atr

    # If target is "behind" the direction from ENTRY, penalize hard
    if dz < 0:
        return 0.05

    # Reasonable target zone (tunable)
    # For short horizons, ~0.3â€“1.2 ATR is usually realistic.
    z0 = 0.8
    k = 1.1
    base = np.exp(-k * (dz - z0) ** 2)

    # Optional VWAP anchoring (very light)
    if vwap is not None and np.isfinite(vwap):
        vw_z = abs(target - vwap) / atr
        vwap_bonus = float(np.exp(-0.6 * (vw_z ** 2)))
        base = 0.85 * base + 0.15 * vwap_bonus

    return _norm01(base)


# -----------------------------
# 2b) Move realism score (volatility-aware)
# -----------------------------
def move_realism_score(
    spot: float,
    atr_daily: float,
    move_pct: float,
    horizon_hours: int,
) -> float:
    """
    Penalize unrealistic claims like "+5% in 1 hour".
    """
    spot = _safe_float(spot, np.nan)
    atr_daily = _safe_float(atr_daily, np.nan)
    move_pct = abs(_safe_float(move_pct, np.nan))
    horizon_hours = int(max(1, horizon_hours))

    if not (np.isfinite(spot) and np.isfinite(atr_daily) and np.isfinite(move_pct)):
        return 0.5
    if spot <= 0:
        return 0.5

    atr_pct = max(atr_daily / spot, 1e-9)
    expected = atr_pct * math.sqrt(horizon_hours / 24.0)
    ratio = move_pct / max(expected, 1e-9)

    return _norm01(math.exp(-(ratio ** 2)))


# -----------------------------
# 3) Liquidity score (Binance depth proxy)
# -----------------------------
def liquidity_score_binance(
    binance_client,
    symbol: str,
    entry: float,
    direction: str,
    band_bps: float = 25.0,
    depth_limit: int = 1000,
) -> float:
    """
    Measure liquidity near entry price using Binance order book depth.
    Output: 0..1

    - BUY consumes asks
    - SELL consumes bids
    - If entry too far from spot => neutral 0.5
    """
    direction = _direction_norm(direction)
    entry = _safe_float(entry, np.nan)

    if binance_client is None or not np.isfinite(entry):
        return 0.5

    try:
        spot = float(binance_client.get_symbol_ticker(symbol=symbol)["price"])
        if not np.isfinite(spot) or spot <= 0:
            return 0.5

        dist_pct = abs(entry - spot) / spot
        if dist_pct > 0.01:
            return 0.5

        book = binance_client.get_order_book(symbol=symbol, limit=depth_limit)
        bids_raw = book.get("bids", []) or []
        asks_raw = book.get("asks", []) or []
        if not bids_raw or not asks_raw:
            return 0.5

        bids = [(float(p), float(q)) for p, q in bids_raw]
        asks = [(float(p), float(q)) for p, q in asks_raw]

        band = entry * (band_bps / 10000.0)
        lo, hi = entry - band, entry + band

        def sum_qty(levels):
            return float(sum(q for p, q in levels if lo <= p <= hi))

        near_bid = sum_qty(bids)
        near_ask = sum_qty(asks)

        top_n = min(200, len(bids), len(asks))
        total_bid = float(sum(q for _, q in bids[:top_n]))
        total_ask = float(sum(q for _, q in asks[:top_n]))

        if direction == "long":
            raw_frac = near_ask / max(total_ask, 1e-9)
        else:
            raw_frac = near_bid / max(total_bid, 1e-9)

        score = 1.0 - np.exp(-raw_frac * 80.0)
        return _norm01(score)

    except Exception:
        return 0.5


# -----------------------------
# 4) Final entry/target score
# -----------------------------
def compute_entry_target_score(
    p_touch_entry: float,
    p_reach_target: float,
    entry_precision: float,
    target_precision: float,
    move_realism: float,
    liquidity: float,
) -> float:
    # Clamp inputs once
    p_touch_entry = _norm01(p_touch_entry)
    p_reach_target = _norm01(p_reach_target)
    entry_precision = _norm01(entry_precision)
    target_precision = _norm01(target_precision)
    move_realism = _norm01(move_realism)
    liquidity = _norm01(liquidity)

    # Weighted average (weights sum to 1)
    score = (
        0.35 * p_touch_entry +
        0.30 * p_reach_target +
        0.12 * entry_precision +
        0.06 * target_precision +
        0.12 * move_realism +
        0.05 * liquidity
    )
    return _norm01(score)



def score_entry_and_move(
    *,
    df_1h: pd.DataFrame,
    closes_1h: pd.Series,
    spot: float,
    atr_daily: float,
    entry_price: float,
    direction: str,
    horizon_hours: int,
    move_pct: float,
    binance_client=None,
    binance_symbol: str | None = None,
) -> dict:
    """
    Pre-trade validation:
    - entry feasibility (touch probability)
    - target feasibility (blended: from spot + from entry) âœ… NEW
    - entry/target precision (ATR+VWAP)
    - move realism (ATR% vs horizon)
    - liquidity near entry (Binance depth; neutral otherwise)
    """
    direction_n = _direction_norm(direction)
    horizon_hours = int(max(1, horizon_hours))

    vwap_24h = compute_vwap(df_1h, window=24)
    target = implied_target_price(entry_price, move_pct, direction_n)

    # --- Entry feasibility
    p_touch_entry = p_touch_bootstrap(
        closes_1h=closes_1h,
        entry_price=entry_price,
        horizon_hours=horizon_hours,
        direction=direction_n,
    )

    # --- Target feasibility (spot-based)
    p_reach_target_from_spot = p_reach_target_bootstrap(
        closes_1h=closes_1h,
        target_price=target if target is not None else np.nan,
        horizon_hours=horizon_hours,
        direction=direction_n,
        start_price=None,
    )

    # --- Target feasibility (entry-based, still NOT conditional)
    p_reach_target_from_entry = p_reach_target_bootstrap(
        closes_1h=closes_1h,
        target_price=target if target is not None else np.nan,
        horizon_hours=horizon_hours,
        direction=direction_n,
        start_price=entry_price,  # âœ… NEW
    )

    # âœ… Blended target feasibility
    p_reach_target = float(np.clip(
        0.60 * p_reach_target_from_spot + 0.40 * p_reach_target_from_entry,
        0.0, 1.0
    ))

    # --- Precision scores
    e_prec = entry_precision_score(
        spot=spot, entry=entry_price, atr=atr_daily, vwap=vwap_24h, direction=direction_n
    )

    t_prec = target_precision_score(
        entry=entry_price,
        target=target if target is not None else np.nan,
        atr=atr_daily,
        vwap=vwap_24h,
        direction=direction_n
    )


    # --- Move realism
    realism = move_realism_score(
        spot=spot, atr_daily=atr_daily, move_pct=move_pct, horizon_hours=horizon_hours
    )

    # --- Liquidity (crypto only)
    liq = 0.5
    if binance_client is not None and binance_symbol:
        liq = liquidity_score_binance(
            binance_client=binance_client,
            symbol=binance_symbol,
            entry=entry_price,
            direction=direction_n,
        )

    final = compute_entry_target_score(
        p_touch_entry=p_touch_entry,
        p_reach_target=p_reach_target,
        entry_precision=e_prec,
        target_precision=t_prec,
        move_realism=realism,
        liquidity=liq,
    )

    return {
        "spot": _safe_float(spot, np.nan),
        "atr_daily": _safe_float(atr_daily, np.nan),
        "vwap_24h": float(vwap_24h) if np.isfinite(vwap_24h) else None,
        "entry_price": _safe_float(entry_price, np.nan),
        "move_pct": abs(_safe_float(move_pct, np.nan)),
        "target_price": target,
        "direction_norm": direction_n,
        "horizon_hours": horizon_hours,

        "p_touch_entry": float(p_touch_entry),

        "p_reach_target_from_spot": float(p_reach_target_from_spot),
        "p_reach_target_from_entry": float(p_reach_target_from_entry),
        "p_reach_target": float(p_reach_target),

        "entry_precision_score": float(e_prec),
        "target_precision_score": float(t_prec),
        "move_realism_score": float(realism),
        "liquidity_score": float(liq),

        "final_entry_score": float(final),
    }
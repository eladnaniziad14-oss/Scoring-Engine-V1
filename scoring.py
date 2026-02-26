# scoring.py
from __future__ import annotations

import numpy as np

from fundamentals import get_fundamental_score
from technical_bias import get_technical_bias
from market_data import get_entry_inputs

from entry_quality import (
    score_entry_and_move,
    p_touch_bootstrap,
    compute_vwap,
    entry_precision_score,
    liquidity_score_binance,
    compute_entry_target_score,
)


def _normalize_direction(direction: str) -> str:
    d = (direction or "").strip().upper()
    if d in ("BUY", "LONG"):
        return "long"
    if d in ("SELL", "SHORT"):
        return "short"
    return "long"


def _safe_float(x, default=0.0) -> float:
    try:
        if x is None:
            return float(default)
        return float(x)
    except Exception:
        return float(default)


def _extract_score_and_breakdown(
    obj,
    score_key_candidates=("score", "final_score", "fundamental_score"),
):
    """
    Your fundamentals functions return dicts most of the time.
    This extracts a float score and keeps the dict as breakdown.
    """
    if isinstance(obj, dict):
        for k in score_key_candidates:
            if k in obj:
                return _safe_float(obj[k], 0.5), obj
        if "final" in obj:
            return _safe_float(obj["final"], 0.5), obj
        if "fundamental_score" in obj:
            return _safe_float(obj["fundamental_score"], 0.5), obj
        return 0.5, obj
    return _safe_float(obj, 0.5), None


def _momentum_alignment(direction: str, weighted_momentum: float) -> float:
    """
    Convert momentum alignment into 0..1:
    - if momentum ~ 0 -> 0.5 (neutral)
    - if aligned -> 0.5..1
    - if misaligned -> 0..0.5
    """
    wm = float(weighted_momentum)

    if abs(wm) < 1e-6:
        return 0.5

    strength = 1.0 - np.exp(-abs(wm) * 20.0)  # 0..1
    aligned = (direction == "long" and wm > 0) or (direction == "short" and wm < 0)

    return float(0.5 + 0.5 * strength) if aligned else float(0.5 - 0.5 * strength)


def _technical_alignment(direction: str, technical_bias: float) -> float:
    """
    technical_bias in [-1..1] -> alignment in [0..1]
    """
    b = float(np.clip(technical_bias, -1, 1))
    score = 0.5 + 0.5 * b if direction == "long" else 0.5 + 0.5 * (-b)
    return float(np.clip(score, 0, 1))


def score_prediction(pred: dict, binance_client=None, momentums: dict | None = None) -> dict:
    momentums = momentums or {}

    asset = pred.get("asset", "")
    direction_norm = _normalize_direction(pred.get("direction", "BUY"))
    user_confidence = _safe_float(pred.get("confidence", pred.get("user_confidence", 0.5)), 0.5)

    # -----------------------------
    # Technical Bias
    # -----------------------------
    tech = get_technical_bias(pred, binance_client=binance_client)
    technical_bias = _safe_float(tech.get("technical_bias", 0.0), 0.0)
    technical_alignment = _technical_alignment(direction_norm, technical_bias)

    # -----------------------------
    # Fundamentals
    # -----------------------------
    f = get_fundamental_score(pred)
    fundamental_score, fundamental_breakdown = _extract_score_and_breakdown(
        f, score_key_candidates=("score", "final_score", "fundamental_score", "fundamental_score")
    )
    fundamental_score = float(np.clip(fundamental_score, 0, 1))

    # -----------------------------
    # Momentum
    # -----------------------------
    weighted_momentum = _safe_float(momentums.get("weighted_momentum", 0.0), 0.0)
    momentum_alignment = _momentum_alignment(direction_norm, weighted_momentum)

    m = momentums.get("momentums", {}) or {}
    m5h = abs(_safe_float(m.get("momentum_5h", 0.0), 0.0))
    m10h = abs(_safe_float(m.get("momentum_10h", 0.0), 0.0))
    hourly_time_consistency = float(np.clip(0.6 * m5h + 0.4 * m10h, 0, 1))

    # -----------------------------
    # Base structural reliability
    # -----------------------------
    structural_reliability = (
        0.45 * momentum_alignment +
        0.35 * technical_alignment +
        0.15 * fundamental_score +
        0.05 * hourly_time_consistency
    )
    structural_reliability = float(np.clip(structural_reliability, 0, 1))

    # Base score BEFORE entry-quality
    confidence_reliability_score = float(np.clip(user_confidence * structural_reliability, 0, 1))

    # =========================================================
    # ENTRY QUALITY LAYER (entry only OR entry+move_pct)
    # =========================================================
    entry_price = _safe_float(pred.get("entry_price", None), np.nan)
    move_pct = _safe_float(pred.get("move_pct", None), np.nan)  # optional
    horizon_hours = int(pred.get("horizon_hours", 1))
    horizon_hours = max(1, min(horizon_hours, 24))

    entry_score = 0.5
    p_touch = 0.5
    precision = 0.5
    liquidity = 0.5
    entry_breakdown = None

    ctx = get_entry_inputs(pred, binance_client=binance_client)
    df_1h = ctx.get("df_1h")
    closes_1h = ctx.get("closes_1h")
    spot = ctx.get("spot")
    atr_d = _safe_float(ctx.get("atr_daily", 0.0), 0.0)
    binance_symbol = ctx.get("binance_symbol")

    have_market = (
        df_1h is not None and not getattr(df_1h, "empty", True) and
        closes_1h is not None and len(closes_1h) > 50 and
        np.isfinite(_safe_float(spot, np.nan))
    )
    have_entry = np.isfinite(entry_price)

    if have_market and have_entry:
        atr_safe = atr_d if atr_d > 0 else abs(float(spot)) * 0.01

        # If move_pct exists -> use full ENTRY+TARGET scoring
        if np.isfinite(move_pct):
            out = score_entry_and_move(
                df_1h=df_1h,
                closes_1h=closes_1h,
                spot=float(spot),
                atr_daily=atr_safe,
                entry_price=float(entry_price),
                direction=pred.get("direction", "BUY"),
                horizon_hours=horizon_hours,
                move_pct=float(move_pct),
                binance_client=binance_client,
                binance_symbol=binance_symbol,
            )
            entry_score = float(out.get("final_entry_score", 0.5))
            entry_breakdown = out

            p_touch = float(out.get("p_touch_entry", 0.5))
            precision = float(out.get("entry_precision_score", 0.5))
            liquidity = float(out.get("liquidity_score", 0.5))

        # Else -> entry-only scoring
        else:
            p_touch = p_touch_bootstrap(closes_1h, entry_price, horizon_hours, pred.get("direction", "BUY"))
            vwap_24h = compute_vwap(df_1h, window=24)
            precision = entry_precision_score(float(spot), float(entry_price), atr_safe, vwap_24h, pred.get("direction", "BUY"))

            liquidity = 0.5
            if binance_client is not None and binance_symbol is not None:
                liquidity = liquidity_score_binance(binance_client, binance_symbol, entry_price, pred.get("direction", "BUY"))

            entry_score = compute_entry_target_score(
                p_touch_entry=p_touch,
                p_reach_target=0.5,
                entry_precision=precision,
                target_precision=0.5,
                move_realism=0.5,
                liquidity=liquidity,
            )

    # ✅ Soft-adjust final score (entry quality enhances, but does NOT dominate)
    final_reliability_score = float(np.clip(confidence_reliability_score * (0.7 + 0.3 * entry_score), 0, 1))

    # Labels based on FINAL score
    if final_reliability_score < 0.4:
        reliability = "low"
    elif final_reliability_score < 0.7:
        reliability = "moderate"
    else:
        reliability = "high"

    return {
        "user_id": pred.get("user_id"),
        "submission_id": pred.get("submission_id"),
        "timestamp": pred.get("timestamp"),

        "asset": asset,
        "direction": pred.get("direction"),
        "user_confidence": user_confidence,

        "technical_bias": technical_bias,
        "technical_alignment": technical_alignment,

        "fundamental_score": fundamental_score,

        "weighted_momentum": weighted_momentum,
        "momentum_alignment": momentum_alignment,

        "hourly_time_consistency": hourly_time_consistency,
        "structural_reliability": structural_reliability,

        # base score (debug)
        "confidence_reliability_score": confidence_reliability_score,

        # entry layer
        "entry_price": float(entry_price) if np.isfinite(entry_price) else None,
        "move_pct": float(move_pct) if np.isfinite(move_pct) else None,
        "horizon_hours": horizon_hours,
        "p_touch": float(p_touch),
        "entry_precision_score": float(precision),
        "liquidity_score": float(liquidity),
        "entry_score": float(entry_score),

        # ✅ final score to rank by
        "final_reliability_score": final_reliability_score,

        "reliability": reliability,

        # debug payloads
        "fundamental_breakdown": fundamental_breakdown,
        "technical_breakdown": tech,
        "momentums": momentums.get("momentums", {}),
        "entry_breakdown": entry_breakdown,
    }
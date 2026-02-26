# data_loader.py
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any


# -----------------------------
# Helpers
# -----------------------------
def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_float(x: Any, default: float | None = None) -> float | None:
    try:
        if x is None:
            return default
        # allow strings like "0.4%" for move_pct
        if isinstance(x, str) and x.strip().endswith("%"):
            v = float(x.strip().replace("%", "")) / 100.0
            return v
        return float(x)
    except Exception:
        return default


def _safe_int(x: Any, default: int | None = None) -> int | None:
    try:
        if x is None:
            return default
        return int(float(x))
    except Exception:
        return default


def _normalize_asset(asset: str) -> str:
    """
    Normalize asset names to what your registry expects.
    - If crypto canonical like BTC/ETH/SOL -> BTCUSDT etc.
    - If already endswith USDT -> keep.
    - Keep Yahoo-style symbols like EURUSD=X, ^GSPC, GC=F, SI=F as-is.
    """
    a = (asset or "").strip().upper()
    if not a:
        return ""

    # keep Yahoo style / futures / indices
    if any(ch in a for ch in ("=", "^")) or a.endswith("=F"):
        return a

    # crypto canonical -> USDT
    if a in ("BTC", "ETH", "SOL"):
        return f"{a}USDT"
    if a.endswith("USDT"):
        return a

    # allow common forex canonical like EURUSD, GBPUSD, USDJPY
    # (your asset_registry should resolve these)
    return a


def _normalize_direction(direction: str) -> str:
    d = (direction or "").strip().upper()
    if d in ("BUY", "LONG"):
        return "BUY"
    if d in ("SELL", "SHORT"):
        return "SELL"
    return "BUY"


def _clamp01(x: float | None, default: float = 0.5) -> float:
    if x is None:
        return default
    if x < 0:
        return 0.0
    if x > 1:
        return 1.0
    return float(x)


def _normalize_move_pct(move_pct: Any) -> float | None:
    """
    Accept:
      - 0.004 (already decimal)
      - 0.4 or "0.4%" (treat as percent)
      - "0.004"
    Heuristic:
      if value > 0.2 -> assume percent and divide by 100
      (so 0.4 -> 0.004, 2 -> 0.02)
    """
    v = _safe_float(move_pct, default=None)
    if v is None:
        return None
    v = abs(v)

    # If someone passed "40" meaning 40%, convert
    if v > 1.0:
        return v / 100.0

    # Heuristic: 0.4 likely means 0.4% (0.004)
    if v > 0.2:
        return v / 100.0

    return v


def _normalize_prediction(p: dict) -> dict:
    """
    Output shape aligned with main/scoring:
    {
      user_id, submission_id, timestamp, asset, direction,
      confidence, horizon_hours, entry_price, move_pct
    }
    """
    user_id = p.get("user_id") or p.get("user") or p.get("uid")
    submission_id = p.get("submission_id") or p.get("id")

    ts = p.get("timestamp") or p.get("time") or _now_iso_utc()

    asset = _normalize_asset(p.get("asset", ""))
    direction = _normalize_direction(p.get("direction", "BUY"))

    # confidence field names you used in prior code
    conf = p.get("confidence", None)
    if conf is None:
        conf = p.get("user_confidence", None)
    confidence = _clamp01(_safe_float(conf, default=0.5), default=0.5)

    horizon_hours = _safe_int(p.get("horizon_hours", None), default=1)
    horizon_hours = max(1, min(int(horizon_hours or 1), 24))

    entry_price = _safe_float(p.get("entry_price", None), default=None)
    move_pct = _normalize_move_pct(p.get("move_pct", None))

    out = {
        "user_id": user_id,
        "submission_id": submission_id,
        "timestamp": ts,
        "asset": asset,
        "direction": direction,
        "confidence": confidence,
        "horizon_hours": horizon_hours,
    }

    # Optional fields
    if entry_price is not None:
        out["entry_price"] = float(entry_price)
    if move_pct is not None:
        out["move_pct"] = float(move_pct)

    return out


# -----------------------------
# Public API
# -----------------------------
def load_predictions_json(path: str | Path) -> list[dict]:
    """
    Load predictions from JSON file.

    Accepts:
    - A list of prediction objects
    - Or {"predictions": [...]} wrapper

    Returns: list of normalized prediction dicts.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Predictions file not found: {p.resolve()}")

    raw = json.loads(p.read_text(encoding="utf-8"))

    if isinstance(raw, dict) and "predictions" in raw:
        items = raw["predictions"]
    else:
        items = raw

    if not isinstance(items, list):
        raise ValueError("predictions.json must be a list or a dict with key 'predictions' (list).")

    normalized: list[dict] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        pred = _normalize_prediction(item)

        # minimal validation: must have asset + user_id
        if not pred.get("asset") or not pred.get("user_id"):
            # skip invalid rows
            continue

        # if submission_id missing, create a stable fallback
        if not pred.get("submission_id"):
            pred["submission_id"] = f"{pred['user_id']}-{i}"

        normalized.append(pred)

    return normalized
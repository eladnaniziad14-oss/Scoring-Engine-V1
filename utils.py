# utils.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_timestamp(ts: Any) -> datetime:
    """
    Parse user_input['timestamp'] into a timezone-aware UTC datetime.

    Accepts:
    - ISO strings: "2026-01-23T08:00:00Z" or with offset "+00:00"
    - datetime objects
    - None/empty => now UTC
    """
    if ts is None or ts == "":
        return datetime.now(timezone.utc)

    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)

    # assume string-like
    s = str(ts).strip()
    if not s:
        return datetime.now(timezone.utc)

    # common Z format
    s = s.replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        # last resort: try a couple common formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                continue

    # fallback
    return datetime.now(timezone.utc)


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return float(default)
        return float(x)
    except Exception:
        return float(default)


def clamp(x: float, lo: float, hi: float) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x
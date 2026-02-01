from __future__ import annotations

import logging
import os
from ast import literal_eval
from datetime import datetime
from typing import Dict, Iterable, List, Sequence

import pandas as pd

from llm_sentiment.sentiment.core.schema import SentimentSignal
from llm_sentiment.sentiment.core.composite_scorer import CompositeScorer
from llm_sentiment.sentiment.pipelines.micros.micros_sentiment import build_micros_sentiment


log = logging.getLogger(__name__)

ASSET_UNIVERSE: Sequence[str] = ("BTC", "ETH")


# ---------- Generic helpers ----------

def _load_df(base_path: str) -> pd.DataFrame | None:
    """
    Load a DataFrame from base_path.[parquet|csv] if present.
    Returns None if both are missing.
    """
    parquet = f"{base_path}.parquet"
    csv = f"{base_path}.csv"

    if os.path.exists(parquet):
        try:
            return pd.read_parquet(parquet)
        except Exception as e:
            log.warning("Failed to read %s: %s, falling back to CSV", parquet, e)

    if os.path.exists(csv):
        try:
            return pd.read_csv(csv)
        except Exception as e:
            log.error("Failed to read %s: %s", csv, e)
            return None

    log.info("No data found for base path %s", base_path)
    return None


def _parse_ts(ts: object) -> datetime:
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, (int, float)):
        # assume unix timestamp seconds
        return datetime.utcfromtimestamp(ts)
    if isinstance(ts, str) and ts:
        # try a few common formats
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d"):
            try:
                return datetime.strptime(ts[:26], fmt)
            except Exception:
                continue
    return datetime.utcnow()


def _latest_ts(values: Iterable[object]) -> datetime:
    parsed = [_parse_ts(v) for v in values if v is not None and v == v]  # v == v filters NaN
    return max(parsed) if parsed else datetime.utcnow()


def _extract_crypto_symbols(raw) -> List[str]:
    """
    Try to interpret the 'tickers' field from CMC / other APIs
    and return a list of uppercased symbols.

    Handles:
      - list / tuple
      - list[dict] with "symbol"/"code"/"ticker"/"currency"
      - CSV-like strings: "BTC,ETH"
      - stringified lists / dicts
    """
    import re

    if raw is None:
        return []

    # If already a list/tuple (e.g. from parquet)
    if isinstance(raw, (list, tuple)):
        out: List[str] = []
        for item in raw:
            if isinstance(item, str):
                out.append(item.upper())
            elif isinstance(item, dict):
                for key in ("symbol", "code", "ticker", "currency"):
                    if key in item:
                        out.append(str(item[key]).upper())
                        break
        return out

    # If it's a string representation of list/dict, try literal_eval
    if isinstance(raw, str):
        txt = raw.strip()
        if txt.startswith("[") or txt.startswith("{"):
            try:
                parsed = literal_eval(txt)
                return _extract_crypto_symbols(parsed)
            except Exception:
                # fall through and treat as plain string
                pass

        # Plain comma / space separated string
        tokens = re.split(r"[\\s,;/]+", txt)
        return [t.upper() for t in tokens if t]

    # Fallback – unknown type
    return []


# ---------- Per-pipeline → aggregated signals ----------

def _micros_signals():
    micros_df = build_micros_sentiment()

    if micros_df.empty:
        return []

    # Compute average per token symbol
    micros_scores = (
        micros_df.explode("tickers")
        .groupby("tickers")["sentiment_score"]
        .mean()
        .to_dict()
    )

    ts = datetime.utcnow()

    return [
        SentimentSignal(
            source="micros",
            symbol=symbol,
            timestamp=ts,
            score=float(score)
        )
        for symbol, score in micros_scores.items()
    ]


def _macros_signals() -> List[SentimentSignal]:
    """
    Uses data/macros/macros_sentiment.* produced by macros_sentiment.py

    Macro sentiment is treated as global crypto sentiment and
    applied equally to BTC and ETH.
    """
    df = _load_df("llm_sentiment/sentiment/data/macros/macros_sentiment")
    if df is None or df.empty:
        return []

    if "sentiment_score" not in df.columns:
        return []

    avg_score = float(df["sentiment_score"].astype(float).mean())
    ts = _latest_ts(df.get("timestamp", []))

    return [
        SentimentSignal(source="macros", symbol=sym, timestamp=ts, score=avg_score)
        for sym in ASSET_UNIVERSE
    ]


def _sector_signals() -> List[SentimentSignal]:
    """
    Uses data/sector/sector_sentiment.*.

    Currently no per-asset mapping → treated as
    broad crypto sector sentiment applied to both BTC and ETH.
    """
    df = _load_df("llm_sentiment/sentiment/data/sector/sector_sentiment")
    if df is None or df.empty:
        return []

    if "sentiment_score" not in df.columns:
        return []

    avg_score = float(df["sentiment_score"].astype(float).mean())
    ts = _latest_ts(df.get("timestamp", []))

    return [
        SentimentSignal(source="sector", symbol=sym, timestamp=ts, score=avg_score)
        for sym in ASSET_UNIVERSE
    ]


def _social_signals() -> List[SentimentSignal]:
    """
    Uses data/social/social_sentiment.*.

    Your current scraper doesn’t attach tickers, it’s global crypto social
    sentiment → apply equally to BTC and ETH.
    """
    df = _load_df("llm_sentiment/sentiment/data/social/social_sentiment")
    if df is None or df.empty:
        return []

    if "sentiment_score" not in df.columns:
        return []

    avg_score = float(df["sentiment_score"].astype(float).mean())
    ts = _latest_ts(df.get("timestamp", []))

    return [
        SentimentSignal(source="social", symbol=sym, timestamp=ts, score=avg_score)
        for sym in ASSET_UNIVERSE
    ]


def _volatility_signals() -> List[SentimentSignal]:
    """
    Uses data/volatility/volatility_sentiment.* produced by volatility_sentiment.py

    Expected columns:
      - source: "CVI" (global crypto vol) or "BTC_VOL"
      - sentiment_score: already mapped via normalize_sentiment() into [-1, 1]
      - timestamp
    """
    df = _load_df("llm_sentiment/sentiment/data/volatility/volatility_sentiment")
    if df is None or df.empty:
        return []

    if "sentiment_score" not in df.columns or "source" not in df.columns:
        return []

    df["sentiment_score"] = df["sentiment_score"].astype(float)

    signals: List[SentimentSignal] = []

    btc_rows = df[df["source"] == "BTC_VOL"]
    cvi_rows = df[df["source"] == "CVI"]

    # BTC: prefer dedicated BTC_VOL, otherwise fall back to CVI
    if not btc_rows.empty:
        btc_score = float(btc_rows["sentiment_score"].mean())
        ts = _latest_ts(btc_rows.get("timestamp", []))
        signals.append(
            SentimentSignal(
                source="volatility",
                symbol="BTC",
                timestamp=ts,
                score=btc_score,
            )
        )
    elif not cvi_rows.empty:
        btc_score = float(cvi_rows["sentiment_score"].mean())
        ts = _latest_ts(cvi_rows.get("timestamp", []))
        signals.append(
            SentimentSignal(
                source="volatility",
                symbol="BTC",
                timestamp=ts,
                score=btc_score,
            )
        )

    # ETH: use global crypto vol (CVI) if available
    if not cvi_rows.empty:
        eth_score = float(cvi_rows["sentiment_score"].mean())
        ts = _latest_ts(cvi_rows.get("timestamp", []))
        signals.append(
            SentimentSignal(
                source="volatility",
                symbol="ETH",
                timestamp=ts,
                score=eth_score,
            )
        )

    return signals


def _calendar_signals() -> List[SentimentSignal]:
    """
    Calendar: you currently fetch World Bank / OECD calendars but
    don’t derive a numeric sentiment index yet.

    This is a hook: once you build calendar_sentiment.py that outputs
    something like data/calendar/calendar_sentiment.*, you can:
      - load it here
      - aggregate
      - emit SentimentSignal(source="calendar", ...)
    """
    return []


# ---------- Orchestrator ----------

class SentimentOrchestrator:
    """
    High-level entry point:
      - loads per-pipeline sentiment outputs from disk
      - aggregates them to BTC / ETH
      - combines them using CompositeScorer + weights.yaml
    """

    def __init__(
        self,
        assets: Sequence[str] | None = None,
        weights_path: str = "llm_sentiment/sentiment/config/weights.yaml",
    ) -> None:
        self.assets: Sequence[str] = tuple(assets) if assets is not None else ASSET_UNIVERSE
        self.scorer = CompositeScorer(weights_path=weights_path)

    def collect_signals(self) -> List[SentimentSignal]:
        signals: List[SentimentSignal] = []
        signals.extend(_micros_signals())
        signals.extend(_macros_signals())
        signals.extend(_sector_signals())
        signals.extend(_social_signals())
        signals.extend(_volatility_signals())
        signals.extend(_calendar_signals())
        # Filter to configured asset universe in case any helper emitted extras
        return [s for s in signals if s.symbol in self.assets]

    def composite_scores(self) -> Dict[str, float]:
        signals = self.collect_signals()
        return self.scorer.score(signals)

    def debug_breakdown(self) -> Dict[str, Dict[str, float]]:
        """
        Returns per-symbol, per-source scores BEFORE weighting,
        useful to debug pipeline behaviour.
        """
        from collections import defaultdict

        signals = self.collect_signals()
        out: Dict[str, Dict[str, float]] = defaultdict(dict)
        for s in signals:
            out[s.symbol][s.source] = s.score
        return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    orch = SentimentOrchestrator()
    scores = orch.composite_scores()
    print("Composite scores:")
    for sym, val in scores.items():
        print(f"  {sym}: {val:.3f}")

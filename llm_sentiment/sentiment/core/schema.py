from dataclasses import dataclass
from datetime import datetime


@dataclass
class SentimentSignal:
    """
    One dimension-level sentiment score for a specific asset.

    Example: micros sentiment for BTC on a given timestamp.
    The `score` field is expected to be in [-1.0, 1.0].
    """
    source: str          # "micros", "macros", "sector", "volatility", "social", "calendar"
    symbol: str          # e.g. "BTC", "ETH"
    timestamp: datetime  # when this score is considered valid
    score: float         # already normalized to [-1, 1]

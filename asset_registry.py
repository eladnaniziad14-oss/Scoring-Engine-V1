# asset_registry.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


# -----------------------------
# Registry (edit freely)
# -----------------------------
ASSET_REGISTRY: Dict[str, Dict[str, Optional[str]]] = {
    # ----------------- Crypto (canonical in your system) -----------------
    "BTC": {
        "canonical": "BTC",
        "type": "crypto",
        "yahoo": "BTC-USD",
        "finnhub": "BINANCE:BTCUSDT",
        "fred": None,
    },
    "ETH": {
        "canonical": "ETH",
        "type": "crypto",
        "yahoo": "ETH-USD",
        "finnhub": "BINANCE:ETHUSDT",
        "fred": None,
    },
    "SOL": {
        "canonical": "SOL",
        "type": "crypto",
        "yahoo": "SOL-USD",
        "finnhub": "BINANCE:SOLUSDT",
        "fred": None,
    },

    # ----------------- Forex -----------------
    "EURUSD": {
        "canonical": "EURUSD",
        "type": "forex",
        "yahoo": "EURUSD=X",
        "finnhub": "OANDA:EUR_USD",
        "fred": "DEXUSEU",
    },
    "GBPUSD": {
        "canonical": "GBPUSD",
        "type": "forex",
        "yahoo": "GBPUSD=X",
        "finnhub": "OANDA:GBP_USD",
        "fred": "DEXUSUK",
    },
    "USDJPY": {
        "canonical": "USDJPY",
        "type": "forex",
        "yahoo": "USDJPY=X",
        "finnhub": "OANDA:USD_JPY",
        "fred": "DEXJPUS",
    },

    # ----------------- Metals / Commodities -----------------
    "XAUUSD": {
        "canonical": "XAUUSD",
        "type": "metal",
        "yahoo": "GC=F",              # Gold futures (most reliable free Yahoo symbol)
        "finnhub": "OANDA:XAU_USD",
        "fred": "GOLDAMGBD228NLBM",   # LBMA gold price series
    },
    "XAGUSD": {
        "canonical": "XAGUSD",
        "type": "metal",
        "yahoo": "SI=F",              # Silver futures
        "finnhub": "OANDA:XAG_USD",
        "fred": None,
    },

    # ----------------- Indices -----------------
    "SP500": {
        "canonical": "SP500",
        "type": "index",
        "yahoo": "^GSPC",
        "finnhub": "SPY",
        "fred": None,
    },
    "NASDAQ": {
        "canonical": "NASDAQ",
        "type": "index",
        "yahoo": "^IXIC",
        "finnhub": "QQQ",
        "fred": None,
    },
    "DAX": {
        "canonical": "DAX",
        "type": "index",
        "yahoo": "^GDAXI",
        "finnhub": "EXS1.DE",
        "fred": None,
    },
    "NIKKEI": {
        "canonical": "NIKKEI",
        "type": "index",
        "yahoo": "^N225",
        "finnhub": "EWJ",
        "fred": None,
    },

    # ----------------- Stocks (examples you tested) -----------------
    "AAPL": {"canonical": "AAPL", "type": "stock", "yahoo": "AAPL", "finnhub": "AAPL", "fred": None},
    "NVDA": {"canonical": "NVDA", "type": "stock", "yahoo": "NVDA", "finnhub": "NVDA", "fred": None},
    "TSLA": {"canonical": "TSLA", "type": "stock", "yahoo": "TSLA", "finnhub": "TSLA", "fred": None},
    "MSFT": {"canonical": "MSFT", "type": "stock", "yahoo": "MSFT", "finnhub": "MSFT", "fred": None},
    "AMZN": {"canonical": "AMZN", "type": "stock", "yahoo": "AMZN", "finnhub": "AMZN", "fred": None},
}


# -----------------------------
# Aliases / Normalization
# -----------------------------
ALIASES: Dict[str, str] = {
    # crypto symbol variants
    "BTCUSDT": "BTC",
    "ETHUSDT": "ETH",
    "SOLUSDT": "SOL",
    "BTC-USD": "BTC",
    "ETH-USD": "ETH",
    "SOL-USD": "SOL",

    # forex variants
    "EURUSD=X": "EURUSD",
    "GBPUSD=X": "GBPUSD",
    "USDJPY=X": "USDJPY",

    # indices variants
    "^GSPC": "SP500",
    "^SPX": "SP500",
    "^IXIC": "NASDAQ",
    "^GDAXI": "DAX",
    "^N225": "NIKKEI",

    # metals/commodities variants
    "GC=F": "XAUUSD",
    "XAU/USD": "XAUUSD",
    "XAU-USD": "XAUUSD",
    "SI=F": "XAGUSD",
    "XAG/USD": "XAGUSD",
    "XAG-USD": "XAGUSD",
}


def _clean(s: str) -> str:
    return (s or "").strip().upper().replace(" ", "")


def resolve_asset(user_input: dict) -> Tuple[str, Optional[dict]]:
    """
    Resolve user_input['asset'] into (canonical_key, asset_data).

    Examples accepted:
      - BTC, BTCUSDT, BTC-USD
      - EURUSD, EURUSD=X
      - XAUUSD, GC=F
      - SP500, ^GSPC
      - AAPL, NVDA, TSLA...
    """
    raw = user_input.get("asset") or user_input.get("symbol") or user_input.get("ticker") or ""
    a = _clean(raw)

    # Normalize separators
    a = a.replace("/", "").replace("-", "")

    # Try direct alias hits using original raw forms too
    raw_up = (raw or "").strip().upper()
    if raw_up in ALIASES:
        a_key = ALIASES[raw_up]
    elif a in ALIASES:
        a_key = ALIASES[a]
    else:
        a_key = a

    # Special: handle crypto inputs like BTCUSDT without needing aliases
    if a_key.endswith("USDT") and a_key not in ASSET_REGISTRY:
        base = a_key.replace("USDT", "")
        if base in ASSET_REGISTRY and ASSET_REGISTRY[base].get("type") == "crypto":
            a_key = base

    # Special: handle forex compact like EURUSD (already covered)
    if a_key in ASSET_REGISTRY:
        return a_key, ASSET_REGISTRY[a_key]

    # Special: if user passed a stock ticker not in registry, allow it as stock
    # (so your engine still runs without manual additions)
    if a_key.isalpha() and 1 <= len(a_key) <= 5:
        return a_key, {
            "canonical": a_key,
            "type": "stock",
            "yahoo": a_key,
            "finnhub": a_key,
            "fred": None,
        }

    return a_key, None
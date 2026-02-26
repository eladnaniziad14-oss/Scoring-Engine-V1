# fundamentals.py
# Hybrid fundamentals layer:
# - Sentiment: VADER default, FinBERT optional (ProsusAI/finbert)
# - Crypto: Fear&Greed + optional Polymarket (horizon-aware)
# - Non-crypto: FRED macro + news sentiment + analyst rec (stocks/ETFs) + econ calendar risk
#
# Output: fundamental_score in [0,1]
#
# NOTE: This module is for scoring/validation only (NOT portfolio sizing).

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional

import numpy as np
import requests
import yfinance as yf

from asset_registry import resolve_asset
from config import (
    FINNHUB_API_KEY,
    FRED_API_KEY,
    REQUEST_TIMEOUT_SECONDS,
    USE_FINBERT_WHEN_AVAILABLE,
    HF_TOKEN,  # optional
)

# -----------------------------
# Sentiment Engines (VADER + optional FinBERT)
# -----------------------------
_VADER_AVAILABLE = False
_FINBERT_AVAILABLE = False

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    _vader = SentimentIntensityAnalyzer()
    _VADER_AVAILABLE = True
except Exception:
    _vader = None

_finbert_pipe = None
if USE_FINBERT_WHEN_AVAILABLE:
    try:
        from transformers import pipeline

        pipe_kwargs = {}
        if HF_TOKEN:
            pipe_kwargs["token"] = HF_TOKEN

        _finbert_pipe = pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            **pipe_kwargs,
        )
        _FINBERT_AVAILABLE = True
    except Exception:
        _finbert_pipe = None
        _FINBERT_AVAILABLE = False


def sentiment_engine_status() -> Dict[str, Any]:
    return {
        "vader_available": _VADER_AVAILABLE,
        "finbert_available": _FINBERT_AVAILABLE,
        "active_default": "finbert"
        if (_FINBERT_AVAILABLE and USE_FINBERT_WHEN_AVAILABLE)
        else ("vader" if _VADER_AVAILABLE else "none"),
    }


def _sentiment_score_0_1(texts: List[str]) -> float:
    """
    Returns average sentiment in [0,1].
    - VADER: compound in [-1,1] => map to [0,1]
    - FinBERT: label {positive, neutral, negative} + score => map to [0,1]
    """
    texts = [t for t in texts if isinstance(t, str) and t.strip()]
    if not texts:
        return 0.5

    # Prefer FinBERT if enabled+available
    if _FINBERT_AVAILABLE and USE_FINBERT_WHEN_AVAILABLE and _finbert_pipe is not None:
        try:
            out = _finbert_pipe(texts[:10])  # keep small/fast
            vals = []
            for r in out:
                label = str(r.get("label", "")).lower()
                score = float(r.get("score", 0.0))
                if "pos" in label:
                    vals.append(0.5 + 0.5 * score)
                elif "neg" in label:
                    vals.append(0.5 - 0.5 * score)
                else:
                    vals.append(0.5)
            return float(np.clip(np.mean(vals), 0, 1))
        except Exception:
            pass  # fall back to VADER

    if _VADER_AVAILABLE and _vader is not None:
        vals = []
        for t in texts[:25]:
            c = float(_vader.polarity_scores(t).get("compound", 0.0))  # [-1,1]
            vals.append((c + 1.0) / 2.0)
        return float(np.clip(np.mean(vals), 0, 1))

    return 0.5


# -----------------------------
# HTTP Helpers
# -----------------------------
def _safe_get_json(url: str) -> Any:
    r = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso_date(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


def _is_stock_like_finnhub_symbol(symbol: Optional[str]) -> bool:
    if not symbol:
        return False
    if ":" in symbol:
        return False
    return True


def _extract_fx_currencies(canonical: str) -> Optional[List[str]]:
    if canonical and len(canonical) == 6 and canonical.isalpha():
        return [canonical[:3].upper(), canonical[3:].upper()]
    return None


# -----------------------------
# 1) Crypto Fear & Greed
# -----------------------------
@lru_cache(maxsize=4)
def get_crypto_fear_greed() -> float:
    try:
        data = _safe_get_json("https://api.alternative.me/fng/")
        value = int(data["data"][0]["value"])  # 0..100
        return float(np.clip(value / 100.0, 0, 1))
    except Exception:
        return 0.5


# -----------------------------
# 2) Polymarket Sentiment (best-effort)
# -----------------------------
@lru_cache(maxsize=64)
def get_polymarket_sentiment(keyword: str, limit: int = 10) -> float:
    """
    Public Polymarket Gamma endpoint.
    Returns mean YES probability of matched markets in [0,1].
    """
    try:
        url = "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=200"
        markets = _safe_get_json(url)

        key = (keyword or "").lower().replace("usdt", "").replace("-usd", "").strip()
        if not key:
            return 0.5

        probs: List[float] = []
        for m in markets:
            text = f"{m.get('question', '')} {m.get('slug', '')}".lower()
            if key not in text:
                continue

            yes_prob = None
            outcomes = m.get("outcomes") or []
            for o in outcomes:
                name = str(o.get("name", "")).lower()
                price = o.get("price", None)
                if name in ("yes", "true") and price is not None:
                    yes_prob = float(price)
                    break

            if yes_prob is None:
                for k in ("yesPrice", "yes_price", "lastTradePrice", "bestAsk"):
                    v = m.get(k, None)
                    if v is not None:
                        try:
                            yes_prob = float(v)
                            break
                        except Exception:
                            pass

            if yes_prob is not None:
                probs.append(float(np.clip(yes_prob, 0, 1)))

            if len(probs) >= limit:
                break

        return float(np.mean(probs)) if probs else 0.5
    except Exception:
        return 0.5


# -----------------------------
# 3) News Sentiment (Finnhub for stocks/ETFs; Yahoo fallback)
# -----------------------------
def get_news_sentiment(user_input: dict, limit: int = 8) -> float:
    canonical, asset_data = resolve_asset(user_input)
    if not asset_data:
        return 0.5

    finnhub_symbol = asset_data.get("finnhub")
    yahoo_symbol = asset_data.get("yahoo")

    # Finnhub company-news works best for stock tickers
    if _is_stock_like_finnhub_symbol(finnhub_symbol) and FINNHUB_API_KEY:
        try:
            to_dt = _now_utc()
            from_dt = to_dt - timedelta(days=7)
            url = (
                f"https://finnhub.io/api/v1/company-news?"
                f"symbol={finnhub_symbol}&from={_iso_date(from_dt)}&to={_iso_date(to_dt)}&token={FINNHUB_API_KEY}"
            )
            data = _safe_get_json(url) or []
            headlines = [a.get("headline", "") for a in data[:limit]]
            if headlines:
                return _sentiment_score_0_1(headlines)
        except Exception:
            pass

    # Yahoo fallback
    try:
        if not yahoo_symbol:
            return 0.5
        t = yf.Ticker(yahoo_symbol)
        news = getattr(t, "news", None) or []
        headlines = [n.get("title", "") for n in news[:limit]]
        return _sentiment_score_0_1(headlines)
    except Exception:
        return 0.5


# -----------------------------
# 4) Analyst Recommendation (stocks/ETFs only)
# -----------------------------
def get_analyst_sentiment(user_input: dict) -> float:
    canonical, asset_data = resolve_asset(user_input)
    if not asset_data or not FINNHUB_API_KEY:
        return 0.5

    finnhub_symbol = asset_data.get("finnhub")
    if not _is_stock_like_finnhub_symbol(finnhub_symbol):
        return 0.5

    url = f"https://finnhub.io/api/v1/stock/recommendation?symbol={finnhub_symbol}&token={FINNHUB_API_KEY}"
    try:
        data = _safe_get_json(url)
        if not data:
            return 0.5

        latest = data[0]
        buy = float(latest.get("buy", 0))
        sell = float(latest.get("sell", 0))
        hold = float(latest.get("hold", 0))

        total = buy + sell + hold
        if total <= 0:
            return 0.5

        score = (buy - sell) / total  # -1..+1
        return float((score + 1) / 2)  # 0..1
    except Exception:
        return 0.5


# -----------------------------
# 5) FRED Macro Impact (placeholder normalization)
# -----------------------------
@lru_cache(maxsize=256)
def _fred_latest_value(series_id: str) -> Optional[float]:
    if not FRED_API_KEY:
        return None
    try:
        url = (
            f"https://api.stlouisfed.org/fred/series/observations?"
            f"series_id={series_id}&api_key={FRED_API_KEY}&file_type=json"
        )
        r = _safe_get_json(url)
        obs = r.get("observations", [])
        if not obs:
            return None
        v = obs[-1].get("value", None)
        if v is None or v == ".":
            return None
        return float(v)
    except Exception:
        return None


def get_fred_impact(user_input: dict) -> float:
    canonical, asset_data = resolve_asset(user_input)
    if not asset_data:
        return 0.5

    series = asset_data.get("fred")
    if not series:
        return 0.5

    val = _fred_latest_value(series)
    if val is None:
        return 0.5

    # Placeholder squash. Replace later with per-series rolling z-scores.
    scaled = 0.5 + 0.25 * np.tanh((val - 0.0) / 1.0)
    return float(np.clip(scaled, 0, 1))


# -----------------------------
# 6) Economic Calendar Risk (instrument-aware, horizon-aware)
# -----------------------------
@lru_cache(maxsize=8)
def _finnhub_econ_calendar() -> Dict[str, Any]:
    if not FINNHUB_API_KEY:
        return {}
    url = f"https://finnhub.io/api/v1/calendar/economic?token={FINNHUB_API_KEY}"
    try:
        return _safe_get_json(url) or {}
    except Exception:
        return {}


def get_economic_event_risk(user_input: dict) -> float:
    """
    Returns risk scalar in 0..1.
    Higher => more high-impact events within horizon relevant to the instrument.
    """
    canonical, asset_data = resolve_asset(user_input)
    if not asset_data:
        return 0.5

    # Crypto: keep neutral for now
    if asset_data.get("type") == "crypto":
        return 0.5

    horizon_hours = int(user_input.get("horizon_hours", 1))
    horizon_hours = max(1, min(horizon_hours, 24))

    currencies = _extract_fx_currencies(canonical)
    if currencies is None:
        currencies = ["USD"]

    data = _finnhub_econ_calendar()
    events = data.get("economicCalendar", []) or []
    if not events:
        return 0.5

    now = _now_utc()
    cutoff = now + timedelta(hours=horizon_hours)

    relevant_high = 0
    for e in events:
        impact = (e.get("impact") or "").lower()
        currency = (e.get("currency") or "").upper()
        date_str = e.get("date")  # "YYYY-MM-DD HH:MM:SS"
        if not date_str:
            continue

        try:
            event_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:
            continue

        if not (now <= event_dt <= cutoff):
            continue
        if currency not in currencies:
            continue
        if impact == "high":
            relevant_high += 1

    if relevant_high == 0:
        return 0.5

    return float(np.clip(0.65 + 0.10 * relevant_high, 0.65, 0.90))


# -----------------------------
# 7) Unified Fundamental Score
# -----------------------------
def get_fundamental_score(user_input: dict) -> Dict[str, Any]:
    """
    Returns:
    {
      "fundamental_score": float in [0,1],
      "breakdown": {...}
    }
    """
    canonical, asset_data = resolve_asset(user_input)
    if not asset_data:
        return {"fundamental_score": 0.5, "breakdown": {"reason": "unresolved_asset"}}

    asset_type = asset_data.get("type", "other")
    horizon_hours = int(user_input.get("horizon_hours", 1))

    # ---- CRYPTO fundamentals
    if asset_type == "crypto":
        fng = get_crypto_fear_greed()
        poly = get_polymarket_sentiment(asset_data.get("canonical", canonical))

        if horizon_hours <= 2:
            w_fng, w_poly = 0.85, 0.15
        elif horizon_hours <= 6:
            w_fng, w_poly = 0.70, 0.30
        else:
            w_fng, w_poly = 0.65, 0.35

        score = float(np.clip(w_fng * fng + w_poly * poly, 0, 1))
        return {
            "fundamental_score": score,
            "breakdown": {
                "asset_type": "crypto",
                "fear_greed": fng,
                "polymarket": poly,
                "weights": {"fng": w_fng, "poly": w_poly},
            },
        }

    # ---- NON-CRYPTO fundamentals
    macro = get_fred_impact(user_input)
    news = get_news_sentiment(user_input)
    analyst = get_analyst_sentiment(user_input)
    event_risk = get_economic_event_risk(user_input)

    # Convert risk -> support (higher risk lowers score)
    event_support = 1.0 - (event_risk - 0.5) * 1.2
    event_support = float(np.clip(event_support, 0, 1))

    w_macro = 0.30
    w_news = 0.35
    w_analyst = 0.20
    w_event = 0.15

    score = float(
        np.clip(
            w_macro * macro
            + w_news * news
            + w_analyst * analyst
            + w_event * event_support,
            0,
            1,
        )
    )

    return {
        "fundamental_score": score,
        "breakdown": {
            "asset_type": asset_type,
            "macro": macro,
            "news": news,
            "analyst": analyst,
            "event_risk": event_risk,
            "event_support": event_support,
            "weights": {
                "macro": w_macro,
                "news": w_news,
                "analyst": w_analyst,
                "event_support": w_event,
            },
            "sentiment_engine": sentiment_engine_status(),
        },
    }
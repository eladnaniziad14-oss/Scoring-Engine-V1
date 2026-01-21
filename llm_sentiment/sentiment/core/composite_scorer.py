from pathlib import Path
from typing import Dict, List
from collections import defaultdict
import numpy as np
import yaml

from llm_sentiment.sentiment.core.schema import SentimentSignal


class CompositeScorer:
    """
    Combines per-dimension sentiment scores into a single composite score
    per asset, using weights from a YAML config.

    Expects weights.yaml like:

    weights:
      micros: 0.40
      macros: 0.25
      sector: 0.20
      volatility: 0.15
      social: 0.10
      calendar: 0.05
    """

    def __init__(self, weights_path: str = "llm_sentiment/sentiment/config/weights.yaml") -> None:
        path = Path(weights_path)
        if not path.exists():
            raise FileNotFoundError(f"Weights config not found at {path}")

        with path.open("r") as fh:
            data = yaml.safe_load(fh) or {}

        weights = data.get("weights", {})
        if not isinstance(weights, dict) or not weights:
            raise ValueError("weights.yaml must contain a 'weights' mapping")

        # Ensure all weights are non-negative floats
        clean_weights: Dict[str, float] = {}
        for k, v in weights.items():
            try:
                v_float = float(v)
            except Exception:
                continue
            if v_float < 0:
                continue
            clean_weights[str(k)] = v_float

        if not clean_weights:
            raise ValueError("No valid non-negative weights found in weights.yaml")

        self.weights: Dict[str, float] = clean_weights

    def score(self, signals: List[SentimentSignal]) -> Dict[str, Dict[str, float | str]]:
        """
        Return per-symbol composite sentiment with:
        - sentiment_score in [-1, 1]
        - confidence in [0, 1]
        - regime classification
        """
        # Group signals by symbol & source
        grouped = defaultdict(lambda: defaultdict(list))
        for sig in signals:
            grouped[sig.symbol][sig.source].append(sig.score)

        results: Dict[str, Dict[str, float | str]] = {}

        for symbol, source_map in grouped.items():
            weighted_sum = 0.0
            confidence_sum = 0.0
            total_weight = sum(self.weights.values())

            for source, scores in source_map.items():
                if source not in self.weights:
                    continue

                weight = self.weights[source]
                avg = float(np.mean(scores))

                # Confidence: more data points = stronger conviction (capped at 1)
                confidence = min(len(scores) / 10.0, 1.0)

                weighted_sum += avg * weight * confidence
                confidence_sum += weight * confidence

            if confidence_sum == 0:
                results[symbol] = {
                    "sentiment_score": 0.0,
                    "confidence": 0.0,
                    "regime": "unknown"
                }
                continue

            # Compute normalized score
            sentiment_score = weighted_sum / confidence_sum
            sentiment_score = max(-1.0, min(1.0, sentiment_score))  # clip

            confidence = confidence_sum / total_weight
            confidence = max(0.0, min(1.0, confidence))

            # --------------- REGIME DETECTION 🚦 ---------------
            if "volatility" in source_map:
                vol_avg = float(np.mean(source_map["volatility"]))
                if vol_avg > 0.20:
                    regime = "risk_on"
                elif vol_avg < -0.20:
                    regime = "risk_off"
                else:
                    regime = "neutral"
            else:
                regime = "unknown"

            results[symbol] = {
                "sentiment_score": round(sentiment_score, 4),
                "confidence": round(confidence, 4),
                "regime": regime
            }

        return results


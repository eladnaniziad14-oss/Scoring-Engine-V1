import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pandas as pd
import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

log = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
SOCIAL_DIR = ROOT_DIR / "data" / "social"
SOCIAL_DIR.mkdir(parents=True, exist_ok=True)
OUT_PARQUET = SOCIAL_DIR / "social_sentiment.parquet"
OUT_CSV = SOCIAL_DIR / "social_sentiment.csv"

REDDIT_SUBS = ["Bitcoin", "Ethereum", "CryptoCurrency"]


def fetch_reddit_posts(subreddit: str, limit: int = 50) -> List[str]:
    """
    Fetch posts from Reddit via PullPush API (Pushshift replacement).
    Much more reliable than Reddit public JSON for server environments.
    """
    url = f"https://api.pullpush.io/reddit/search/submission/?subreddit={subreddit}&size={limit}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning("PullPush failed for /r/%s: %s", subreddit, e)
        return []

    out = []
    for post in data.get("data", []):
        title = post.get("title") or ""
        text = post.get("selftext") or ""
        combined = (title + " " + text).strip()
        if combined:
            out.append(combined)

    return out



def fetch_fear_greed_score() -> float:
    """
    Fetch the Crypto Fear & Greed index (0–100) and map to [-1, 1]:
      0 → -1 (extreme fear)
     50 →  0 (neutral)
    100 → +1 (extreme greed)
    """
    url = "https://api.alternative.me/fng/"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        value_str = data["data"][0]["value"]
        value = float(value_str)
    except Exception as e:
        log.warning("Failed to fetch Fear & Greed index: %s", e)
        return 0.0

    score = (value - 50.0) / 50.0
    return max(-1.0, min(1.0, score))


def sentiment_from_texts(texts: List[str], analyzer: SentimentIntensityAnalyzer) -> float:
    """Average VADER compound score across a list of texts."""
    scores = []
    for t in texts:
        t = t.strip()
        if not t:
            continue
        res = analyzer.polarity_scores(t)
        scores.append(res["compound"])
    if not scores:
        return 0.0
    return float(sum(scores) / len(scores))


def build_social_sentiment() -> pd.DataFrame:
    """Compute a single global crypto social sentiment score and save it."""
    logging.basicConfig(level=logging.INFO)
    analyzer = SentimentIntensityAnalyzer()

    all_texts: List[str] = []
    for sub in REDDIT_SUBS:
        posts = fetch_reddit_posts(sub, limit=50)
        log.info("Fetched %d posts from /r/%s", len(posts), sub)
        all_texts.extend(posts)

    reddit_score = sentiment_from_texts(all_texts, analyzer)
    fng_score = fetch_fear_greed_score()

    # Simple blend: heavier weight on Reddit, smaller on F&G
    combined = 0.7 * reddit_score + 0.3 * fng_score

    now = datetime.now(timezone.utc).isoformat()

    df = pd.DataFrame(
        [
            {
                "timestamp": now,
                "sentiment_score": combined,
                "source": "reddit+fear_greed",
            }
        ]
    )

    df.to_parquet(OUT_PARQUET, index=False)
    df.to_csv(OUT_CSV, index=False)

    log.info("Saved social sentiment to %s and %s", OUT_PARQUET, OUT_CSV)
    return df


if __name__ == "__main__":
    build_social_sentiment()

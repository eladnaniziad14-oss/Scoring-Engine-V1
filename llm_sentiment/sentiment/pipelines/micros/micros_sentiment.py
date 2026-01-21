import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

log = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
MICROS_DIR = ROOT_DIR / "data" / "micros"
MICROS_DIR.mkdir(parents=True, exist_ok=True)

RAW_PATH = MICROS_DIR / "micros_raw.csv"
OUT_PARQUET = MICROS_DIR / "micros_sentiment.parquet"
OUT_CSV = MICROS_DIR / "micros_sentiment.csv"

TOKEN_MAP = {
    "BITCOIN": "BTC",
    "BTC": "BTC",
    "XBT": "BTC",
    "ETHEREUM": "ETH",
    "ETH": "ETH",
    "ETHER": "ETH",
}


def detect_tickers(text: str):
    text = text.upper()
    tokens = re.split(r"[^\w]+", text)
    return list({TOKEN_MAP[t] for t in tokens if t in TOKEN_MAP})


def build_micros_sentiment():
    logging.basicConfig(level=logging.INFO)
    analyzer = SentimentIntensityAnalyzer()

    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Raw micros file missing: {RAW_PATH}")

    df = pd.read_csv(RAW_PATH)

    # Extract text for sentiment
    title = df["title"].fillna("") if "title" in df.columns else ""
    summary = df["summary"].fillna("") if "summary" in df.columns else ""
    combined_text = (title + " " + summary).astype(str)

    # Compute sentiment
    df["raw_text"] = combined_text
    df["sentiment_score"] = df["raw_text"].apply(
        lambda t: analyzer.polarity_scores(t)["compound"]
    )

    # Extract tickers based on text
    df["tickers"] = df["raw_text"].apply(detect_tickers)
    df = df[df["tickers"].map(len) > 0]

    if df.empty:
        log.warning("No Bitcoin/Ethereum mentions found.")
        return pd.DataFrame()

    # Use existing timestamp if found
    if "timestamp" not in df.columns:
        df["timestamp"] = datetime.now(timezone.utc).isoformat()

    out = df[["timestamp", "tickers", "sentiment_score"]].reset_index(drop=True)

    out.to_parquet(OUT_PARQUET, index=False)
    out.to_csv(OUT_CSV, index=False)

    log.info(f"✔ Saved {len(out)} micros sentiment rows → {OUT_PARQUET}")
    return out


if __name__ == "__main__":
    build_micros_sentiment()

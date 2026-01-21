import logging
from datetime import datetime
from pipelines.volatility.volatility_sentiment import build_volatility_sentiment
from ingestion.clickhouse_ingest import ingest_to_clickhouse

log = logging.getLogger(__name__)

def run():
    try:
        df = build_volatility_sentiment()
        if df.empty:
            log.warning("Volatility sentiment returned empty DF")
            return

        ingest_to_clickhouse(
            df=df,
            table="volatility_sentiment",
            timestamp_field="timestamp",
        )
        log.info(f"[{datetime.utcnow()}] Volatility pipeline executed OK. Rows: {len(df)}")

    except Exception as e:
        log.exception(f"[{datetime.utcnow()}] Volatility pipeline failed: {e}")

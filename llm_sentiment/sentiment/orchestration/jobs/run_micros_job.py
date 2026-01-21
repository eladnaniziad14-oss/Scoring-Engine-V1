import logging
from datetime import datetime
from pipelines.micros.micros_sentiment import build_micros_sentiment
from ingestion.clickhouse_ingest import ingest_to_clickhouse

log = logging.getLogger(__name__)

def run():
    try:
        df = build_micros_sentiment()
        if df.empty:
            log.warning("Micros sentiment returned empty DF")
            return

        ingest_to_clickhouse(
            df=df,
            table="micros_sentiment",
            timestamp_field="timestamp",
        )
        log.info(f"[{datetime.utcnow()}] Micros pipeline executed OK. Rows: {len(df)}")

    except Exception as e:
        log.exception(f"[{datetime.utcnow()}] Micros pipeline failed: {e}")

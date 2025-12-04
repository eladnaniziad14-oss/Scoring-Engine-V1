import logging
from datetime import datetime
from pipelines.macros.macros_sentiment import build_macros_sentiment
from ingestion.clickhouse_ingest import ingest_to_clickhouse

log = logging.getLogger(__name__)

def run():
    try:
        df = build_macros_sentiment()
        if df.empty:
            log.warning("Macros sentiment returned empty DF")
            return

        ingest_to_clickhouse(
            df=df,
            table="macros_sentiment",
            timestamp_field="timestamp",
        )
        log.info(f"[{datetime.utcnow()}] Macros pipeline executed OK. Rows: {len(df)}")

    except Exception as e:
        log.exception(f"[{datetime.utcnow()}] Macros pipeline failed: {e}")

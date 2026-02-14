import logging
from datetime import datetime
from pipelines.sector.sector_sentiment import build_sector_sentiment
from ingestion.clickhouse_ingest import ingest_to_clickhouse

log = logging.getLogger(__name__)

def run():
    try:
        df = build_sector_sentiment()
        if df.empty:
            log.warning("Sector sentiment returned empty DF")
            return

        ingest_to_clickhouse(
            df=df,
            table="sector_sentiment",
            timestamp_field="timestamp",
        )
        log.info(f"[{datetime.utcnow()}] Sector pipeline executed OK. Rows: {len(df)}")

    except Exception as e:
        log.exception(f"[{datetime.utcnow()}] Sector pipeline failed: {e}")

import logging
from datetime import datetime
# TODO: implement calendar_sentiment builder
from ingestion.clickhouse_ingest import ingest_to_clickhouse

log = logging.getLogger(__name__)

def run():
    try:
        log.info("Calendar pipeline not implemented yet — skipping.")
    except Exception as e:
        log.exception(f"[{datetime.utcnow()}] Calendar pipeline failed: {e}")

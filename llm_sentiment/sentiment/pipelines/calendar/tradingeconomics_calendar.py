import pandas as pd
from datetime import datetime
from utils.save_utils import save_csv_parquet
from utils.https_client import https_get, safe_json
from utils.logger import get_logger

logger=get_logger("calendar")

def fetch_tradingeconomics_calendar():
    url="https://api.tradingeconomics.com/calendar?client=guest:guest"
    resp=https_get(url, timeout=20)
    data=safe_json(resp)
    if not data:
        logger.error("TradingEconomics calendar failed")
        return None
    events=[]
    try:
        for e in data[:500]:
            events.append({
                "country": e.get("Country"),
                "category": e.get("Category"),
                "impact": e.get("Impact"),
                "date": e.get("Date"),
                "actual": e.get("Actual"),
                "forecast": e.get("Forecast"),
                "previous": e.get("Previous"),
                "timestamp": datetime.utcnow().isoformat()
            })
    except Exception:
        logger.exception("parse error")
    df=pd.DataFrame(events)
    save_csv_parquet(df, "data/calendar/tradingeconomics_releases")
    logger.info(f"Saved {len(df)} tradingeconomics events")
    return df

if __name__=='__main__':
    fetch_tradingeconomics_calendar()

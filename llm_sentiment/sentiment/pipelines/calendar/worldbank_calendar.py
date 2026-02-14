import pandas as pd
from datetime import datetime
from utils.save_utils import save_csv_parquet
from utils.https_client import https_get, safe_json
from utils.logger import get_logger

logger=get_logger("calendar")

def fetch_world_bank_calendar():
    url="https://api.worldbank.org/v2/indicator?format=json&per_page=2000"
    resp=https_get(url, timeout=20)
    data=safe_json(resp)
    if not data or len(data)<2:
        logger.error("Worldbank data fail")
        return None
    entries=[]
    for item in data[1]:
        entries.append({
            "indicator_id": item.get("id"),
            "name": item.get("name"),
            "unit": item.get("unit",""),
            "timestamp": datetime.utcnow().isoformat()
        })
    df=pd.DataFrame(entries)
    save_csv_parquet(df, "data/calendar/worldbank_releases")
    logger.info(f"Saved {len(df)} worldbank entries")
    return df

if __name__=='__main__':
    fetch_world_bank_calendar()

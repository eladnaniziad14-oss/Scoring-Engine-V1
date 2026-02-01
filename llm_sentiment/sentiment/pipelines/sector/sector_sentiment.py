import pandas as pd
from utils.transformers import compute_sentiment
from utils.save_utils import save_csv_parquet
from utils.logger import get_logger
logger=get_logger("sector")

def generate_sector_sentiment():
    try:
        df=pd.read_csv("data/sector/sector_raw.csv")
    except Exception:
        logger.error("sector_raw.csv missing")
        return
    out=[]
    for _,r in df.iterrows():
        text=f"{r.get('title','')} {r.get('summary','')}"
        score=compute_sentiment(text)
        out.append({
            "source": r.get("source"),
            "title": r.get("title"),
            "summary": r.get("summary"),
            "url": r.get("url"),
            "published_at": r.get("published_at"),
            "sector": r.get("sector"),
            "sentiment_score": score,
            "timestamp": r.get("timestamp")
        })
    res=pd.DataFrame(out)
    save_csv_parquet(res, "data/sector/sector_sentiment")
    logger.info(f"Saved {len(res)} sector sentiment rows")
    return res

if __name__=='__main__':
    generate_sector_sentiment()

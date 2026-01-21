import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from utils.save_utils import save_csv_parquet
from utils.https_client import https_get
from utils.logger import get_logger

logger=get_logger("macros")
HEADERS={'User-Agent':'Mozilla/5.0'}

def fetch_rss(url, limit=100):
    resp = https_get(url, headers=HEADERS, timeout=15)
    if not resp:
        return []
    try:
        soup=BeautifulSoup(resp.text,'xml')
        items=soup.find_all("item")[:limit]
        out=[]
        for it in items:
            out.append({
                "source": url,
                "title": it.title.text if it.title else "",
                "summary": it.description.text if it.description else "",
                "url": it.link.text if it.link else "",
                "published_at": it.pubDate.text if it.pubDate else "",
                "timestamp": datetime.utcnow().isoformat()
            })
        return out
    except Exception:
        logger.exception("rss parse failed")
        return []

def fetch_all_macros():
    from utils.config_loader import load_sources
    cfg=load_sources().get("macros",{})
    arts=[]
    for k,v in cfg.items():
        if not v.get("enabled",False): continue
        url=v.get("endpoint")
        try:
            if 'tradingeconomics' in url:
                resp=https_get(url, timeout=15)
                if resp:
                    try:
                        data=resp.json()
                        for item in data[:50]:
                            arts.append({
                                "source":"tradingeconomics",
                                "title": str(item)[:120],
                                "summary":"",
                                "url":"",
                                "published_at":"",
                                "timestamp": datetime.utcnow().isoformat()
                            })
                    except Exception:
                        logger.exception("tradingeconomics parse")
            else:
                arts += fetch_rss(url)
        except Exception:
            logger.exception(f"failed {k}")
    df=pd.DataFrame(arts)
    save_csv_parquet(df, "data/macros/macro_raw")
    logger.info(f"Saved {len(df)} macro articles")
    return df

if __name__=='__main__':
    fetch_all_macros()

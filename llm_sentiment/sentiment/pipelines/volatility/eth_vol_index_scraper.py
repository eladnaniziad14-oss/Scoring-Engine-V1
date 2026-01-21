import pandas as pd
from datetime import datetime
from utils.save_utils import save_csv_parquet
from utils.https_client import https_get, safe_json
from utils.logger import get_logger

logger=get_logger("volatility")

def fetch_eth_vol():
    url = "https://api.coingecko.com/api/v3/coins/ethereum/market_chart?vs_currency=usd&days=30"
    resp = https_get(url, timeout=15)
    data = safe_json(resp)
    if not data:
        logger.error("CoinGecko ETH data failed")
        return None
    prices = [p[1] for p in data.get("prices",[])]
    if len(prices)<2:
        logger.error("Not enough prices")
        return None
    import pandas as pd
    dfp=pd.DataFrame({"price":prices})
    dfp["ret"]=dfp["price"].pct_change()
    vol = dfp["ret"].std()*(365**0.5)
    out=pd.DataFrame([{"index":vol,"source":"ETH_VOL","timestamp":datetime.utcnow().isoformat()}])
    save_csv_parquet(out, "data/volatility/eth_vol")
    logger.info("Saved ETH volatility")
    return out

if __name__=='__main__':
    fetch_eth_vol()

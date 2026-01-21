import pandas as pd
from utils.save_utils import save_csv_parquet
from utils.sentiment_scaler import vol_to_sentiment
from utils.logger import get_logger

logger=get_logger("volatility")

def generate_volatility_sentiment():
    records=[]
    try:
        btc=pd.read_csv("data/volatility/btc_vol.csv")
    except Exception:
        btc=None
    try:
        eth=pd.read_csv("data/volatility/eth_vol.csv")
    except Exception:
        eth=None
    if btc is not None:
        for _,r in btc.iterrows():
            records.append({"source":"BTC_VOL","index_value":r.get("index"), "sentiment_score": vol_to_sentiment(r.get("index")), "timestamp": r.get("timestamp")})
    if eth is not None:
        for _,r in eth.iterrows():
            records.append({"source":"ETH_VOL","index_value":r.get("index"), "sentiment_score": vol_to_sentiment(r.get("index")), "timestamp": r.get("timestamp")})
    if btc is not None and eth is not None:
        try:
            bval=btc.iloc[-1].get("index")
            eval=eth.iloc[-1].get("index")
            scvi = 0.5*(bval+eval)
            records.append({"source":"SCVI","index_value":scvi,"sentiment_score":vol_to_sentiment(scvi),"timestamp": pd.Timestamp.now().isoformat()})
        except Exception:
            pass
    if records:
        df=pd.DataFrame(records)
        save_csv_parquet(df, "data/volatility/volatility_sentiment")
        logger.info(f"Saved {len(df)} volatility sentiment rows")
        return df
    logger.info("No volatility records")
    return None

if __name__=='__main__':
    generate_volatility_sentiment()

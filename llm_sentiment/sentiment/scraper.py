import traceback
from pipelines.calendar.worldbank_calendar import fetch_world_bank_calendar
from pipelines.calendar.tradingeconomics_calendar import fetch_tradingeconomics_calendar
from pipelines.macros.macros_scraper import fetch_all_macros
from pipelines.macros.macros_sentiment import generate_macro_sentiment
from pipelines.micros.micros_scraper import fetch_all_micros
from pipelines.micros.micros_sentiment import build_micros_sentiment
from pipelines.sector.sector_scraper import fetch_all_sector_news
from pipelines.sector.sector_sentiment import generate_sector_sentiment
from pipelines.social.social_scraper import fetch_all_social
from pipelines.social.social_sentiment import generate_social_sentiment
from pipelines.volatility.btc_vol_index_scraper import fetch_btc_vol
from pipelines.volatility.eth_vol_index_scraper import fetch_eth_vol
from pipelines.volatility.volatility_sentiment import generate_volatility_sentiment
from pipelines.volatility.cvi_scraper import fetch_cvi_index

steps = [
    ("World Bank Calendar", fetch_world_bank_calendar),
    ("TradingEconomics Calendar", fetch_tradingeconomics_calendar),
    ("Macro Scraper", fetch_all_macros),
    ("Macro Sentiment", generate_macro_sentiment),
    ("Micro Scraper", fetch_all_micros),
    ("Micro Sentiment", build_micros_sentiment),
    ("Sector Scraper", fetch_all_sector_news),
    ("Sector Sentiment", generate_sector_sentiment),
    ("Social Scraper", fetch_all_social),
    ("Social Sentiment", generate_social_sentiment),
    ("BTC Vol Scraper", fetch_btc_vol),
    ("ETH Vol Scraper", fetch_eth_vol),
    ("Volatility Sentiment", generate_volatility_sentiment),
    ("Synthetic CVI Placeholder", fetch_cvi_index)
]

def run_step(name, fn):
    print(f"=== {name} ===")
    try:
        fn()
        print(f"✓ {name} OK\n")
    except Exception as e:
        print(f"⚠ {name} failed but continuing: {e}\n")
        traceback.print_exc()

def run_all():
    for name, fn in steps:
        run_step(name, fn)

if __name__=='__main__':
    run_all()

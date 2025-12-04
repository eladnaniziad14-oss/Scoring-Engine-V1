from utils.logger import get_logger
logger=get_logger("social")
def fetch_all_social():
    logger.info("Social scraping disabled on this deployment (sources blocked).")
    return []
if __name__=='__main__':
    fetch_all_social()

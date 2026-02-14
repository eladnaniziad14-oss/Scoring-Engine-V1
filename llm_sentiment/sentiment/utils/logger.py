import logging, os
def get_logger(name):
    os.makedirs("logs", exist_ok=True)
    logger=logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh=logging.FileHandler(f"logs/{name}.log")
        formatter=logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger

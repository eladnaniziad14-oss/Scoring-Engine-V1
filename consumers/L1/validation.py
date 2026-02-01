import time

def validate_l1(data: dict) -> bool:
    required = [
        "symbol",
        "timestamp_utc_micros",
        "best_bid_price",
        "best_ask_price"
    ]

    for f in required:
        if f not in data:
            return False

    bid = float(data["best_bid_price"])
    ask = float(data["best_ask_price"])

    if bid <= 0 or ask <= 0 or bid >= ask:
        return False

    now = time.time()
    msg_time = data["timestamp_utc_micros"] / 1_000_000

    return abs(now - msg_time) <= 300

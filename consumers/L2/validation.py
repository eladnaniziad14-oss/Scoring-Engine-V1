import time

def validate_l2(data: dict) -> bool:
    """
    Validation des données Market Data Level 2
    """

    # 1️⃣ Champs obligatoires
    required_fields = [
        "symbol",
        "timestamp_utc_micros",
        "bids",
        "asks",
        "exchange"
    ]

    for field in required_fields:
        if field not in data:
            return False

    # 2️⃣ Validation du timestamp (± 5 minutes)
    now_sec = time.time()
    msg_time_sec = data["timestamp_utc_micros"] / 1_000_000

    if abs(now_sec - msg_time_sec) > 300:
        return False

    # 3️⃣ Validation des niveaux de carnet
    def valid_levels(levels):
        valid_count = 0
        for level in levels:
            try:
                price, qty = level
                if float(price) > 0 and float(qty) > 0:
                    valid_count += 1
            except Exception:
                continue
        return valid_count > 0

    if not valid_levels(data["bids"]):
        return False

    if not valid_levels(data["asks"]):
        return False

    return True

def compute_l1_metrics(data: dict) -> dict:
    bid = float(data["best_bid_price"])
    ask = float(data["best_ask_price"])

    mid = (bid + ask) / 2
    spread = (ask - bid) / mid

    return {
        "symbol": data["symbol"],
        "exchange": data["exchange"],
        "best_bid_price":data["best_bid_price"],
        "best_ask_price":data["best_ask_price"],
        "mid_price": mid,
        "spread_bps": spread * 10_000,
        "timestamp": data["timestamp_utc_micros"]
    }

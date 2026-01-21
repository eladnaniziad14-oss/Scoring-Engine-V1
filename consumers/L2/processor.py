def compute_depth_l2(data: dict, pct: float = 0.01) -> dict:
    """
    Calcule la profondeur du carnet à ±pct (ex: 1%)
    Retourne la profondeur bid / ask en dollars
    """

    bids = data["bids"]
    asks = data["asks"]

    # Best prices
    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])

    bid_limit = best_bid * (1 - pct)
    ask_limit = best_ask * (1 + pct)

    bid_depth = 0.0
    ask_depth = 0.0

    # Depth côté bids
    for price, qty in bids:
        price = float(price)
        qty = float(qty)
        if price >= bid_limit:
            bid_depth += price * qty

    # Depth côté asks
    for price, qty in asks:
        price = float(price)
        qty = float(qty)
        if price <= ask_limit:
            ask_depth += price * qty

    return {
        "symbol": data["symbol"],
        "exchange": data["exchange"],
        "bid_depth_usd": bid_depth,
        "ask_depth_usd": ask_depth,
        "total_depth_usd": bid_depth + ask_depth,
        "timestamp_utc_micros": data["timestamp_utc_micros"]
    }

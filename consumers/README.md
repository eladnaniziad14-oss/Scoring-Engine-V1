
# Market Data Kafka Consumers (L1 & L2)

This project has two Kafka consumers:

- **L1 consumer**: reads top-of-book data (best bid/ask) from `market-data-l1`
- **L2 consumer**: reads full order book snapshots from `market-data`

Both compute simple market quality metrics and print them.

---

## 1. Kafka Topics

- **`market-data-l1`**  
  Contains **Level 1** messages with:
  - `symbol`
  - `best_bid_price`
  - `best_ask_price`
  - `timestamp_utc_micros` (microseconds since Unix epoch, UTC)

- **`market-data`**  
  Contains **Level 2** messages with:
  - `symbol`
  - `exchange`
  - `bids`: `[[price, qty], ...]`
  - `asks`: `[[price, qty], ...]`
  - `timestamp_utc_micros` (microseconds since Unix epoch, UTC)

---

## 2. L1 Metrics (Topic: `market-data-l1`)

### 2.1 Computation

```python
def compute_l1_metrics(data: dict) -> dict:
    bid = float(data["best_bid_price"])
    ask = float(data["best_ask_price"])

    mid = (bid + ask) / 2
    spread = (ask - bid) / mid  # relative spread

    return {
        "symbol": data["symbol"],
        "mid_price": mid,
        "spread_bps": spread * 10_000,          # spread in basis points
        "timestamp": data["timestamp_utc_micros"]
    }
```

- **mid_price**: average of best bid and best ask  
- **spread_bps**: bid–ask spread in basis points  
  - 10 bps = 0.1%

### 2.2 Example print format

```text
✅ L1 METRICS
Symbol          : ETHUSDT
Exchange:      : binance
Ask Price       : 2986.070000
Bid Price       : 2986.060000
Mid Price       : 2986.065000
Spread (bps)    : 0.033489
Timestamp (µs)  : 1766231407173271
------------------------------------------------------------
```

---

## 3. L2 Depth Metrics (Topic: `market-data`)

### 3.1 Computation (depth at ±1%)

```python
def compute_depth_l2(data: dict, pct: float = 0.01) -> dict:
    bids = data["bids"]
    asks = data["asks"]

    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])

    bid_limit = best_bid * (1 - pct)   # e.g. 1% below best bid
    ask_limit = best_ask * (1 + pct)   # e.g. 1% above best ask

    bid_depth = 0.0
    ask_depth = 0.0

    for price, qty in bids:
        price = float(price)
        qty = float(qty)
        if price >= bid_limit:
            bid_depth += price * qty    # USD notional

    for price, qty in asks:
        price = float(price)
        qty = float(qty)
        if price <= ask_limit:
            ask_depth += price * qty    # USD notional

    return {
        "symbol": data["symbol"],
        "exchange": data["exchange"],
        "bid_depth_usd": bid_depth,
        "ask_depth_usd": ask_depth,
        "total_depth_usd": bid_depth + ask_depth,
        "timestamp_utc_micros": data["timestamp_utc_micros"],
    }
```

With `pct = 0.01`:

- **bid_depth_usd**: buy-side liquidity within 1% below best bid  
- **ask_depth_usd**: sell-side liquidity within 1% above best ask  
- **total_depth_usd**: sum of both

### 3.2 Example print format

```text
✅ L2 DEPTH
Symbol           : ETHUSDT
Exchange         : binance
Bid Depth (USD)  : 48400.49
Ask Depth (USD)  : 83555.82
Total Depth USD  : 131956.31
Timestamp (µs)  : 1766230675160063
------------------------------------------------------------
```

---

## 4. Time Handling

- Field: `timestamp_utc_micros`
- Unit: **microseconds** since Unix epoch, UTC (not nanoseconds).

Basic freshness check (5 minutes):

```python
import time

now = time.time()  # seconds
msg_time = data["timestamp_utc_micros"] / 1_000_000

is_fresh = abs(now - msg_time) <= 300
```

---

## 5. Docker Usage
Single Docker image with CONSUMER_TYPE switch.
### 5.1 Dockerfile (consumer image)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV CONSUMER_TYPE=L1

CMD ["sh", "-c", "python $CONSUMER_TYPE/run.py"]
```

- `CONSUMER_TYPE=L1` → runs `L1/run.py`
- `CONSUMER_TYPE=L2` → runs `L2/run.py`

### 5.2 Build

```bash
docker build -t market-data-consumer ./consumers
```

### 5.3 Run L1 consumer (topic `market-data-l1`)

```bash
docker run --rm \
  --network cq-ingestion_flink-network \
  -e CONSUMER_TYPE=L1 \
  market-data-consumer
```

L1 code should subscribe to `market-data-l1`.

### 5.4 Run L2 consumer (topic `market-data`)

```bash
docker run --rm \
  --network cq-ingestion_flink-network \
  -e CONSUMER_TYPE=L2 \
  market-data-consumer
```

L2 code should subscribe to `market-data`.


### 6. Project Layout 
---
```
.
├── common/
│   ├── kafka_consumer.py       # BaseKafkaConsumer implementation
│   └── config.py               # BASE_CONSUMER_CONFIG
├── consumers/
│   ├── L1/
│   │   ├── run.py              # L1 consumer
│       ├── processor.py        # compute_depth_l1
│       └── validation.py       # validate_l1
│   └── L2/
│       ├── run.py              # L2 consumer
│       ├── processor.py        # compute_depth_l2
│       └── validation.py       # validate_l2
├── Dockerfile                  # Builds the consumer image
└── requirements.txt

```
---

**Author:** Zrayouil karima
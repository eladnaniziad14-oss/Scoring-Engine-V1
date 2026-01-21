from common.kafka_consumer import BaseKafkaConsumer
from common.config import BASE_CONSUMER_CONFIG
from L2.validation import validate_l2
from L2.processor import compute_depth_l2

TOPIC = "market-data"

config = {
    **BASE_CONSUMER_CONFIG,
    "group.id": "market-data-l2-karima-consumer",
    "auto.offset.reset": "earliest",
}

consumer = BaseKafkaConsumer(config, TOPIC)
consumer.start()

try:
    while True:
        data = consumer.poll()
        if not data:
            continue

        if not validate_l2(data):
            continue

        depth = compute_depth_l2(data)

        print("✅ L2 DEPTH")
        print(f"Symbol           : {depth['symbol']}")
        print(f"Exchange:      : {depth['exchange']}")
        print(f"Bid Depth (USD)  : {depth['bid_depth_usd']:.2f}")
        print(f"Ask Depth (USD)  : {depth['ask_depth_usd']:.2f}")
        print(f"Total Depth USD : {depth['total_depth_usd']:.2f}")
        print(f"Timestamp (µs)  : {depth['timestamp_utc_micros']}")
        print("-" * 60)

except KeyboardInterrupt:
    pass
finally:
    consumer.close()

from common.kafka_consumer import BaseKafkaConsumer
from common.config import BASE_CONSUMER_CONFIG
from L1.validation import validate_l1
from L1.processor import compute_l1_metrics  # adjust name if different

TOPIC = "market-data-l1"

config = {
    **BASE_CONSUMER_CONFIG,
    "group.id": "market-data-l1-karima-consumer",
    "auto.offset.reset": "earliest",
}

def main():
    consumer = BaseKafkaConsumer(config, TOPIC)
    consumer.start()

    try:
        while True:
            data = consumer.poll()
            if not data:
                continue

            if not validate_l1(data):
                continue

            metrics = compute_l1_metrics(data)

            print("✅ L1 METRICS")
            print(f"Symbol          : {metrics['symbol']}")
            print(f"Exchange:      : {metrics['exchange']}")
            print(f"Ask Price       : {metrics['best_ask_price']:.6f}")
            print(f"Bid Price       : {metrics['best_bid_price']:.6f}")
            print(f"Mid Price       : {metrics['mid_price']:.6f}")
            print(f"Spread (bps)    : {metrics['spread_bps']:.6f}")
            print(f"Timestamp (µs)  : {metrics['timestamp']}")
            print("-" * 60)

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()

if __name__ == "__main__":
    main()
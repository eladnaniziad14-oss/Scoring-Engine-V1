from clickhouse_driver import Client

client = Client("localhost")

def ingest_to_clickhouse(df, table: str, timestamp_field: str):
    records = df.to_dict("records")
    client.execute(
        f"INSERT INTO {table} (*) VALUES",
        records,
    )

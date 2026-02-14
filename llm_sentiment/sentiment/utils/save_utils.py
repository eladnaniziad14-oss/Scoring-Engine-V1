import os, pandas as pd
def ensure_folder(path):
    d=os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def save_csv_parquet(df, base):
    ensure_folder(base)
    csv = base + ".csv"
    parquet = base + ".parquet"
    try:
        df.to_csv(csv, index=False)
    except Exception:
        df.to_csv(csv, index=False)
    try:
        df.to_parquet(parquet, index=False)
    except Exception:
        pass

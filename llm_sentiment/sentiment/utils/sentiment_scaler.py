from math import tanh
def vol_to_sentiment(v):
    try:
        val=float(v)
    except Exception:
        return 0.0
    z=(val-0.5)/0.5
    return -tanh(z)

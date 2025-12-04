import requests, time
DEFAULT_SLEEP=0.3
def https_get(url, headers=None, timeout=10):
    try:
        r=requests.get(url, headers=headers, timeout=timeout)
        time.sleep(DEFAULT_SLEEP)
        return r
    except Exception:
        return None

def safe_json(resp):
    if resp is None:
        return None
    try:
        return resp.json()
    except Exception:
        return None

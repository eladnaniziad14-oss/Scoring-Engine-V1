import yaml, os
def load_sources():
    p='config/sources.yaml'
    if not os.path.exists(p): return {}
    with open(p,'r') as f:
        return yaml.safe_load(f)

def load_api_keys():
    p='config/api_keys.yaml'
    if not os.path.exists(p): return {}
    with open(p,'r') as f:
        return yaml.safe_load(f)

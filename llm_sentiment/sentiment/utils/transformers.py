from transformers import pipeline
_nlp=None
def compute_sentiment(text):
    global _nlp
    if not text:
        return 0.0
    if _nlp is None:
        try:
            _nlp = pipeline("sentiment-analysis")
        except Exception:
            _nlp = None
    if _nlp is None:
        return 0.0
    try:
        r=_nlp(text[:512])[0]
        label=r.get("label","")
        score=float(r.get("score",0.0))
        return score if "POS" in label.upper() else -score
    except Exception:
        return 0.0

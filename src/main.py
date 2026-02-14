from fastapi import FastAPI

app = FastAPI(title="Scoring Engine Service")

@app.get("/health")
def health_check():
    return {"status": "ok", "module": "scoring-engine"}
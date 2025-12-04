# 🧠 Composite Sentiment Scoring API

FastAPI‑based microservice that powers the **CompositeScorer** sentiment engine.  
This layer exposes HTTP endpoints for asset sentiment analysis, system health checks, and deployment monitoring.

---

## 📦 Overview

**Main capabilities**

| Endpoint | Description | Example |
|-----------|--------------|----------|
| `/sentiment` | Analyzes a single asset’s sentiment score at a given timestamp. | `/sentiment?asset=GOLD&timestamp=2025‑01‑01T00:00:00Z` |
| `/health` | Lightweight “I’m alive” . | `/health` |
| `/status` | Reports database connectivity and pipeline heartbeat. | `/status` |

---

## ⚙️ Tech Stack

| Component | Purpose |
|------------|----------|
| **FastAPI** | API framework |
| **Uvicorn** | ASGI server |
| **Poetry** | Dependency & environment manager |
| **pydantic‑settings** | Configuration management /
 environment variables |
| **clickhouse‑driver** | Connects to ClickHouse database |
| **python‑dotenv** | Loads `.env` configs |
| **Pandas** | Data handling for scoring pipeline |

---

## 🧱 Directory Layout

```
llm_sentiment/sentiment/api/
│
├── Dockerfile            # Build definition for API container
├── main.py               # FastAPI app entry point
├── pyproject.toml        # Poetry project & deps definition
├── routers/
│   ├── sentiment_router.py   # /sentiment endpoint
│   └── health_router.py      # /health + /status monitoring
├── core/
│   ├── settings.py
│   ├── security.py
│   └── logging.py
└── models/
    └── sentiment_model.py
```

## 🧩 Installation & Local Development

### 1.  Install Dependencies

```bash
cd llm_sentiment/sentiment
pip install requirements.txt
```

### 3.  Run Locally

```bash
 run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Now open [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 🐳 Docker Deployment

The service is fully containerized for standalone deployment.

### Dockerfile Highlights
- **Base image:** `python:3.11-slim`
- **Dependency manager:** Poetry 1.8+
- **Exposed port:** 8001
- **Command:** `poetry run uvicorn main:app --host 0.0.0.0 --port 8001`

### Build & Run

```bash
# Build image
docker build -t sentiment-api .

# Run (exposes 8001)
docker run --env-file .env -p 8001:8001 sentiment-api
```

Visit → [http://localhost:8001/docs](http://localhost:8001/docs)

---

## 🩺 Health & Status Endpoints

| Endpoint | Description | Example Output |
|-----------|--------------|----------------|
| `/health` | Liveness probe | `{ "status": "ok" }` |
| `/status` | Readiness check (ClickHouse + pipeline) | `{ "database": "online", "pipelines": "running", "api": "healthy" }` |

---

## 🧠 Sentiment Scoring Endpoint

### `/sentiment`
Example:
```
GET /sentiment?asset=TSLA.O&timestamp=2025-11-21T00:00:00Z
```

Example Response:
```json
{
  "asset": "TSLA.O",
  "timestamp": "2025-11-21T00:00:00Z",
  "sentiment_score": 0.281,
  "confidence": 0.89,
  "regime": "bullish"
}
```

Errors are reported with appropriate HTTP codes (400 for bad input, 500 for internal issues).

---

## 🧩 Health & Monitoring Integration

- `/health` → used by orchestration liveness probes  
- `/status` → used by deployment readiness probes  
  Checks:  
  - API : test /status 
  - ClickHouse → `SELECT 1` test  
  - Pipeline heartbeat → local file or custom logic

---

## 🏗️ Design Notes

1. **Settings** loaded via `pydantic-settings` + `.env`.  
2. **API key validation** guards endpoints (security.py).  
3. **CompositeScorer** integrates data scraping, sentiment analysis, and aggregation.  
4. **Error handling** converts runtime exceptions into structured HTTP responses.  
5. **Dockerized** with Poetry to ensure deterministic builds.

---

## 🧮 Useful Commands

| Task | Command |
|------|----------|
| Start API | ` run uvicorn llm_sentiment.sentiment.api.main:app --reload` |
| Build Docker image | `docker compose up --build api ` |

---

## ✅ Deployment Readiness

- Health endpoint ..... 
- Readiness endpoint ✔️  
- Sentiment scoring ......  
- ClickHouse status checks ✔️  
- Poetry‑managed deterministic dependencies ✔️  
- Docker image exposing port 8001 ✔️  

The API layer is completely *deployment‑ready* and can run as an independent service in Docker, Docker Compose.

---

**Author:** Zrayouil karima



# ============================
#   Dockerfile (API service)
# ============================

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/root/.local/bin:$PATH" \
    APP_HOME="/app" \
    POETRY_VERSION=1.8.3

WORKDIR $APP_HOME

# ---- Install system deps & Poetry ----
RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && rm -rf /var/lib/apt/lists/*

# ---- Copy only API dependency files ----
COPY llm_sentiment/sentiment/api/pyproject.toml pyproject.toml
# ---- Install dependencies ----
RUN poetry install --no-root --no-dev

# ---- Copy  code  ----
COPY llm_sentiment/ llm_sentiment/
COPY llm_sentiment/sentiment/config/ llm_sentiment/sentiment/config/

# ---- Expose port ----
EXPOSE 8001

# ---- Run the API ----
CMD ["poetry", "run", "uvicorn", "llm_sentiment.sentiment.api.main:app", "--host", "0.0.0.0", "--port", "8001"]
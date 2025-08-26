FROM ghcr.io/LotusCapital2025/cq-python-base:3.11-slim

WORKDIR /app

COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false && poetry install --no-root --no-dev

COPY ./src /app/src

EXPOSE 80
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "80"]
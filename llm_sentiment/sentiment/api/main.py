from fastapi import FastAPI,Depends
from llm_sentiment.sentiment.api.routers.health_router import router as health_router
from llm_sentiment.sentiment.api.routers.sentiment_router import router as sentiment_router
from llm_sentiment.sentiment.api.core.security import validate_api_key
app = FastAPI(
    title="Sentiment Scoring API",
    version="1.0.0",
    description="Real-time sentiment scoring service"
)

# Attach routers
app.include_router(sentiment_router, prefix="/sentiment", tags=["Sentiment"],dependencies=[Depends(validate_api_key)])
app.include_router(health_router , tags=["Health"])

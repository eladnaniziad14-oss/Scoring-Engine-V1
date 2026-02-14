from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class SentimentQuery(BaseModel):
    asset: str = Field(..., description="Asset symbol, e.g. BTC")
    timestamp: Optional[datetime] = Field(
        None, description="Timestamp for scoring (UTC). Defaults to now."
    )

class SentimentResponse(BaseModel):
    asset: str
    timestamp: datetime
    sentiment_score: float
    confidence: float
    regime: str

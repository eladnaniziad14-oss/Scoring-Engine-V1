from fastapi import APIRouter, HTTPException,Depends,Query
from datetime import datetime
from typing import Optional
from llm_sentiment.sentiment.api.core.security import validate_api_key
from llm_sentiment.sentiment.api.models.sentiment_model import (
    SentimentQuery,
    SentimentResponse,
)
from llm_sentiment.sentiment.api.core.logging import logger
from llm_sentiment.sentiment.core.orchestrator import SentimentOrchestrator

def composite_score(asset: str, timestamp: datetime):
    """
    Use the real orchestrator to compute the composite sentiment.
    """
    try:
        orchestrator = SentimentOrchestrator()  
        scores = orchestrator.composite_scores()  
        data = scores.get(asset.upper())
        if not data:
            raise ValueError(f"No sentiment data found for asset '{asset}'")

        return (
            data["sentiment_score"],
            data["confidence"],
            data["regime"],
        )

    except Exception as e:
        logger.error(f"Composite scoring failed for {asset}: {e}", exc_info=True)
        raise
router = APIRouter()

@router.get("", response_model=SentimentResponse, summary="Get sentiment score for a given asset")
def get_sentiment(
    asset: str = Query(..., description="Asset symbol to score, e.g. 'GOLD' or 'BTC'"),
    timestamp: Optional[datetime] = Query(None, description="Datetime for scoring context (UTC)"),api_key: str = Depends(validate_api_key)
):
    """
    Returns sentiment classification and score for the requested asset.
    If no timestamp is provided, uses current UTC time.
    """
    try:
        if timestamp is None:
            timestamp = datetime.utcnow()
            logger.debug(f"No timestamp provided, using UTC now: {timestamp}")
         # Call the composite scoring engine
        sentiment_score, confidence, regime = composite_score(asset, timestamp)
        logger.info(f"Scored {asset} at {timestamp}: score={sentiment_score:.3f}, confidence={confidence:.2f}, regime={regime}")
        
        return SentimentResponse(
            asset=asset,
            timestamp=timestamp,
            sentiment_score=sentiment_score,
            confidence=confidence,
            regime=regime,
        )

    except ValueError as ve:
        # Use 400 for user/input errors
        logger.warning(f"Invalid input for {asset}: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))

    except Exception as e:
        # Catch everything else as internal error
        logger.error(f"Internal scoring failure for {asset}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal sentiment scoring error")

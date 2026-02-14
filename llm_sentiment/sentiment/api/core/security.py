from fastapi import Security, HTTPException
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_401_UNAUTHORIZED
import os
from llm_sentiment.sentiment.api.core.settings import settings
print(settings.api_key)

API_KEY = settings.api_key
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def validate_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    return api_key

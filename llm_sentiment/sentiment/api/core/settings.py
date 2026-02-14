from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    model_name: str = "CompositeSentimentScorer"
    debug: bool = True
    api_key: str = Field("DEV_DEFAULT_KEY", env="API_KEY")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  

settings = Settings()

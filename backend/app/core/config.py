from pydantic_settings import BaseSettings
from pathlib import Path
import os

class Settings(BaseSettings):
    # API Keys
    HF_TOKEN: str = ""
    OPENROUTER_API_KEY: str
    
    # Server Config
    PORT: int
    HOST: str
    DEBUG: bool
    
    # CORS
    CORS_ORIGIN: str
    
    # Paths
    INDEX_PATH: str
    UPLOAD_PATH: str
    
    # Models
    EMBEDDING_MODEL: str
    EMBEDDING_DIM: int
    LLM_MODEL: str
    
    class Config:
        env_file = ".env"

settings = Settings()

# Create directories relative to project root or use absolute paths? 
# Usually best to create them relative to the execution context or define absolute paths.
Path(settings.INDEX_PATH).mkdir(exist_ok=True)
Path(settings.UPLOAD_PATH).mkdir(exist_ok=True)

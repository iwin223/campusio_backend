"""Application configuration loaded from environment variables"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration"""
    
    # Database - PostgreSQL
    database_url: str 
    ALLOWED_HOSTS:list[str]
    # JWT
    secret_key: str 
    algorithm: str 
    access_token_expire_minutes: int
    
    # Resend Email
    resend_api_key: str 
    resend_from_email: str 
    resend_from_name: str 
    
    # CORS
    cors_origins: list[str]    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Load settings once and cache them"""
    return Settings()

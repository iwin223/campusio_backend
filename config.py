"""Application configuration loaded from environment variables"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


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
    
    # USMS SMS Service (optional - can fail gracefully if not configured)
    usms_token: Optional[str] = None
    usms_sender_id: str = "SchoolERP"
    usms_base_url: str = "https://webapp.usmsgh.com"
    
    # Twilio WhatsApp (optional - can fail gracefully if not configured)
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_whatsapp_number: Optional[str] = None
    superadmin_whatsapp_phone: Optional[str] = None
    
    # Meta Business WhatsApp API (optional - alternative to Twilio)
    meta_whatsapp_api_token: Optional[str] = None
    meta_whatsapp_phone_number_id: Optional[str] = None
    meta_whatsapp_business_account_id: Optional[str] = None
    meta_whatsapp_sender_phone: Optional[str] = None  # Phone number to send from
    meta_superadmin_whatsapp_phone: Optional[str] = None  # Recipient phone
    
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

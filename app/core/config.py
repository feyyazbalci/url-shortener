from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os

class Settings(BaseSettings):
    """Application configuration settings."""

    app_name: str = "URL Shortener Service"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # API settings
    api_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000

    # gRPC settings
    gRPC_host: str = "0.0.0.0"
    grpc_port: int = 50051

    # Database settings
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/url_shortener.db",
        description="Async database URL"
    )
    database_echo: bool = False  # for SQL echo

    # Redis settings (cache)
    redis_url: Optional[str] = Field(
        default="redis://localhost:6385",
        description="Redis cache URL"
    )

    redis_enabled: bool = True
    cache_ttl: int = 3600  # Cache time-to-live in seconds

    # URL Shortening settings
    base_url: str = "http://localhost:8000"
    short_code_length: int = 6
    allowed_chars: str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    max_url_length: int = 2048
    default_expiry_days: int = 365  # 1 year

    # Rate limiting settings
    rate_limit_per_minute: int = 60  # requests per minute
    rate_limit_burst: int = 10

    # Security settings
    allowed_origins: list[str] = ["*"]
    allowed_methods: list[str] = ["*"]
    allowed_headers: list[str] = ["*"]

    # Monitoring
    enable_metrics: bool = True
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

# Global settings instance
settings = Settings()

def get_settings() -> Settings:
    """Retrieve the global settings instance."""
    return settings

def get_database_url() -> str:
    """Get the database URL from settings."""
    url = settings.database_url

    if url.startswith("sqlite"):
        os.makedirs("./data", exist_ok=True)

    return url

def get_redis_url() -> Optional[str]:
    """Get the Redis URL from settings if caching is enabled."""
    if settings.redis_enabled and settings.redis_url:
        return settings.redis_url
    return None
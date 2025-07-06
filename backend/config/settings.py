"""
Application settings and configuration
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application settings
    APP_NAME: str = "BargainB Admin API"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=True, env="DEBUG")
    ENVIRONMENT: str = Field(default="development", env="PYTHON_ENV")
    
    # Server settings
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="BACKEND_PORT")
    
    # CORS settings
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        env="ALLOWED_ORIGINS"
    )
    ALLOWED_HOSTS: List[str] = Field(
        default=["localhost", "127.0.0.1", "*"],
        env="ALLOWED_HOSTS"
    )
    
    # Database settings - made optional for development
    DATABASE_URL: str = Field(default="postgresql://localhost:5432/bargainb_dev", env="DATABASE_URL")
    
    # Supabase settings
    SUPABASE_URL: str = Field(default="https://mock-project.supabase.co", env="SUPABASE_URL")
    SUPABASE_ANON_KEY: str = Field(default="mock-anon-key", env="SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(default="mock-service-role-key", env="SUPABASE_SERVICE_ROLE_KEY")
    
    # Redis settings
    REDIS_URL: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    
    # LangGraph & LangChain Configuration
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    OPENAI_MODEL: str = Field(default="gpt-4", env="OPENAI_MODEL")
    AI_MODEL: Optional[str] = Field(default=None, env="AI_MODEL")  # Alternative model field
    LANGCHAIN_API_KEY: Optional[str] = Field(default=None, env="LANGCHAIN_API_KEY")
    LANGSMITH_API_KEY: Optional[str] = Field(default=None, env="LANGSMITH_API_KEY")  # LangSmith API key
    LANGCHAIN_TRACING_V2: bool = Field(default=True, env="LANGCHAIN_TRACING_V2")
    LANGCHAIN_ENDPOINT: str = Field(default="https://api.smith.langchain.com", env="LANGCHAIN_ENDPOINT")
    LANGCHAIN_PROJECT: str = Field(default="bargainb-admin", env="LANGCHAIN_PROJECT")
    
    # Additional API Keys
    WASENDER_API_KEY: Optional[str] = Field(default=None, env="WASENDER_API_KEY")
    TAVILY_API_KEY: Optional[str] = Field(default=None, env="TAVILY_API_KEY")
    
    # Scraping settings
    SCRAPER_RATE_LIMIT: float = Field(default=2.0, env="SCRAPER_RATE_LIMIT")
    SCRAPER_MAX_RETRIES: int = Field(default=3, env="SCRAPER_MAX_RETRIES")
    SCRAPER_TIMEOUT: int = Field(default=30, env="SCRAPER_TIMEOUT")
    
    # Security settings - made optional for development
    JWT_SECRET: str = Field(default="dev-jwt-secret-change-in-production", env="JWT_SECRET")
    API_SECRET_KEY: str = Field(default="dev-api-secret-change-in-production", env="API_SECRET_KEY")
    
    # Monitoring
    SENTRY_DSN: Optional[str] = Field(default=None, env="SENTRY_DSN")
    LOG_LEVEL: str = Field(default="info", env="LOG_LEVEL")
    
    # Email settings (for alerts)
    SMTP_HOST: Optional[str] = Field(default=None, env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USER: Optional[str] = Field(default=None, env="SMTP_USER")
    SMTP_PASS: Optional[str] = Field(default=None, env="SMTP_PASS")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.ENVIRONMENT.lower() in ["development", "dev"]
    
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.ENVIRONMENT.lower() in ["production", "prod"]
    
    def get_database_url(self) -> str:
        """Get the database URL with proper formatting."""
        return self.DATABASE_URL
    
    def has_openai_key(self) -> bool:
        """Check if OpenAI API key is configured."""
        return self.OPENAI_API_KEY is not None and len(self.OPENAI_API_KEY.strip()) > 0
    
    def has_langchain_key(self) -> bool:
        """Check if LangChain API key is configured."""
        return (self.LANGCHAIN_API_KEY is not None and len(self.LANGCHAIN_API_KEY.strip()) > 0) or \
               (self.LANGSMITH_API_KEY is not None and len(self.LANGSMITH_API_KEY.strip()) > 0)
    
    def agents_available(self) -> bool:
        """Check if agent dependencies are available."""
        return self.has_openai_key()  # Minimum requirement for agents
    
    def get_log_config(self) -> dict:
        """Get logging configuration based on environment."""
        level = self.LOG_LEVEL.upper()
        
        config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
                "detailed": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default" if self.is_production() else "detailed",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": level,
                "handlers": ["default"],
            },
        }
        
        return config


# Create settings instance
settings = Settings() 
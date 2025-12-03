from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List
import os


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All settings have type hints and validation. Values are loaded from
    environment variables with fallback to defaults specified here.
    """
    
    # Application Settings
    APP_NAME: str = Field(
        default="Product Availability Service",
        description="Application name"
    )
    APP_VERSION: str = Field(
        default="1.0.0",
        description="Application version"
    )
    DEBUG: bool = Field(
        default=False,
        description="Debug mode flag"
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    
    # Server Configuration
    HOST: str = Field(
        default="0.0.0.0",
        description="Server host address"
    )
    PORT: int = Field(
        default=8000,
        description="Server port"
    )
    WORKERS: int = Field(
        default=4,
        description="Number of worker processes for production"
    )
    
    # Redis Configuration
    REDIS_HOST: str = Field(
        default="localhost",
        description="Redis host address"
    )
    REDIS_PORT: int = Field(
        default=6379,
        description="Redis port"
    )
    REDIS_PASSWORD: str = Field(
        default="",
        description="Redis password (empty for no auth)"
    )
    REDIS_DB: int = Field(
        default=0,
        description="Redis database number"
    )
    CACHE_TTL_SECONDS: int = Field(
        default=120,
        description="Cache time-to-live in seconds (2 minutes for senior requirement)"
    )
    
    # Vendor API Settings
    VENDOR_TIMEOUT_SECONDS: int = Field(
        default=2,
        description="Timeout for vendor API calls in seconds"
    )
    VENDOR_MAX_RETRIES: int = Field(
        default=2,
        description="Maximum number of retry attempts per vendor"
    )
    DATA_FRESHNESS_MINUTES: int = Field(
        default=10,
        description="Maximum age of vendor data in minutes before discarding"
    )
    PRICE_DIFFERENCE_THRESHOLD_PERCENT: int = Field(
        default=10,
        description="Price difference threshold percentage for stock-based decision"
    )
    
    # Circuit Breaker Settings
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = Field(
        default=3,
        description="Number of consecutive failures before opening circuit"
    )
    CIRCUIT_BREAKER_TIMEOUT_SECONDS: int = Field(
        default=30,
        description="Cooldown period when circuit is open in seconds"
    )
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = Field(
        default=60,
        description="Maximum requests per window per API key"
    )
    RATE_LIMIT_WINDOW_SECONDS: int = Field(
        default=60,
        description="Rate limit time window in seconds"
    )
    
    # Background Jobs
    CACHE_PREWARM_INTERVAL_MINUTES: int = Field(
        default=5,
        description="Interval for cache prewarming in minutes"
    )
    POPULAR_SKUS: str = Field(
        default="ABC123,XYZ789,DEF456,LMN101,PQR202",
        description="Comma-separated list of popular SKUs to prewarm"
    )
    
    # Mock Vendor Configurations
    # Vendor 1 (Fast & Reliable)
    VENDOR_ONE_BASE_URL: str = Field(
        default="http://mock-vendor-one.local",
        description="Base URL for Vendor 1"
    )
    VENDOR_ONE_MIN_DELAY_MS: int = Field(
        default=100,
        description="Minimum response delay for Vendor 1 in milliseconds"
    )
    VENDOR_ONE_MAX_DELAY_MS: int = Field(
        default=300,
        description="Maximum response delay for Vendor 1 in milliseconds"
    )
    VENDOR_ONE_FAILURE_RATE: float = Field(
        default=0.01,
        description="Failure rate for Vendor 1 (0.0 to 1.0)"
    )
    
    # Vendor 2 (Standard)
    VENDOR_TWO_BASE_URL: str = Field(
        default="http://mock-vendor-two.local",
        description="Base URL for Vendor 2"
    )
    VENDOR_TWO_MIN_DELAY_MS: int = Field(
        default=200,
        description="Minimum response delay for Vendor 2 in milliseconds"
    )
    VENDOR_TWO_MAX_DELAY_MS: int = Field(
        default=500,
        description="Maximum response delay for Vendor 2 in milliseconds"
    )
    VENDOR_TWO_FAILURE_RATE: float = Field(
        default=0.05,
        description="Failure rate for Vendor 2 (0.0 to 1.0)"
    )
    
    # Vendor 3 (Slow & Unreliable)
    VENDOR_THREE_BASE_URL: str = Field(
        default="http://mock-vendor-three.local",
        description="Base URL for Vendor 3"
    )
    VENDOR_THREE_MIN_DELAY_MS: int = Field(
        default=1000,
        description="Minimum response delay for Vendor 3 in milliseconds"
    )
    VENDOR_THREE_MAX_DELAY_MS: int = Field(
        default=3000,
        description="Maximum response delay for Vendor 3 in milliseconds"
    )
    VENDOR_THREE_FAILURE_RATE: float = Field(
        default=0.30,
        description="Failure rate for Vendor 3 (0.0 to 1.0)"
    )
    
    # Security
    VALID_API_KEYS: str = Field(
        default="test-api-key-12345,demo-key-67890,dev-key-abcdef",
        description="Comma-separated list of valid API keys"
    )
    
    # Monitoring & Metrics
    ENABLE_VENDOR_METRICS: bool = Field(
        default=True,
        description="Enable detailed vendor performance logging"
    )
    ENABLE_CACHE_METRICS: bool = Field(
        default=True,
        description="Enable cache hit/miss tracking"
    )
    
    @field_validator('LOG_LEVEL')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the allowed values."""
        allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        v_upper = v.upper()
        if v_upper not in allowed_levels:
            raise ValueError(f"LOG_LEVEL must be one of {allowed_levels}")
        return v_upper
    
    @field_validator('PRICE_DIFFERENCE_THRESHOLD_PERCENT')
    @classmethod
    def validate_price_threshold(cls, v: int) -> int:
        """Validate price difference threshold is between 0 and 100."""
        if not 0 <= v <= 100:
            raise ValueError("PRICE_DIFFERENCE_THRESHOLD_PERCENT must be between 0 and 100")
        return v
    
    @field_validator(
        'VENDOR_ONE_FAILURE_RATE',
        'VENDOR_TWO_FAILURE_RATE',
        'VENDOR_THREE_FAILURE_RATE'
    )
    @classmethod
    def validate_failure_rate(cls, v: float) -> float:
        """Validate failure rate is between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Failure rate must be between 0.0 and 1.0")
        return v
    
    def get_popular_skus_list(self) -> List[str]:
        """
        Parse and return popular SKUs as a list.
        
        Returns:
            List of popular SKU strings
        """
        return [sku.strip() for sku in self.POPULAR_SKUS.split(',') if sku.strip()]
    
    def get_valid_api_keys_list(self) -> List[str]:
        """
        Parse and return valid API keys as a list.
        
        Returns:
            List of valid API key strings
        """
        return [key.strip() for key in self.VALID_API_KEYS.split(',') if key.strip()]
    
    @property
    def redis_url(self) -> str:
        """
        Construct Redis connection URL.
        
        Returns:
            Redis URL string for connection
        """
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

settings = Settings()
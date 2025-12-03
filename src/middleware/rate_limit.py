import logging
from typing import TYPE_CHECKING

from src.config import settings

if TYPE_CHECKING:
    from src.services.cache_service import CacheService

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Token bucket rate limiter using Redis.
    
    Implements sliding window rate limiting:
    - Each API key gets N requests per time window
    - Uses Redis INCR for atomic counter operations
    - Automatically expires counters after window
    
    Example:
        rate_limiter = RateLimiter(cache_service)
        
        if await rate_limiter.check_rate_limit("api-key-123"):
            # Request allowed
            process_request()
        else:
            # Rate limit exceeded
            return 429 error
    """
    
    def __init__(self, cache_service: "CacheService"):
        """
        Initialize rate limiter.
        
        Args:
            cache_service: Redis cache service for storing counters
        """
        self.cache_service = cache_service
        self.max_requests = settings.RATE_LIMIT_REQUESTS
        self.window_seconds = settings.RATE_LIMIT_WINDOW_SECONDS
        
        logger.info(
            f"Rate limiter initialized: "
            f"{self.max_requests} requests per {self.window_seconds}s"
        )
    
    async def check_rate_limit(self, api_key: str) -> bool:
        """
        Check if request is within rate limit.
        
        Uses Redis atomic INCR operation to safely increment counter.
        Sets expiration on first request in window.
        
        Args:
            api_key: API key to check limit for
            
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        try:
            # Create unique key for this API key's rate limit
            rate_limit_key = f"rate_limit:{api_key}"
            
            # Atomically increment counter
            # Returns the new value after increment
            count = await self.cache_service.increment(rate_limit_key)
            
            # Set expiration on first request
            # Subsequent requests in same window won't update TTL
            if count == 1:
                await self.cache_service.expire(
                    rate_limit_key,
                    self.window_seconds
                )
                logger.debug(
                    f"Started new rate limit window for API key: "
                    f"{self._mask_api_key(api_key)}"
                )
            
            # Check if within limit
            if count <= self.max_requests:
                logger.debug(
                    f"Rate limit check passed for {self._mask_api_key(api_key)}: "
                    f"{count}/{self.max_requests}"
                )
                return True
            else:
                logger.warning(
                    f"Rate limit exceeded for API key {self._mask_api_key(api_key)}: "
                    f"{count}/{self.max_requests} in {self.window_seconds}s window"
                )
                return False
        
        except Exception as e:
            # Fail open strategy: if Redis fails, allow the request
            # This prevents Redis issues from breaking the entire service
            logger.error(
                f"Rate limit check error for {self._mask_api_key(api_key)}: {e}. "
                f"Failing open (allowing request)"
            )
            return True
    
    async def get_remaining_requests(self, api_key: str) -> dict:
        """
        Get remaining requests for an API key.
        
        Useful for returning rate limit headers or dashboard.
        
        Args:
            api_key: API key to check
            
        Returns:
            Dictionary with limit, remaining, and reset info
        """
        try:
            rate_limit_key = f"rate_limit:{api_key}"
            
            # Get current count
            count_str = await self.cache_service.get_key(rate_limit_key)
            count = int(count_str) if count_str else 0
            
            remaining = max(0, self.max_requests - count)
            
            return {
                "limit": self.max_requests,
                "remaining": remaining,
                "used": count,
                "window_seconds": self.window_seconds,
                "exceeded": count > self.max_requests
            }
        
        except Exception as e:
            logger.error(f"Error getting rate limit info: {e}")
            return {
                "limit": self.max_requests,
                "remaining": self.max_requests,
                "used": 0,
                "window_seconds": self.window_seconds,
                "exceeded": False
            }
    
    async def reset_rate_limit(self, api_key: str) -> bool:
        """
        Reset rate limit for an API key.
        
        Useful for administrative actions or testing.
        
        Args:
            api_key: API key to reset
            
        Returns:
            True if successful
        """
        try:
            rate_limit_key = f"rate_limit:{api_key}"
            
            # Delete the counter key
            success = await self.cache_service.delete_product(rate_limit_key)
            
            if success:
                logger.info(
                    f"Rate limit reset for API key: "
                    f"{self._mask_api_key(api_key)}"
                )
            
            return success
        
        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")
            return False
    
    def _mask_api_key(self, api_key: str) -> str:
        """
        Mask API key for logging (security).
        
        Shows first 4 and last 4 characters, masks the rest.
        Example: "test-api-key-12345" → "test-***-12345"
        
        Args:
            api_key: API key to mask
            
        Returns:
            Masked API key string
        """
        if len(api_key) <= 8:
            return "***"
        
        return f"{api_key[:4]}-***-{api_key[-4:]}"
    
    def get_config(self) -> dict:
        """
        Get rate limiter configuration.
        
        Returns:
            Dictionary with current settings
        """
        return {
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds,
            "algorithm": "token_bucket"
        }
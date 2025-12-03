import logging
from config import settings
from services.cache_service import CacheService

logger = logging.getLogger(__name__)

class RateLimiter:
    """Token bucket rate limiter using Redis."""
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
    
    async def check_rate_limit(self, api_key: str) -> bool:
        """
        Check if request is within rate limit.
        
        Returns:
            True if allowed, False if rate limit exceeded
        """
        try:
            rate_limit_key = f"rate_limit:{api_key}"
            
            # Increment counter
            count = await self.cache_service.increment(rate_limit_key)
            
            # Set expiration on first request
            if count == 1:
                await self.cache_service.expire(
                    rate_limit_key,
                    settings.RATE_LIMIT_WINDOW_SECONDS
                )
            
            # Check if within limit
            if count <= settings.RATE_LIMIT_REQUESTS:
                return True
            else:
                logger.warning(
                    f"Rate limit exceeded for API key: {api_key} "
                    f"({count}/{settings.RATE_LIMIT_REQUESTS})"
                )
                return False
        
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # Fail open - allow request on error
            return True
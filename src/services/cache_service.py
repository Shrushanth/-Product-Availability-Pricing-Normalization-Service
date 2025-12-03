import json
import logging
from typing import Optional
import redis.asyncio as redis
from config import settings
from models.models import ProductResponse

logger = logging.getLogger(__name__)

class CacheService:
    """Redis-based caching service."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
    
    async def connect(self) -> None:
        """Establish Redis connection."""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")
    
    async def ping(self) -> bool:
        """Check Redis connection health."""
        try:
            return await self.redis_client.ping()
        except:
            return False
    
    async def get_product(self, sku: str) -> Optional[ProductResponse]:
        """Retrieve cached product data."""
        try:
            cache_key = f"product:{sku}"
            data = await self.redis_client.get(cache_key)
            
            if data:
                logger.debug(f"Cache hit for SKU: {sku}")
                product_dict = json.loads(data)
                return ProductResponse(**product_dict)
            
            logger.debug(f"Cache miss for SKU: {sku}")
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    async def set_product(self, sku: str, product: ProductResponse) -> bool:
        """Cache product data with TTL."""
        try:
            cache_key = f"product:{sku}"
            data = product.model_dump_json()
            
            await self.redis_client.setex(
                cache_key,
                settings.CACHE_TTL_SECONDS,
                data
            )
            
            logger.debug(f"Cached product for SKU: {sku}")
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    async def delete_product(self, sku: str) -> bool:
        """Delete cached product data."""
        try:
            cache_key = f"product:{sku}"
            await self.redis_client.delete(cache_key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    async def increment(self, key: str) -> int:
        """Increment a counter (for rate limiting)."""
        return await self.redis_client.incr(key)
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on a key."""
        return await self.redis_client.expire(key, seconds)
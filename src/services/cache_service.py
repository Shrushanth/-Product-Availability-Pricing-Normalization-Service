import json
import logging
from typing import Optional
import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from src.config import settings
from src.models.models import ProductResponse

logger = logging.getLogger(__name__)


class CacheService:
    """
    Async Redis-based caching service.
    
    Handles all cache operations including:
    - Product data caching with automatic expiration
    - Rate limiting via counters
    - Connection health monitoring
    - Graceful error handling (fail-open strategy)
    """
    
    def __init__(self):
        """Initialize cache service (connection happens in connect() method)."""
        self.redis_client: Optional[redis.Redis] = None
        self._cache_hits = 0
        self._cache_misses = 0
    
    async def connect(self) -> None:
        """
        Establish connection to Redis.
        
        Creates async Redis client with connection pooling.
        Verifies connection with ping.
        
        Raises:
            RedisConnectionError: If unable to connect to Redis
        """
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Verify connection
            await self.redis_client.ping()
            
            logger.info(
                f"Connected to Redis successfully at "
                f"{settings.REDIS_HOST}:{settings.REDIS_PORT}"
            )
            
        except RedisConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {e}")
            raise
    
    async def close(self) -> None:
        """
        Close Redis connection gracefully.
        
        Should be called during application shutdown.
        """
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")
    
    async def ping(self) -> bool:
        """
        Check Redis connection health.
        
        Returns:
            True if Redis is accessible, False otherwise
        """
        try:
            if not self.redis_client:
                return False
            return await self.redis_client.ping()
        except RedisError:
            logger.warning("Redis ping failed")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during Redis ping: {e}")
            return False
    
    async def get_product(self, sku: str) -> Optional[ProductResponse]:
        """
        Retrieve cached product data.
        
        Args:
            sku: Product SKU
            
        Returns:
            ProductResponse if cached, None if not found or error
        """
        try:
            cache_key = f"product:{sku}"
            data = await self.redis_client.get(cache_key)
            
            if data:
                logger.debug(f"Cache HIT for SKU: {sku}")
                self._cache_hits += 1
                
                # Deserialize JSON to ProductResponse
                product_dict = json.loads(data)
                return ProductResponse(**product_dict)
            
            logger.debug(f"Cache MISS for SKU: {sku}")
            self._cache_misses += 1
            return None
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to deserialize cached product {sku}: {e}")
            # Delete corrupted cache entry
            await self.delete_product(sku)
            return None
        except RedisError as e:
            logger.error(f"Redis error during cache get for {sku}: {e}")
            # Fail open - return None to allow fetching from vendors
            return None
        except Exception as e:
            logger.error(f"Unexpected error during cache get for {sku}: {e}")
            return None
    
    async def set_product(
        self,
        sku: str,
        product: ProductResponse,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache product data with TTL.
        
        Args:
            sku: Product SKU
            product: Product data to cache
            ttl: Time-to-live in seconds (defaults to config value)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cache_key = f"product:{sku}"
            
            # Serialize ProductResponse to JSON
            # model_dump() converts Pydantic model to dict
            # json.dumps() handles datetime serialization
            data = product.model_dump_json()
            
            # Set with TTL
            ttl_seconds = ttl or settings.CACHE_TTL_SECONDS
            await self.redis_client.setex(
                cache_key,
                ttl_seconds,
                data
            )
            
            logger.debug(
                f"Cached product for SKU: {sku} "
                f"(TTL: {ttl_seconds}s)"
            )
            return True
            
        except RedisError as e:
            logger.error(f"Redis error during cache set for {sku}: {e}")
            # Fail open - don't block the request
            return False
        except Exception as e:
            logger.error(f"Unexpected error during cache set for {sku}: {e}")
            return False
    
    async def delete_product(self, sku: str) -> bool:
        """
        Delete cached product data.
        
        Useful for cache invalidation or cleanup.
        
        Args:
            sku: Product SKU
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            cache_key = f"product:{sku}"
            result = await self.redis_client.delete(cache_key)
            
            if result:
                logger.debug(f"Deleted cached product: {sku}")
            
            return bool(result)
            
        except RedisError as e:
            logger.error(f"Redis error during cache delete for {sku}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during cache delete for {sku}: {e}")
            return False
    
    async def increment(self, key: str) -> int:
        """
        Increment a counter atomically.
        
        Used for rate limiting. Creates key if doesn't exist.
        
        Args:
            key: Counter key
            
        Returns:
            New counter value
            
        Raises:
            RedisError: If Redis operation fails
        """
        try:
            count = await self.redis_client.incr(key)
            return count
        except RedisError as e:
            logger.error(f"Redis error during increment for {key}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during increment for {key}: {e}")
            raise
    
    async def expire(self, key: str, seconds: int) -> bool:
        """
        Set expiration time on a key.
        
        Args:
            key: Key to expire
            seconds: TTL in seconds
            
        Returns:
            True if expiration was set, False otherwise
        """
        try:
            result = await self.redis_client.expire(key, seconds)
            return bool(result)
        except RedisError as e:
            logger.error(f"Redis error during expire for {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during expire for {key}: {e}")
            return False
    
    async def get_key(self, key: str) -> Optional[str]:
        """
        Get raw value for a key.
        
        Generic getter for non-product data.
        
        Args:
            key: Key to retrieve
            
        Returns:
            Value as string or None
        """
        try:
            return await self.redis_client.get(key)
        except RedisError as e:
            logger.error(f"Redis error during get for {key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during get for {key}: {e}")
            return None
    
    async def set_key(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set raw value for a key.
        
        Generic setter for non-product data.
        
        Args:
            key: Key to set
            value: Value to store
            ttl: Optional TTL in seconds
            
        Returns:
            True if successful
        """
        try:
            if ttl:
                await self.redis_client.setex(key, ttl, value)
            else:
                await self.redis_client.set(key, value)
            return True
        except RedisError as e:
            logger.error(f"Redis error during set for {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during set for {key}: {e}")
            return False
    
    def get_cache_stats(self) -> dict:
        """
        Get cache hit/miss statistics.
        
        Returns:
            Dictionary with cache metrics
        """
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0
        
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "total_requests": total,
            "hit_rate_percent": round(hit_rate, 2)
        }
    
    def reset_cache_stats(self) -> None:
        """Reset cache statistics counters."""
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("Cache statistics reset")
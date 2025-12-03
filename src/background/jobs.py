import asyncio
import logging
from datetime import datetime
from config import settings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.vendor_service import VendorService
    from services.cache_service import CacheService

logger = logging.getLogger(__name__)

async def prewarm_cache_task(
    vendor_service: "VendorService",
    cache_service: "CacheService"
) -> None:
    """Prewarm cache for popular SKUs."""
    popular_skus = settings.get_popular_skus_list()
    
    logger.info(f"Prewarming cache for {len(popular_skus)} popular SKUs")
    
    for sku in popular_skus:
        try:
            await vendor_service.get_best_vendor(sku)
        except Exception as e:
            logger.error(f"Error prewarming SKU {sku}: {e}")
    
    logger.info("Cache prewarming completed")

async def log_vendor_metrics_task(
    vendor_service: "VendorService"
) -> None:
    """Log vendor performance metrics."""
    if not settings.ENABLE_VENDOR_METRICS:
        return
    
    logger.info("=== Vendor Performance Metrics ===")
    
    for vendor_name in ["VendorOne", "VendorTwo", "VendorThree"]:
        breaker = vendor_service.circuit_breaker_manager.get_breaker(vendor_name)
        logger.info(
            f"{vendor_name}: "
            f"state={breaker.state}, "
            f"failures={breaker.failure_count}"
        )
    
    logger.info("=" * 35)

async def background_job_loop(
    vendor_service: "VendorService",
    cache_service: "CacheService"
) -> None:
    """Main background job loop."""
    interval_seconds = settings.CACHE_PREWARM_INTERVAL_MINUTES * 60
    
    while True:
        try:
            await prewarm_cache_task(vendor_service, cache_service)
            await log_vendor_metrics_task(vendor_service)
        except Exception as e:
            logger.error(f"Background job error: {e}")
        
        await asyncio.sleep(interval_seconds)

async def start_background_jobs(
    vendor_service: "VendorService",
    cache_service: "CacheService"
) -> None:
    """Start background jobs."""
    await background_job_loop(vendor_service, cache_service)

async def stop_background_jobs(task: asyncio.Task) -> None:
    """Stop background jobs."""
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info("Background jobs stopped")
import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from src.config import settings

# Type checking imports to avoid circular dependencies
if TYPE_CHECKING:
    from src.services.vendor_service import VendorService
    from src.services.cache_service import CacheService

logger = logging.getLogger(__name__)


async def prewarm_cache_task(
    vendor_service: "VendorService",
    cache_service: "CacheService"
) -> None:
    """
    Prewarm cache for popular SKUs.
    
    Fetches product data for frequently-requested SKUs to ensure
    they're always available in cache, reducing API latency for
    popular items.
    
    Args:
        vendor_service: Service for fetching vendor data
        cache_service: Service for caching results
    """
    popular_skus = settings.get_popular_skus_list()
    
    if not popular_skus:
        logger.warning("No popular SKUs configured for prewarming")
        return
    
    logger.info(
        f"🔥 Starting cache prewarm for {len(popular_skus)} popular SKUs: "
        f"{', '.join(popular_skus)}"
    )
    
    success_count = 0
    error_count = 0
    
    for sku in popular_skus:
        try:
            # Fetch product data (will cache automatically)
            result = await vendor_service.get_best_vendor(sku)
            
            if result:
                success_count += 1
                logger.debug(f"✅ Prewarmed cache for SKU: {sku}")
            else:
                logger.debug(f"⚠️  SKU {sku} out of stock (not cached)")
                
        except Exception as e:
            error_count += 1
            logger.error(f"❌ Error prewarming SKU {sku}: {str(e)}")
    
    logger.info(
        f"🔥 Cache prewarm completed: "
        f"{success_count} successful, {error_count} errors"
    )


async def log_vendor_metrics_task(
    vendor_service: "VendorService"
) -> None:
    """
    Log vendor performance metrics.
    
    Outputs circuit breaker states, failure rates, and health status
    for all vendors. Useful for monitoring and debugging.
    
    Args:
        vendor_service: Service with circuit breaker manager
    """
    if not settings.ENABLE_VENDOR_METRICS:
        logger.debug("Vendor metrics logging disabled")
        return
    
    logger.info("=" * 70)
    logger.info("📊 VENDOR PERFORMANCE METRICS")
    logger.info("=" * 70)
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    logger.info("-" * 70)
    
    # Get all circuit breaker metrics
    all_metrics = vendor_service.circuit_breaker_manager.get_all_metrics()
    
    for vendor_name, metrics in all_metrics.items():
        # Format state with emoji indicators
        state_emoji = {
            "closed": "✅",
            "open": "🔴",
            "half_open": "🟡"
        }
        
        state = metrics["state"]
        emoji = state_emoji.get(state, "❓")
        
        logger.info(f"\n{emoji} {vendor_name}")
        logger.info(f"   State: {state.upper()}")
        logger.info(f"   Total Calls: {metrics['total_calls']}")
        logger.info(f"   Failures: {metrics['total_failures']}")
        logger.info(f"   Failure Rate: {metrics['failure_rate_percent']}%")
        logger.info(
            f"   Time in Current State: "
            f"{metrics['time_in_current_state_seconds']}s"
        )
        
        if metrics['last_failure']:
            logger.info(f"   Last Failure: {metrics['last_failure']}")
    
    logger.info("\n" + "-" * 70)
    
    # Summary statistics
    healthy_vendors = vendor_service.circuit_breaker_manager.get_healthy_vendors()
    unhealthy_vendors = vendor_service.circuit_breaker_manager.get_unhealthy_vendors()
    
    logger.info(f"✅ Healthy Vendors: {len(healthy_vendors)}")
    logger.info(f"🔴 Unhealthy Vendors: {len(unhealthy_vendors)}")
    
    if unhealthy_vendors:
        logger.warning(
            f"⚠️  WARNING: Circuit breakers OPEN for: "
            f"{', '.join(unhealthy_vendors)}"
        )
    
    logger.info("=" * 70)


async def log_cache_metrics_task(
    cache_service: "CacheService"
) -> None:
    """
    Log cache performance metrics.
    
    Outputs cache hit/miss rates to monitor cache effectiveness.
    
    Args:
        cache_service: Service with cache statistics
    """
    if not settings.ENABLE_CACHE_METRICS:
        logger.debug("Cache metrics logging disabled")
        return
    
    stats = cache_service.get_cache_stats()
    
    logger.info("=" * 70)
    logger.info("💾 CACHE PERFORMANCE METRICS")
    logger.info("=" * 70)
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    logger.info("-" * 70)
    logger.info(f"Total Requests: {stats['total_requests']}")
    logger.info(f"Cache Hits: {stats['hits']}")
    logger.info(f"Cache Misses: {stats['misses']}")
    logger.info(f"Hit Rate: {stats['hit_rate_percent']}%")
    logger.info("=" * 70)


async def combined_metrics_task(
    vendor_service: "VendorService",
    cache_service: "CacheService"
) -> None:
    """
    Run all metrics logging tasks.
    
    Combines vendor metrics and cache metrics into one report.
    
    Args:
        vendor_service: Service for vendor metrics
        cache_service: Service for cache metrics
    """
    await log_vendor_metrics_task(vendor_service)
    await log_cache_metrics_task(cache_service)


async def background_job_loop(
    vendor_service: "VendorService",
    cache_service: "CacheService"
) -> None:
    """
    Main background job loop.
    
    Runs scheduled tasks at configured intervals:
    - Cache prewarming every N minutes
    - Metrics logging every N minutes
    
    This loop runs indefinitely until cancelled.
    
    Args:
        vendor_service: Service for vendor operations
        cache_service: Service for cache operations
    """
    interval_seconds = settings.CACHE_PREWARM_INTERVAL_MINUTES * 60
    
    logger.info(
        f"🚀 Background jobs starting (interval: "
        f"{settings.CACHE_PREWARM_INTERVAL_MINUTES} minutes)"
    )
    
    # Run initial prewarm immediately on startup
    try:
        await prewarm_cache_task(vendor_service, cache_service)
        await combined_metrics_task(vendor_service, cache_service)
    except Exception as e:
        logger.error(f"Error in initial background tasks: {e}", exc_info=True)
    
    # Main loop
    iteration = 0
    while True:
        try:
            iteration += 1
            logger.debug(
                f"⏰ Background job iteration {iteration} - "
                f"sleeping for {interval_seconds}s"
            )
            
            # Wait for next interval
            await asyncio.sleep(interval_seconds)
            
            logger.info(
                f"🔄 Running scheduled background tasks "
                f"(iteration {iteration})"
            )
            
            # Run cache prewarming
            await prewarm_cache_task(vendor_service, cache_service)
            
            # Run metrics logging
            await combined_metrics_task(vendor_service, cache_service)
            
        except asyncio.CancelledError:
            logger.info("🛑 Background job loop cancelled")
            break
        except Exception as e:
            logger.error(
                f"Error in background job iteration {iteration}: {e}",
                exc_info=True
            )
            # Continue running despite errors
            continue


async def start_background_jobs(
    vendor_service: "VendorService",
    cache_service: "CacheService"
) -> None:
    """
    Start background jobs.
    
    Entry point for background job system. Called during app startup.
    
    Args:
        vendor_service: Service for vendor operations
        cache_service: Service for cache operations
    """
    try:
        await background_job_loop(vendor_service, cache_service)
    except asyncio.CancelledError:
        logger.info("Background jobs stopped gracefully")
    except Exception as e:
        logger.error(f"Fatal error in background jobs: {e}", exc_info=True)
        raise


async def stop_background_jobs(task: asyncio.Task) -> None:
    """
    Stop background jobs gracefully.
    
    Called during app shutdown. Cancels the background task and
    waits for it to finish.
    
    Args:
        task: The background job task to stop
    """
    if task and not task.done():
        logger.info("🛑 Stopping background jobs...")
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            logger.info("✅ Background jobs stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping background jobs: {e}")


# Additional utility functions for manual triggering

async def trigger_cache_prewarm_now(
    vendor_service: "VendorService",
    cache_service: "CacheService"
) -> dict:
    """
    Manually trigger cache prewarming.
    
    Useful for API endpoint or administrative command.
    
    Returns:
        Dictionary with prewarm results
    """
    logger.info("🔥 Manual cache prewarm triggered")
    
    start_time = asyncio.get_event_loop().time()
    await prewarm_cache_task(vendor_service, cache_service)
    elapsed = asyncio.get_event_loop().time() - start_time
    
    return {
        "status": "completed",
        "skus_count": len(settings.get_popular_skus_list()),
        "elapsed_seconds": round(elapsed, 2)
    }


async def trigger_metrics_log_now(
    vendor_service: "VendorService",
    cache_service: "CacheService"
) -> dict:
    """
    Manually trigger metrics logging.
    
    Useful for API endpoint or administrative command.
    
    Returns:
        Dictionary with metrics
    """
    logger.info("📊 Manual metrics logging triggered")
    
    await combined_metrics_task(vendor_service, cache_service)
    
    return {
        "status": "completed",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "vendor_metrics": vendor_service.circuit_breaker_manager.get_all_metrics(),
        "cache_metrics": cache_service.get_cache_stats()
    }
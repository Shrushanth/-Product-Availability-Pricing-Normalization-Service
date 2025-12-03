from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from config import settings
from models.models import ProductResponse, ErrorResponse
from services.vendor_service import VendorService
from services.cache_service import CacheService
from services.circuit_breaker import CircuitBreakerManager
from middleware.rate_limit import RateLimiter
from background.jobs import start_background_jobs, stop_background_jobs
import logging
import re

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events:
    - Startup: Initialize Redis, circuit breakers, and background jobs
    - Shutdown: Clean up resources and stop background tasks
    """
    logger.info("Starting up Product Availability Service...")
    
    # Initialize Redis cache
    cache_service = CacheService()
    await cache_service.connect()
    app.state.cache_service = cache_service
    
    # Initialize circuit breaker manager
    circuit_breaker_manager = CircuitBreakerManager()
    app.state.circuit_breaker_manager = circuit_breaker_manager
    
    # Initialize vendor service
    vendor_service = VendorService(cache_service, circuit_breaker_manager)
    app.state.vendor_service = vendor_service
    
    # Initialize rate limiter
    rate_limiter = RateLimiter(cache_service)
    app.state.rate_limiter = rate_limiter
    
    # Start background jobs
    background_task = asyncio.create_task(
        start_background_jobs(vendor_service, cache_service)
    )
    app.state.background_task = background_task
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Product Availability Service...")
    
    # Stop background jobs
    await stop_background_jobs(background_task)
    
    # Close Redis connection
    await cache_service.close()
    
    logger.info("Application shutdown complete")


# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A microservice for normalizing product availability and pricing from multiple vendors",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware for rate limiting
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware.
    
    Enforces rate limits per API key (60 requests per minute).
    Returns 429 Too Many Requests if limit exceeded.
    """
    # Skip rate limiting for health check and docs
    if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
        return await call_next(request)
    
    api_key = request.headers.get("x-api-key")
    
    if not api_key:
        return JSONResponse(
            status_code=401,
            content={"error": "Missing API key", "message": "x-api-key header is required"}
        )
    
    # Validate API key
    if api_key not in settings.VALID_API_KEYS:
        return JSONResponse(
            status_code=403,
            content={"error": "Invalid API key", "message": "The provided API key is not valid"}
        )
    
    # Check rate limit
    rate_limiter: RateLimiter = request.app.state.rate_limiter
    allowed = await rate_limiter.check_rate_limit(api_key)
    
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": f"Maximum {settings.RATE_LIMIT_REQUESTS} requests per {settings.RATE_LIMIT_WINDOW_SECONDS} seconds"
            }
        )
    
    response = await call_next(request)
    return response


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """Root endpoint returning service information."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health_check(request: Request) -> dict[str, str]:
    """
    Health check endpoint.
    
    Returns the health status of the service and its dependencies.
    """
    cache_service: CacheService = request.app.state.cache_service
    
    # Check Redis connection
    redis_healthy = await cache_service.ping()
    
    if redis_healthy:
        return {
            "status": "healthy",
            "redis": "connected",
            "service": settings.APP_NAME
        }
    else:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "redis": "disconnected",
                "service": settings.APP_NAME
            }
        )


def validate_sku(sku: str) -> None:
    """
    Validate SKU format.
    
    Requirements:
    - Alphanumeric characters only
    - Length between 3 and 20 characters
    
    Args:
        sku: The SKU to validate
        
    Raises:
        HTTPException: If SKU is invalid
    """
    if not sku:
        raise HTTPException(
            status_code=400,
            detail="SKU is required"
        )
    
    if len(sku) < 3 or len(sku) > 20:
        raise HTTPException(
            status_code=400,
            detail="SKU must be between 3 and 20 characters"
        )
    
    if not re.match(r'^[a-zA-Z0-9]+$', sku):
        raise HTTPException(
            status_code=400,
            detail="SKU must contain only alphanumeric characters"
        )


@app.get(
    "/products/{sku}",
    response_model=ProductResponse,
    responses={
        200: {"description": "Product found with best vendor"},
        400: {"description": "Invalid SKU format"},
        401: {"description": "Missing API key"},
        403: {"description": "Invalid API key"},
        404: {"description": "Product out of stock from all vendors"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    },
    tags=["Products"]
)
async def get_product(
    sku: str,
    request: Request,
    x_api_key: str = Header(..., description="API key for authentication")
) -> ProductResponse:
    """
    Get product availability and pricing from the best vendor.
    
    This endpoint:
    1. Validates the SKU format
    2. Checks cache for recent results
    3. Queries all vendors concurrently
    4. Normalizes vendor responses
    5. Applies business rules to select best vendor
    6. Caches the result
    
    Args:
        sku: Product SKU (alphanumeric, 3-20 chars)
        request: FastAPI request object
        x_api_key: API key for authentication (header)
        
    Returns:
        ProductResponse with best vendor information or OUT_OF_STOCK status
        
    Raises:
        HTTPException: For invalid SKU or other errors
    """
    # Validate SKU format
    validate_sku(sku)
    
    # Get vendor service
    vendor_service: VendorService = request.app.state.vendor_service
    
    try:
        # Get best vendor for product
        result = await vendor_service.get_best_vendor(sku)
        
        if result:
            return result
        else:
            # Product out of stock from all vendors
            raise HTTPException(
                status_code=404,
                detail={
                    "sku": sku,
                    "status": "OUT_OF_STOCK",
                    "message": "Product not available from any vendor"
                }
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing request for SKU {sku}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your request"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled exceptions.
    
    Logs the error and returns a generic error response.
    """
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
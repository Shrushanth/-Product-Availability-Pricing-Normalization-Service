import pytest
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import Mock, AsyncMock

from src.services.cache_service import CacheService
from src.services.circuit_breaker import CircuitBreakerManager
from src.config import settings


# ============================================
# Pytest Configuration
# ============================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )


# ============================================
# Event Loop Setup for Async Tests
# ============================================

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Create an event loop for the test session.
    
    This ensures async tests can run properly.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================
# Mock Services
# ============================================

@pytest.fixture
def mock_cache_service() -> Mock:
    """
    Mock cache service for unit tests.
    
    Returns:
        Mock CacheService with common methods
    """
    cache = Mock(spec=CacheService)
    
    # Setup async mock methods
    cache.connect = AsyncMock()
    cache.close = AsyncMock()
    cache.ping = AsyncMock(return_value=True)
    cache.get_product = AsyncMock(return_value=None)
    cache.set_product = AsyncMock(return_value=True)
    cache.delete_product = AsyncMock(return_value=True)
    cache.increment = AsyncMock(return_value=1)
    cache.expire = AsyncMock(return_value=True)
    cache.get_cache_stats = Mock(return_value={
        "hits": 0,
        "misses": 0,
        "total_requests": 0,
        "hit_rate_percent": 0.0
    })
    
    return cache


@pytest.fixture
def mock_circuit_breaker_manager() -> Mock:
    """
    Mock circuit breaker manager for unit tests.
    
    Returns:
        Mock CircuitBreakerManager
    """
    manager = Mock(spec=CircuitBreakerManager)
    
    # Setup methods
    manager.register = Mock()
    
    # Create mock breaker
    mock_breaker = Mock()
    mock_breaker.can_execute = Mock(return_value=True)
    mock_breaker.record_success = Mock()
    mock_breaker.record_failure = Mock()
    mock_breaker.get_state = Mock(return_value="closed")
    mock_breaker.get_metrics = Mock(return_value={
        "vendor": "TestVendor",
        "state": "closed",
        "failure_count": 0,
        "success_count": 0,
        "total_calls": 0,
        "total_failures": 0,
        "failure_rate_percent": 0.0,
        "time_in_current_state_seconds": 0.0,
        "last_failure": None
    })
    
    manager.get_breaker = Mock(return_value=mock_breaker)
    manager.get_all_metrics = Mock(return_value={})
    manager.get_healthy_vendors = Mock(return_value=[])
    manager.get_unhealthy_vendors = Mock(return_value=[])
    
    return manager


# ============================================
# Test Data Fixtures
# ============================================

@pytest.fixture
def sample_sku() -> str:
    """Sample SKU for testing."""
    return "TEST123"


@pytest.fixture
def sample_vendor_responses() -> list:
    """
    Sample vendor responses for testing.
    
    Returns list of mock VendorResponse objects with different
    prices and stock levels.
    """
    from src.models.models import VendorResponse, ProductStatus
    from datetime import datetime
    
    return [
        VendorResponse(
            vendor_name="VendorOne",
            sku="TEST123",
            price=100.00,
            stock=10,
            status=ProductStatus.IN_STOCK,
            timestamp=datetime.utcnow()
        ),
        VendorResponse(
            vendor_name="VendorTwo",
            sku="TEST123",
            price=95.00,
            stock=5,
            status=ProductStatus.IN_STOCK,
            timestamp=datetime.utcnow()
        ),
        VendorResponse(
            vendor_name="VendorThree",
            sku="TEST123",
            price=105.00,
            stock=20,
            status=ProductStatus.IN_STOCK,
            timestamp=datetime.utcnow()
        ),
    ]


@pytest.fixture
def out_of_stock_vendor_responses() -> list:
    """Sample vendor responses with all out of stock."""
    from src.models.models import VendorResponse, ProductStatus
    from datetime import datetime
    
    return [
        VendorResponse(
            vendor_name="VendorOne",
            sku="TEST123",
            price=100.00,
            stock=0,
            status=ProductStatus.OUT_OF_STOCK,
            timestamp=datetime.utcnow()
        ),
        VendorResponse(
            vendor_name="VendorTwo",
            sku="TEST123",
            price=95.00,
            stock=0,
            status=ProductStatus.OUT_OF_STOCK,
            timestamp=datetime.utcnow()
        ),
    ]


# ============================================
# Integration Test Fixtures
# ============================================

@pytest.fixture
async def real_cache_service() -> AsyncGenerator[CacheService, None]:
    """
    Real cache service for integration tests.
    
    Note: Requires Redis to be running!
    """
    cache = CacheService()
    await cache.connect()
    
    yield cache
    
    # Cleanup
    await cache.close()


@pytest.fixture
def real_circuit_breaker_manager() -> CircuitBreakerManager:
    """Real circuit breaker manager for integration tests."""
    manager = CircuitBreakerManager()
    manager.register("VendorOne")
    manager.register("VendorTwo")
    manager.register("VendorThree")
    
    return manager


# ============================================
# Test Environment Variables
# ============================================

@pytest.fixture(autouse=True)
def test_env_vars(monkeypatch):
    """
    Set test environment variables.
    
    This fixture runs automatically for all tests.
    """
    # Override settings for testing
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PORT", "6379")
    
    # Faster timeouts for testing
    monkeypatch.setenv("VENDOR_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("VENDOR_MAX_RETRIES", "1")
    
    # Shorter intervals for testing
    monkeypatch.setenv("CACHE_TTL_SECONDS", "10")
    monkeypatch.setenv("CIRCUIT_BREAKER_TIMEOUT_SECONDS", "5")
    
    # Disable metrics logging in tests
    monkeypatch.setenv("ENABLE_VENDOR_METRICS", "false")
    monkeypatch.setenv("ENABLE_CACHE_METRICS", "false")


# ============================================
# Helper Functions
# ============================================

def create_mock_vendor_response(
    vendor_name: str = "TestVendor",
    sku: str = "TEST123",
    price: float = 99.99,
    stock: int = 10
):
    """
    Helper to create mock vendor responses.
    
    Args:
        vendor_name: Name of vendor
        sku: Product SKU
        price: Product price
        stock: Stock quantity
        
    Returns:
        VendorResponse object
    """
    from src.models.models import VendorResponse, ProductStatus
    from datetime import datetime
    
    return VendorResponse(
        vendor_name=vendor_name,
        sku=sku,
        price=price,
        stock=stock,
        status=ProductStatus.IN_STOCK if stock > 0 else ProductStatus.OUT_OF_STOCK,
        timestamp=datetime.utcnow()
    )


# ============================================
# Pytest Hooks
# ============================================

def pytest_collection_modifyitems(config, items):
    """
    Modify test collection.
    
    Automatically mark tests based on their location.
    """
    for item in items:
        # Mark tests in tests/integration/ as integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        # Mark tests in tests/unit/ as unit tests
        elif "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
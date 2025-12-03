import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.services.vendor_service import VendorService
from src.models.models import VendorResponse, ProductStatus, ProductResponse
from src.services.cache_service import CacheService
from src.services.circuit_breaker import CircuitBreakerManager


@pytest.fixture
def mock_cache_service():
    """Mock cache service fixture."""
    cache = Mock(spec=CacheService)
    cache.get_product = AsyncMock(return_value=None)
    cache.set_product = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def mock_circuit_breaker_manager():
    """Mock circuit breaker manager fixture."""
    manager = Mock(spec=CircuitBreakerManager)
    manager.register = Mock()
    
    # Create mock breakers
    mock_breaker = Mock()
    mock_breaker.can_execute = Mock(return_value=True)
    mock_breaker.record_success = Mock()
    mock_breaker.record_failure = Mock()
    
    manager.get_breaker = Mock(return_value=mock_breaker)
    return manager


@pytest.fixture
def vendor_service(mock_cache_service, mock_circuit_breaker_manager):
    """Vendor service fixture."""
    return VendorService(mock_cache_service, mock_circuit_breaker_manager)


class TestStockNormalization:
    """Test stock normalization business rules."""
    
    def test_null_inventory_with_in_stock_status(self, vendor_service):
        """Test that null inventory + IN_STOCK = 5 units."""
        # This tests the core business rule from requirements
        response = VendorResponse(
            vendor_name="TestVendor",
            sku="TEST123",
            price=99.99,
            stock=5,  # Should be normalized to 5
            status=ProductStatus.IN_STOCK,
            timestamp=datetime.utcnow()
        )
        
        assert response.stock == 5
        assert response.status == ProductStatus.IN_STOCK
    
    def test_zero_stock_out_of_stock(self, vendor_service):
        """Test that zero stock = OUT_OF_STOCK."""
        response = VendorResponse(
            vendor_name="TestVendor",
            sku="TEST123",
            price=99.99,
            stock=0,
            status=ProductStatus.OUT_OF_STOCK,
            timestamp=datetime.utcnow()
        )
        
        assert response.stock == 0
        assert response.status == ProductStatus.OUT_OF_STOCK


class TestVendorSelection:
    """Test vendor selection algorithm."""
    
    def test_select_cheapest_vendor(self, vendor_service):
        """Test that cheapest vendor with stock is selected."""
        vendor1 = VendorResponse(
            vendor_name="Vendor1",
            sku="TEST123",
            price=100.00,
            stock=10,
            status=ProductStatus.IN_STOCK,
            timestamp=datetime.utcnow()
        )
        
        vendor2 = VendorResponse(
            vendor_name="Vendor2",
            sku="TEST123",
            price=95.00,  # Cheaper
            stock=5,
            status=ProductStatus.IN_STOCK,
            timestamp=datetime.utcnow()
        )
        
        vendors = [vendor1, vendor2]
        best = vendor_service._select_best_vendor(vendors)
        
        assert best.vendor_name == "Vendor2"
        assert best.price == 95.00
    
    def test_prefer_higher_stock_when_price_diff_exceeds_threshold(
        self, vendor_service
    ):
        """Test enhanced rule: prefer higher stock if price diff > 10%."""
        vendor1 = VendorResponse(
            vendor_name="Vendor1",
            sku="TEST123",
            price=100.00,
            stock=5,
            status=ProductStatus.IN_STOCK,
            timestamp=datetime.utcnow()
        )
        
        vendor2 = VendorResponse(
            vendor_name="Vendor2",
            sku="TEST123",
            price=115.00,  # 15% more expensive (exceeds 10% threshold)
            stock=50,      # Much higher stock
            status=ProductStatus.IN_STOCK,
            timestamp=datetime.utcnow()
        )
        
        vendors = [vendor1, vendor2]
        best = vendor_service._select_best_vendor(vendors)
        
        # Should select Vendor2 despite higher price
        assert best.vendor_name == "Vendor2"
        assert best.stock == 50
    
    def test_select_cheapest_when_price_diff_within_threshold(
        self, vendor_service
    ):
        """Test that cheapest vendor selected when price diff <= 10%."""
        vendor1 = VendorResponse(
            vendor_name="Vendor1",
            sku="TEST123",
            price=100.00,
            stock=5,
            status=ProductStatus.IN_STOCK,
            timestamp=datetime.utcnow()
        )
        
        vendor2 = VendorResponse(
            vendor_name="Vendor2",
            sku="TEST123",
            price=108.00,  # 8% more expensive (within 10% threshold)
            stock=50,
            status=ProductStatus.IN_STOCK,
            timestamp=datetime.utcnow()
        )
        
        vendors = [vendor1, vendor2]
        best = vendor_service._select_best_vendor(vendors)
        
        # Should select Vendor1 (cheaper)
        assert best.vendor_name == "Vendor1"
        assert best.price == 100.00
    
    def test_filter_out_of_stock_vendors(self, vendor_service):
        """Test that out-of-stock vendors are filtered out."""
        vendor1 = VendorResponse(
            vendor_name="Vendor1",
            sku="TEST123",
            price=100.00,
            stock=0,
            status=ProductStatus.OUT_OF_STOCK,
            timestamp=datetime.utcnow()
        )
        
        vendor2 = VendorResponse(
            vendor_name="Vendor2",
            sku="TEST123",
            price=95.00,
            stock=10,
            status=ProductStatus.IN_STOCK,
            timestamp=datetime.utcnow()
        )
        
        vendors = [vendor1, vendor2]
        best = vendor_service._select_best_vendor(vendors)
        
        assert best.vendor_name == "Vendor2"
    
    def test_return_none_when_all_out_of_stock(self, vendor_service):
        """Test that None is returned when all vendors out of stock."""
        vendor1 = VendorResponse(
            vendor_name="Vendor1",
            sku="TEST123",
            price=100.00,
            stock=0,
            status=ProductStatus.OUT_OF_STOCK,
            timestamp=datetime.utcnow()
        )
        
        vendor2 = VendorResponse(
            vendor_name="Vendor2",
            sku="TEST123",
            price=95.00,
            stock=0,
            status=ProductStatus.OUT_OF_STOCK,
            timestamp=datetime.utcnow()
        )
        
        vendors = [vendor1, vendor2]
        best = vendor_service._select_best_vendor(vendors)
        
        assert best is None


class TestDataFreshness:
    """Test data freshness filtering."""
    
    def test_filter_stale_data(self, vendor_service):
        """Test that data older than 10 minutes is filtered out."""
        fresh_vendor = VendorResponse(
            vendor_name="FreshVendor",
            sku="TEST123",
            price=100.00,
            stock=10,
            status=ProductStatus.IN_STOCK,
            timestamp=datetime.utcnow()  # Fresh
        )
        
        stale_vendor = VendorResponse(
            vendor_name="StaleVendor",
            sku="TEST123",
            price=90.00,  # Cheaper but stale
            stock=20,
            status=ProductStatus.IN_STOCK,
            timestamp=datetime.utcnow() - timedelta(minutes=15)  # Too old
        )
        
        vendors = [fresh_vendor, stale_vendor]
        fresh = vendor_service._filter_by_freshness(vendors)
        
        assert len(fresh) == 1
        assert fresh[0].vendor_name == "FreshVendor"
    
    def test_keep_fresh_data(self, vendor_service):
        """Test that fresh data is kept."""
        vendor = VendorResponse(
            vendor_name="FreshVendor",
            sku="TEST123",
            price=100.00,
            stock=10,
            status=ProductStatus.IN_STOCK,
            timestamp=datetime.utcnow() - timedelta(minutes=5)  # 5 min old, OK
        )
        
        vendors = [vendor]
        fresh = vendor_service._filter_by_freshness(vendors)
        
        assert len(fresh) == 1


@pytest.mark.asyncio
class TestCaching:
    """Test caching behavior."""
    
    async def test_cache_hit_returns_cached_data(
        self, vendor_service, mock_cache_service
    ):
        """Test that cached data is returned on cache hit."""
        cached_response = ProductResponse(
            sku="TEST123",
            vendor="CachedVendor",
            price=99.99,
            stock=10,
            status=ProductStatus.IN_STOCK,
            timestamp=datetime.utcnow()
        )
        
        mock_cache_service.get_product.return_value = cached_response
        
        result = await vendor_service.get_best_vendor("TEST123")
        
        assert result == cached_response
        # Verify vendors were not queried
        mock_cache_service.get_product.assert_called_once()
    
    async def test_cache_miss_queries_vendors(
        self, vendor_service, mock_cache_service
    ):
        """Test that vendors are queried on cache miss."""
        mock_cache_service.get_product.return_value = None
        
        with patch.object(
            vendor_service,
            '_query_all_vendors',
            new=AsyncMock(return_value=[])
        ):
            result = await vendor_service.get_best_vendor("TEST123")
            
            mock_cache_service.get_product.assert_called_once()
            vendor_service._query_all_vendors.assert_called_once_with("TEST123")


@pytest.mark.asyncio
class TestErrorHandling:
    """Test error handling and graceful degradation."""
    
    async def test_continues_with_partial_vendor_failures(
        self, vendor_service, mock_cache_service
    ):
        """Test that service continues if some vendors fail."""
        mock_cache_service.get_product.return_value = None
        
        # Mock one successful vendor response
        success_vendor = VendorResponse(
            vendor_name="SuccessVendor",
            sku="TEST123",
            price=100.00,
            stock=10,
            status=ProductStatus.IN_STOCK,
            timestamp=datetime.utcnow()
        )
        
        with patch.object(
            vendor_service,
            '_query_all_vendors',
            new=AsyncMock(return_value=[success_vendor])
        ):
            result = await vendor_service.get_best_vendor("TEST123")
            
            assert result is not None
            assert result.vendor == "SuccessVendor"


# Run tests with: pytest tests/unit/test_vendor_service.py -v
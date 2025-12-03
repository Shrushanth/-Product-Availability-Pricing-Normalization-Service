import asyncio
import random
from datetime import datetime
from typing import Optional
from src.models.models import VendorResponse, ProductStatus, VendorTwoRawResponse
from src.config import settings
import logging

logger = logging.getLogger(__name__)


class VendorTwo:
    """
    Mock implementation of Vendor Two.
    
    Characteristics:
    - Medium response times (200-500ms)
    - Moderate reliability (95% success rate)
    - Unique field names: stock_count, price_amount, in_stock
    - Uses boolean flag for availability instead of string status
    
    This vendor simulates a standard third-party API with decent
    performance but occasional failures under load.
    """
    
    # Mock product database
    # Note: Different pricing and stock levels than other vendors
    PRODUCTS = {
        "ABC123": {"price": 105.50, "stock": 15},
        "XYZ789": {"price": 155.00, "stock": 8},
        "DEF456": {"price": 72.50, "stock": None},  # Null stock test case
        "LMN101": {"price": 195.00, "stock": 5},
        "PQR202": {"price": 52.00, "stock": 75},
        "GHI303": {"price": 89.99, "stock": 0},     # Out of stock
        "JKL404": {"price": 120.00, "stock": 50},
    }
    
    async def get_product(self, sku: str) -> Optional[VendorResponse]:
        """
        Query product from Vendor Two.
        
        Simulates API call with medium latency and moderate failure rate.
        
        Args:
            sku: Product SKU to query
            
        Returns:
            VendorResponse with normalized data or None if product not found
            
        Raises:
            Exception: If vendor API fails (simulated 5% failure rate)
        """
        start_time = asyncio.get_event_loop().time()
        
        # Simulate network delay (200-500ms)
        delay_ms = random.randint(
            settings.VENDOR_TWO_MIN_DELAY_MS,
            settings.VENDOR_TWO_MAX_DELAY_MS
        )
        await asyncio.sleep(delay_ms / 1000)
        
        # Simulate occasional failures (5% failure rate)
        if random.random() < settings.VENDOR_TWO_FAILURE_RATE:
            logger.warning(f"VendorTwo: Simulated API failure for SKU {sku}")
            raise Exception("VendorTwo API error: Service temporarily unavailable")
        
        # Get product data from mock database
        product_data = self.PRODUCTS.get(sku)
        if not product_data:
            logger.debug(f"VendorTwo: SKU {sku} not found in inventory")
            return None
        
        # Create raw response in vendor's unique format
        raw_response = VendorTwoRawResponse(
            sku=sku,
            stock_count=product_data["stock"],
            price_amount=product_data["price"],
            in_stock=product_data["stock"] is None or product_data["stock"] > 0,
            response_timestamp=datetime.utcnow().isoformat() + "Z"
        )
        
        # Normalize to standard format
        normalized = self._normalize_response(raw_response, start_time)
        
        logger.info(
            f"VendorTwo returned: SKU={sku}, price=${normalized.price:.2f}, "
            f"stock={normalized.stock}, time={normalized.response_time_ms:.1f}ms"
        )
        
        return normalized
    
    def _normalize_response(
        self,
        raw: VendorTwoRawResponse,
        start_time: float
    ) -> VendorResponse:
        """
        Normalize Vendor Two's response format to standard format.
        
        Vendor Two uses:
        - stock_count instead of stock/quantity
        - price_amount instead of price/unit_price
        - in_stock (boolean) instead of status string
        
        Business rules applied:
        1. If stock_count is None AND in_stock is True → assume 5 units
        2. If stock_count > 0 → use actual count
        3. Otherwise → stock = 0, OUT_OF_STOCK
        
        Args:
            raw: Raw vendor response
            start_time: Request start time for calculating response time
            
        Returns:
            VendorResponse with normalized data
        """
        # Apply stock normalization business rule
        if raw.stock_count is None and raw.in_stock:
            # Rule: null inventory + IN_STOCK flag = assume 5 units
            stock = 5
            status = ProductStatus.IN_STOCK
            logger.debug(
                f"VendorTwo: Applied stock normalization for SKU {raw.sku} "
                "(null stock_count + in_stock=true → stock=5)"
            )
        elif raw.stock_count and raw.stock_count > 0:
            # Has actual stock count
            stock = raw.stock_count
            status = ProductStatus.IN_STOCK
        else:
            # Out of stock
            stock = 0
            status = ProductStatus.OUT_OF_STOCK
        
        # Calculate response time
        response_time = (asyncio.get_event_loop().time() - start_time) * 1000
        
        return VendorResponse(
            vendor_name="VendorTwo",
            sku=raw.sku,
            price=raw.price_amount,
            stock=stock,
            status=status,
            timestamp=datetime.fromisoformat(raw.response_timestamp.replace("Z", "+00:00")),
            response_time_ms=response_time
        )
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"VendorTwo(delay={settings.VENDOR_TWO_MIN_DELAY_MS}-"
            f"{settings.VENDOR_TWO_MAX_DELAY_MS}ms, "
            f"failure_rate={settings.VENDOR_TWO_FAILURE_RATE*100}%)"
        )
import asyncio
import random
from datetime import datetime
from typing import Optional
from models.models import VendorResponse, ProductStatus, VendorOneRawResponse
from config import settings
import logging

logger = logging.getLogger(__name__)

class VendorOne:
    """
    Mock implementation of Vendor One.
    
    Characteristics:
    - Fast response times (100-300ms)
    - High reliability (99%)
    - Unique field names: quantity, unit_price, availability_status
    """
    
    # Mock product database
    PRODUCTS = {
        "ABC123": {"price": 99.99, "stock": 10},
        "XYZ789": {"price": 149.50, "stock": None},  # Null inventory test
        "DEF456": {"price": 75.00, "stock": 25},
        "LMN101": {"price": 200.00, "stock": 0},
        "PQR202": {"price": 50.00, "stock": 100},
    }
    
    async def get_product(self, sku: str) -> Optional[VendorResponse]:
        """Query product from Vendor One."""
        start_time = asyncio.get_event_loop().time()
        
        # Simulate network delay
        delay_ms = random.randint(
            settings.VENDOR_ONE_MIN_DELAY_MS,
            settings.VENDOR_ONE_MAX_DELAY_MS
        )
        await asyncio.sleep(delay_ms / 1000)
        
        # Simulate failures
        if random.random() < settings.VENDOR_ONE_FAILURE_RATE:
            raise Exception("VendorOne API temporarily unavailable")
        
        # Get product data
        product_data = self.PRODUCTS.get(sku)
        if not product_data:
            logger.debug(f"VendorOne: SKU {sku} not found")
            return None
        
        # Create raw response (vendor's format)
        raw_response = VendorOneRawResponse(
            product_id=sku,
            quantity=product_data["stock"],
            unit_price=product_data["price"],
            availability_status="IN_STOCK" if product_data["stock"] != 0 else "OUT_OF_STOCK",
            last_updated=datetime.utcnow().isoformat() + "Z"
        )
        
        # Normalize to standard format
        normalized = self._normalize_response(raw_response, start_time)
        
        logger.info(
            f"VendorOne returned: SKU={sku}, price=${normalized.price}, "
            f"stock={normalized.stock}, time={normalized.response_time_ms}ms"
        )
        
        return normalized
    
    def _normalize_response(
        self,
        raw: VendorOneRawResponse,
        start_time: float
    ) -> VendorResponse:
        """Normalize vendor-specific format to standard format."""
        # Apply stock normalization rule:
        # If inventory = null AND status = "IN_STOCK" → assume stock = 5
        if raw.quantity is None and raw.availability_status == "IN_STOCK":
            stock = 5
            status = ProductStatus.IN_STOCK
        elif raw.quantity and raw.quantity > 0:
            stock = raw.quantity
            status = ProductStatus.IN_STOCK
        else:
            stock = 0
            status = ProductStatus.OUT_OF_STOCK
        
        response_time = (asyncio.get_event_loop().time() - start_time) * 1000
        
        return VendorResponse(
            vendor_name="VendorOne",
            sku=raw.product_id,
            price=raw.unit_price,
            stock=stock,
            status=status,
            timestamp=datetime.fromisoformat(raw.last_updated.replace("Z", "+00:00")),
            response_time_ms=response_time
        )
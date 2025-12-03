import asyncio
import logging
from typing import Optional, List
from datetime import datetime, timedelta

from models.models import VendorResponse, ProductResponse, ProductStatus
from config import settings
from vendors.vendor_one import VendorOne
from vendors.vendor_two import VendorTwo
from vendors.vendor_three import VendorThree
from services.cache_service import CacheService
from services.circuit_breaker import CircuitBreakerManager

logger = logging.getLogger(__name__)


class VendorService:
    """
    Service for managing vendor integrations and product queries.
    
    Coordinates querying multiple vendors, normalizing responses,
    and selecting the best vendor based on business rules.
    """
    
    def __init__(
        self,
        cache_service: CacheService,
        circuit_breaker_manager: CircuitBreakerManager
    ):
        """
        Initialize vendor service.
        
        Args:
            cache_service: Cache service instance
            circuit_breaker_manager: Circuit breaker manager instance
        """
        self.cache_service = cache_service
        self.circuit_breaker_manager = circuit_breaker_manager
        
        # Initialize vendor clients
        self.vendor_one = VendorOne()
        self.vendor_two = VendorTwo()
        self.vendor_three = VendorThree()
        
        # Register circuit breakers for each vendor
        self.circuit_breaker_manager.register("VendorOne")
        self.circuit_breaker_manager.register("VendorTwo")
        self.circuit_breaker_manager.register("VendorThree")
        
        logger.info("VendorService initialized with 3 vendors")
    
    async def get_best_vendor(self, sku: str) -> Optional[ProductResponse]:
        """
        Get the best vendor for a given SKU.
        
        Process:
        1. Check cache for recent result
        2. Query all vendors concurrently
        3. Normalize responses
        4. Filter by data freshness
        5. Apply business rules to select best vendor
        6. Cache the result
        
        Args:
            sku: Product SKU to query
            
        Returns:
            ProductResponse with best vendor or None if out of stock
        """
        # Check cache first
        cached_result = await self.cache_service.get_product(sku)
        if cached_result:
            logger.info(f"Cache hit for SKU: {sku}")
            return cached_result
        
        logger.info(f"Cache miss for SKU: {sku}, querying vendors")
        
        # Query all vendors concurrently
        vendor_responses = await self._query_all_vendors(sku)
        
        # Filter responses by data freshness (must be within last 10 minutes)
        fresh_responses = self._filter_by_freshness(vendor_responses)
        
        if not fresh_responses:
            logger.warning(f"No fresh vendor responses for SKU: {sku}")
            return None
        
        # Select best vendor based on business rules
        best_vendor = self._select_best_vendor(fresh_responses)
        
        if best_vendor:
            # Create response
            result = ProductResponse(
                sku=sku,
                vendor=best_vendor.vendor_name,
                price=best_vendor.price,
                stock=best_vendor.stock,
                status=best_vendor.status,
                timestamp=best_vendor.timestamp
            )
            
            # Cache the result
            await self.cache_service.set_product(sku, result)
            
            logger.info(
                f"Best vendor for SKU {sku}: {best_vendor.vendor_name} "
                f"(price: ${best_vendor.price}, stock: {best_vendor.stock})"
            )
            
            return result
        else:
            logger.info(f"No vendors have stock for SKU: {sku}")
            return None
    
    async def _query_all_vendors(self, sku: str) -> List[VendorResponse]:
        """
        Query all vendors concurrently.
        
        Uses asyncio.gather to call vendors in parallel. If a vendor fails
        or times out, it's gracefully skipped.
        
        Args:
            sku: Product SKU to query
            
        Returns:
            List of successful vendor responses
        """
        # Create tasks for all vendors
        tasks = [
            self._query_vendor_with_circuit_breaker("VendorOne", self.vendor_one, sku),
            self._query_vendor_with_circuit_breaker("VendorTwo", self.vendor_two, sku),
            self._query_vendor_with_circuit_breaker("VendorThree", self.vendor_three, sku),
        ]
        
        # Execute all queries concurrently
        # return_exceptions=True ensures one failure doesn't stop others
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out failures and return successful responses
        successful_responses = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                vendor_name = ["VendorOne", "VendorTwo", "VendorThree"][i]
                logger.warning(f"{vendor_name} query failed: {str(result)}")
            elif result is not None:
                successful_responses.append(result)
        
        logger.info(
            f"Queried {len(tasks)} vendors, {len(successful_responses)} responded successfully"
        )
        
        return successful_responses
    
    async def _query_vendor_with_circuit_breaker(
        self,
        vendor_name: str,
        vendor_client,
        sku: str
    ) -> Optional[VendorResponse]:
        """
        Query a vendor with circuit breaker protection.
        
        Args:
            vendor_name: Name of the vendor
            vendor_client: Vendor client instance
            sku: Product SKU
            
        Returns:
            VendorResponse or None if circuit is open or query fails
        """
        circuit_breaker = self.circuit_breaker_manager.get_breaker(vendor_name)
        
        # Check if circuit is open
        if not circuit_breaker.can_execute():
            logger.warning(f"Circuit breaker open for {vendor_name}, skipping")
            return None
        
        try:
            # Query vendor with retry logic
            response = await self._query_vendor_with_retry(
                vendor_name,
                vendor_client,
                sku
            )
            
            # Record success
            circuit_breaker.record_success()
            
            return response
            
        except Exception as e:
            # Record failure
            circuit_breaker.record_failure()
            logger.error(f"{vendor_name} query failed: {str(e)}")
            raise
    
    async def _query_vendor_with_retry(
        self,
        vendor_name: str,
        vendor_client,
        sku: str,
        attempt: int = 1
    ) -> Optional[VendorResponse]:
        """
        Query a vendor with retry logic.
        
        Implements exponential backoff for retries.
        
        Args:
            vendor_name: Name of the vendor
            vendor_client: Vendor client instance
            sku: Product SKU
            attempt: Current attempt number
            
        Returns:
            VendorResponse or None
            
        Raises:
            Exception: If all retry attempts fail
        """
        try:
            # Apply timeout to vendor call
            response = await asyncio.wait_for(
                vendor_client.get_product(sku),
                timeout=settings.VENDOR_TIMEOUT_SECONDS
            )
            
            return response
            
        except asyncio.TimeoutError:
            logger.warning(
                f"{vendor_name} timeout on attempt {attempt} "
                f"(timeout: {settings.VENDOR_TIMEOUT_SECONDS}s)"
            )
            
            # Retry if attempts remaining
            if attempt < settings.VENDOR_MAX_RETRIES:
                # Exponential backoff: wait 0.1s, 0.2s, 0.4s, etc.
                backoff_time = 0.1 * (2 ** (attempt - 1))
                await asyncio.sleep(backoff_time)
                
                return await self._query_vendor_with_retry(
                    vendor_name,
                    vendor_client,
                    sku,
                    attempt + 1
                )
            else:
                raise Exception(f"Max retries exceeded for {vendor_name}")
        
        except Exception as e:
            logger.error(f"{vendor_name} error on attempt {attempt}: {str(e)}")
            
            # Retry if attempts remaining
            if attempt < settings.VENDOR_MAX_RETRIES:
                backoff_time = 0.1 * (2 ** (attempt - 1))
                await asyncio.sleep(backoff_time)
                
                return await self._query_vendor_with_retry(
                    vendor_name,
                    vendor_client,
                    sku,
                    attempt + 1
                )
            else:
                raise
    
    def _filter_by_freshness(
        self,
        responses: List[VendorResponse]
    ) -> List[VendorResponse]:
        """
        Filter vendor responses by data freshness.
        
        Discards responses older than DATA_FRESHNESS_MINUTES (default 10 minutes).
        
        Args:
            responses: List of vendor responses
            
        Returns:
            List of fresh vendor responses
        """
        cutoff_time = datetime.utcnow() - timedelta(
            minutes=settings.DATA_FRESHNESS_MINUTES
        )
        
        fresh_responses = [
            response for response in responses
            if response.timestamp >= cutoff_time
        ]
        
        if len(fresh_responses) < len(responses):
            logger.info(
                f"Filtered out {len(responses) - len(fresh_responses)} stale responses "
                f"(older than {settings.DATA_FRESHNESS_MINUTES} minutes)"
            )
        
        return fresh_responses
    
    def _select_best_vendor(
        self,
        responses: List[VendorResponse]
    ) -> Optional[VendorResponse]:
        """
        Select the best vendor based on business rules.
        
        Rules:
        1. Filter vendors with stock > 0
        2. Standard rule: Select vendor with lowest price
        3. Enhanced rule: If price difference > 10%, prefer higher stock
        
        Args:
            responses: List of vendor responses
            
        Returns:
            Best vendor response or None if all out of stock
        """
        # Filter vendors with stock
        in_stock_vendors = [
            response for response in responses
            if response.stock > 0 and response.status == ProductStatus.IN_STOCK
        ]
        
        if not in_stock_vendors:
            return None
        
        # Sort by price (ascending)
        sorted_by_price = sorted(in_stock_vendors, key=lambda x: x.price)
        
        if len(sorted_by_price) == 1:
            return sorted_by_price[0]
        
        # Get cheapest and second cheapest
        cheapest = sorted_by_price[0]
        
        # Apply enhanced rule: if price difference > 10%, consider stock
        for vendor in sorted_by_price[1:]:
            price_diff_percent = (
                (vendor.price - cheapest.price) / cheapest.price * 100
            )
            
            if price_diff_percent <= settings.PRICE_DIFFERENCE_THRESHOLD_PERCENT:
                # Within threshold, prefer cheaper
                continue
            else:
                # Price difference > 10%, prefer higher stock
                if vendor.stock > cheapest.stock:
                    logger.info(
                        f"Selecting {vendor.vendor_name} over {cheapest.vendor_name}: "
                        f"price diff {price_diff_percent:.1f}% > {settings.PRICE_DIFFERENCE_THRESHOLD_PERCENT}%, "
                        f"but stock is higher ({vendor.stock} vs {cheapest.stock})"
                    )
                    return vendor
        
        # Return cheapest if no better option found
        return cheapest
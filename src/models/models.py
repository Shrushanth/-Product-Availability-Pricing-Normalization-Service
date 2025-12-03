from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime
from enum import Enum


class ProductStatus(str, Enum):
    """Product availability status enum."""
    IN_STOCK = "IN_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"


class VendorResponse(BaseModel):
    """
    Normalized vendor response model.
    
    This is the internal model used after normalizing different vendor formats.
    Each vendor's unique response format is converted to this standard structure.
    """
    vendor_name: str = Field(
        ...,
        description="Name of the vendor"
    )
    sku: str = Field(
        ...,
        description="Product SKU"
    )
    price: float = Field(
        ...,
        gt=0,
        description="Product price (must be greater than 0)"
    )
    stock: int = Field(
        ...,
        ge=0,
        description="Available stock quantity (must be non-negative)"
    )
    status: ProductStatus = Field(
        ...,
        description="Availability status"
    )
    timestamp: datetime = Field(
        ...,
        description="Response timestamp from vendor"
    )
    response_time_ms: Optional[float] = Field(
        default=None,
        description="API response time in milliseconds"
    )
    
    @field_validator('price')
    @classmethod
    def validate_price(cls, v: float) -> float:
        """Ensure price is positive."""
        if v <= 0:
            raise ValueError("Price must be greater than 0")
        return v
    
    @field_validator('stock')
    @classmethod
    def validate_stock(cls, v: int) -> int:
        """Ensure stock is non-negative."""
        if v < 0:
            raise ValueError("Stock cannot be negative")
        return v
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "vendor_name": "VendorOne",
                "sku": "ABC123",
                "price": 99.99,
                "stock": 10,
                "status": "IN_STOCK",
                "timestamp": "2024-11-28T10:30:00Z",
                "response_time_ms": 150.5
            }
        }


class ProductResponse(BaseModel):
    """
    API response model for product queries.
    
    This is what clients receive when querying the /products/{sku} endpoint.
    """
    sku: str = Field(
        ...,
        description="Product SKU"
    )
    vendor: Optional[str] = Field(
        default=None,
        description="Selected vendor name (null if out of stock)"
    )
    price: Optional[float] = Field(
        default=None,
        gt=0,
        description="Product price from selected vendor"
    )
    stock: Optional[int] = Field(
        default=None,
        ge=0,
        description="Available stock from selected vendor"
    )
    status: ProductStatus = Field(
        ...,
        description="Overall availability status"
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the vendor response"
    )
    message: Optional[str] = Field(
        default=None,
        description="Additional information or error message"
    )
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "examples": [
                {
                    "sku": "ABC123",
                    "vendor": "VendorOne",
                    "price": 99.99,
                    "stock": 10,
                    "status": "IN_STOCK",
                    "timestamp": "2024-11-28T10:30:00Z",
                    "message": None
                },
                {
                    "sku": "XYZ789",
                    "vendor": None,
                    "price": None,
                    "stock": None,
                    "status": "OUT_OF_STOCK",
                    "timestamp": None,
                    "message": "Product not available from any vendor"
                }
            ]
        }


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(
        ...,
        description="Error type or code"
    )
    message: str = Field(
        ...,
        description="Human-readable error message"
    )
    detail: Optional[dict] = Field(
        default=None,
        description="Additional error details"
    )
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "error": "Invalid SKU",
                "message": "SKU must contain only alphanumeric characters",
                "detail": {"provided_sku": "ABC-123"}
            }
        }


class VendorOneRawResponse(BaseModel):
    """
    Raw response format from Vendor 1.
    
    Vendor 1 uses different field names:
    - quantity (instead of stock)
    - unit_price (instead of price)
    - availability_status (instead of status)
    """
    product_id: str
    quantity: Optional[int] = None  # Can be null
    unit_price: float
    availability_status: str  # "IN_STOCK", "OUT_OF_STOCK", etc.
    last_updated: str  # ISO 8601 timestamp
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "product_id": "ABC123",
                "quantity": None,
                "unit_price": 99.99,
                "availability_status": "IN_STOCK",
                "last_updated": "2024-11-28T10:30:00Z"
            }
        }


class VendorTwoRawResponse(BaseModel):
    """
    Raw response format from Vendor 2.
    
    Vendor 2 uses different field names:
    - stock_count (instead of stock)
    - price_amount (instead of price)
    - in_stock (boolean flag)
    """
    sku: str
    stock_count: Optional[int] = None
    price_amount: float
    in_stock: bool
    response_timestamp: str  # ISO 8601 timestamp
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "sku": "ABC123",
                "stock_count": 15,
                "price_amount": 105.50,
                "in_stock": True,
                "response_timestamp": "2024-11-28T10:30:00Z"
            }
        }


class VendorThreeRawResponse(BaseModel):
    """
    Raw response format from Vendor 3.
    
    Vendor 3 uses completely different field names:
    - available_units (instead of stock)
    - cost (instead of price)
    - status_code (numeric code)
    """
    item_code: str
    available_units: Optional[int] = None
    cost: float
    status_code: int  # 1 = in stock, 0 = out of stock
    data_timestamp: str  # ISO 8601 timestamp
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "item_code": "ABC123",
                "available_units": 8,
                "cost": 95.00,
                "status_code": 1,
                "data_timestamp": "2024-11-28T10:30:00Z"
            }
        }


class VendorMetrics(BaseModel):
    """
    Vendor performance metrics for monitoring.
    
    Tracked by background jobs to monitor vendor health and performance.
    """
    vendor_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_response_time_ms: float = 0.0
    average_response_time_ms: float = 0.0
    failure_rate: float = 0.0
    circuit_breaker_state: Literal["closed", "open", "half_open"] = "closed"
    last_updated: datetime
    
    def update_success(self, response_time_ms: float) -> None:
        """Update metrics for a successful call."""
        self.total_calls += 1
        self.successful_calls += 1
        self.total_response_time_ms += response_time_ms
        self.average_response_time_ms = self.total_response_time_ms / self.successful_calls
        self.failure_rate = self.failed_calls / self.total_calls
        self.last_updated = datetime.utcnow()
    
    def update_failure(self) -> None:
        """Update metrics for a failed call."""
        self.total_calls += 1
        self.failed_calls += 1
        self.failure_rate = self.failed_calls / self.total_calls
        self.last_updated = datetime.utcnow()
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "vendor_name": "VendorOne",
                "total_calls": 1000,
                "successful_calls": 995,
                "failed_calls": 5,
                "total_response_time_ms": 150000.0,
                "average_response_time_ms": 150.75,
                "failure_rate": 0.005,
                "circuit_breaker_state": "closed",
                "last_updated": "2024-11-28T10:30:00Z"
            }
        }


class CacheMetrics(BaseModel):
    """
    Cache performance metrics.
    
    Tracks cache hit/miss rates for monitoring and optimization.
    """
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    hit_rate: float = 0.0
    
    def record_hit(self) -> None:
        """Record a cache hit."""
        self.total_requests += 1
        self.cache_hits += 1
        self.hit_rate = self.cache_hits / self.total_requests
    
    def record_miss(self) -> None:
        """Record a cache miss."""
        self.total_requests += 1
        self.cache_misses += 1
        self.hit_rate = self.cache_hits / self.total_requests
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "total_requests": 1000,
                "cache_hits": 750,
                "cache_misses": 250,
                "hit_rate": 0.75
            }
        }
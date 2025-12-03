from src.models.models import ProductResponse, ProductStatus
from datetime import datetime

def test_product_response_in_stock():
    """Test ProductResponse with in-stock product."""
    response = ProductResponse(
        sku="TEST123",
        vendor="VendorOne",
        price=99.99,
        stock=10,
        status=ProductStatus.IN_STOCK,
        timestamp=datetime.utcnow()
    )
    
    assert response.sku == "TEST123"
    assert response.vendor == "VendorOne"
    assert response.price == 99.99
    assert response.stock == 10
    assert response.status == ProductStatus.IN_STOCK

def test_product_response_out_of_stock():
    """Test ProductResponse with out-of-stock product."""
    response = ProductResponse(
        sku="TEST456",
        status=ProductStatus.OUT_OF_STOCK
    )
    
    assert response.sku == "TEST456"
    assert response.vendor is None
    assert response.status == ProductStatus.OUT_OF_STOCK
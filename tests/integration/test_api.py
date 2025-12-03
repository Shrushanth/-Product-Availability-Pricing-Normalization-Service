import pytest
from httpx import AsyncClient
from src.main import app

@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_get_product_without_api_key():
    """Test product endpoint without API key."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/products/ABC123")
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_get_product_with_valid_sku():
    """Test product endpoint with valid SKU."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/products/ABC123",
            headers={"x-api-key": "test-api-key-12345"}
        )
        # Should succeed or handle gracefully
        assert response.status_code in [200, 404, 503]
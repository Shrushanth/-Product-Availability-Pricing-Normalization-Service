# Product Availability & Pricing Normalization Service

A FastAPI-based microservice that integrates with multiple vendor APIs, normalizes product data, and returns the best vendor based on price and availability.

## 🏗️ Architecture Overview

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│         FastAPI Service             │
│  ┌───────────────────────────────┐  │
│  │   Rate Limiter Middleware     │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │   SKU Validation              │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │   Redis Cache Layer           │  │
│  │   (TTL: 120s)                 │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │   Circuit Breaker Pattern     │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │   Concurrent Vendor Calls     │  │
│  │   (asyncio.gather)            │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
           │     │     │
           ▼     ▼     ▼
    ┌────────┐ ┌────────┐ ┌────────┐
    │Vendor 1│ │Vendor 2│ │Vendor 3│
    │ (Fast) │ │(Normal)│ │ (Slow) │
    └────────┘ └────────┘ └────────┘
```

## 🚀 Features

### Junior Requirements ✅
- ✅ Dual vendor integration with different data structures
- ✅ Stock normalization (null inventory + IN_STOCK = 5 units)
- ✅ Price validation (numeric, > 0)
- ✅ Best vendor selection (lowest price with stock)
- ✅ Concurrent API calls using `asyncio.gather()`
- ✅ Graceful error handling
- ✅ Redis caching with 120-second TTL
- ✅ SKU validation (alphanumeric, 3-20 chars)

### Senior Requirements ✅
- ✅ Third vendor with simulated delays/failures
- ✅ Data freshness validation (10-minute cutoff)
- ✅ Smart price-stock decision (10% price diff → prefer higher stock)
- ✅ Request timeouts (2s) & retries (2 attempts)
- ✅ Redis cache (mandatory)
- ✅ Circuit breaker pattern (3 failures → 30s cooldown)
- ✅ Background job (cache prewarming + vendor metrics)
- ✅ Rate limiting (60 req/min per API key)

### Bonus Features ✅
- ✅ Docker Compose setup
- ✅ OpenAPI/Swagger documentation
- ✅ Comprehensive unit & integration tests
- ✅ Type hints throughout

## 📋 Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Redis (via Docker)

## 🛠️ Setup Instructions

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd product-availability-service
```

### 2. Environment Configuration

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` with your configuration (defaults work for Docker setup).

### 3. Run with Docker Compose (Recommended)

```bash
# Build and start all services
docker-compose up --build

# Run in detached mode
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

The API will be available at `http://localhost:8000`

### 4. Manual Setup (Without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start Redis (separate terminal)
redis-server

# Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📡 API Usage

### Get Product by SKU

```bash
# Basic request
curl -X GET "http://localhost:8000/products/ABC123" \
  -H "x-api-key: test-api-key-12345"

# Response (Best vendor found)
{
  "sku": "ABC123",
  "vendor": "VendorOne",
  "price": 99.99,
  "stock": 10,
  "status": "IN_STOCK",
  "timestamp": "2024-11-28T10:30:00Z"
}

# Response (Out of stock)
{
  "sku": "ABC123",
  "status": "OUT_OF_STOCK",
  "message": "Product not available from any vendor"
}
```

### API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_vendor_service.py -v

# Run integration tests only
pytest tests/integration/ -v
```

## 🏭 Mock Vendors

The service includes three mock vendor implementations:

### Vendor 1 (Fast & Reliable)
- Response time: 100-300ms
- Field structure: `quantity`, `unit_price`, `availability_status`
- Reliability: 99%

### Vendor 2 (Standard)
- Response time: 200-500ms
- Field structure: `stock_count`, `price_amount`, `in_stock`
- Reliability: 95%

### Vendor 3 (Slow & Unreliable)
- Response time: 1000-3000ms
- Field structure: `available_units`, `cost`, `status_code`
- Reliability: 70%
- Simulates: timeouts, intermittent failures

## 🔧 Configuration

Key environment variables (see `.env.example`):

```bash
# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
CACHE_TTL_SECONDS=120

# Vendor Settings
VENDOR_TIMEOUT_SECONDS=2
VENDOR_MAX_RETRIES=2
DATA_FRESHNESS_MINUTES=10

# Circuit Breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=3
CIRCUIT_BREAKER_TIMEOUT_SECONDS=30

# Rate Limiting
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60

# Background Jobs
CACHE_PREWARM_INTERVAL_MINUTES=5
POPULAR_SKUS=ABC123,XYZ789,DEF456
```

## 🏗️ Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry
│   ├── config.py               # Configuration management
│   ├── models.py               # Pydantic models
│   ├── services/
│   │   ├── vendor_service.py   # Vendor integration logic
│   │   ├── cache_service.py    # Redis caching
│   │   ├── circuit_breaker.py  # Circuit breaker pattern
│   │   └── rate_limiter.py     # Rate limiting
│   ├── vendors/
│   │   ├── vendor_one.py       # Mock vendor 1
│   │   ├── vendor_two.py       # Mock vendor 2
│   │   └── vendor_three.py     # Mock vendor 3
│   ├── middleware/
│   │   └── rate_limit.py       # Rate limit middleware
│   └── background/
│       └── jobs.py             # Scheduled background tasks
├── tests/
│   ├── unit/
│   └── integration/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## 🧠 Business Logic

### Stock Normalization
```python
if inventory is None and status == "IN_STOCK":
    stock = 5  # Assume 5 units available
else:
    stock = 0  # Out of stock
```

### Price Validation
- Must be numeric and greater than 0
- Invalid prices are discarded

### Best Vendor Selection

**Standard Rule:**
- Vendor with stock > 0 and lowest price wins

**Enhanced Rule (Senior):**
- If price difference > 10% between vendors
- Choose vendor with higher stock (even if slightly more expensive)

**Example:**
```
Vendor A: $100, 5 units
Vendor B: $115, 50 units  (15% more expensive)
→ Choose Vendor B (higher stock, price within tolerance)
```

### Data Freshness
- Vendor data older than 10 minutes is discarded
- Ensures users get current information

### Circuit Breaker
- Opens after 3 consecutive failures
- Skips vendor for 30 seconds (cooldown)
- Half-open state: tests with single request
- Closes on successful call

## 📊 Monitoring & Observability

### Background Job Metrics
Every 5 minutes, the system logs:
- Vendor latency averages
- Failure rates per vendor
- Cache hit rates
- Circuit breaker states

### Health Check
```bash
curl http://localhost:8000/health
```

## 🔐 Security

- API key authentication via `x-api-key` header
- Rate limiting per API key (60 req/min)
- Input validation (SKU format)
- Error messages don't expose internal details

## 🚀 Deployment

### Docker Deployment
```bash
docker-compose up -d
```

### Manual Deployment
1. Set up Redis instance
2. Configure environment variables
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker`

## 🤔 Design Decisions & Assumptions

### Assumptions Made:

1. **Vendor Data Structure**: Each vendor has completely different field names to simulate real-world scenarios
2. **Cache Strategy**: Redis chosen over in-memory for production-readiness and scalability
3. **Concurrent Execution**: All vendors called in parallel for optimal performance
4. **Graceful Degradation**: Service continues if one/two vendors fail
5. **API Key Format**: Simple string-based keys (in production, use JWT/OAuth)
6. **Popular SKUs**: Hardcoded list for cache prewarming (in production, track via analytics)

### Why These Choices:

- **FastAPI**: High performance, async support, excellent OpenAPI integration
- **Redis**: Industry-standard caching, supports TTL, cluster-ready
- **Circuit Breaker**: Prevents cascading failures from unreliable vendors
- **Rate Limiting**: Protects service from abuse and ensures fair usage
- **Type Hints**: Catches errors early, improves IDE support, better documentation

## 📝 Future Enhancements

- [ ] Kubernetes deployment manifests
- [ ] Prometheus metrics export
- [ ] Distributed tracing (OpenTelemetry)
- [ ] GraphQL API option
- [ ] Webhook notifications for price drops
- [ ] Machine learning for demand prediction

## 🐛 Troubleshooting

### Redis Connection Issues
```bash
# Check Redis is running
docker-compose ps redis

# View Redis logs
docker-compose logs redis

# Test Redis connection
redis-cli ping
```

### API Not Responding
```bash
# Check API logs
docker-compose logs api

# Verify port is not in use
lsof -i :8000
```

## 📄 License

MIT License - Feel free to use this for learning and projects.

## 👤 Author

Created as part of a technical assessment demonstrating:
- Microservice architecture
- Async/concurrent programming
- Cache strategies
- Resilience patterns
- Production-ready code practices
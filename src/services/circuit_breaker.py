import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Literal
from config import settings

logger = logging.getLogger(__name__)

CircuitState = Literal["closed", "open", "half_open"]

class CircuitBreaker:
    """Circuit breaker for a single vendor."""
    
    def __init__(self, name: str):
        self.name = name
        self.failure_count = 0
        self.state: CircuitState = "closed"
        self.last_failure_time: Optional[datetime] = None
        self.success_count_in_half_open = 0
    
    def can_execute(self) -> bool:
        """Check if requests can be executed."""
        if self.state == "closed":
            return True
        
        if self.state == "open":
            # Check if cooldown period has passed
            if self.last_failure_time:
                cooldown_end = self.last_failure_time + timedelta(
                    seconds=settings.CIRCUIT_BREAKER_TIMEOUT_SECONDS
                )
                if datetime.utcnow() >= cooldown_end:
                    logger.info(f"Circuit breaker for {self.name} entering half-open state")
                    self.state = "half_open"
                    self.success_count_in_half_open = 0
                    return True
            return False
        
        # half_open state: allow requests to test recovery
        return True
    
    def record_success(self) -> None:
        """Record a successful call."""
        if self.state == "half_open":
            self.success_count_in_half_open += 1
            # Close circuit after successful call in half-open
            logger.info(f"Circuit breaker for {self.name} closing (recovered)")
            self.state = "closed"
            self.failure_count = 0
        elif self.state == "closed":
            # Reset failure count on success
            self.failure_count = 0
    
    def record_failure(self) -> None:
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == "half_open":
            # Failed during half-open, reopen circuit
            logger.warning(f"Circuit breaker for {self.name} reopening")
            self.state = "open"
        elif self.failure_count >= settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD:
            # Threshold exceeded, open circuit
            logger.warning(
                f"Circuit breaker for {self.name} opening "
                f"(failures: {self.failure_count})"
            )
            self.state = "open"

class CircuitBreakerManager:
    """Manages circuit breakers for all vendors."""
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
    
    def register(self, vendor_name: str) -> None:
        """Register a new circuit breaker."""
        self.breakers[vendor_name] = CircuitBreaker(vendor_name)
        logger.info(f"Registered circuit breaker for {vendor_name}")
    
    def get_breaker(self, vendor_name: str) -> CircuitBreaker:
        """Get circuit breaker for a vendor."""
        return self.breakers[vendor_name]
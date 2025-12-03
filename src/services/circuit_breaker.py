import logging
from datetime import datetime, timedelta
from typing import Dict, Literal, Optional
from src.config import settings

logger = logging.getLogger(__name__)

# Type alias for circuit states
CircuitState = Literal["closed", "open", "half_open"]


class CircuitBreaker:
    """
    Circuit breaker for a single vendor.
    
    State transitions:
    1. CLOSED → OPEN: After threshold consecutive failures
    2. OPEN → HALF_OPEN: After timeout period
    3. HALF_OPEN → CLOSED: After successful call
    4. HALF_OPEN → OPEN: If call fails during testing
    
    Example:
        breaker = CircuitBreaker("VendorOne")
        
        if breaker.can_execute():
            try:
                result = await call_vendor()
                breaker.record_success()
            except Exception:
                breaker.record_failure()
    """
    
    def __init__(self, name: str):
        """
        Initialize circuit breaker for a vendor.
        
        Args:
            name: Vendor name for logging
        """
        self.name = name
        self.failure_count = 0
        self.success_count = 0
        self.state: CircuitState = "closed"
        self.last_failure_time: Optional[datetime] = None
        self.last_state_change: datetime = datetime.utcnow()
        self.total_calls = 0
        self.total_failures = 0
        
        logger.info(f"Circuit breaker initialized for {name}")
    
    def can_execute(self) -> bool:
        """
        Check if requests can be executed.
        
        Returns:
            True if requests should proceed, False if blocked
        """
        self.total_calls += 1
        
        if self.state == "closed":
            # Normal operation - allow all requests
            return True
        
        if self.state == "open":
            # Check if cooldown period has passed
            if self._should_attempt_reset():
                logger.info(
                    f"Circuit breaker for {self.name} transitioning to "
                    f"half_open state (cooldown expired)"
                )
                self._transition_to_half_open()
                return True
            
            # Still in cooldown - block request
            logger.debug(
                f"Circuit breaker for {self.name} is OPEN, "
                f"blocking request"
            )
            return False
        
        # half_open state: allow requests to test if service recovered
        logger.debug(
            f"Circuit breaker for {self.name} is HALF_OPEN, "
            f"allowing test request"
        )
        return True
    
    def record_success(self) -> None:
        """
        Record a successful call.
        
        In HALF_OPEN state, success closes the circuit.
        In CLOSED state, resets the failure counter.
        """
        self.success_count += 1
        
        if self.state == "half_open":
            # Success in half-open means service recovered
            logger.info(
                f"Circuit breaker for {self.name} CLOSING "
                f"(successful call in half-open state)"
            )
            self._transition_to_closed()
            
        elif self.state == "closed":
            # Reset failure count on success
            if self.failure_count > 0:
                logger.debug(
                    f"Circuit breaker for {self.name}: "
                    f"resetting failure count after success"
                )
                self.failure_count = 0
    
    def record_failure(self) -> None:
        """
        Record a failed call.
        
        In HALF_OPEN state, failure reopens the circuit.
        In CLOSED state, opens circuit if threshold exceeded.
        """
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == "half_open":
            # Failed during recovery test - reopen circuit
            logger.warning(
                f"Circuit breaker for {self.name} REOPENING "
                f"(failure during half-open test)"
            )
            self._transition_to_open()
            
        elif self.state == "closed":
            # Check if we've hit the failure threshold
            if self.failure_count >= settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD:
                logger.warning(
                    f"Circuit breaker for {self.name} OPENING "
                    f"(failures: {self.failure_count}/"
                    f"{settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD})"
                )
                self._transition_to_open()
            else:
                logger.debug(
                    f"Circuit breaker for {self.name}: "
                    f"failure recorded ({self.failure_count}/"
                    f"{settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD})"
                )
    
    def _should_attempt_reset(self) -> bool:
        """
        Check if enough time has passed to attempt reset.
        
        Returns:
            True if cooldown period expired
        """
        if not self.last_failure_time:
            return False
        
        cooldown_end = self.last_failure_time + timedelta(
            seconds=settings.CIRCUIT_BREAKER_TIMEOUT_SECONDS
        )
        
        return datetime.utcnow() >= cooldown_end
    
    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        self.state = "closed"
        self.failure_count = 0
        self.last_state_change = datetime.utcnow()
    
    def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        self.state = "open"
        self.last_state_change = datetime.utcnow()
    
    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state."""
        self.state = "half_open"
        self.last_state_change = datetime.utcnow()
    
    def get_state(self) -> CircuitState:
        """
        Get current circuit state.
        
        Returns:
            Current state: "closed", "open", or "half_open"
        """
        return self.state
    
    def get_metrics(self) -> dict:
        """
        Get circuit breaker metrics.
        
        Returns:
            Dictionary with state and statistics
        """
        uptime = (datetime.utcnow() - self.last_state_change).total_seconds()
        failure_rate = (
            (self.total_failures / self.total_calls * 100)
            if self.total_calls > 0
            else 0
        )
        
        return {
            "vendor": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "failure_rate_percent": round(failure_rate, 2),
            "time_in_current_state_seconds": round(uptime, 2),
            "last_failure": (
                self.last_failure_time.isoformat()
                if self.last_failure_time
                else None
            )
        }
    
    def reset(self) -> None:
        """
        Manually reset circuit breaker.
        
        Useful for testing or administrative intervention.
        """
        logger.warning(f"Circuit breaker for {self.name} manually reset")
        self.state = "closed"
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = datetime.utcnow()
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"CircuitBreaker(name={self.name}, state={self.state}, "
            f"failures={self.failure_count})"
        )


class CircuitBreakerManager:
    """
    Manages circuit breakers for all vendors.
    
    Provides centralized access to circuit breakers and
    aggregate metrics across all vendors.
    """
    
    def __init__(self):
        """Initialize circuit breaker manager."""
        self.breakers: Dict[str, CircuitBreaker] = {}
        logger.info("Circuit breaker manager initialized")
    
    def register(self, vendor_name: str) -> CircuitBreaker:
        """
        Register a new circuit breaker for a vendor.
        
        Args:
            vendor_name: Name of the vendor
            
        Returns:
            Created CircuitBreaker instance
        """
        if vendor_name in self.breakers:
            logger.warning(
                f"Circuit breaker for {vendor_name} already registered"
            )
            return self.breakers[vendor_name]
        
        breaker = CircuitBreaker(vendor_name)
        self.breakers[vendor_name] = breaker
        
        logger.info(f"Registered circuit breaker for {vendor_name}")
        return breaker
    
    def get_breaker(self, vendor_name: str) -> CircuitBreaker:
        """
        Get circuit breaker for a vendor.
        
        Args:
            vendor_name: Name of the vendor
            
        Returns:
            CircuitBreaker instance
            
        Raises:
            KeyError: If vendor not registered
        """
        if vendor_name not in self.breakers:
            raise KeyError(
                f"Circuit breaker not found for vendor: {vendor_name}. "
                f"Did you forget to register it?"
            )
        
        return self.breakers[vendor_name]
    
    def get_all_metrics(self) -> dict:
        """
        Get metrics for all circuit breakers.
        
        Returns:
            Dictionary with metrics for each vendor
        """
        return {
            vendor_name: breaker.get_metrics()
            for vendor_name, breaker in self.breakers.items()
        }
    
    def get_healthy_vendors(self) -> list[str]:
        """
        Get list of vendors with closed circuits.
        
        Returns:
            List of vendor names with healthy circuits
        """
        return [
            vendor_name
            for vendor_name, breaker in self.breakers.items()
            if breaker.get_state() == "closed"
        ]
    
    def get_unhealthy_vendors(self) -> list[str]:
        """
        Get list of vendors with open circuits.
        
        Returns:
            List of vendor names with open circuits
        """
        return [
            vendor_name
            for vendor_name, breaker in self.breakers.items()
            if breaker.get_state() == "open"
        ]
    
    def reset_all(self) -> None:
        """Reset all circuit breakers (use with caution)."""
        logger.warning("Resetting ALL circuit breakers")
        for breaker in self.breakers.values():
            breaker.reset()
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"CircuitBreakerManager(vendors={list(self.breakers.keys())}, "
            f"healthy={len(self.get_healthy_vendors())}, "
            f"unhealthy={len(self.get_unhealthy_vendors())})"
        )
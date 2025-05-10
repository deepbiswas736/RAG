"""
Circuit Breaker
--------------
Implementation of the Circuit Breaker pattern for resilient service calls
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, TypeVar, Awaitable
import asyncio

logger = logging.getLogger(__name__)

T = TypeVar('T')

class CircuitBreaker:
    """
    Circuit breaker pattern implementation to protect external service calls.
    Prevents cascading failures by failing fast when a service is experiencing issues.
    """
    
    def __init__(
        self, 
        name: str = "default",
        failure_threshold: int = 5,
        reset_timeout: int = 60,
        half_open_timeout: int = 30
    ):
        """
        Initialize the circuit breaker.
        
        Args:
            name: Name of this circuit breaker for logging
            failure_threshold: Number of failures before circuit opens
            reset_timeout: Seconds to wait before attempting to close circuit
            half_open_timeout: Seconds to wait in half-open state
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_timeout = half_open_timeout
        
        # Circuit state
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed (normal), open (failing), half-open (testing)
        self.last_state_change = datetime.now()
        
        logger.info(f"Circuit breaker '{name}' initialized with threshold: {failure_threshold}, reset: {reset_timeout}s")
    
    async def execute(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to execute
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Result of the function execution
            
        Raises:
            CircuitBreakerOpenError: If circuit is open (service unavailable)
            Exception: Any exception raised by the function
        """
        await self._update_circuit_state()
        
        if self.state == "open":
            raise CircuitBreakerOpenError(f"Circuit '{self.name}' is open")
        
        try:
            result = await func(*args, **kwargs)
            
            # If successful and in half-open state, close the circuit
            if self.state == "half-open":
                self._close_circuit()
                
            return result
            
        except Exception as e:
            await self._handle_failure(e)
            raise
    
    async def _update_circuit_state(self):
        """Update circuit state based on timeouts and current state"""
        now = datetime.now()
        
        if self.state == "open":
            # Check if reset timeout has elapsed
            if self.last_state_change + timedelta(seconds=self.reset_timeout) < now:
                self._half_open_circuit()
                
        elif self.state == "half-open":
            # If in half-open state too long, open it again
            if self.last_state_change + timedelta(seconds=self.half_open_timeout) < now:
                self._open_circuit()
    
    async def _handle_failure(self, exception):
        """Handle a failure and update circuit state accordingly"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        logger.warning(f"Circuit '{self.name}' recorded failure: {type(exception).__name__}: {exception}")
        
        if self.state == "half-open" or (self.state == "closed" and self.failure_count >= self.failure_threshold):
            self._open_circuit()
            
    def _open_circuit(self):
        """Open the circuit"""
        if self.state != "open":
            logger.warning(f"Circuit '{self.name}' OPENED after {self.failure_count} failures")
            self.state = "open"
            self.last_state_change = datetime.now()
    
    def _close_circuit(self):
        """Close the circuit"""
        if self.state != "closed":
            logger.info(f"Circuit '{self.name}' CLOSED")
            self.state = "closed"
            self.failure_count = 0
            self.last_state_change = datetime.now()
    
    def _half_open_circuit(self):
        """Set circuit to half-open state"""
        if self.state != "half-open":
            logger.info(f"Circuit '{self.name}' HALF-OPEN")
            self.state = "half-open"
            self.last_state_change = datetime.now()


class CircuitBreakerOpenError(Exception):
    """Error raised when a circuit breaker is open"""
    pass

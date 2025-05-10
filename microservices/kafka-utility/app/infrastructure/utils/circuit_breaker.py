"""
Circuit Breaker

Implements the circuit breaker pattern for enhanced resilience when communicating with Kafka.
"""

import time
import logging
import enum
from typing import Callable, TypeVar, Generic, Optional, Any

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')

class CircuitState(enum.Enum):
    """States for the circuit breaker."""
    CLOSED = 'closed'  # Normal operation, requests flow through
    OPEN = 'open'      # Failing, requests are blocked
    HALF_OPEN = 'half_open'  # Testing if service is back, limited requests allowed


class CircuitBreaker(Generic[T, R]):
    """
    A circuit breaker implementation to prevent repeated calls to failing services.
    
    The circuit breaker monitors for failures and when a threshold is reached,
    it "trips" to prevent further calls to the failing service. After a reset
    timeout, it allows a test request through, and if successful, resets to
    normal operation.
    """
    
    def __init__(self, 
                name: str,
                failure_threshold: int = 5,
                reset_timeout: float = 60.0,
                half_open_timeout: float = 5.0,
                exception_types: tuple = (Exception,)
                ):
        """
        Initialize the circuit breaker.
        
        Args:
            name: A name for this circuit breaker (for logging)
            failure_threshold: Number of failures before opening the circuit
            reset_timeout: Time in seconds before attempting to close the circuit after opening
            half_open_timeout: Time in seconds to wait in half-open state before declaring success
            exception_types: Tuple of exception types that should count as failures
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_timeout = half_open_timeout
        self.exception_types = exception_types
        
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time = 0
        self.last_attempted_reset = 0
    
    async def execute(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> Optional[R]:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: The function to execute
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            The result of the function call, or None if the circuit is open
            
        Raises:
            Various: Any exceptions raised by the function that aren't handled by the circuit breaker
        """
        if self.state == CircuitState.OPEN:
            # Check if reset timeout has elapsed
            if time.time() - self.last_failure_time > self.reset_timeout:
                logger.info(f"Circuit {self.name} trying half-open state")
                self.state = CircuitState.HALF_OPEN
                self.last_attempted_reset = time.time()
            else:
                # Circuit is open and reset timeout hasn't elapsed
                logger.warning(f"Circuit {self.name} is open, rejecting request")
                return None
        
        try:
            result = await func(*args, **kwargs)
            
            # If we're in half-open state and call succeeded
            if self.state == CircuitState.HALF_OPEN:
                current_time = time.time()
                if current_time - self.last_attempted_reset >= self.half_open_timeout:
                    # Reset the circuit if enough time has passed in half-open state
                    logger.info(f"Circuit {self.name} reset to closed state after successful test")
                    self._reset()
                # else we stay in half-open state until half_open_timeout elapses
            
            return result
            
        except self.exception_types as e:
            # Handle failures
            self.failures += 1
            self.last_failure_time = time.time()
            
            logger.warning(f"Circuit {self.name} recorded failure ({self.failures}/{self.failure_threshold}): {e}")
            
            if self.state == CircuitState.CLOSED and self.failures >= self.failure_threshold:
                # Trip the circuit
                logger.warning(f"Circuit {self.name} tripped - opening circuit")
                self.state = CircuitState.OPEN
            elif self.state == CircuitState.HALF_OPEN:
                # Failed during testing, reopen the circuit
                logger.warning(f"Circuit {self.name} failed during half-open test - reopening circuit")
                self.state = CircuitState.OPEN
                
            # Re-raise the exception
            raise
    
    def _reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failures = 0

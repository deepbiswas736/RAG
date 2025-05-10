"""
Message Request Handler

Provides a mechanism for tracking and responding to request-reply patterns in Kafka.
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, Callable, Awaitable, TypeVar, Generic

logger = logging.getLogger(__name__)

T = TypeVar('T')

class RequestReplyHandler(Generic[T]):
    """
    Helper for implementing request-reply patterns over Kafka.
    
    This class allows tracking of request messages and matching them with 
    their corresponding replies using correlation IDs.
    """
    
    def __init__(self, timeout_seconds: float = 60.0):
        """
        Initialize the request-reply handler.
        
        Args:
            timeout_seconds: Default timeout for requests
        """
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.timeout_seconds = timeout_seconds
    
    def create_request_id(self) -> str:
        """
        Create a unique request ID.
        
        Returns:
            A unique correlation ID for the request
        """
        return str(uuid.uuid4())
    
    async def wait_for_reply(self, correlation_id: str, timeout: Optional[float] = None) -> T:
        """
        Wait for a reply with the given correlation ID.
        
        Args:
            correlation_id: The correlation ID to wait for
            timeout: Optional timeout in seconds. If None, uses the default timeout.
            
        Returns:
            The reply payload
            
        Raises:
            asyncio.TimeoutError: If the timeout is reached
            KeyError: If the correlation ID is not found
        """
        if correlation_id not in self.pending_requests:
            self.pending_requests[correlation_id] = asyncio.Future()
        
        try:
            timeout_to_use = timeout if timeout is not None else self.timeout_seconds
            return await asyncio.wait_for(self.pending_requests[correlation_id], timeout=timeout_to_use)
        finally:
            # Remove the future from pending requests after it completes or times out
            if correlation_id in self.pending_requests:
                del self.pending_requests[correlation_id]
    
    def handle_reply(self, correlation_id: str, result: T) -> bool:
        """
        Handle a reply message.
        
        Args:
            correlation_id: The correlation ID of the reply
            result: The result to set as the future's result
            
        Returns:
            True if the correlation ID was found and the future was set,
            False otherwise
        """
        if correlation_id not in self.pending_requests:
            logger.warning(f"Received reply for unknown correlation ID: {correlation_id}")
            return False
        
        future = self.pending_requests[correlation_id]
        if not future.done():
            future.set_result(result)
            return True
        else:
            logger.warning(f"Future for correlation ID {correlation_id} is already done")
            return False
    
    def is_pending(self, correlation_id: str) -> bool:
        """
        Check if a request with the given correlation ID is pending.
        
        Args:
            correlation_id: The correlation ID to check
            
        Returns:
            True if the request is pending, False otherwise
        """
        return correlation_id in self.pending_requests and not self.pending_requests[correlation_id].done()
    
    def cancel_request(self, correlation_id: str) -> bool:
        """
        Cancel a pending request.
        
        Args:
            correlation_id: The correlation ID of the request to cancel
            
        Returns:
            True if the request was cancelled, False if it was not found
        """
        if correlation_id in self.pending_requests:
            future = self.pending_requests[correlation_id]
            if not future.done():
                future.cancel()
            del self.pending_requests[correlation_id]
            return True
        return False
    
    def clear_all_pending(self) -> None:
        """Cancel and clear all pending requests."""
        for correlation_id, future in list(self.pending_requests.items()):
            if not future.done():
                future.cancel()
        self.pending_requests.clear()

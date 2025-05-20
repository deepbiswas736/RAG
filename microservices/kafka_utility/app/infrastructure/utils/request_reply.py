"""
Message Request Handler

Provides a mechanism for tracking and responding to request-reply patterns in Kafka with tracing support.
"""

import asyncio
import logging
import uuid
import opentelemetry.trace as trace
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from typing import Dict, Any, Optional, Callable, Awaitable, TypeVar, Generic

logger = logging.getLogger(__name__)

T = TypeVar('T')

class RequestReplyHandler(Generic[T]):
    """
    Helper for implementing request-reply patterns over Kafka with distributed tracing.
    
    This class allows tracking of request messages and matching them with 
    their corresponding replies using correlation IDs and trace context.
    """
    
    def __init__(self, service_name: str, timeout_seconds: float = 60.0):
        """
        Initialize the request-reply handler.
        
        Args:
            service_name: Name of the service for tracing
            timeout_seconds: Default timeout for requests
        """
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.timeout_seconds = timeout_seconds
        self.service_name = service_name
        self.tracer = trace.get_tracer(__name__)
        self.propagator = TraceContextTextMapPropagator()
    
    def create_request_context(self, operation_name: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a request context with tracing information.
        
        Args:
            operation_name: Name of the operation being performed
            correlation_id: Optional correlation ID to use
            
        Returns:
            Dictionary with request metadata including trace context
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        carrier: Dict[str, str] = {}
        
        # Get current span context and inject it into carrier
        current_span = trace.get_current_span()
        self.propagator.inject(carrier)
        
        context = {
            "correlation_id": correlation_id,
            "trace_context": {
                "traceparent": carrier.get("traceparent", ""),
                "tracestate": carrier.get("tracestate", "")
            },
            "source_service": self.service_name,
            "source_operation": operation_name,
            "timestamp": str(uuid.uuid4().isoformat())
        }
        
        return context
    
    async def wait_for_reply(
        self,
        correlation_id: str,
        operation_name: str,
        timeout: Optional[float] = None,
        attributes: Optional[Dict[str, str]] = None
    ) -> T:
        """
        Wait for a reply with distributed tracing support.
        
        Args:
            correlation_id: The correlation ID to wait for
            operation_name: Name of the operation being performed
            timeout: Optional timeout in seconds. If None, uses the default timeout.
            attributes: Optional span attributes
            
        Returns:
            The reply payload
            
        Raises:
            asyncio.TimeoutError: If the timeout is reached
            KeyError: If the correlation ID is not found
        """
        if correlation_id not in self.pending_requests:
            self.pending_requests[correlation_id] = asyncio.Future()
        
        try:
            # Start span for waiting operation
            with self.tracer.start_as_current_span(
                name=f"{operation_name}_wait",
                kind=SpanKind.CONSUMER,
                attributes=attributes or {}
            ) as span:
                # Link span to parent if exists
                if carrier := self.propagator.extract({}):
                    span.set_parent(carrier)
                
                timeout_to_use = timeout if timeout is not None else self.timeout_seconds
                try:
                    result = await asyncio.wait_for(
                        self.pending_requests[correlation_id],
                        timeout=timeout_to_use
                    )
                    span.set_status(Status(StatusCode.OK))
                    return result
                except asyncio.TimeoutError:
                    span.set_status(
                        Status(StatusCode.ERROR, "Request timed out")
                    )
                    raise
        finally:
            if correlation_id in self.pending_requests:
                del self.pending_requests[correlation_id]
    
    def handle_reply(
        self,
        correlation_id: str,
        result: T,
        operation_name: str,
        trace_context: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Handle a reply message with tracing context.
        
        Args:
            correlation_id: The correlation ID of the reply
            result: The result to set as the future's result
            operation_name: Name of the operation being handled
            trace_context: Optional trace context from the reply message
            
        Returns:
            True if the correlation ID was found and the future was set
        """
        if correlation_id not in self.pending_requests:
            logger.warning(f"Received reply for unknown correlation ID: {correlation_id}")
            return False
        
        # Start span for reply handling
        with self.tracer.start_as_current_span(
            name=f"{operation_name}_reply",
            kind=SpanKind.CONSUMER,
            attributes={"messaging.correlation_id": correlation_id}
        ) as span:
            # Link to parent span if trace context exists
            if trace_context:
                carrier = trace_context.copy()
                if parent_context := self.propagator.extract(carrier):
                    span.set_parent(parent_context)
            
            future = self.pending_requests[correlation_id]
            if not future.done():
                future.set_result(result)
                span.set_status(Status(StatusCode.OK))
                return True
            else:
                logger.warning(f"Future for correlation ID {correlation_id} is already done")
                span.set_status(
                    Status(StatusCode.ERROR, "Future already completed")
                )
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

"""
Message serialization with tracing support.
"""

from typing import Dict, Any, Optional
import json
import logging
import uuid
from datetime import datetime
import opentelemetry.trace as trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from ...domain.entities.message import MessageMetadata, Message

logger = logging.getLogger(__name__)

class MessageSerializer:
    """
    Handles message serialization with OpenTelemetry trace context.
    """
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.propagator = TraceContextTextMapPropagator()
    
    def create_envelope(
        self,
        payload: Dict[str, Any],
        message_type: str,
        version: str = "1.0",
        parent_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        operation_name: Optional[str] = None,
        destination_service: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a message envelope with trace context and message metadata.
        
        Args:
            payload: Message payload
            message_type: Type of message
            version: Message format version
            parent_id: ID of parent message if any
            correlation_id: Custom correlation ID, or generates one
            operation_name: Name of operation being performed
            destination_service: Target service name
        
        Returns:
            Message envelope with tracing context
        """
        # Get current trace context
        span_context = trace.get_current_span().get_span_context()
        carrier: Dict[str, str] = {}
        self.propagator.inject(carrier)
        
        metadata = MessageMetadata(
            message_type=message_type,
            version=version,
            correlation_id=correlation_id or str(uuid.uuid4()),
            trace_context={
                "traceparent": carrier.get("traceparent", ""),
                "tracestate": carrier.get("tracestate", ""),
            },
            parent_id=parent_id,
            causation_id=parent_id,  # Causation tracks message chain
            source_service=self.service_name,
            source_operation=operation_name,
            destination_service=destination_service,
            timestamp=int(datetime.now().timestamp() * 1000)
        )
        
        # Merge headers with any existing trace context headers
        headers = carrier.copy()
        headers.update(metadata.headers)
        metadata.headers = headers
        
        message = Message(metadata=metadata, payload=payload)
        return self._serialize_message(message)
    
    def _serialize_message(self, message: Message) -> Dict[str, Any]:
        """Serialize a Message object to a dictionary."""
        return {
            "metadata": {
                "messageType": message.metadata.message_type,
                "version": message.metadata.version,
                "timestamp": message.metadata.timestamp,
                "correlationId": message.metadata.correlation_id,
                "traceContext": message.metadata.trace_context,
                "parentId": message.metadata.parent_id,
                "causationId": message.metadata.causation_id,
                "sequenceNumber": message.metadata.sequence_number,
                "sourceService": message.metadata.source_service,
                "sourceOperation": message.metadata.source_operation,
                "destinationService": message.metadata.destination_service,
                "retryCount": message.metadata.retry_count,
                "errorDetails": message.metadata.error_details,
                "headers": message.metadata.headers
            },
            "payload": message.payload
        }
    
    def deserialize_message(self, data: Dict[str, Any]) -> Message:
        """
        Deserialize a dictionary into a Message object.
        
        Args:
            data: Message data dictionary
            
        Returns:
            Message object with metadata and payload
        """
        metadata = MessageMetadata(
            message_type=data["metadata"]["messageType"],
            version=data["metadata"].get("version", "1.0"),
            timestamp=data["metadata"].get("timestamp"),
            correlation_id=data["metadata"].get("correlationId"),
            trace_context=data["metadata"].get("traceContext", {}),
            parent_id=data["metadata"].get("parentId"),
            causation_id=data["metadata"].get("causationId"),
            sequence_number=data["metadata"].get("sequenceNumber"),
            source_service=data["metadata"].get("sourceService"),
            source_operation=data["metadata"].get("sourceOperation"),
            destination_service=data["metadata"].get("destinationService"),
            retry_count=data["metadata"].get("retryCount", 0),
            error_details=data["metadata"].get("errorDetails"),
            headers=data["metadata"].get("headers", {})
        )
        
        return Message(metadata=metadata, payload=data["payload"])

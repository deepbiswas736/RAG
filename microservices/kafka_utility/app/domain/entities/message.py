"""
Message Entities

Defines domain entities for Kafka messages.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class MessageMetadata:
    """Represents message metadata with W3C trace context support."""
    message_type: str
    version: str = "1.0"
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    correlation_id: Optional[str] = None
    trace_context: Dict[str, str] = field(default_factory=lambda: {
        "traceparent": "",  # W3C trace parent
        "tracestate": "",   # W3C trace state
    })
    parent_id: Optional[str] = None  # Parent message correlation ID
    causation_id: Optional[str] = None  # ID that caused this message
    sequence_number: Optional[int] = None  # Message sequence in a flow
    source_service: Optional[str] = None
    source_operation: Optional[str] = None
    destination_service: Optional[str] = None
    retry_count: int = 0
    error_details: Optional[Dict[str, Any]] = None
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class Message:
    """Represents a Kafka message with metadata and payload."""
    metadata: MessageMetadata
    payload: Dict[str, Any]


@dataclass
class DocumentEvent:
    """Represents a document event."""
    document_id: str
    status: str
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    chunks: Optional[List[Dict[str, Any]]] = None
    error: Optional[Dict[str, Any]] = None


@dataclass
class QueryEvent:
    """Represents a query event."""
    query_id: str
    query: str
    status: str
    user_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    document_ids: Optional[List[str]] = None
    results: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    processing_time: Optional[float] = None


@dataclass
class LLMTask:
    """Represents an LLM task."""
    task_id: str
    task_type: str  # "embedding" or "completion"
    model: Optional[str] = None
    priority: int = 5
    input: Any = None  # str or List[str]
    embedding_results: Optional[List[List[float]]] = None
    completion_results: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    processing_time: Optional[float] = None

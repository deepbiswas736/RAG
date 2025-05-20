"""
Query Service Kafka Client

This module provides a client for interacting with the Query Service via Kafka.
"""

import os
import logging
import uuid
from typing import Dict, Any, List, Optional

from ...application.services.schema_registry_service import SchemaRegistryService
from ...infrastructure.adapters.kafka_producer import KafkaProducerAdapter
from ...infrastructure.utils.message_serialization import MessageSerializer

logger = logging.getLogger(__name__)

class QueryServiceKafkaClient:
    """
    Client for interacting with the Query Service via Kafka.
    """
    
    def __init__(self, bootstrap_servers: Optional[str] = None):
        """
        Initialize the Query Service Kafka client.
        
        Args:
            bootstrap_servers: Optional Kafka bootstrap servers.
                               If None, uses KAFKA_BOOTSTRAP_SERVERS environment variable.
        """
        self.bootstrap_servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.producer = KafkaProducerAdapter(bootstrap_servers=self.bootstrap_servers)
        
        # Initialize schema registry
        self.schema_registry = SchemaRegistryService()
        self.message_serializer = MessageSerializer(schema_registry=self.schema_registry)
        
    async def initialize(self) -> None:
        """Initialize the client."""
        await self.schema_registry.initialize()
    
    async def send_query_event(self, query_id: str, query: str, 
                             user_id: Optional[str] = None,
                             filters: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send a query submitted event.
        
        Args:
            query_id: The ID of the query
            query: The query text
            user_id: Optional user ID that submitted the query
            filters: Optional filters to apply to the query
            
        Returns:
            True if the event was sent successfully, False otherwise
        """
        payload = {
            "queryId": query_id,
            "query": query,
            "status": "submitted"
        }
        
        if user_id:
            payload["userId"] = user_id
            
        if filters:
            payload["filters"] = filters
        
        # Create message envelope
        correlation_id = str(uuid.uuid4())
        envelope = self.message_serializer.create_envelope(
            payload=payload,
            message_type="query.submitted",
            metadata={"correlationId": correlation_id}
        )
        
        # Validate against schema
        if not self.message_serializer.validate_message(envelope, "query_event"):
            logger.error(f"Invalid query event for query {query_id}")
            return False
        
        # Send message
        return await self.producer.send_message(
            topic="query_events",
            key=query_id,
            value=envelope
        )
    
    async def send_query_result_event(self, query_id: str, answer: str,
                                    source_chunks: List[Dict[str, Any]],
                                    processing_time: float) -> bool:
        """
        Send a query result event.
        
        Args:
            query_id: The ID of the query
            answer: The generated answer
            source_chunks: List of source chunks used for the answer
            processing_time: Processing time in seconds
            
        Returns:
            True if the event was sent successfully, False otherwise
        """
        payload = {
            "queryId": query_id,
            "status": "completed",
            "results": {
                "answer": answer,
                "sourceChunks": source_chunks
            },
            "processingTime": processing_time
        }
        
        # Create message envelope
        envelope = self.message_serializer.create_envelope(
            payload=payload,
            message_type="query.completed",
            metadata={"correlationId": str(uuid.uuid4())}
        )
        
        # Validate against schema
        if not self.message_serializer.validate_message(envelope, "query_event"):
            logger.error(f"Invalid query result event for query {query_id}")
            return False
        
        # Send message
        return await self.producer.send_message(
            topic="query_events",
            key=query_id,
            value=envelope
        )
    
    async def send_query_failed_event(self, query_id: str, error_message: str, 
                                    error_code: Optional[str] = None) -> bool:
        """
        Send a query failed event.
        
        Args:
            query_id: The ID of the query
            error_message: The error message
            error_code: Optional error code
            
        Returns:
            True if the event was sent successfully, False otherwise
        """
        error = {
            "message": error_message
        }
        
        if error_code:
            error["code"] = error_code
            
        payload = {
            "queryId": query_id,
            "status": "failed",
            "error": error
        }
        
        # Create message envelope
        envelope = self.message_serializer.create_envelope(
            payload=payload,
            message_type="query.failed",
            metadata={"correlationId": str(uuid.uuid4())}
        )
        
        # Validate against schema
        if not self.message_serializer.validate_message(envelope, "query_event"):
            logger.error(f"Invalid query failed event for query {query_id}")
            return False
        
        # Send message
        return await self.producer.send_message(
            topic="query_events",
            key=query_id,
            value=envelope
        )
    
    async def close(self) -> None:
        """Close the client."""
        await self.producer.close()

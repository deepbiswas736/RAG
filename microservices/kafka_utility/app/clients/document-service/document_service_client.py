"""
Document Service Kafka Client

This module provides a client for interacting with the Document Service via Kafka.
"""

import os
import logging
import uuid
from typing import Dict, Any, List, Optional

from ...application.services.schema_registry_service import SchemaRegistryService
from ...infrastructure.adapters.kafka_producer import KafkaProducerAdapter
from ...infrastructure.utils.message_serialization import MessageSerializer

logger = logging.getLogger(__name__)

class DocumentServiceKafkaClient:
    """
    Client for interacting with the Document Service via Kafka.
    """
    
    def __init__(self, bootstrap_servers: Optional[str] = None):
        """
        Initialize the Document Service Kafka client.
        
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
    
    async def send_document_created_event(self, document_id: str, file_name: str, file_type: str, 
                                        file_size: int, user_id: Optional[str] = None, 
                                        metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send a document created event.
        
        Args:
            document_id: The ID of the document
            file_name: The name of the file
            file_type: The type/extension of the file
            file_size: The size of the file in bytes
            user_id: Optional user ID that created the document
            metadata: Optional additional metadata
            
        Returns:
            True if the event was sent successfully, False otherwise
        """
        payload = {
            "documentId": document_id,
            "status": "created",
            "fileName": file_name,
            "fileType": file_type,
            "fileSize": file_size
        }
        
        if user_id:
            payload["userId"] = user_id
            
        if metadata:
            payload["metadata"] = metadata
        
        # Create message envelope
        envelope = self.message_serializer.create_envelope(
            payload=payload,
            message_type="document.created",
            metadata={"correlationId": str(uuid.uuid4())}
        )
        
        # Validate against schema
        if not self.message_serializer.validate_message(envelope, "document_event"):
            logger.error(f"Invalid document created event for document {document_id}")
            return False
        
        # Send message
        return await self.producer.send_message(
            topic="document_events",
            key=document_id,
            value=envelope
        )
    
    async def send_document_processed_event(self, document_id: str, status: str, 
                                          chunks: Optional[List[Dict[str, Any]]] = None,
                                          metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send a document processed event.
        
        Args:
            document_id: The ID of the document
            status: The processing status ("completed" or "failed")
            chunks: Optional list of document chunks
            metadata: Optional additional metadata
            
        Returns:
            True if the event was sent successfully, False otherwise
        """
        payload = {
            "documentId": document_id,
            "status": status
        }
        
        if chunks:
            payload["chunks"] = chunks
            
        if metadata:
            payload["metadata"] = metadata
        
        # Create message envelope
        envelope = self.message_serializer.create_envelope(
            payload=payload,
            message_type="document.processed",
            metadata={"correlationId": str(uuid.uuid4())}
        )
        
        # Validate against schema
        if not self.message_serializer.validate_message(envelope, "document_event"):
            logger.error(f"Invalid document processed event for document {document_id}")
            return False
        
        # Send message
        return await self.producer.send_message(
            topic="document_events",
            key=document_id,
            value=envelope
        )
    
    async def send_metadata_extraction_request(self, document_id: str, document_path: str, 
                                             file_type: str, priority: int = 5) -> bool:
        """
        Send a request to extract metadata from a document.
        
        Args:
            document_id: The ID of the document
            document_path: Path to the document (can be a storage URL or file path)
            file_type: The type/extension of the file
            priority: Priority level (1-10, with 10 being highest)
            
        Returns:
            True if the event was sent successfully, False otherwise
        """
        payload = {
            "documentId": document_id,
            "documentPath": document_path,
            "fileType": file_type,
            "status": "metadata_requested",
            "priority": priority
        }
        
        # Create message envelope
        correlation_id = str(uuid.uuid4())
        envelope = self.message_serializer.create_envelope(
            payload=payload,
            message_type="document.metadata_requested",
            metadata={"correlationId": correlation_id}
        )
        
        # Validate against schema
        if not self.message_serializer.validate_message(envelope, "document_event"):
            logger.error(f"Invalid metadata extraction request for document {document_id}")
            return False
        
        # Send message
        return await self.producer.send_message(
            topic="metadata_extraction",
            key=document_id,
            value=envelope
        )
    
    async def send_document_failed_event(self, document_id: str, error_message: str, 
                                      error_code: Optional[str] = None) -> bool:
        """
        Send a document failed event.
        
        Args:
            document_id: The ID of the document
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
            "documentId": document_id,
            "status": "failed",
            "error": error
        }
        
        # Create message envelope
        envelope = self.message_serializer.create_envelope(
            payload=payload,
            message_type="document.failed",
            metadata={"correlationId": str(uuid.uuid4())}
        )
        
        # Validate against schema
        if not self.message_serializer.validate_message(envelope, "document_event"):
            logger.error(f"Invalid document failed event for document {document_id}")
            return False
        
        # Send message
        return await self.producer.send_message(
            topic="document_events",
            key=document_id,
            value=envelope
        )
    
    async def close(self) -> None:
        """Close the client."""
        await self.producer.close()

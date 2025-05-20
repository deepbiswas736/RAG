"""
Kafka Client
-----------
Provides messaging capabilities for sending document events to Kafka.
"""
import logging
import json
import os
from typing import Dict, Any, Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Configure logging
logger = logging.getLogger(__name__)

class KafkaClient:
    """Client for sending document events to Kafka"""
    
    def __init__(self, bootstrap_servers: Optional[str] = None):
        """
        Initialize Kafka client
        
        Args:
            bootstrap_servers: Kafka bootstrap servers
        """
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        
        # Initialize producer
        self._producer = None
        self._initialize_producer()
        
    def _initialize_producer(self):
        """Initialize Kafka producer"""
        try:
            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                # Set reasonable timeouts
                api_version_auto_timeout_ms=5000,
                request_timeout_ms=10000,
                max_block_ms=10000
            )
            
            logger.info(f"Kafka producer initialized with bootstrap servers: {self.bootstrap_servers}")
            
        except KafkaError as e:
            logger.warning(f"Failed to initialize Kafka producer: {e}. Messages will not be sent.")
            self._producer = None
            
    async def send_document_created_event(self, document_id: str, metadata: Dict[str, Any]):
        """
        Send document created event to Kafka
        
        Args:
            document_id: ID of the created document
            metadata: Document metadata
        """
        if not self._producer:
            logger.warning("Kafka producer not available, skipping document created event")
            return
            
        try:
            # Prepare message
            message = {
                "event_type": "document_created",
                "document_id": document_id,
                "metadata": metadata
            }
            
            # Send message to Kafka
            self._producer.send(
                topic="document-created",
                value=message
            )
            
            # Flush to ensure message is sent
            self._producer.flush()
            
            logger.info(f"Document created event sent for document: {document_id}")
            
        except KafkaError as e:
            logger.error(f"Error sending document created event: {e}")
            
    async def send_document_processed_event(self, document_id: str, status: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send document processed event
        
        Args:
            document_id: Document ID
            status: Processing status
            metadata: Optional metadata
            
        Returns:
            True if successful, False otherwise
        """
        if not self._producer:
            logger.warning(f"Cannot send document processed event: Kafka producer not initialized")
            return False
            
        try:
            data = {
                "documentId": document_id,
                "status": status
            }
            
            if metadata:
                data["metadata"] = metadata
                
            future = self._producer.send(
                'document_events', 
                key=document_id.encode('utf-8'), 
                value=data
            )
            
            # Wait for the message to be delivered
            record_metadata = future.get(timeout=10)
            logger.info(f"Sent document processed event for {document_id} to "
                      f"partition {record_metadata.partition} at offset {record_metadata.offset}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send document processed event: {e}")
            return False
            
    async def send_metadata_extraction_request(self, document_id: str, document_path: str, file_type: str) -> bool:
        """
        Send metadata extraction request
        
        Args:
            document_id: Document ID
            document_path: Path to the document
            file_type: File type/extension
            
        Returns:
            True if successful, False otherwise
        """
        if not self._producer:
            logger.warning(f"Cannot send metadata extraction request: Kafka producer not initialized")
            return False
            
        try:
            data = {
                "documentId": document_id,
                "documentPath": document_path,
                "fileType": file_type,
                "status": "metadata_requested",
                "priority": 5  # Default priority
            }
                
            future = self._producer.send(
                'metadata_extraction', 
                key=document_id.encode('utf-8'), 
                value=data
            )
            
            # Wait for the message to be delivered
            record_metadata = future.get(timeout=10)
            logger.info(f"Sent metadata extraction request for {document_id} to "
                      f"partition {record_metadata.partition} at offset {record_metadata.offset}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send metadata extraction request: {e}")
            return False
    
    async def send_document_chunks_created_event(self, document_id: str, chunk_count: int):
        """
        Send document chunks created event to Kafka
        
        Args:
            document_id: ID of the chunked document
            chunk_count: Number of chunks created
        """
        if not self._producer:
            logger.warning("Kafka producer not available, skipping document chunks created event")
            return
            
        try:
            # Prepare message
            message = {
                "event_type": "document_chunks_created",
                "document_id": document_id,
                "chunk_count": chunk_count
            }
            
            # Send message to Kafka
            self._producer.send(
                topic="document-chunks-created",
                value=message
            )
            
            # Flush to ensure message is sent
            self._producer.flush()
            
            logger.info(f"Document chunks created event sent for document: {document_id}, chunks: {chunk_count}")
            
        except KafkaError as e:
            logger.error(f"Error sending document chunks created event: {e}")
            
    async def send_embedding_request(self, document_id: str, chunks: list) -> bool:
        """
        Send embedding request to Kafka
        
        Args:
            document_id: ID of the document
            chunks: List of chunks
            
        Returns:
            True if successful, False otherwise
        """
        if not self._producer:
            logger.warning(f"Cannot send embedding request: Kafka producer not initialized")
            return False
            
        try:
            data = {
                "documentId": document_id,
                "chunks": chunks
            }
                
            future = self._producer.send(
                'embedding_requests', 
                key=document_id.encode('utf-8'), 
                value=data
            )
            
            # Wait for the message to be delivered
            record_metadata = future.get(timeout=10)
            logger.info(f"Sent embedding request for {document_id} to "
                      f"partition {record_metadata.partition} at offset {record_metadata.offset}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send embedding request: {e}")
            return False
    
    def close(self):
        """Close the Kafka producer"""
        if self._producer:
            self._producer.close()
            logger.info("Kafka producer closed")

"""
Document Service Kafka Client.
This module provides a client for interacting with the Document Service via Kafka.
"""

import logging
import json
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class DocumentServiceKafkaClient:
    """Kafka client for the Document Service."""
    
    def __init__(self, producer=None):
        """
        Initialize the Document Service Kafka client.
        
        Args:
            producer: The Kafka producer to use for sending messages.
        """
        self.producer = producer
        self.document_topic = "document_events"
        self.metadata_topic = "metadata_enrichment"
        
    def send_document_event(self, document_id: str, event_type: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Send a document event to the document_events topic.
        
        Args:
            document_id: The ID of the document.
            event_type: The type of event (e.g., "created", "updated", "deleted").
            metadata: Optional metadata to include with the event.
        """
        if self.producer is None:
            logger.warning("No producer available to send document event")
            return
            
        message = {
            "document_id": document_id,
            "event_type": event_type,
            "metadata": metadata or {}
        }
        
        self.producer.produce(
            topic=self.document_topic,
            key=document_id,
            value=json.dumps(message)
        )
        logger.info(f"Sent document event: {event_type} for document {document_id}")
            
    def request_metadata_extraction(self, document_id: str, content_type: str, file_path: str) -> None:
        """
        Request metadata extraction for a document.
        
        Args:
            document_id: The ID of the document.
            content_type: The MIME type of the document.
            file_path: The path to the document file.
        """
        if self.producer is None:
            logger.warning("No producer available to request metadata extraction")
            return
            
        message = {
            "document_id": document_id,
            "content_type": content_type,
            "file_path": file_path
        }
        
        self.producer.produce(
            topic=self.metadata_topic,
            key=document_id,
            value=json.dumps(message)
        )
        logger.info(f"Requested metadata extraction for document {document_id}")

"""
Query Service Kafka Client.
This module provides a client for interacting with the Query Service via Kafka.
"""

import logging
import json
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class QueryServiceKafkaClient:
    """Kafka client for the Query Service."""
    
    def __init__(self, producer=None):
        """
        Initialize the Query Service Kafka client.
        
        Args:
            producer: The Kafka producer to use for sending messages.
        """
        self.producer = producer
        self.query_topic = "rag_queries"
        
    def send_query_event(self, query_id: str, query_text: str, user_id: Optional[str] = None, 
                         conversation_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Send a query event to the rag_queries topic.
        
        Args:
            query_id: The ID of the query.
            query_text: The query text.
            user_id: Optional user ID.
            conversation_id: Optional conversation ID.
            metadata: Optional metadata to include with the event.
        """
        if self.producer is None:
            logger.warning("No producer available to send query event")
            return
            
        message = {
            "query_id": query_id,
            "query_text": query_text,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "metadata": metadata or {}
        }
        
        self.producer.produce(
            topic=self.query_topic,
            key=query_id,
            value=json.dumps(message)
        )
        logger.info(f"Sent query event for query {query_id}")

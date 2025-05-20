"""
LLM Service Kafka Client.
This module provides a client for interacting with the LLM Service via Kafka.
"""

import logging
import json
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class LLMServiceKafkaClient:
    """Kafka client for the LLM Service."""
    
    def __init__(self, producer=None):
        """
        Initialize the LLM Service Kafka client.
        
        Args:
            producer: The Kafka producer to use for sending messages.
        """
        self.producer = producer
        self.llm_request_topic = "llm_requests"
        self.embedding_topic = "embedding_requests"
        
    def send_llm_request(self, request_id: str, prompt: str, model: Optional[str] = None, 
                          parameters: Optional[Dict[str, Any]] = None) -> None:
        """
        Send an LLM request to the llm_requests topic.
        
        Args:
            request_id: The ID of the request.
            prompt: The prompt text.
            model: Optional model name to use.
            parameters: Optional parameters for the LLM.
        """
        if self.producer is None:
            logger.warning("No producer available to send LLM request")
            return
            
        message = {
            "request_id": request_id,
            "prompt": prompt,
            "model": model,
            "parameters": parameters or {}
        }
        
        self.producer.produce(
            topic=self.llm_request_topic,
            key=request_id,
            value=json.dumps(message)
        )
        logger.info(f"Sent LLM request {request_id}")
        
    def request_embedding(self, request_id: str, text: str, model: Optional[str] = None) -> None:
        """
        Request text embedding via the embedding_requests topic.
        
        Args:
            request_id: The ID of the request.
            text: The text to embed.
            model: Optional embedding model to use.
        """
        if self.producer is None:
            logger.warning("No producer available to request embedding")
            return
            
        message = {
            "request_id": request_id,
            "text": text,
            "model": model
        }
        
        self.producer.produce(
            topic=self.embedding_topic,
            key=request_id,
            value=json.dumps(message)
        )
        logger.info(f"Requested embedding for text with ID {request_id}")

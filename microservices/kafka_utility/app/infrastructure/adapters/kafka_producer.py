"""
Kafka Producer Adapter

This module provides a concrete implementation of the MessageProducer interface
that uses aiokafka to send messages to Kafka.
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ...domain.interfaces.message_producer import MessageProducer
from ..utils.metrics import track_producer_latency, increment_message_produced, increment_producer_errors

logger = logging.getLogger(__name__)

class KafkaProducerAdapter(MessageProducer):
    """
    Concrete implementation of MessageProducer interface using aiokafka.
    """
    
    def __init__(self, bootstrap_servers: str):
        """
        Initialize the Kafka producer adapter.
        
        Args:
            bootstrap_servers: Comma-separated list of Kafka bootstrap servers
        """
        self.bootstrap_servers = bootstrap_servers
        self._producer = None
        self._producer_lock = asyncio.Lock()
    
    async def _ensure_producer_initialized(self) -> bool:
        """
        Ensure the Kafka producer is initialized.
        
        Returns:
            True if the producer is initialized, False otherwise
        """
        if self._producer is not None:
            return True
        
        async with self._producer_lock:
            if self._producer is not None:
                return True
                
            try:
                self._producer = AIOKafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    key_serializer=lambda k: k.encode('utf-8') if k else None,
                    acks="all",  # Wait for all replicas to acknowledge
                    enable_idempotence=True,  # Prevent duplicate messages
                    compression_type="gzip",  # Compress messages
                )
                await self._producer.start()
                logger.info(f"Kafka producer initialized with bootstrap servers: {self.bootstrap_servers}")
                return True
            except Exception as e:
                logger.error(f"Failed to initialize Kafka producer: {e}")
                self._producer = None
                return False
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(KafkaError),
        reraise=True
    )
    async def send_message(self, topic: str, key: Optional[str], value: Dict[str, Any],
                          headers: Optional[Dict[str, str]] = None) -> bool:
        """
        Send a message to Kafka with retry capability.
        
        Args:
            topic: The topic to send the message to
            key: The optional message key
            value: The message value
            headers: Optional message headers
            
        Returns:
            True if the message was sent successfully, False otherwise
        """
        if not await self._ensure_producer_initialized():
            increment_producer_errors(topic)
            return False
        
        try:
            # Convert header values to bytes
            kafka_headers = None
            if headers:
                kafka_headers = [(k, v.encode('utf-8')) for k, v in headers.items()]
            
            # Track latency
            with track_producer_latency(topic):
                # Send the message
                await self._producer.send_and_wait(
                    topic=topic,
                    key=key,
                    value=value,
                    headers=kafka_headers
                )
            
            # Track metrics
            increment_message_produced(topic)
            
            return True
        except KafkaError as e:
            logger.error(f"Kafka error sending message to {topic}: {e}")
            increment_producer_errors(topic)
            raise  # Let retry decorator handle it
        except Exception as e:
            logger.error(f"Error sending message to {topic}: {e}")
            increment_producer_errors(topic)
            return False
    
    async def close(self) -> None:
        """Close the producer."""
        if self._producer:
            try:
                await self._producer.stop()
                self._producer = None
                logger.info("Kafka producer closed")
            except Exception as e:
                logger.error(f"Error closing Kafka producer: {e}")

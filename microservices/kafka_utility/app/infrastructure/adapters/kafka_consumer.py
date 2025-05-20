"""
Kafka Consumer Adapter

This module provides a concrete implementation of the MessageConsumer interface
that uses aiokafka to consume messages from Kafka.
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable, List, Set
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

from ...domain.interfaces.message_consumer import MessageConsumer
from ..utils.metrics import (
    track_consumer_latency, increment_message_consumed, 
    increment_consumer_errors, set_kafka_connection_status
)

logger = logging.getLogger(__name__)

class KafkaConsumerAdapter(MessageConsumer):
    """
    Concrete implementation of MessageConsumer interface using aiokafka.
    """
    
    def __init__(self, bootstrap_servers: str, group_id: str, auto_offset_reset: str = "earliest"):
        """
        Initialize the Kafka consumer adapter.
        
        Args:
            bootstrap_servers: Comma-separated list of Kafka bootstrap servers
            group_id: Consumer group ID
            auto_offset_reset: Offset reset strategy ("earliest" or "latest")
        """
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.auto_offset_reset = auto_offset_reset
        
        self._consumer = None
        self._handlers: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = {}
        self._subscribed_topics: Set[str] = set()
        self._running = False
        self._consumption_task = None
        self._consumer_lock = asyncio.Lock()
    
    def register_handler(self, topic: str, 
                        handler: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """
        Register a handler for a topic.
        
        Args:
            topic: The topic to handle
            handler: The handler function that will be called with the message value
        """
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)
        self._subscribed_topics.add(topic)
        logger.info(f"Registered handler for topic {topic}")
    
    async def _ensure_consumer_initialized(self) -> bool:
        """
        Ensure the Kafka consumer is initialized.
        
        Returns:
            True if the consumer is initialized, False otherwise
        """
        if self._consumer is not None:
            return True
        
        if not self._subscribed_topics:
            logger.error("Cannot initialize consumer: no topics have been registered")
            return False
        
        async with self._consumer_lock:
            if self._consumer is not None:
                return True
                
            try:
                self._consumer = AIOKafkaConsumer(
                    *self._subscribed_topics,
                    bootstrap_servers=self.bootstrap_servers,
                    group_id=self.group_id,
                    auto_offset_reset=self.auto_offset_reset,
                    enable_auto_commit=False,  # We'll commit manually
                    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                )
                await self._consumer.start()
                logger.info(f"Kafka consumer initialized for topics {self._subscribed_topics}")
                set_kafka_connection_status(self.bootstrap_servers, True)
                return True
            except Exception as e:
                logger.error(f"Failed to initialize Kafka consumer: {e}")
                self._consumer = None
                set_kafka_connection_status(self.bootstrap_servers, False)
                return False
    
    async def start_consuming(self) -> None:
        """Start consuming messages from Kafka."""
        if self._running:
            logger.warning("Consumer is already running")
            return
            
        if not await self._ensure_consumer_initialized():
            raise RuntimeError("Failed to initialize Kafka consumer")
            
        self._running = True
        self._consumption_task = asyncio.create_task(self._consume_loop())
        logger.info("Started consuming messages")
    
    async def _consume_loop(self) -> None:
        """Main consumption loop."""
        try:
            while self._running:
                try:
                    # Batch fetch messages with timeout
                    async for message in self._consumer:
                        topic = message.topic
                        
                        if topic not in self._handlers:
                            logger.warning(f"No handler registered for topic {topic}")
                            continue
                        
                        try:
                            # Process the message
                            value = message.value
                            
                            # Process with all registered handlers for this topic
                            for handler in self._handlers[topic]:
                                with track_consumer_latency(topic, self.group_id):
                                    await handler(value)
                                
                            # Track successful processing
                            increment_message_consumed(topic, self.group_id)
                            
                            # Commit offset after successful processing
                            await self._consumer.commit()
                        except Exception as e:
                            # Handle processing errors
                            increment_consumer_errors(topic, self.group_id)
                            logger.error(f"Error processing message from {topic}: {e}")
                            
                            # Don't commit offset on error - message will be reprocessed
                            # TODO: Implement dead-letter queue for failed messages
                
                except asyncio.CancelledError:
                    raise
                except KafkaError as e:
                    logger.error(f"Kafka error in consumer: {e}")
                    set_kafka_connection_status(self.bootstrap_servers, False)
                    # Wait before reconnecting
                    await asyncio.sleep(5)
                    
                    # Try to reconnect
                    if await self._ensure_consumer_initialized():
                        set_kafka_connection_status(self.bootstrap_servers, True)
                except Exception as e:
                    logger.error(f"Unexpected error in consumer loop: {e}")
                    await asyncio.sleep(1)
        
        except asyncio.CancelledError:
            logger.info("Consumer task cancelled")
        finally:
            if self._consumer:
                await self._consumer.stop()
                self._consumer = None
            self._running = False
    
    async def stop(self) -> None:
        """Stop consuming messages from Kafka."""
        if not self._running:
            logger.info("Consumer is not running")
            return
        
        self._running = False
        
        if self._consumption_task:
            self._consumption_task.cancel()
            try:
                await self._consumption_task
            except asyncio.CancelledError:
                pass
            self._consumption_task = None
        
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
            
        logger.info("Stopped consuming messages")

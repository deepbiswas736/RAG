import asyncio
import json
import logging
import os
from typing import Dict, Optional
from datetime import datetime
import time
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from kafka.structs import OffsetAndMetadata, TopicPartition
import aiohttp
from aiolimiter import AsyncLimiter

from ...domain.services.metadata_extraction_service import MetadataExtractionService
from ...infrastructure.llm.llm_manager import LLMManager
from ...domain.repositories.document_repository import DocumentRepository

# Create a separate logger with enhanced formatting for the metadata consumer
logger = logging.getLogger(__name__)

class MetadataConsumerService:
    """
    Consumer service for processing metadata enrichment messages from Kafka.
    Handles the second phase of the two-step metadata extraction process.
    """
    
    def __init__(
        self,
        document_repository: DocumentRepository,
        llm_manager: LLMManager,
        kafka_bootstrap_servers: str = None,
        consumer_group_id: str = "metadata_enrichment_group",
        topic: str = "metadata_enrichment",
        rate_limit: int = 10,  # Default: 10 requests per minute
        rate_period: int = 60  # Default: 1 minute period
    ):
        """
        Initialize the metadata consumer service.
        
        Args:
            document_repository: Repository for document storage
            llm_manager: LLM manager for metadata enrichment
            kafka_bootstrap_servers: Kafka servers for consuming messages
            consumer_group_id: Kafka consumer group ID
            topic: Kafka topic to consume from
            rate_limit: Maximum number of LLM requests per period
            rate_period: Time period in seconds for rate limiting
        """
        self.document_repository = document_repository
        self.llm_manager = llm_manager
        self.bootstrap_servers = kafka_bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.consumer_group_id = consumer_group_id
        self.topic = topic
        self.running = False
        self.message_count = 0  # Add counter to track processed messages
        
        # Enable explicit document ID tracking during enrichment
        self.ensure_document_id = True
        
        # Initialize rate limiter for LLM requests
        self.rate_limiter = AsyncLimiter(rate_limit, rate_period)
        
        # Initialize metadata extraction service
        self.metadata_service = MetadataExtractionService(llm_manager=llm_manager)
        logger.info(f"[METADATA_CONSUMER] Initialized metadata consumer service for topic: {self.topic} with rate limit: {rate_limit}/{rate_period}s")
    
    async def start(self):
        """Start consuming metadata enrichment messages."""
        if self.running:
            logger.info("[METADATA_CONSUMER] Metadata consumer is already running.")
            return
            
        self.running = True
        logger.info(f"[METADATA_CONSUMER] Starting metadata consumer for topic {self.topic}")
        
        # Run the consumer in a background task
        loop = asyncio.get_event_loop()
        self.consumer_task = loop.create_task(self._consume_messages())
        
        # Log every 5 minutes about consumer status
        self.status_task = loop.create_task(self._log_status_periodically())
        
        # Wait a short time to check for immediate startup issues
        await asyncio.sleep(2)
        
        # If the task has already failed, log it clearly
        if hasattr(self, 'consumer_task') and self.consumer_task.done() and self.consumer_task.exception() is not None:
            logger.error(f"[METADATA_CONSUMER] Failed to start: {self.consumer_task.exception()}")
            raise self.consumer_task.exception()
            
        logger.info("[METADATA_CONSUMER] Started successfully")
        
    async def _log_status_periodically(self):
        """Log status information periodically to confirm the consumer is still running"""
        try:
            while self.running:
                logger.info(f"[METADATA_CONSUMER] Status update - Running: {self.running}, Messages processed: {self.message_count}")
                await asyncio.sleep(300)  # Log every 5 minutes
        except asyncio.CancelledError:
            logger.info("[METADATA_CONSUMER] Status logging task cancelled")
        except Exception as e:
            logger.error(f"[METADATA_CONSUMER] Error in status logging: {e}")
        
    async def stop(self):
        """Stop the metadata consumer."""
        if not self.running:
            return
            
        self.running = False
        
        # Cancel status task if it exists
        if hasattr(self, 'status_task') and not self.status_task.done():
            self.status_task.cancel()
            try:
                await self.status_task
            except asyncio.CancelledError:
                pass
        
        if hasattr(self, 'consumer_task') and not self.consumer_task.done():
            self.consumer_task.cancel()
            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass
            
        logger.info(f"[METADATA_CONSUMER] Metadata consumer stopped. Total messages processed: {self.message_count}")
    
    async def _consume_messages(self):
        """Consume metadata enrichment messages from Kafka."""
        try:
            # Add verbose logging about consumer creation attempt
            logger.info(f"[METADATA_CONSUMER] Creating Kafka consumer for topic {self.topic} with bootstrap servers {self.bootstrap_servers}")
            
            # Create consumer in a thread-safe way
            consumer = await asyncio.to_thread(
                KafkaConsumer,
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.consumer_group_id,
                auto_offset_reset='earliest',
                value_deserializer=lambda m: json.loads(m.decode('utf-8')) if m else None,
                enable_auto_commit=False,
                # Add shorter timeouts to fail faster
                session_timeout_ms=10000,
                request_timeout_ms=15000,
                api_version_auto_timeout_ms=5000
            )
            
            # List of known invalid document IDs to ignore
            invalid_document_ids = [
                "e4995364-b743-4eb2-915d-7a308038ec18",
                "c0cb8211-fc04-46f1-b091-a60042d640ad"
            ]
            
            logger.info(f"[METADATA_CONSUMER] Connected to Kafka and started consuming messages from topic: {self.topic}")
            logger.info(f"[METADATA_CONSUMER] Consumer settings - Group: {self.consumer_group_id}, Auto offset reset: earliest")
            logger.info(f"[METADATA_CONSUMER] The following document IDs will be ignored: {invalid_document_ids}")
            
            # Log information about existing topics
            try:
                topics = consumer.topics()
                logger.info(f"[METADATA_CONSUMER] Available Kafka topics: {', '.join(topics)}")
                if self.topic not in topics:
                    logger.warning(f"[METADATA_CONSUMER] Warning: Topic '{self.topic}' does not exist in Kafka!")
            except Exception as e:
                logger.error(f"[METADATA_CONSUMER] Could not check available topics: {e}")
            
            poll_count = 0
            empty_polls = 0
            last_message_time = time.time()
            
            while self.running:
                poll_count += 1
                
                # Every 100 polls, log that we're still polling
                if poll_count % 100 == 0:
                    time_since_last = time.time() - last_message_time
                    logger.debug(f"[METADATA_CONSUMER] Still polling for messages (polls: {poll_count}, empty: {empty_polls}, seconds since last message: {time_since_last:.1f})")
                
                # Poll for messages
                messages = await asyncio.to_thread(consumer.poll, timeout_ms=1000)
                
                if not messages:
                    empty_polls += 1
                    await asyncio.sleep(0.1)  # Short sleep if no messages
                    continue
                
                # Reset counters when we get messages
                empty_polls = 0
                last_message_time = time.time()
                
                for topic_partition, records in messages.items():
                    logger.info(f"[METADATA_CONSUMER] Received {len(records)} messages from {topic_partition.topic}:{topic_partition.partition}")
                    
                    for record in records:
                        try:
                            message = record.value
                            logger.info(f"[METADATA_CONSUMER] Processing message at offset {record.offset}: {message}")
                            
                            # Check if this is a known invalid document ID that should be skipped
                            if message.get('document_id') in invalid_document_ids:
                                logger.warning(f"[METADATA_CONSUMER] Skipping known invalid document ID: {message.get('document_id')}")
                                # Skip processing but still commit the offset to move past this message
                                tp = TopicPartition(topic_partition.topic, topic_partition.partition)
                                om = OffsetAndMetadata(record.offset + 1, None, 0)  # Added leader_epoch parameter (0)
                                consumer.commit({tp: om})
                                logger.info(f"[METADATA_CONSUMER] Committed offset to skip invalid document ID with offset {record.offset}")
                                continue
                            
                            # Process the metadata enrichment message within rate limiting
                            async with self.rate_limiter:
                                logger.info(f"[METADATA_CONSUMER] Starting enrichment for document_id: {message.get('document_id', 'unknown')}")
                                await self.metadata_service.process_enrichment_message(
                                    message, self.document_repository
                                )
                                self.message_count += 1
                                logger.info(f"[METADATA_CONSUMER] Completed enrichment for document_id: {message.get('document_id', 'unknown')}, total processed: {self.message_count}")
                                
                            # Always commit the offset even if document wasn't found
                            # This prevents the AssertionError in the Kafka client
                            try:
                                tp = TopicPartition(topic_partition.topic, topic_partition.partition)
                                om = OffsetAndMetadata(record.offset + 1, None, 0)  # Added leader_epoch parameter (0)
                                consumer.commit({tp: om})
                                logger.info(f"[METADATA_CONSUMER] Committed offset {record.offset + 1} for partition {topic_partition}")
                            except Exception as commit_error:
                                logger.error(f"[METADATA_CONSUMER] Error committing offset: {commit_error}", exc_info=True)
                            
                        except Exception as e:
                            logger.error(f"[METADATA_CONSUMER] Error processing metadata enrichment message: {e}", exc_info=True)
                            # Still commit offset to prevent reprocessing the problematic message
                            try:
                                tp = TopicPartition(topic_partition.topic, topic_partition.partition)
                                om = OffsetAndMetadata(record.offset + 1, None, 0)  # Added leader_epoch parameter (0)
                                consumer.commit({tp: om})
                                logger.info(f"[METADATA_CONSUMER] Committed offset after error to skip problematic message with offset {record.offset}")
                            except Exception as commit_error:
                                logger.error(f"[METADATA_CONSUMER] Error committing offset after processing error: {commit_error}", exc_info=True)
                
                # Small delay to prevent CPU hogging
                await asyncio.sleep(0.01)
                
        except Exception as e:
            logger.error(f"[METADATA_CONSUMER] Critical error in metadata consumer: {e}", exc_info=True)
            # Re-raise to trigger application recovery if needed
            raise
            
        finally:
            if 'consumer' in locals():
                consumer.close()
            self.running = False
            logger.info(f"[METADATA_CONSUMER] Metadata consumer stopped due to error or shutdown. Total messages processed: {self.message_count}")
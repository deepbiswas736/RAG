"""
Refactored Metadata Consumer

This module implements a Kafka consumer for document metadata extraction requests
that uses multiple services to extract and enhance document metadata.
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime

# Kafka and utility imports
from kafka_utility.app.infrastructure.adapters.kafka_consumer import KafkaConsumerAdapter
from kafka_utility.app.infrastructure.adapters.kafka_producer import KafkaProducerAdapter
from kafka_utility.app.infrastructure.adapters.consumer_debug import diagnose_kafka_connection, get_consumer_status

# Local application imports
from kafka_utility.app.clients.document_service import DocumentServiceKafkaClient
from kafka_utility.app.clients.llm_service import LLMServiceKafkaClient
from ...application.services.llm_service import LLMService
from ...domain.models.embedding import Embedding
from ..persistence.mongodb_client import MongoDBClient

# Import the service classes
from ...domain.services.document_retrieval_service import DocumentRetrievalService
from ...domain.services.document_summarizer import DocumentSummarizer
from ...domain.services.topic_extractor import TopicExtractor
from ...domain.services.metadata_updater import MetadataUpdater

logger = logging.getLogger(__name__)

MAX_CONCURRENT_TASKS_DEFAULT = 5

class MetadataConsumerService:
    """
    Metadata Consumer Service for processing document metadata extraction requests.
    """
    
    def __init__(
        self,
        consumer_config: Dict[str, Any],
        document_topic: str,
        producer_config: Dict[str, Any],
        llm_service: LLMService,
        max_concurrent_tasks: int = MAX_CONCURRENT_TASKS_DEFAULT
    ):
        """
        Initializes the MetadataConsumerService.

        Args:
            consumer_config: Configuration for the Kafka consumer.
            document_topic: The Kafka topic for document metadata.
            producer_config: Configuration for the Kafka producer.
            llm_service: Instance of LLMService.
            max_concurrent_tasks: Maximum concurrent processing tasks.
        """
        # Store configuration
        self.consumer_config = consumer_config
        self.producer_config = producer_config
        self.document_topic = document_topic
        self.llm_service = llm_service
        
        # Initialize Kafka components
        self.consumer = KafkaConsumerAdapter(
            bootstrap_servers=self.consumer_config.get('bootstrap.servers'),
            group_id=self.consumer_config.get('group.id'),
            auto_offset_reset=self.consumer_config.get('auto.offset.reset', 'earliest')
        )
        
        self.producer_adapter = KafkaProducerAdapter(
            bootstrap_servers=self.producer_config.get('bootstrap.servers')
        )
        
        # Initialize clients
        self.document_client = DocumentServiceKafkaClient(producer=self.producer_adapter)
        self.llm_client = LLMServiceKafkaClient(producer=self.producer_adapter)
        self.mongo_client = MongoDBClient()
        
        # Initialize service classes
        self.document_service = DocumentRetrievalService(self.document_client, self.mongo_client)
        self.document_summarizer = DocumentSummarizer(self.llm_service)
        self.topic_extractor = TopicExtractor(self.llm_service)
        self.metadata_updater = MetadataUpdater(self.document_client, self.mongo_client)
        
        # Task semaphore for concurrency control
        self.task_semaphore = asyncio.Semaphore(max_concurrent_tasks)
        
        # Stats
        self.processed_count = 0
        self.failed_count = 0
        
        logger.info("Metadata Consumer Service initialized with required services")

    async def initialize(self) -> None:
        """Initialize the consumer service and its dependencies."""
        bootstrap_servers = self.consumer_config.get('bootstrap.servers')
        logger.info(f"Initializing metadata consumer for topic {self.document_topic} with bootstrap servers: {bootstrap_servers}")
        
        try:
            # Initialize MongoDB client
            await self.mongo_client.initialize()
            
            # Register message handler
            self.consumer.register_handler(self.document_topic, self._handle_metadata_request)
            logger.info(f"Handler registered successfully for topic: {self.document_topic}")
            
            logger.info("Metadata consumer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize metadata consumer: {e}", exc_info=True)
            raise

    async def start(self) -> None:
        """Start consuming metadata extraction requests."""
        logger.info(f"Starting metadata consumer for topic {self.document_topic}")
        
        try:
            # Start consuming messages
            await self.consumer.start_consuming()
            
            # Start background task for periodic stats reporting
            asyncio.create_task(self._report_stats_periodically())
            
            # Verify Kafka connection
            await self._verify_kafka_connection()
            
            logger.info("Metadata consumer started successfully")
        except Exception as e:
            logger.error(f"Failed to start metadata consumer: {e}", exc_info=True)
            raise
    
    async def stop(self) -> None:
        """Stop consuming messages."""
        logger.info("Stopping metadata consumer")
        
        # Stop consuming messages
        await self.consumer.stop()
        
        logger.info("Metadata consumer stopped")
    
    async def _verify_kafka_connection(self) -> None:
        """Verify Kafka connection and log status."""
        logger.info("Verifying Kafka connection and topic subscription...")
        
        if not hasattr(self.consumer, '_consumer') or not self.consumer._consumer:
            logger.warning("Consumer internal AIOKafkaConsumer not initialized or accessible")
            return
            
        try:
            is_connected = False
            
            # Try accessing bootstrap_connected via the internal client object
            if hasattr(self.consumer._consumer, 'client') and self.consumer._consumer.client:
                is_connected = self.consumer._consumer.client.bootstrap_connected()
            else:
                logger.warning("Consumer's internal KafkaClient not available for bootstrap_connected check.")
                
            logger.info(f"Consumer connected (via client check): {is_connected}")
            
            # Log assigned partitions
            if hasattr(self.consumer._consumer, 'assignment'):
                assigned_partitions = self.consumer._consumer.assignment()
                logger.info(f"Consumer current assignment: {assigned_partitions}")
            else:
                logger.warning("Could not retrieve consumer assignment.")
                
            logger.info(f"Subscribed topics: {self.consumer._subscribed_topics}")
            logger.info(f"Consumer group: {self.consumer.group_id}")
            
        except Exception as e:
            logger.warning(f"Error checking Kafka connection: {e}")
            
    async def _report_stats_periodically(self) -> None:
        """Report consumer stats periodically."""
        while True:
            logger.info(f"Metadata consumer stats - Processed: {self.processed_count}, Failed: {self.failed_count}")
            await asyncio.sleep(300)  # Report every 5 minutes
            
    async def _handle_metadata_request(self, message: Dict[str, Any]) -> None:
        """
        Handle a metadata extraction request message.
        
        Args:
            message: The Kafka message value (document event)
        """
        try:
            logger.info(f"Handler received message: {message}")
            
            # Handle both direct message and payload structure
            if "payload" in message:
                payload = message.get("payload", {})
                metadata = message.get("metadata", {})
            else:
                payload = message
                metadata = {}
            
            # Support both camelCase (from API) and snake_case naming
            document_id = payload.get("documentId") or payload.get("document_id")
            document_path = payload.get("documentPath") or payload.get("document_path")
            file_type = payload.get("fileType") or payload.get("file_type")
            priority = payload.get("priority", 5)
            
            logger.info(f"Received metadata extraction request for document {document_id}")
            
            if not document_id:
                logger.error("Invalid metadata request: missing documentId/document_id")
                return
                
            # Process the request with concurrency control
            async with self.task_semaphore:
                await self._process_metadata_request(
                    document_id=document_id,
                    document_path=document_path,
                    file_type=file_type,
                    priority=priority
                )
        
        except Exception as e:
            logger.error(f"Error handling metadata extraction request: {e}", exc_info=True)
            self.failed_count += 1
    
    async def _process_metadata_request(
        self, document_id: str, document_path: str, file_type: str, priority: int
    ) -> None:
        """
        Process a metadata extraction request using the service classes.
        
        Args:
            document_id: The ID of the document
            document_path: Path to the document
            file_type: The type/extension of the file
            priority: Priority level
        """
        try:
            logger.info(f"Processing metadata and topics for document {document_id}")

            # Step 1: Retrieve document and its chunks
            document_data = await self.document_service.get_document_by_id(document_id)
            if not document_data:
                logger.error(f"Document {document_id} not found.")
                self.failed_count += 1
                await self.document_service.update_document_processing_status(
                    document_id=document_id,
                    status="failed",
                    error=f"Document {document_id} not found during metadata extraction."
                )
                return

            document_chunks = await self.document_service.get_document_chunks(document_id)
            if not document_chunks:
                logger.warning(f"No chunks found for document {document_id}. Proceeding with document-level metadata.")
            
            # Get document content for analysis
            document_content = self.document_service.get_document_content(document_data, document_chunks)

            # Step 2: Extract document summary and metadata
            parsed_document_summary = await self.document_summarizer.generate_recursive_summary(
                document_content=document_content,
                file_type=file_type
            )
            
            # Step 3: Extract topics for each chunk
            updated_chunks_metadata = []
            
            for chunk in document_chunks:
                chunk_id = chunk.get("chunk_id")
                chunk_content = chunk.get("content", "")
                
                if not chunk_content:
                    logger.warning(f"Chunk {chunk_id} for document {document_id} has no content. Skipping topic extraction.")
                    continue

                # Extract topics for this chunk
                chunk_topics = await self.topic_extractor.extract_chunk_topics(chunk_content)
                
                # Prepare updated metadata
                current_chunk_metadata = chunk.get("metadata", {})
                current_chunk_metadata["extracted_topics"] = chunk_topics
                current_chunk_metadata["last_topic_extraction_timestamp"] = datetime.utcnow().isoformat()
                
                updated_chunks_metadata.append({
                    "chunk_id": chunk_id,
                    "metadata": current_chunk_metadata,
                    "topics": chunk_topics
                })
                
                # Save topics to dedicated collection
                await self.metadata_updater.save_document_topics(
                    document_id=document_id,
                    topics=chunk_topics,
                    chunk_id=chunk_id
                )
                
                logger.info(f"Extracted topics for chunk {chunk_id} of document {document_id}: {chunk_topics}")

            # Step 4: Consolidate overall document metadata
            final_document_metadata = document_data.get("metadata", {})
            final_document_metadata["document_description"] = parsed_document_summary.get("description", "N/A")
            final_document_metadata["document_category"] = parsed_document_summary.get("category", "N/A")
            final_document_metadata["related_entity"] = parsed_document_summary.get("related_entity", "N/A")
            
            # Collect all unique topics across chunks
            all_topics = list(set(
                topic 
                for chunk_meta in updated_chunks_metadata 
                for topic in chunk_meta.get("topics", [])
            ))
            
            final_document_metadata["overall_topics"] = all_topics
            final_document_metadata["last_metadata_extraction_timestamp"] = datetime.utcnow().isoformat()
            
            # Save document-level topics to dedicated collection
            await self.metadata_updater.save_document_topics(
                document_id=document_id,
                topics=all_topics
            )

            # Step 5: Update document and chunks metadata
            success = await self.metadata_updater.update_document_and_chunks(
                document_id=document_id,
                document_metadata=final_document_metadata,
                chunks_metadata=updated_chunks_metadata
            )
            
            if success:
                logger.info(f"Successfully processed and updated metadata and topics for document {document_id}")
                self.processed_count += 1
            else:
                logger.error(f"Failed to update metadata for document {document_id}")
                self.failed_count += 1
                
        except Exception as e:
            logger.error(f"Error processing metadata for document {document_id}: {e}", exc_info=True)
            self.failed_count += 1
            
            # Update document status
            await self.document_service.update_document_processing_status(
                document_id=document_id,
                status="failed",
                error=f"Error in metadata processing: {str(e)}"
            )
    
    async def debug_status(self) -> Dict[str, Any]:
        """
        Get detailed debug information about the consumer's status.
        
        Returns:
            A dictionary with detailed consumer status information
        """
        try:
            from aiokafka.admin import AIOKafkaAdminClient
            
            status = {
                "initialized": self.consumer is not None,
                "service_status": {
                    "bootstrap_servers": self.consumer_config.get('bootstrap.servers'),
                    "topic": self.document_topic,
                    "consumer_group_id": self.consumer_config.get('group.id'),
                    "processed_count": self.processed_count,
                    "failed_count": self.failed_count,
                },
            }
            
            # Add detailed consumer status
            consumer_status = get_consumer_status(self.consumer)
            status["consumer_status"] = consumer_status
            
            # Check topic existence
            bootstrap_servers = self.consumer_config.get('bootstrap.servers')
            try:
                admin_client = AIOKafkaAdminClient(bootstrap_servers=bootstrap_servers)
                await admin_client.start()
                topics = await admin_client.list_topics()
                status["topic_exists"] = self.document_topic in topics
                status["available_topics"] = list(topics)
                await admin_client.close()
            except Exception as e:
                logger.error(f"Failed to check topic existence: {e}")
                status["topic_error"] = str(e)
            
            # Test connection to Kafka
            try:
                from aiokafka import AIOKafkaProducer
                producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)
                await producer.start()
                status["kafka_connection"] = "Connected"
                await producer.stop()
            except Exception as e:
                logger.error(f"Failed to connect to Kafka: {e}")
                status["kafka_connection"] = f"Error: {str(e)}"
            
            return status
        except Exception as e:
            logger.error(f"Error getting debug status: {e}", exc_info=True)
            return {
                "error": str(e),
                "status": "Error collecting debug information"
            }

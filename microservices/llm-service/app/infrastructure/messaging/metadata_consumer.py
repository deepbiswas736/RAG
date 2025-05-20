"""
Metadata Consumer

This module implements a Kafka consumer for document metadata extraction requests.
It processes incoming metadata extraction requests and uses LLM services
to extract and enhance document metadata, then creates embeddings.
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime
import json

# Kafka and utility imports
from kafka_utility.app.infrastructure.adapters.kafka_consumer import KafkaConsumerAdapter
from kafka_utility.app.infrastructure.adapters.kafka_producer import KafkaProducerAdapter
from document_service.app.domain.entities.document import Document
from ...application.services.llm_service import LLMService
from kafka_utility.app.infrastructure.adapters.consumer_debug import diagnose_kafka_connection, get_consumer_status

# Local application imports
from kafka_utility.app.clients.document_service import DocumentServiceKafkaClient
from kafka_utility.app.clients.llm_service import LLMServiceKafkaClient
from ...domain.models.embedding import Embedding

logger = logging.getLogger(__name__)

MAX_CONCURRENT_TASKS_DEFAULT = 5

class MetadataConsumerService:
    """
    Metadata Consumer Service for processing document metadata extraction requests.
    """
    
    def __init__(
        self,
        consumer_config: Dict[str, Any],
        document_topic: str, # This is one of the topics the consumer will subscribe to
        # llm_topic: str, # This seems unused directly by consumer, maybe for producer?
        producer_config: Dict[str, Any], # Added producer_config
        llm_service: LLMService, # Added llm_service
        max_concurrent_tasks: int = MAX_CONCURRENT_TASKS_DEFAULT # Added
    ): # Corrected signature
        """
        Initializes the MetadataConsumerService.

        Args:
            consumer_config: Configuration for the Kafka consumer.
            document_topic: The Kafka topic for document metadata.
            # llm_topic: The Kafka topic for LLM responses.
            producer_config: Configuration for the Kafka producer.
            llm_service: Instance of LLMService.
            max_concurrent_tasks: Maximum concurrent processing tasks.
        """
        self.consumer_config = consumer_config
        self.producer_config = producer_config
        self.document_topic = document_topic # Store for later use
        self.llm_service = llm_service # Store llm_service instance

        # Initialize KafkaConsumerAdapter directly
        self.consumer = KafkaConsumerAdapter(
            bootstrap_servers=self.consumer_config.get('bootstrap.servers'),
            group_id=self.consumer_config.get('group.id'),
            auto_offset_reset=self.consumer_config.get('auto.offset.reset', 'earliest')
            # topics=[self.document_topic] # Removed: Topics are handled by register_handler
        )
        # Initialize KafkaProducerAdapter
        self.producer_adapter = KafkaProducerAdapter(
            bootstrap_servers=self.producer_config.get('bootstrap.servers')
        )
        # Pass the producer adapter to the clients
        self.document_client = DocumentServiceKafkaClient(producer=self.producer_adapter)
        self.llm_client = LLMServiceKafkaClient(producer=self.producer_adapter) # This client is for sending requests TO llm-service via Kafka, if needed.
                                                                                # If llm_service is local, direct calls are better.
        
        # Task semaphore for concurrency control
        self.task_semaphore = asyncio.Semaphore(max_concurrent_tasks)
        
        # Stats
        self.processed_count = 0
        self.failed_count = 0

    async def initialize(self) -> None:
        """Initialize the consumer service."""
        # Use attributes from consumer_config or consumer object for logging
        bootstrap_servers = self.consumer_config.get('bootstrap.servers')
        logger.info(f"Initializing metadata consumer for topic {self.document_topic} with bootstrap servers: {bootstrap_servers}")
        
        try:
            # Initialize clients - DocumentServiceKafkaClient and LLMServiceKafkaClient do not have an initialize method
            # logger.info("Initializing document client...")
            # await self.document_client.initialize() # Removed, as client has no initialize
            # logger.info("Document client initialized successfully")
            
            # logger.info("Initializing LLM client...")
            # await self.llm_client.initialize() # Removed, as client has no initialize
            # logger.info("LLM client initialized successfully")
            
            # Register message handler
            logger.info(f"Registering handler for topic: {self.document_topic}")
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
            logger.info("Calling consumer.start_consuming()...")
            await self.consumer.start_consuming()
            logger.info("Consumer.start_consuming() completed successfully")
            
            # Start background task for periodic stats reporting
            logger.info("Starting periodic stats reporting task...")
            asyncio.create_task(self._report_stats_periodically()) # Removed assignment to stats_task as it's not used
            logger.info("Periodic stats reporting task started")
            
            # Add connection verification
            logger.info("Verifying Kafka connection and topic subscription...")
            # This will log if the consumer is properly connected and subscribed
            if hasattr(self.consumer, '_consumer') and self.consumer._consumer: # Check internal _consumer attribute
                # Accessing internal _consumer might be risky if library changes.
                # Consider adding explicit status methods to KafkaConsumerAdapter.
                is_connected = False
                try:
                    # Try accessing bootstrap_connected via the internal client object
                    if hasattr(self.consumer._consumer, 'client') and self.consumer._consumer.client:
                        is_connected = self.consumer._consumer.client.bootstrap_connected()
                    else:
                        logger.warning("Consumer's internal KafkaClient not available for bootstrap_connected check.")
                except AttributeError as e_attr:
                    logger.warning(f"AttributeError while checking bootstrap_connected status via client: {e_attr}")
                except Exception as e_conn_check:
                    logger.warning(f"Could not check bootstrap_connected status via client: {e_conn_check}")

                logger.info(f"Consumer connected (via client check): {is_connected}")
                # Log assigned partitions as another indicator of health
                if hasattr(self.consumer._consumer, 'assignment'):
                    assigned_partitions = self.consumer._consumer.assignment()
                    logger.info(f"Consumer current assignment: {assigned_partitions}")
                else:
                    logger.warning("Could not retrieve consumer assignment.")
                    
                logger.info(f"Subscribed topics: {self.consumer._subscribed_topics}") 
                logger.info(f"Consumer group: {self.consumer.group_id}")
            else:
                logger.warning("Consumer internal AIOKafkaConsumer not initialized or accessible via _consumer attribute.")
            
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
        # Extract message data
        try:
            logger.info(f"Handler received message: {message}")
            
            payload = message.get("payload", {})
            metadata = message.get("metadata", {})
            
            document_id = payload.get("documentId")
            document_path = payload.get("documentPath")
            file_type = payload.get("fileType")
            priority = payload.get("priority", 5)
            
            logger.info(f"Received metadata extraction request for document {document_id} with path {document_path}, type {file_type}, priority {priority}")
            
            if not document_id or not document_path:
                logger.error(f"Invalid metadata request: missing required fields - document_id: {document_id}, document_path: {document_path}")
                return
                
            # Process the request in a separate task with concurrency control
            async with self.task_semaphore:
                await self._process_metadata_extraction(
                    document_id=document_id,
                    document_path=document_path,
                    file_type=file_type,
                    priority=priority
                )
        
        except Exception as e:
            logger.error(f"Error handling metadata extraction request: {e}", exc_info=True)
            self.failed_count += 1
    
    async def _process_metadata_extraction(
        self, document_id: str, document_path: str, file_type: str, priority: int
    ) -> None:
        """
        Process a metadata extraction request.
        
        Args:
            document_id: The ID of the document
            document_path: Path to the document
            file_type: The type/extension of the file
            priority: Priority level
        """
        try:
            # Step 1: Retrieve document content (assuming document_path is accessible)
            # In a real implementation, this might involve downloading from storage
            logger.info(f"Processing metadata for document {document_id} from {document_path}")
            
            # Step 2: Extract metadata using LLM
            # This is a simplified example - in reality you might use different approaches
            # depending on the file type and available metadata extractors
            extraction_prompt = self._create_metadata_extraction_prompt(document_path, file_type)
            
            metadata_text = await self.llm_service.generate_text(
                prompt=extraction_prompt,
                temperature=0.2,  # Low temperature for more deterministic output
                max_tokens=800
            )
            
            # Step 3: Parse the metadata text into a structured format
            # (This is a simplified example - in production you would parse the LLM output more robustly)
            metadata = self._parse_metadata_from_llm_output(metadata_text)
            
            # Step 4: Create embeddings for the metadata
            embedding_response: Embedding = await self.llm_service.create_embedding(
                text=metadata_text
            )
            
            # Step 5: Notify the document service about the extracted metadata
            success = await self.document_client.send_document_processed_event(
                document_id=document_id,
                status="metadata_extracted",
                metadata={
                    "extracted_metadata": metadata,
                    "metadata_embedding": embedding_response.embedding,
                    "extraction_timestamp": datetime.utcnow().isoformat()
                }
            )
            
            if success:
                logger.info(f"Successfully processed metadata for document {document_id}")
                self.processed_count += 1
            else:
                logger.error(f"Failed to send metadata extraction result for document {document_id}")
                self.failed_count += 1
                
        except Exception as e:
            logger.error(f"Error processing metadata for document {document_id}: {e}", exc_info=True)
            self.failed_count += 1
            
            # Notify failure
            await self.document_client.send_document_processed_event(
                document_id=document_id,
                status="failed",
                metadata={
                    "error": str(e),
                    "stage": "metadata_extraction",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
    
    def _create_metadata_extraction_prompt(self, document_path: str, file_type: str) -> str:
        """
        Create a prompt for metadata extraction.
        
        Args:
            document_path: Path to the document
            file_type: The type/extension of the file
            
        Returns:
            Prompt for the LLM
        """
        # In a real implementation, you would read content from the document_path
        # Here we're simulating with a generic extraction prompt
        return f"""Extract key metadata from the following document.
Focus on:
- Title/Subject
- Author(s)
- Creation Date
- Main Topics/Keywords
- Summary/Abstract (1-2 sentences)
- Document Type: {file_type}

Return the metadata in a structured format:
```json
{{
  "title": "",
  "authors": [""],
  "date": "",
  "topics": [""],
  "summary": "",
  "document_type": "{file_type}"
}}
```

Document content:
[Document content would be inserted here in a real implementation]
"""
    
    def _parse_metadata_from_llm_output(self, llm_output: str) -> Dict[str, Any]:
        """
        Parse metadata from LLM output.
        
        Args:
            llm_output: Text output from the LLM
            
        Returns:
            Parsed metadata dictionary
        """
        # This is a simplified extraction - in a real implementation you would use
        # more robust parsing techniques
        try:
            # Try to find and parse JSON from the output
            import re
            import json
            
            # Look for JSON structure in the response
            json_match = re.search(r'```json\s*(.*?)\s*```', llm_output, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                metadata = json.loads(json_str)
                return metadata
            
            # Fallback to extracting key-value pairs
            metadata = {
                "title": self._extract_field(llm_output, "title"),
                "authors": self._extract_list_field(llm_output, "authors"),
                "date": self._extract_field(llm_output, "date"),
                "topics": self._extract_list_field(llm_output, "topics"),
                "summary": self._extract_field(llm_output, "summary"),
            }
            return metadata
            
        except Exception as e:
            logger.error(f"Error parsing metadata from LLM output: {e}")
            # Return minimal metadata if parsing fails
            return {
                "error": "Failed to parse metadata",
                "raw_output": llm_output[:500]  # Truncated raw output
            }
    
    def _extract_field(self, text: str, field_name: str) -> str:
        """Extract a single field value from text."""
        import re
        match = re.search(rf'"{field_name}"\s*:\s*"([^"]*)"', text)
        if match:
            return match.group(1)
        return ""
    
    def _extract_list_field(self, text: str, field_name: str) -> list:
        """Extract a list field value from text."""
        import re
        match = re.search(rf'"{field_name}"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if match:
            items_text = match.group(1)
            # Extract quoted strings
            items = re.findall(r'"([^"]*)"', items_text)
            return items
        return []
        
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
                    "bootstrap_servers": self.bootstrap_servers,
                    "topic": self.topic,
                    "consumer_group_id": self.consumer_group_id,
                    "processed_count": self.processed_count,
                    "failed_count": self.failed_count,
                },
            }
            
            # Add detailed consumer status
            consumer_status = get_consumer_status(self.consumer)
            status["consumer_status"] = consumer_status
            
            # Check topic existence
            try:
                admin_client = AIOKafkaAdminClient(bootstrap_servers=self.bootstrap_servers)
                await admin_client.start()
                topics = await admin_client.list_topics()
                status["topic_exists"] = self.topic in topics
                status["available_topics"] = list(topics)
                await admin_client.close()
            except Exception as e:
                logger.error(f"Failed to check topic existence: {e}")
                status["topic_error"] = str(e)
            
            # Test connection to Kafka
            try:
                from aiokafka import AIOKafkaProducer
                producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
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

"""
Metadata Consumer

This module implements a Kafka consumer for document metadata extraction requests.
It processes incoming metadata extraction requests and uses LLM services
to extract and enhance document metadata, then creates embeddings.
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional, List
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

# MongoDB client import
from ..persistence.mongodb_client import MongoDBClient

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
        
        # Initialize MongoDB client
        self.mongo_client = MongoDBClient()
        
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
            
            # Directly extract fields from the message object
            document_id = message.get("documentId")
            document_path = message.get("documentPath")
            file_type = message.get("fileType")
            # Assuming 'status' might also be relevant from the message, though not used directly in the next log line
            # status = message.get("status") 
            priority = message.get("priority", 5) # Default priority if not in message
            
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
        Retrieves document, extracts metadata and topics for chunks, and updates the document.
        
        Args:
            document_id: The ID of the document
            document_path: Path to the document (may be less relevant if fetching from DB)
            file_type: The type/extension of the file
            priority: Priority level
        """
        try:
            logger.info(f"Processing metadata and topics for document {document_id}")

            # Step 1: Retrieve document and its chunks
            # Assuming document_client has methods to fetch these from MongoDB
            # You might need to implement these in DocumentServiceKafkaClient or a direct MongoDB client
            document_data = await self.mongo_client.get_document_by_id(document_id) # Placeholder
            if not document_data:
                logger.error(f"Document {document_id} not found.")
                self.failed_count += 1
                # Notify failure if document not found
                await self.document_client.send_document_processed_event(
                    document_id=document_id,
                    status="failed",
                    metadata={
                        "error": f"Document {document_id} not found during metadata extraction.",
                        "stage": "metadata_extraction_document_retrieval",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
                return

            document_chunks = await self.mongo_client.get_document_chunks(document_id) # Placeholder
            if not document_chunks:
                logger.warning(f"No chunks found for document {document_id}. Proceeding with document-level metadata.")
            
            # Simulate document content for overall analysis (replace with actual content retrieval if needed)
            # This could come from document_data or a specific field within it.
            document_content_for_summary = document_data.get("text_content", "") # Example field
            if not document_content_for_summary and document_chunks: # Fallback to concatenating chunk content
                document_content_for_summary = " ".join([chunk.get("content", "") for chunk in document_chunks])


            # Step 2: Extract overall document description (e.g., "resume of X", "property tax of Y")
            document_summary_prompt = self._create_document_summary_prompt(document_content_for_summary, file_type)
            document_description_text = await self.llm_service.generate_text(
                prompt=document_summary_prompt,
                temperature=0.3,
                max_tokens=150 
            )
            parsed_document_summary = self._parse_document_summary_from_llm_output(document_description_text)
            
            # Step 3: Extract topics for each chunk
            updated_chunks_metadata = []
            for chunk in document_chunks:
                chunk_id = chunk.get("chunk_id") # Assuming chunks have IDs
                chunk_content = chunk.get("content", "")
                if not chunk_content:
                    logger.warning(f"Chunk {chunk_id} for document {document_id} has no content. Skipping topic extraction.")
                    updated_chunks_metadata.append({
                        "chunk_id": chunk_id,
                        "metadata": chunk.get("metadata", {}), # Keep existing metadata
                        "topics": [] # No topics if no content
                    })
                    continue

                topic_extraction_prompt = self._create_topic_extraction_prompt(chunk_content)
                topics_text = await self.llm_service.generate_text(
                    prompt=topic_extraction_prompt,
                    temperature=0.5, # Higher temperature for more diverse topics
                    max_tokens=100
                )
                extracted_topics = self._parse_topics_from_llm_output(topics_text)
                
                # Update chunk metadata with topics
                current_chunk_metadata = chunk.get("metadata", {})
                current_chunk_metadata["extracted_topics"] = extracted_topics
                current_chunk_metadata["last_topic_extraction_timestamp"] = datetime.utcnow().isoformat()
                
                updated_chunks_metadata.append({
                    "chunk_id": chunk_id,
                    "metadata": current_chunk_metadata,
                    "topics": extracted_topics # Also store at top level for convenience if desired
                })
                logger.info(f"Extracted topics for chunk {chunk_id} of document {document_id}: {extracted_topics}")

            # Step 4: Consolidate overall document metadata
            # This includes the summary and potentially an aggregation of chunk topics
            final_document_metadata = document_data.get("metadata", {}) # Start with existing metadata
            final_document_metadata["document_description"] = parsed_document_summary.get("description", "N/A")
            final_document_metadata["document_category"] = parsed_document_summary.get("category", "N/A") # e.g. resume, tax_document
            final_document_metadata["related_entity"] = parsed_document_summary.get("related_entity", "N/A") # e.g. Person X, Property Y
            final_document_metadata["overall_topics"] = list(set(topic for chunk_meta in updated_chunks_metadata for topic in chunk_meta.get("topics", []))) # Aggregate unique topics
            final_document_metadata["last_full_metadata_extraction_timestamp"] = datetime.utcnow().isoformat()

            # Step 5: Create embeddings for the new metadata if needed (e.g., for the document description)
            # For simplicity, we'll assume the document service handles embedding updates based on new metadata.
            # If not, you'd create embeddings here:
            # description_embedding_response: Embedding = await self.llm_service.create_embedding(
            # text=parsed_document_summary.get("description", "")
            # )
            # final_document_metadata["description_embedding"] = description_embedding_response.embedding

            # Step 6: Notify the document service to update the document and its chunks
            # This might require a new method in DocumentServiceKafkaClient or a more complex event payload
            success = await self.document_client.send_document_update_event( # Placeholder for actual update method
                document_id=document_id,
                updated_document_metadata=final_document_metadata,
                updated_chunks_metadata=updated_chunks_metadata # Pass list of {"chunk_id": id, "metadata": new_meta}
            )
            
            if success:
                logger.info(f"Successfully processed and updated metadata and topics for document {document_id}")
                self.processed_count += 1
            else:
                logger.error(f"Failed to send document update event for document {document_id}")
                self.failed_count += 1
                
        except Exception as e:
            logger.error(f"Error processing metadata and topics for document {document_id}: {e}", exc_info=True)
            self.failed_count += 1
            
            # Notify failure
            await self.document_client.send_document_processed_event(
                document_id=document_id,
                status="failed",
                metadata={
                    "error": str(e),
                    "stage": "metadata_and_topic_extraction",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

    def _create_document_summary_prompt(self, document_content: str, file_type: str) -> str:
        """
        Create a prompt for summarizing the document's purpose and category.
        Example: "This document is a resume for John Doe." or "This is a property tax document for 123 Main St."
        """
        # Simplified content for prompt if too long
        preview_content = document_content[:2000] # Use first 2000 chars for summary

        return f"""Analyze the following document content (and file type '{file_type}') to determine its primary purpose and category.
Provide a concise description, identify the main category (e.g., 'resume', 'invoice', 'property_tax_document', 'legal_agreement', 'research_paper', 'other'), and if applicable, the primary entity it relates to (e.g., a person's name, a company name, a property address).

Document content preview:
{preview_content}
...

Return the information in a structured JSON format:
```json
{{
  "description": "Concise description of the document's purpose (e.g., Resume of John Doe, Property tax statement for 123 Main St, Q3 Financial Report for Acme Corp).",
  "category": "Document category (e.g., resume, invoice, property_tax_document, financial_report, legal_agreement, correspondence, other).",
  "related_entity": "The main person, organization, or item this document is about (e.g., John Doe, Acme Corp, 123 Main St). If not applicable, use 'N/A'."
}}
```
"""

    def _parse_document_summary_from_llm_output(self, llm_output: str) -> Dict[str, Any]:
        """
        Parse the document summary, category, and related entity from LLM output.
        """
        try:
            import re
            import json
            json_match = re.search(r'```json\\s*(.*?)\\s*```', llm_output, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                data = json.loads(json_str)
                return {
                    "description": data.get("description", "N/A"),
                    "category": data.get("category", "other"),
                    "related_entity": data.get("related_entity", "N/A")
                }
            logger.warning(f"Could not parse JSON summary from LLM output: {llm_output}")
            return {"description": "Failed to parse summary", "category": "unknown", "related_entity": "N/A"}
        except Exception as e:
            logger.error(f"Error parsing document summary from LLM output: {e}. Output: {llm_output}")
            return {"description": "Error in parsing summary", "category": "unknown", "related_entity": "N/A"}

    def _create_topic_extraction_prompt(self, chunk_content: str) -> str:
        """
        Create a prompt for extracting topics from a text chunk.
        """
        # Simplified content for prompt if too long
        preview_content = chunk_content[:1500]

        return f"""Identify the main topics discussed in the following text chunk.
List up to 5 key topics as a JSON list of strings.
For example: ["topic1", "topic2", "topic3"]

Text chunk:
{preview_content}
...

Return the topics in a structured JSON format:
```json
{{
  "topics": ["Primary topic 1", "Secondary topic 2", "Keyword topic 3"]
}}
```
"""

    def _parse_topics_from_llm_output(self, llm_output: str) -> List[str]:
        """
        Parse topics from LLM output (expected to be a JSON list of strings).
        """
        try:
            import re
            import json
            json_match = re.search(r'```json\\s*(.*?)\\s*```', llm_output, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                data = json.loads(json_str)
                topics = data.get("topics", [])
                if isinstance(topics, list) and all(isinstance(topic, str) for topic in topics):
                    return topics
                else:
                    logger.warning(f"Parsed 'topics' is not a list of strings: {topics}. LLM Output: {llm_output}")
                    return []
            
            logger.warning(f"Could not parse JSON topics from LLM output: {llm_output}")
            # Fallback: try to extract simple list if no JSON block found (less reliable)
            # This is a basic fallback and might need refinement
            if "topics:" in llm_output.lower():
                lines = llm_output.splitlines()
                for line in lines:
                    if line.lower().strip().startswith("topics:"):
                        try:
                            # Assuming topics are comma-separated after "topics:"
                            extracted = [t.strip().replace('"',"") for t in line.split(":",1)[1].strip().split(",") if t.strip()]
                            if extracted: return extracted
                        except:
                            pass # ignore if this basic parsing fails
            return []
        except Exception as e:
            logger.error(f"Error parsing topics from LLM output: {e}. Output: {llm_output}")
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

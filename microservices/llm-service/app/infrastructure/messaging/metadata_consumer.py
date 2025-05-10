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

from kafka_utility.infrastructure.adapters.kafka_consumer import KafkaConsumerAdapter
from kafka_utility.clients.document_service import DocumentServiceKafkaClient
from kafka_utility.clients.llm_service import LLMServiceKafkaClient

from ...application.services.llm_service import LLMService
from ...domain.models.embedding import EmbeddingResponse

logger = logging.getLogger(__name__)

class MetadataConsumerService:
    """
    Metadata Consumer Service for processing document metadata extraction requests.
    """
    
    def __init__(
        self,
        llm_service: LLMService,
        bootstrap_servers: Optional[str] = None,
        consumer_group_id: str = "metadata_extraction_group",
        topic: str = "metadata_extraction",
        max_concurrent_tasks: int = 5
    ):
        """
        Initialize the metadata consumer service.
        
        Args:
            llm_service: Service for LLM operations
            bootstrap_servers: Kafka bootstrap servers
            consumer_group_id: Kafka consumer group ID
            topic: Kafka topic to consume from
            max_concurrent_tasks: Maximum number of concurrent metadata extraction tasks
        """
        self.llm_service = llm_service
        self.bootstrap_servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.consumer_group_id = consumer_group_id
        self.topic = topic
        self.max_concurrent_tasks = max_concurrent_tasks
        
        # Initialize Kafka consumer
        self.consumer = KafkaConsumerAdapter(
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.consumer_group_id
        )
        
        # Initialize clients
        self.document_client = DocumentServiceKafkaClient(bootstrap_servers=self.bootstrap_servers)
        self.llm_client = LLMServiceKafkaClient(bootstrap_servers=self.bootstrap_servers)
        
        # Task semaphore for concurrency control
        self.task_semaphore = asyncio.Semaphore(max_concurrent_tasks)
        
        # Stats
        self.processed_count = 0
        self.failed_count = 0
    
    async def initialize(self) -> None:
        """Initialize the consumer service."""
        logger.info(f"Initializing metadata consumer for topic {self.topic}")
        
        # Initialize clients
        await self.document_client.initialize()
        await self.llm_client.initialize()
        
        # Register message handler
        self.consumer.register_handler(self.topic, self._handle_metadata_request)
        
        logger.info("Metadata consumer initialized successfully")
    
    async def start(self) -> None:
        """Start consuming metadata extraction requests."""
        logger.info(f"Starting metadata consumer for topic {self.topic}")
        
        # Start consuming messages
        await self.consumer.start_consuming()
        
        # Start background task for periodic stats reporting
        asyncio.create_task(self._report_stats_periodically())
        
        logger.info("Metadata consumer started")
    
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
            payload = message.get("payload", {})
            metadata = message.get("metadata", {})
            
            document_id = payload.get("documentId")
            document_path = payload.get("documentPath")
            file_type = payload.get("fileType")
            priority = payload.get("priority", 5)
            
            logger.info(f"Received metadata extraction request for document {document_id}")
            
            if not document_id or not document_path:
                logger.error(f"Invalid metadata request: missing required fields")
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
            embedding_response: EmbeddingResponse = await self.llm_service.create_embedding(
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

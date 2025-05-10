import re
import os
import logging
import uuid
import json
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from kafka import KafkaProducer
from kafka.errors import KafkaError
import math

from ...infrastructure.llm.llm_manager import LLMManager
from ..value_objects.metadata import DocumentMetadata
from ..entities.document import Document

logger = logging.getLogger(__name__)

class MetadataExtractionService:
    def __init__(self, 
                 llm_manager: Optional[LLMManager] = None, 
                 kafka_bootstrap_servers: str = None,
                 embedding_model = None):
        """
        Initialize the metadata extraction service.
        
        Args:
            llm_manager: LLM manager for enriching metadata with AI
            kafka_bootstrap_servers: Kafka servers for async metadata enrichment
            embedding_model: Model for generating embeddings
        """
        self.llm_manager = llm_manager
        self.embedding_model = embedding_model
        self.producer = None
        
        # Initialize the Kafka producer
        self._setup_kafka(kafka_bootstrap_servers)
        
    def _setup_kafka(self, bootstrap_servers: str = None):
        """Initialize Kafka producer for async metadata enrichment."""
        try:
            if not bootstrap_servers:
                bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
            
            logger.info(f"Initializing Kafka producer for metadata enrichment with bootstrap servers: {bootstrap_servers}")
            self.producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                api_version_auto_timeout_ms=5000,
                request_timeout_ms=10000,
                max_block_ms=10000
            )
            logger.info("Kafka producer for metadata enrichment initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Kafka producer for metadata enrichment: {e}")
            self.producer = None

    async def extract_basic_metadata(self, document: Document) -> Document:
        """
        First phase: Extract basic metadata during document upload.
        
        This extracts immediately available metadata like file name, simple person name patterns,
        and schedules async enrichment for deeper analysis.
        
        Args:
            document: The document to extract metadata from
            
        Returns:
            Document with basic metadata extracted
        """
        logger.info(f"Extracting basic metadata for document: {document.title}")
        
        # Create base metadata if not exists
        if not document.metadata:
            document.metadata = DocumentMetadata()
        
        # Extract file name from title if not already set
        if not document.metadata.file_name and document.title:
            document.metadata.file_name = document.title
        
        # Extract basic metadata from content
        metadata_dict = document.metadata.__dict__.copy()
        
        # Extract person name if it's a resume (simple pattern matching)
        if self._is_likely_resume(document):
            person_name = self._extract_person_name_from_content(document)
            if person_name:
                metadata_dict['person_name'] = person_name
                logger.info(f"Extracted person name: {person_name}")
        
        # Schedule async metadata enrichment
        document_id = getattr(document, 'id', None) or str(uuid.uuid4())
        if not metadata_dict.get('document_id'):
            metadata_dict['document_id'] = document_id
            
        await self._schedule_metadata_enrichment(document_id, document.title)
        
        # Update document with basic metadata
        document.metadata = DocumentMetadata.from_dict(metadata_dict)
        
        return document
    
    def _is_likely_resume(self, document: Document) -> bool:
        """
        Check if the document is likely a resume based on title or content patterns.
        
        Args:
            document: The document to check
            
        Returns:
            True if the document is likely a resume, False otherwise
        """
        # Check title for resume-related keywords
        title_lower = document.title.lower() if document.title else ""
        if any(kw in title_lower for kw in ["resume", "cv", "curriculum vitae"]):
            return True
            
        # Check first few lines of content for resume indicators
        if document.content:
            try:
                # For binary content, try to decode first 2000 bytes
                if isinstance(document.content, bytes):
                    sample = document.content[:2000].decode('utf-8', errors='ignore')
                else:
                    sample = document.content[:2000]
                    
                sample_lower = sample.lower()
                resume_patterns = [
                    r"resume\b", 
                    r"curriculum\s+vitae", 
                    r"\bcv\b", 
                    r"professional\s+experience",
                    r"work\s+experience",
                    r"education\s+and\s+training",
                    r"skills\s+and\s+expertise"
                ]
                
                for pattern in resume_patterns:
                    if re.search(pattern, sample_lower):
                        return True
            except Exception as e:
                logger.warning(f"Error analyzing document content: {e}")
                
        return False
        
    def _extract_person_name_from_content(self, document: Document) -> Optional[str]:
        """
        Extract person name from document content using simple patterns.
        For a more robust extraction, we'll use LLM in the enrichment phase.
        
        Args:
            document: The document to extract name from
            
        Returns:
            Extracted person name or None if not found
        """
        try:
            # Try to get first 1000 chars of content for name extraction
            if isinstance(document.content, bytes):
                text_sample = document.content[:1000].decode('utf-8', errors='ignore')
            else:
                text_sample = document.content[:1000]
                
            # Look for common name patterns in resumes
            # Usually a name appears at the top of a resume, often in larger font
            lines = text_sample.split('\n')
            
            # Filter out lines that are likely to be a name:
            # - Not too long (names are typically < 50 chars)
            # - Not containing common non-name elements like @, http, www
            # - Containing at least one letter (names have letters)
            potential_name_lines = [
                line.strip() for line in lines[:10]  # Look at first 10 lines
                if line.strip() and len(line.strip()) < 50
                and not any(x in line.lower() for x in ['@', 'http', 'www', '.com', '.org'])
                and re.search(r'[a-zA-Z]', line)
            ]
            
            if potential_name_lines:
                # The first non-empty line that meets our criteria is often the name
                return potential_name_lines[0].strip()
                
        except Exception as e:
            logger.error(f"Error extracting person name: {e}")
            
        return None
        
    async def _schedule_metadata_enrichment(self, document_id: str, title: str) -> bool:
        """
        Schedule asynchronous metadata enrichment via Kafka.
        
        Args:
            document_id: ID of the document to enrich
            title: Title of the document for logging
            
        Returns:
            True if scheduling succeeded, False otherwise
        """
        if not self.producer:
            logger.warning(f"Cannot schedule metadata enrichment for {title}: Kafka producer not available")
            return False
            
        try:
            # Send message to Kafka for async processing
            self.producer.send('metadata_enrichment', {
                'document_id': document_id,
                'title': title,
                'timestamp': datetime.now().isoformat()
            })
            self.producer.flush()
            logger.info(f"Scheduled metadata enrichment for document: {title} (ID: {document_id})")
            return True
        except Exception as e:
            logger.error(f"Failed to schedule metadata enrichment for {title}: {e}")
            return False
            
    async def enrich_document_metadata(self, document: Document) -> Document:
        """
        Second phase: Enrich document metadata using LLM analysis.
        
        This performs deep analysis of document content to extract:
        - Person information (name, contact details, etc.)
        - Topics and themes
        - Skills and expertise
        - Keywords
        - Summary
        
        Args:
            document: Document to enrich
            
        Returns:
            Document with enriched metadata
        """
        if not self.llm_manager:
            logger.warning("Cannot enrich metadata: LLM manager not available")
            return document
            
        logger.info(f"Enriching metadata for document: {document.title}")
        
        try:
            # Convert content to text if needed
            if isinstance(document.content, bytes):
                text_content = document.content.decode('utf-8', errors='ignore')
            else:
                text_content = document.content
                
            # Generate prompt for LLM to extract metadata
            prompt = self._create_metadata_extraction_prompt(text_content, document.title)
            
            # Get LLM response
            llm_response = await self.llm_manager.generate_response(prompt, [])
            
            # Parse LLM response into structured metadata
            enriched_metadata = self._parse_llm_metadata_response(llm_response)
            
            # Merge with existing metadata
            metadata_dict = document.metadata.__dict__.copy()
            metadata_dict.update(enriched_metadata)
            
            # Create new metadata object
            document.metadata = DocumentMetadata.from_dict(metadata_dict)
            
            logger.info(f"Metadata enrichment complete for: {document.title}")
            return document
        except Exception as e:
            logger.error(f"Error enriching metadata for {document.title}: {e}")
            return document
    
    def _create_metadata_extraction_prompt(self, text_content: str, title: str) -> str:
        """
        Create a prompt for the LLM to extract metadata from document content.
        
        Args:
            text_content: The document text content
            title: The document title
            
        Returns:
            Prompt string for LLM
        """
        # Sample size to avoid sending too much text to LLM
        # For a real implementation, you might want to analyze the document in chunks
        max_sample_size = 4000  # Adjust based on LLM token limits
        text_sample = text_content[:max_sample_size] if len(text_content) > max_sample_size else text_content
        
        return f"""Extract metadata from the following document titled "{title}".
Return your analysis as JSON with the following fields:
- person_name: The full name of the person if this is a personal document (like a resume)
- topics: List of main topics/themes discussed in the document
- keywords: List of important keywords from the document
- entities: Dictionary of entity types and their values (like organizations, locations, dates)
- summary: A brief summary of the document content

Document text:
{text_sample}

Respond with only the JSON object, properly formatted. Example format:
{{
  "person_name": "John Smith",
  "topics": ["Machine Learning", "Data Science"],
  "keywords": ["Python", "TensorFlow", "Neural Networks"],
  "entities": {{
    "PERSON": ["John Smith"],
    "ORG": ["Google", "Microsoft"]
  }},
  "summary": "Resume describing John Smith's experience in data science and machine learning."
}}
"""
    
    def _parse_llm_metadata_response(self, llm_response: str) -> Dict:
        """
        Parse the LLM response into structured metadata.
        Handles cases where the JSON is embedded within other text.
        
        Args:
            llm_response: The LLM response text
            
        Returns:
            Dictionary with extracted metadata fields or empty dict if parsing fails
        """
        try:
            # Find the start and end of the first JSON object
            start_index = llm_response.find('{')
            end_index = llm_response.rfind('}')
            
            if start_index != -1 and end_index != -1 and end_index > start_index:
                json_str = llm_response[start_index:end_index+1]
                try:
                    metadata = json.loads(json_str)
                    logger.debug(f"Successfully parsed JSON from LLM response.")
                    return metadata
                except json.JSONDecodeError as e:
                    logger.warning(f"Found potential JSON but failed to parse: {e}")
                    logger.debug(f"Potential JSON string: {json_str}")
            
            # Fallback: Try parsing the whole response if no clear JSON object found
            # This might succeed if the response is *only* JSON
            try:
                metadata = json.loads(llm_response)
                logger.debug("Parsed entire LLM response as JSON.")
                return metadata
            except json.JSONDecodeError:
                logger.error(f"Failed to parse LLM metadata response. No valid JSON found.")
                logger.debug(f"Problematic LLM response: {llm_response}")
                return {}

        except Exception as e:
            logger.error(f"Unexpected error parsing LLM metadata response: {e}")
            logger.debug(f"Problematic LLM response: {llm_response}")
            return {}

    async def process_enrichment_message(self, message: Dict, document_repository):
        """
        Process a metadata enrichment message from Kafka.
        
        Args:
            message: The Kafka message
            document_repository: Repository to fetch and update documents
        """
        document_id = message.get('document_id')
        if not document_id:
            logger.error("Received metadata enrichment message without document_id")
            return
            
        try:
            # Fetch document from repository
            document = await document_repository.find_by_id(document_id)
            if not document:
                logger.error(f"Document not found for enrichment: {document_id}")
                return
                
            # Fetch document chunks from repository
            chunks = await document_repository.get_chunks_by_document_id(document_id)
            if not chunks:
                logger.error(f"No chunks found for document: {document_id}")
                return
                
            logger.info(f"Processing metadata enrichment for document: {document.title} (ID: {document_id}) with {len(chunks)} chunks")
            
            # 1. Process each chunk for metadata
            from .metadata_enrichment.chunk_processor import ChunkProcessor
            chunk_processor = ChunkProcessor(self.llm_manager)
            
            chunk_results = []
            for chunk in chunks:
                chunk_content = chunk.get('content', '')
                chunk_id = chunk.get('id', '')
                position = chunk.get('position', 0)
                
                chunk_metadata = await chunk_processor.process_chunk(
                    chunk_content=chunk_content,
                    chunk_id=chunk_id,
                    position=position,
                    doc_title=document.title
                )
                
                if chunk_metadata:
                    chunk_results.append(chunk_metadata)
                    # Update chunk with extracted metadata
                    await document_repository.update_chunk_metadata(chunk_id, chunk_metadata.get('metadata', {}))
            
            # 2. Aggregate metadata from all chunks
            from .metadata_enrichment.metadata_aggregator import MetadataAggregator
            metadata_aggregator = MetadataAggregator(self.llm_manager)
            
            aggregated_metadata = await metadata_aggregator.aggregate_metadata(
                chunk_metadata=chunk_results,
                doc_title=document.title
            )
            
            # Ensure document_id is preserved in aggregated metadata
            aggregated_metadata['document_id'] = document_id
            
            # 3. Generate embeddings for chunks and metadata
            from .metadata_enrichment.embedding_processor import EmbeddingProcessor
            embedding_model = getattr(self, 'embedding_model', None)
            
            if embedding_model:
                embedding_processor = EmbeddingProcessor(embedding_model)
                embedding_results = await embedding_processor.process_embeddings(chunks, aggregated_metadata)
                
                # Add embeddings to metadata
                if embedding_results and 'metaEmbeddings' in embedding_results:
                    aggregated_metadata['metaEmbeddings'] = embedding_results['metaEmbeddings']
            else:
                logger.warning(f"Embedding model not available, skipping embedding generation for document: {document_id}")
            
            # 4. Update document metadata
            await document_repository.update_metadata(document_id, aggregated_metadata)
            
            logger.info(f"Completed metadata enrichment for document: {document.title} (ID: {document_id})")
        except Exception as e:
            logger.error(f"Error processing metadata enrichment for document {document_id}: {e}")    # Methods moved to metadata_enrichment module
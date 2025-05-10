from typing import List, Dict, Optional, AsyncGenerator, Tuple
from dataclasses import dataclass
import uuid
import asyncio
from kafka import KafkaProducer
from kafka.errors import KafkaError
import json
import os
import logging

from ...domain.services.document_processing_service import DocumentProcessingService
from ...domain.services.query_metadata_extractor import QueryMetadataExtractor, QueryMetadata
from ..services.document_service import DocumentService, ChunkDTO
from ...infrastructure.llm.llm_manager import LLMManager

logger = logging.getLogger(__name__)

@dataclass
class QueryResult:
    query_id: str
    answer: str
    source_chunks: List[ChunkDTO]  # Corrected syntax: List[ChunkDTO]
    status: str
    chunk_responses: Optional[List[str]] = None
    query_metadata: Optional[QueryMetadata] = None

class QueryService:
    def __init__(
        self,
        document_service: DocumentService,
        llm_manager: LLMManager,
        kafka_bootstrap_servers: str = None
    ):
        self.document_service = document_service
        self.llm_manager = llm_manager
        self._setup_kafka(kafka_bootstrap_servers)
        self.query_results: Dict[str, Optional[QueryResult]] = {}
        
        # Initialize the query metadata extractor
        self.metadata_extractor = QueryMetadataExtractor(llm_manager=self.llm_manager)
        logger.info("Initialized query metadata extractor")

    def _setup_kafka(self, bootstrap_servers: str = None):
        try:
            if not bootstrap_servers:
                bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
            
            self.producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                # Add shorter timeouts to fail faster if Kafka is not available
                api_version_auto_timeout_ms=5000,
                request_timeout_ms=10000,
                max_block_ms=10000
            )
            logger.info("Kafka producer initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Kafka producer: {e}. Will process async queries directly.")
            self.producer = None

    async def _process_chunk_with_llm(self, query: str, chunk: Dict) -> str:
        """Process a single chunk with LLM"""
        # Create a context list with a single chunk for the LLM
        single_chunk_context = [chunk]
        
        # Generate response for this chunk
        chunk_response = await self.llm_manager.generate_response(query, single_chunk_context)
        return chunk_response

    async def _generate_summary_from_chunk_responses(self, query: str, chunk_responses: List[str], 
                                                    sources: List[str]) -> str:
        """Generate a summary response from individual chunk responses"""
        # Create a special prompt for summarizing the chunk responses
        summary_context = "\n\n".join([
            f"Response {i+1}: {resp}" for i, resp in enumerate(chunk_responses)
        ])
        
        sources_text = "\n".join([f"- {source}" for source in sources])
        
        summary_prompt = f"""I've analyzed the query: "{query}" against multiple text chunks and received these responses:

{summary_context}

The information comes from these sources:
{sources_text}

Please synthesize a comprehensive, coherent answer based on all these responses. Combine the information logically, 
avoid redundancy, and ensure all key points are covered. Include specific references to sources where appropriate.
"""
        
        # Using a dedicated method for summary to avoid mixing with normal contexts
        summary_response = await self.llm_manager.generate_summary(summary_prompt)
        return summary_response

    def _extract_query_metadata(self, query: str) -> QueryMetadata:
        """
        Extract structured metadata from the query synchronously using LLM to ensure high precision.
        
        Args:
            query: The user's query
            
        Returns:
            QueryMetadata object containing structured metadata
        """
        try:
            logger.info(f"Extracting metadata from query with LLM synchronously: {query}")
            # Use LLM-based extraction synchronously for high precision
            return self.metadata_extractor.extract_metadata_with_llm_sync(query)
        except Exception as e:
            logger.error(f"Error extracting query metadata: {e}")
            # Return basic metadata on error
            return self.metadata_extractor.extract_metadata(query)

    async def query_sync(self, query: str) -> AsyncGenerator[str, None]:
        """Execute a synchronous query with streaming response using the two-step process"""
        # Extract metadata from the query to understand intent and context
        query_metadata = self._extract_query_metadata(query)
        
        # Use the processed query if available, otherwise use original
        query_to_use = query_metadata.processed_query or query
        logger.info(f"Using processed query: '{query_to_use}' (original: '{query}')")
        
        # Convert extracted metadata to filters if applicable
        metadata_filters = self._create_metadata_filters(query_metadata)
        
        # Use the new two-step semantic search approach for better results
        # First search metadata semantically, then search content within relevant documents
        chunks = await self.document_service.semantic_metadata_then_content_search(query_to_use)
        
        if not chunks:
            yield "I couldn't find any relevant information to answer your query."
            return
        
        # Convert chunks to format expected by LLM
        contexts = [
            {
                "content": chunk.content,
                "source": chunk.source
            }
            for chunk in chunks
        ]

        # First yield message that we're analyzing chunks
        yield "Analyzing document chunks...\n"
        
        # Step 1: Process each chunk individually
        chunk_responses = []
        for i, context in enumerate(contexts):
            chunk_response = await self._process_chunk_with_llm(query_to_use, context)
            chunk_responses.append(chunk_response)
            # Don't yield individual chunk responses in streaming mode

        # Step 2: Generate the summary response from all chunk responses
        sources = [chunk.source for chunk in chunks]
        
        yield "\nSynthesizing final answer...\n\n"
        
        # Stream the final summary
        summary_context = "\n\n".join([
            f"Response {i+1}: {resp}" for i, resp in enumerate(chunk_responses)
        ])
        
        sources_text = "\n".join([f"- {source}" for source in set(sources)])
        
        # Include relevant query metadata in the summary prompt
        metadata_hints = self._get_metadata_hints(query_metadata)
        
        summary_prompt = f"""I've analyzed the query: "{query_to_use}" against multiple text chunks and received these responses:

{summary_context}

The information comes from these sources:
{sources_text}

{metadata_hints}

Please synthesize a comprehensive, coherent answer based on all these responses. Combine the information logically, 
avoid redundancy, and ensure all key points are covered. Include specific references to sources where appropriate.
"""
        
        # Stream the summary response
        async for token in self.llm_manager.generate_streaming_response(summary_prompt, []):
            yield token
            
    def _get_metadata_hints(self, metadata: QueryMetadata) -> str:
        """
        Generate hints from metadata to include in LLM prompt.
        
        Args:
            metadata: QueryMetadata object
            
        Returns:
            String with hints based on metadata
        """
        hints = []
        
        # Add person focus if present
        if metadata.entities["person"]:
            persons = ", ".join(metadata.entities["person"])
            hints.append(f"This query is about the person(s): {persons}.")
        
        # Add organization focus if present
        if metadata.entities["organization"]:
            orgs = ", ".join(metadata.entities["organization"])
            hints.append(f"The query relates to organization(s): {orgs}.")
        
        # Add time context if present
        if metadata.time_period:
            hints.append(f"Focus on the time period: {metadata.time_period}.")
        
        # Add intent if present
        if metadata.intent:
            hints.append(f"The query intent appears to be: {metadata.intent}.")
        
        # Add topic focus if present
        if metadata.topics:
            topics = ", ".join(metadata.topics)
            hints.append(f"The query relates to these topics: {topics}.")
            
        if hints:
            return "Additional context for your response:\n" + "\n".join(hints)
        return ""
        
    def _create_metadata_filters(self, metadata: QueryMetadata) -> Optional[Dict]:
        """
        Convert extracted query metadata to filters for retrieval synchronously.
        
        Args:
            metadata: QueryMetadata object with extracted metadata
            
        Returns:
            Dictionary with metadata filters or None
        """
        filters = {}
        
        # Person filter (most important for personalized content)
        if metadata.entities["person"]:
            # Use the first person mentioned as the filter
            filters["person_name"] = metadata.entities["person"][0]
            
        # Organization filter if present
        if metadata.entities["organization"] and not filters:
            # Only add org filter if person filter isn't present (person is more specific)
            filters["organization"] = metadata.entities["organization"][0]
            
        # Topic filter if applicable and specific enough
        if len(metadata.topics) == 1:
            # Only add single topic filter to avoid over-constraining
            topic = metadata.topics[0]
            if topic not in ["technology", "business", "education", "healthcare"]:
                # Only add specific topics, not general categories
                filters["topics"] = topic
                
        return filters if filters else None

    async def query_async(self, query: str) -> str:
        """Submit an asynchronous query and return a query ID"""
        query_id = str(uuid.uuid4())
        self.query_results[query_id] = None

        # Check if Kafka producer is available
        if self.producer is not None:
            try:
                # Send to Kafka for processing
                logger.info(f"Sending query {query_id} to Kafka")
                self.producer.send('rag_queries', {
                    'query_id': query_id,
                    'query': query
                })
                self.producer.flush()  # Use sync version instead of await
                logger.info(f"Query {query_id} sent to Kafka successfully")
            except Exception as e:
                logger.error(f"Error sending query {query_id} to Kafka: {e}")
                # Fall back to direct processing if Kafka fails
                asyncio.create_task(self.process_async_query(query_id, query))
        else:
            # Process directly if Kafka is not available
            logger.info(f"Kafka unavailable, processing query {query_id} directly")
            asyncio.create_task(self.process_async_query(query_id, query))

        return query_id

    async def get_query_result(self, query_id: str) -> Optional[QueryResult]:
        """Get the result of an asynchronous query"""
        return self.query_results.get(query_id)

    async def process_async_query(self, query_id: str, query: str):
        """Process an async query (called by Kafka consumer) using the two-step process"""
        try:
            # Extract metadata from the query for better understanding
            query_metadata = self._extract_query_metadata(query)
            
            # Use the processed query if available, otherwise use original
            query_to_use = query_metadata.processed_query or query
            logger.info(f"Processing async query {query_id} with processed query: '{query_to_use}'")
            
            # Convert extracted metadata to filters if applicable
            metadata_filters = self._create_metadata_filters(query_metadata)
            
            # Get relevant chunks using the semantic metadata-then-content search
            chunks = await self.document_service.semantic_metadata_then_content_search(query_to_use)
            
            if not chunks:
                self.query_results[query_id] = QueryResult(
                    query_id=query_id,
                    answer="I couldn't find any relevant information to answer your query.",
                    source_chunks=[],
                    status="completed",
                    chunk_responses=[],
                    query_metadata=query_metadata
                )
                return
                
            # Convert chunks for LLM
            contexts = [
                {
                    "content": chunk.content,
                    "source": chunk.source
                }
                for chunk in chunks
            ]

            # Step 1: Process each chunk individually
            logger.info(f"Processing query {query_id}: Analyzing {len(chunks)} chunks individually")
            chunk_responses = []
            for i, context in enumerate(contexts):
                chunk_response = await self._process_chunk_with_llm(query_to_use, context)
                chunk_responses.append(chunk_response)
                logger.debug(f"Chunk {i+1} response: {chunk_response[:100]}...")  # Log first 100 chars

            # Step 2: Generate the summary from all chunk responses
            sources = [chunk.source for chunk in chunks]
            logger.info(f"Processing query {query_id}: Generating summary from {len(chunk_responses)} chunk responses")
            
            # Include query metadata hints in the summary prompt
            metadata_hints = self._get_metadata_hints(query_metadata)
            
            # Generate summary
            summary = await self._generate_summary_with_metadata(query_to_use, chunk_responses, sources, query_metadata)

            # Store result with both final answer and individual chunk responses
            self.query_results[query_id] = QueryResult(
                query_id=query_id,
                answer=summary,
                source_chunks=chunks,
                status="completed",
                chunk_responses=chunk_responses,
                query_metadata=query_metadata
            )
            logger.info(f"Completed query {query_id} with metadata-enhanced processing")
            
        except Exception as e:
            logger.error(f"Error processing query {query_id}: {e}", exc_info=True)
            self.query_results[query_id] = QueryResult(
                query_id=query_id,
                answer=f"Error: {str(e)}",
                source_chunks=[],
                status="error",
                chunk_responses=[],
                query_metadata=QueryMetadata()
            )
            
    async def _generate_summary_with_metadata(self, query: str, chunk_responses: List[str],
                                           sources: List[str], metadata: QueryMetadata) -> str:
        """Generate a summary response from chunks with metadata context"""
        # Create a special prompt for summarizing the chunk responses
        summary_context = "\n\n".join([
            f"Response {i+1}: {resp}" for i, resp in enumerate(chunk_responses)
        ])
        
        sources_text = "\n".join([f"- {source}" for source in set(sources)])
        
        # Include query metadata hints
        metadata_hints = self._get_metadata_hints(metadata)
        
        summary_prompt = f"""I've analyzed the query: "{query}" against multiple text chunks and received these responses:

{summary_context}

The information comes from these sources:
{sources_text}

{metadata_hints}

Please synthesize a comprehensive, coherent answer based on all these responses. Combine the information logically, 
avoid redundancy, and ensure all key points are covered. Include specific references to sources where appropriate.
"""
        
        # Using a dedicated method for summary to avoid mixing with normal contexts
        summary_response = await self.llm_manager.generate_summary(summary_prompt)
        return summary_response

    async def get_completed_queries(self) -> List[Dict]:
        """Get a list of all completed queries"""
        completed_queries = []
        
        for query_id, result in self.query_results.items():
            if result and result.status in ["completed", "error"]:
                query_preview = result.answer[:100] + "..." if len(result.answer) > 100 else result.answer
                completed_queries.append({
                    "query_id": query_id,
                    "status": result.status,
                    "preview": query_preview,
                    "timestamp": getattr(result, "timestamp", None),  # In case we add timestamps later
                    "source_count": len(result.source_chunks) if result.source_chunks else 0
                })
                
        # Sort by newest first (if we add timestamps later)
        # For now return in order of completion
        return completed_queries

    async def _extract_metadata_filters(self, query: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Extract metadata filters from the query.
        Returns a tuple of (metadata_filters, processed_query).
        If no filters are found, returns (None, None).
        """
        # Use simple pattern matching to identify queries about skills of a specific person
        import re
        
        # Look for patterns like "skills of [name]" or "[name]'s skills" or "skills for [name]"
        person_patterns = [
            r"skills of ([A-Za-z\s]+)",
            r"([A-Za-z\s]+)'s skills",
            r"skills for ([A-Za-z\s]+)",
            r"what skills does ([A-Za-z\s]+) have",
            r"what are ([A-Za-z\s]+)'s skills"
        ]
        
        for pattern in person_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                person_name = match.group(1).strip()
                logger.info(f"Extracted person name '{person_name}' from query: '{query}'")
                
                # Create metadata filter for the person name
                metadata_filters = {"person_name": person_name}
                
                # Return both the filters and the original query
                return metadata_filters, query
        
        # No person name found in the query
        return None, None
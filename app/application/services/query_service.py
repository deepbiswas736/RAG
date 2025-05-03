from typing import List, Dict, Optional, AsyncGenerator
from dataclasses import dataclass
import uuid
import asyncio
from kafka import KafkaProducer
from kafka.errors import KafkaError
import json
import os
import logging

from ...domain.services.document_processing_service import DocumentProcessingService
from ..services.document_service import DocumentService, ChunkDTO
from ...infrastructure.llm.llm_manager import LLMManager

logger = logging.getLogger(__name__)

@dataclass
class QueryResult:
    query_id: str
    answer: str
    source_chunks: List[ChunkDTO]
    status: str
    chunk_responses: Optional[List[str]] = None  # Add field to store per-chunk responses

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

    async def query_sync(self, query: str) -> AsyncGenerator[str, None]:
        """Execute a synchronous query with streaming response using the two-step process"""
        chunks = await self.document_service.search_similar_chunks(query)
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
            chunk_response = await self._process_chunk_with_llm(query, context)
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
        
        summary_prompt = f"""I've analyzed the query: "{query}" against multiple text chunks and received these responses:

{summary_context}

The information comes from these sources:
{sources_text}

Please synthesize a comprehensive, coherent answer based on all these responses. Combine the information logically, 
avoid redundancy, and ensure all key points are covered. Include specific references to sources where appropriate.
"""
        
        # Stream the summary response
        async for token in self.llm_manager.generate_streaming_response(summary_prompt, []):
            yield token

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
            # Get relevant chunks
            chunks = await self.document_service.search_similar_chunks(query)
            
            if not chunks:
                self.query_results[query_id] = QueryResult(
                    query_id=query_id,
                    answer="I couldn't find any relevant information to answer your query.",
                    source_chunks=[],
                    status="completed",
                    chunk_responses=[]
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
                chunk_response = await self._process_chunk_with_llm(query, context)
                chunk_responses.append(chunk_response)
                logger.debug(f"Chunk {i+1} response: {chunk_response[:100]}...")  # Log first 100 chars

            # Step 2: Generate the summary from all chunk responses
            sources = [chunk.source for chunk in chunks]
            logger.info(f"Processing query {query_id}: Generating summary from {len(chunk_responses)} chunk responses")
            
            summary = await self._generate_summary_from_chunk_responses(query, chunk_responses, sources)

            # Store result with both final answer and individual chunk responses
            self.query_results[query_id] = QueryResult(
                query_id=query_id,
                answer=summary,
                source_chunks=chunks,
                status="completed",
                chunk_responses=chunk_responses
            )
            logger.info(f"Completed query {query_id} with two-step processing")
            
        except Exception as e:
            logger.error(f"Error processing query {query_id}: {e}", exc_info=True)
            self.query_results[query_id] = QueryResult(
                query_id=query_id,
                answer=f"Error: {str(e)}",
                source_chunks=[],
                status="error",
                chunk_responses=[]
            )

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
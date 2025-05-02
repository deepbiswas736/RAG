from typing import List, Dict, Optional, AsyncGenerator
from dataclasses import dataclass
import uuid
import asyncio
from kafka import KafkaProducer
from kafka.errors import KafkaError
import json
import os

from ...domain.services.document_processing_service import DocumentProcessingService
from ..services.document_service import DocumentService, ChunkDTO
from ...infrastructure.llm.llm_manager import LLMManager

@dataclass
class QueryResult:
    query_id: str
    answer: str
    source_chunks: List[ChunkDTO]
    status: str

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
        if not bootstrap_servers:
            bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    async def query_sync(self, query: str) -> AsyncGenerator[str, None]:
        """Execute a synchronous query with streaming response"""
        chunks = await self.document_service.search_similar_chunks(query)
        
        # Convert chunks to format expected by LLM
        context = [
            {
                "content": chunk.content,
                "source": chunk.source
            }
            for chunk in chunks
        ]

        async for token in self.llm_manager.generate_streaming_response(query, context):
            yield token

    async def query_async(self, query: str) -> str:
        """Submit an asynchronous query and return a query ID"""
        query_id = str(uuid.uuid4())
        self.query_results[query_id] = None

        # Send to Kafka for processing
        try:
            self.producer.send('rag_queries', {
                'query_id': query_id,
                'query': query
            })
            await self.producer.flush()
        except KafkaError as e:
            print(f"Error sending to Kafka: {e}")
            raise

        return query_id

    async def get_query_result(self, query_id: str) -> Optional[QueryResult]:
        """Get the result of an asynchronous query"""
        return self.query_results.get(query_id)

    async def process_async_query(self, query_id: str, query: str):
        """Process an async query (called by Kafka consumer)"""
        try:
            # Get relevant chunks
            chunks = await self.document_service.search_similar_chunks(query)
            
            # Convert chunks for LLM
            context = [
                {
                    "content": chunk.content,
                    "source": chunk.source
                }
                for chunk in chunks
            ]

            # Generate response
            answer = await self.llm_manager.generate_response(query, context)

            # Store result
            self.query_results[query_id] = QueryResult(
                query_id=query_id,
                answer=answer,
                source_chunks=chunks,
                status="completed"
            )
        except Exception as e:
            print(f"Error processing query {query_id}: {e}")
            self.query_results[query_id] = QueryResult(
                query_id=query_id,
                answer=f"Error: {str(e)}",
                source_chunks=[],
                status="error"
            )
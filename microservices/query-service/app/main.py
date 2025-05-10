"""
Query Service API
---------------
FastAPI implementation of the Query Service API
"""

import os
import logging
import json
import socket
from typing import List, Dict, Any, Optional, Union, AsyncGenerator
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import asyncio
import uvicorn
import uuid

from . import config
from .application.services.query_processor import QueryProcessor
from .domain.models.query import Query, QueryType
from .domain.interfaces.query_repository import QueryRepository
from .domain.interfaces.llm_service_client import LLMServiceClient
from .domain.interfaces.document_service_client import DocumentServiceClient
from .infrastructure.persistence.mongodb_query_repository import MongoDBQueryRepository
from .infrastructure.adapters.http_llm_service_client import HttpLLMServiceClient
from .infrastructure.adapters.http_document_service_client import HttpDocumentServiceClient
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Define service name and version
SERVICE_NAME = "QueryService"
SERVICE_VERSION = "1.0.0"

# Pydantic models for API
class ContextItem(BaseModel):
    content: str
    source: str


class QueryRequest(BaseModel):
    text: str
    query_type: str = Field(default="hybrid", description="Type of query: conversational, retrieval, hybrid, or direct")
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    conversation_history: Optional[List[Dict[str, Any]]] = None
    filters: Optional[Dict[str, Any]] = None
    context: Optional[List[ContextItem]] = None


class DocumentReferenceResponse(BaseModel):
    document_id: str
    title: Optional[str] = None
    source: Optional[str] = None
    page: Optional[int] = None
    relevance_score: Optional[float] = None
    content_excerpt: Optional[str] = None


class QueryResponseModel(BaseModel):
    id: str
    query_id: str
    text: str
    references: List[DocumentReferenceResponse] = []
    model: Optional[str] = None
    latency: Optional[float] = None
    token_usage: Dict[str, int] = {}


class StreamingResponseModel(BaseModel):
    query_id: str
    text: str
    is_final: bool = False
    is_error: bool = False


# API configuration
class ApiConfig:
    # MongoDB connection
    MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "query_db")
    
    # Service URLs
    LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://llm-service:8001")
    DOCUMENT_SERVICE_URL = os.getenv("DOCUMENT_SERVICE_URL", "http://document-service:8000")
    
    # API root path
    ROOT_PATH = os.getenv("ROOT_PATH", "")

# Initialize configuration
config = ApiConfig()

# Create the FastAPI app instance
app = FastAPI(
    title="Query Service API",
    description="Microservice for processing queries using RAG",
    version=SERVICE_VERSION,
    root_path=config.ROOT_PATH
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Dependencies
def get_query_repository() -> QueryRepository:
    """Get query repository instance"""
    repository = MongoDBQueryRepository(
        connection_url=config.MONGODB_URL,
        database_name=config.MONGODB_DB_NAME
    )
    return repository


def get_llm_service_client() -> LLMServiceClient:
    """Get LLM service client instance"""
    client = HttpLLMServiceClient(base_url=config.LLM_SERVICE_URL)
    return client


def get_document_service_client() -> DocumentServiceClient:
    """Get document service client instance"""
    client = HttpDocumentServiceClient(base_url=config.DOCUMENT_SERVICE_URL)
    return client


def get_query_processor(
    query_repository: QueryRepository = Depends(get_query_repository),
    llm_service_client: LLMServiceClient = Depends(get_llm_service_client),
    document_service_client: DocumentServiceClient = Depends(get_document_service_client),
) -> QueryProcessor:
    """Get query processor instance"""
    processor = QueryProcessor(
        llm_service_client=llm_service_client,
        document_service_client=document_service_client,
        query_repository=query_repository,
    )
    return processor


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting Query Service")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    logger.info("Shutting down Query Service")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint to verify API is running"""
    return {"status": "ok", "message": "Query Service API is operational"}


# Service information endpoint
@app.get("/service-info")
async def service_info(request: Request):
    """Service information endpoint for service registry"""
    hostname = socket.gethostname()
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "hostname": hostname,
        "endpoints": [
            {"path": "/query", "methods": ["POST"], "description": "Submit a new query"},
            {"path": "/query/{query_id}", "methods": ["GET"], "description": "Get query result by ID"},
            {"path": "/query/stream", "methods": ["POST"], "description": "Stream query results"},
            {"path": "/conversation/{conversation_id}", "methods": ["GET"], "description": "Get conversation history"}
        ]
    }


@app.get("/health")
async def health_check(
    llm_service_client: LLMServiceClient = Depends(get_llm_service_client),
    document_service_client: DocumentServiceClient = Depends(get_document_service_client),
):
    """Health check endpoint"""
    try:
        # Check dependencies
        llm_status = await llm_service_client.check_health()
        document_status = await document_service_client.check_health()
        
        all_healthy = (
            llm_status.get("status") == "healthy" and 
            document_status.get("status") == "healthy"
        )
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "llm_service": llm_status,
            "document_service": document_status,
            "query_service": "running"
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "degraded",
            "error": str(e)
        }


@app.post("/query", response_model=QueryResponseModel)
async def process_query(
    request: QueryRequest,
    query_processor: QueryProcessor = Depends(get_query_processor),
):
    """Process a query and return a response"""
    try:
        # Create query domain object
        query = Query.create(
            text=request.text,
            query_type=QueryType(request.query_type),
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            conversation_history=request.conversation_history,
            filters=request.filters or {}
        )
        
        # Process query
        response = await query_processor.process_query(query)
        
        # Convert to API response
        references = [
            DocumentReferenceResponse(
                document_id=ref.document_id,
                title=ref.title,
                source=ref.source,
                page=ref.page,
                relevance_score=ref.relevance_score,
                content_excerpt=ref.content_excerpt
            )
            for ref in response.references
        ]
        
        return QueryResponseModel(
            id=response.id.value,
            query_id=response.query_id,
            text=response.text,
            references=references,
            model=response.model,
            latency=response.latency,
            token_usage=response.token_usage
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.post("/query/stream")
async def process_streaming_query(
    request: QueryRequest,
    query_processor: QueryProcessor = Depends(get_query_processor),
):
    """Process a query with streaming response"""
    try:
        # Create query domain object
        query = Query.create(
            text=request.text,
            query_type=QueryType(request.query_type),
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            conversation_history=request.conversation_history,
            filters=request.filters or {}
        )
        
        # Set up streaming response
        async def event_generator():
            try:
                async for chunk in query_processor.process_streaming_query(query):
                    yield f"data: {json.dumps(chunk)}\n\n"
                    await asyncio.sleep(0.01)  # Small delay to avoid overwhelming the client
            except Exception as e:
                logger.error(f"Error in stream generation: {str(e)}")
                error_chunk = {
                    "query_id": query.id.value,
                    "text": f"Error: {str(e)}",
                    "is_final": True,
                    "is_error": True
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
        
    except Exception as e:
        logger.error(f"Error setting up streaming response: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error setting up streaming: {str(e)}")


@app.get("/query/{query_id}", response_model=QueryResponseModel)
async def get_query_result(
    query_id: str,
    query_repository: QueryRepository = Depends(get_query_repository),
):
    """Get the result of a query by ID"""
    try:
        from .domain.models.query import QueryId
        from .domain.models.response import ResponseId
        
        # Find responses for the query
        responses = await query_repository.find_responses_by_query_id(QueryId(value=query_id))
        
        if not responses:
            raise HTTPException(status_code=404, detail=f"No response found for query ID {query_id}")
        
        # Return the most recent response
        response = responses[0]  # Assuming responses are ordered by time
        
        # Convert to API response
        references = [
            DocumentReferenceResponse(
                document_id=ref.document_id,
                title=ref.title,
                source=ref.source,
                page=ref.page,
                relevance_score=ref.relevance_score,
                content_excerpt=ref.content_excerpt
            )
            for ref in response.references
        ]
        
        return QueryResponseModel(
            id=response.id.value,
            query_id=response.query_id,
            text=response.text,
            references=references,
            model=response.model,
            latency=response.latency,
            token_usage=response.token_usage
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving query result: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving query result: {str(e)}")


@app.get("/conversation/{conversation_id}")
async def get_conversation_history(
    conversation_id: str,
    query_repository: QueryRepository = Depends(get_query_repository),
):
    """Get the history of a conversation"""
    try:
        # Find queries for the conversation
        queries = await query_repository.find_by_conversation_id(conversation_id)
        
        if not queries:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
        
        # Build history
        history = []
        for query in queries:
            query_dict = query.to_dict()
            
            # Find responses for this query
            from .domain.models.query import QueryId
            responses = await query_repository.find_responses_by_query_id(QueryId(value=query.id.value))
            
            if responses:
                response_dict = responses[0].to_dict()  # Most recent response
                history.append({
                    "query": query_dict,
                    "response": response_dict
                })
            else:
                history.append({
                    "query": query_dict,
                    "response": None
                })
        
        return {
            "conversation_id": conversation_id,
            "history": history
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving conversation history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving conversation history: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

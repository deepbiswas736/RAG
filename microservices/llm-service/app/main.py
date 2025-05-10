"""
LLM Service API
-------------
FastAPI implementation for the LLM service API
"""

import logging
import os
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn
import json
import socket

# Import application service
from application.services.llm_service import LLMService

# Import infrastructure implementations
from infrastructure.llm.ollama_adapter import OllamaTextGeneration, OllamaEmbedding
from infrastructure.messaging.metadata_consumer import MetadataConsumerService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define service name and version
SERVICE_NAME = "LLMService"
SERVICE_VERSION = "1.0.0"

# Create service instances
text_generation_service = OllamaTextGeneration()
embedding_service = OllamaEmbedding()

# Create application service
llm_service = LLMService(
    text_generation_service=text_generation_service,
    embedding_service=embedding_service
)

# API request/response models
class TextGenerationRequest(BaseModel):
    prompt: str = Field(..., description="Input prompt for text generation")
    context: Optional[List[Dict[str, str]]] = Field(None, description="Optional context items")
    model: Optional[str] = Field(None, description="Model name to use (default: system default)")
    temperature: Optional[float] = Field(0.7, description="Temperature parameter (0.0-2.0)")
    max_tokens: Optional[int] = Field(500, description="Maximum tokens to generate")

class EmbeddingRequest(BaseModel):
    text: str = Field(..., description="Text to generate embedding for")
    model: Optional[str] = Field(None, description="Model name to use (default: system default)")
    
class BatchEmbeddingRequest(BaseModel):
    texts: List[str] = Field(..., description="List of texts to generate embeddings for")
    model: Optional[str] = Field(None, description="Model name to use (default: system default)")

# Create FastAPI app
app = FastAPI(
    title="LLM Service API",
    description="API for text generation and embedding creation",
    version=SERVICE_VERSION,
    docs_url="/docs"
)

# Initialize metadata consumer
metadata_consumer = MetadataConsumerService(
    llm_service=llm_service,
    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    consumer_group_id="llm_metadata_group",
    topic="metadata_extraction",
    max_concurrent_tasks=int(os.getenv("MAX_CONCURRENT_METADATA_TASKS", "5"))
)

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize and start services on application startup"""
    logger.info("Starting LLM Service")
    
    # Check Ollama availability
    if not await text_generation_service.check_availability():
        logger.warning("Ollama service is not available - text generation will fail")
    
    # Initialize and start metadata consumer
    try:
        logger.info("Initializing metadata consumer")
        await metadata_consumer.initialize()
        logger.info("Starting metadata consumer")
        await metadata_consumer.start()
    except Exception as e:
        logger.error(f"Failed to start metadata consumer: {e}")
        # Continue running even if the consumer failed to start
        # This way the REST API can still function

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("Stopping LLM Service")
    
    # Stop metadata consumer
    try:
        logger.info("Stopping metadata consumer")
        await metadata_consumer.stop()
    except Exception as e:
        logger.error(f"Error stopping metadata consumer: {e}")

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# API endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {"status": "ok", "service": "LLM Service"}

@app.get("/health")
async def health():
    """Health check endpoint"""
    ollama_available = await text_generation_service.check_availability()
    return {
        "status": "healthy" if ollama_available else "degraded",
        "ollama": "available" if ollama_available else "unavailable"
    }

@app.get("/service-info")
async def service_info(request: Request):
    """Service information endpoint for service registry"""
    hostname = socket.gethostname()
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "hostname": hostname,
        "endpoints": [
            {"path": "/generate", "methods": ["POST"], "description": "Generate text responses"},
            {"path": "/generate/stream", "methods": ["POST"], "description": "Stream text generation"},
            {"path": "/embeddings", "methods": ["POST"], "description": "Generate embeddings"},
            {"path": "/embeddings/batch", "methods": ["POST"], "description": "Generate batch embeddings"},
            {"path": "/metadata/status", "methods": ["GET"], "description": "Get metadata consumer status"}
        ]
    }

@app.get("/metadata/status")
async def metadata_status():
    """Get metadata consumer status"""
    return {
        "running": True,  # The service is running if this endpoint responds
        "processed_count": metadata_consumer.processed_count,
        "failed_count": metadata_consumer.failed_count,
        "active_tasks": metadata_consumer.max_concurrent_tasks - metadata_consumer.task_semaphore._value,
        "max_concurrent_tasks": metadata_consumer.max_concurrent_tasks,
        "topic": metadata_consumer.topic,
        "consumer_group_id": metadata_consumer.consumer_group_id
    }

@app.post("/generate")
async def generate_text(request: TextGenerationRequest):
    """Generate text based on prompt and optional context"""
    try:
        result = await llm_service.generate_text(
            prompt=request.prompt,
            context=request.context,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        return result
    except Exception as e:
        logger.error(f"Error generating text: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating text: {str(e)}")

@app.post("/generate/stream")
async def generate_streaming(request: TextGenerationRequest):
    """Generate streaming text based on prompt and optional context"""
    try:
        async def streaming_generator():
            async for chunk in llm_service.generate_streaming(
                prompt=request.prompt,
                context=request.context,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        
        return StreamingResponse(
            streaming_generator(),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.error(f"Error generating streaming text: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating streaming text: {str(e)}")

@app.post("/embeddings")
async def create_embedding(request: EmbeddingRequest):
    """Create an embedding for the given text"""
    try:
        result = await llm_service.create_embedding(
            text=request.text,
            model=request.model
        )
        return result
    except Exception as e:
        logger.error(f"Error creating embedding: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating embedding: {str(e)}")

@app.post("/embeddings/batch")
async def create_batch_embeddings(request: BatchEmbeddingRequest):
    """Create embeddings for multiple texts"""
    try:
        result = await llm_service.create_batch_embeddings(
            texts=request.texts,
            model=request.model
        )
        return {"embeddings": result}
    except Exception as e:
        logger.error(f"Error creating batch embeddings: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating batch embeddings: {str(e)}")

# LLM endpoints will be implemented here
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=os.getenv("DEBUG", "False").lower() == "true"
    )

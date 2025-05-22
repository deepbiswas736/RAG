"""
LLM Service API
-------------
FastAPI implementation for the LLM service API
"""

import logging
import os
from typing import List, Dict, Any, Optional, AsyncGenerator, Union
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
import uvicorn
import json
import socket

# Import application service
from .application.services.llm_service import LLMService

# Import infrastructure implementations
from .infrastructure.llm.ollama_adapter import OllamaTextGeneration, OllamaEmbedding
from .infrastructure.messaging.metadata_consumer import MetadataConsumerService

# Import Kafka debug helpers
# Try to import directly, assuming kafka_utility is in PYTHONPATH or discoverable
from kafka_utility.app.infrastructure.adapters.consumer_debug import diagnose_kafka_connection, get_consumer_status

# Configure logging
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure OpenTelemetry
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter # Changed from http to grpc
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter # Changed from http to grpc
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor # Changed OpenTelemetryInstrumentor to FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
# For Kafka, ensure you have opentelemetry-instrumentation-kafka-python installed
from opentelemetry.instrumentation.kafka import KafkaInstrumentor


# Configure OpenTelemetry Logging
otel_log_level_str = os.environ.get("OTEL_PYTHON_LOG_LEVEL", "INFO").upper()
otel_log_level = getattr(logging, otel_log_level_str, logging.INFO)

resource = Resource.create({
    "service.name": os.environ.get("OTEL_SERVICE_NAME", "llm-service")
})

# Logs
logger_provider = LoggerProvider(resource=resource)
otlp_log_exporter = OTLPLogExporter(
    endpoint=os.environ.get("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "otel-collector:4317"))
)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_log_exporter))
logging.getLogger().addHandler(LoggingHandler(level=otel_log_level, logger_provider=logger_provider))
# Ensure the root logger's level is also appropriate if not already set
if logging.getLogger().level > otel_log_level:
    logging.getLogger().setLevel(otel_log_level)


# Traces
# Check if a global tracer provider is already set by another instrumentation
if not isinstance(trace.get_tracer_provider(), TracerProvider):
    provider = TracerProvider(resource=resource)
    otlp_trace_exporter = OTLPSpanExporter(
        endpoint=os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "otel-collector:4317"))
    )
    processor = BatchSpanProcessor(otlp_trace_exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
else:
    # If a provider is already set (e.g. by auto-instrumentation), try to add processor to it
    # This part is more complex as the global provider might not be configurable directly
    # For now, we assume if it's set, it's managed elsewhere or by auto-instrumentation
    logger.info("Global TracerProvider already set. Assuming it's correctly configured.")


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

# Instrument FastAPI app
FastAPIInstrumentor().instrument_app(app) # Changed OpenTelemetryInstrumentor to FastAPIInstrumentor

# Instrument Logging
LoggingInstrumentor().instrument(set_logging_format=True)

# Instrument Requests
RequestsInstrumentor().instrument()

# Instrument Kafka
# This will instrument confluent_kafka producers and consumers
# Ensure 'opentelemetry-instrumentation-kafka-python' is in requirements.txt
KafkaInstrumentor().instrument()


# Initialize metadata consumer
# Define Kafka configurations
consumer_config = {
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    "group.id": "llm_metadata_group",
    "auto.offset.reset": "earliest" # Default auto offset reset
}

producer_config = {
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
}

metadata_consumer = MetadataConsumerService(
    llm_service=llm_service,
    consumer_config=consumer_config, # Pass the consumer_config dictionary
    producer_config=producer_config, # Pass the producer_config dictionary
    document_topic="metadata_extraction", # Pass the specific topic name
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
        logger.info("Initializing metadata consumer with bootstrap servers: " + 
                  os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
        await metadata_consumer.initialize()
        logger.info("Metadata consumer initialization successful")
        
        # Check Kafka topic existence
        logger.info("Starting metadata consumer")
        try:
            from kafka.admin import KafkaAdminClient, NewTopic
            admin_client = KafkaAdminClient(
                bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
                client_id='llm-service-admin'
            )
            topics = admin_client.list_topics()
            logger.info(f"Available Kafka topics: {topics}")
            
            metadata_topic = "metadata_extraction"
            if metadata_topic not in topics:
                logger.warning(f"Topic {metadata_topic} does not exist in Kafka")
                logger.info(f"Creating topic {metadata_topic}...")
                try:
                    admin_client.create_topics([
                        NewTopic(name=metadata_topic, num_partitions=1, replication_factor=1)
                    ])
                    logger.info(f"Successfully created topic {metadata_topic}")
                except Exception as topic_error:
                    logger.warning(f"Could not create topic: {topic_error}")
            else:
                logger.info(f"Topic {metadata_topic} exists in Kafka")
        except Exception as admin_error:
            logger.warning(f"Failed to check Kafka topics: {admin_error}")
        
        # Start the consumer
        await metadata_consumer.start()
        logger.info("Metadata consumer started successfully")
    except Exception as e:
        logger.error(f"Failed to start metadata consumer: {e}", exc_info=True)
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
    return {            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
            "hostname": hostname,
            "endpoints": [
                {"path": "/generate", "methods": ["POST"], "description": "Generate text responses"},
                {"path": "/generate/stream", "methods": ["POST"], "description": "Stream text generation"},
                {"path": "/embeddings", "methods": ["POST"], "description": "Generate embeddings"},
                {"path": "/embeddings/batch", "methods": ["POST"], "description": "Generate batch embeddings"},
                {"path": "/metadata/status", "methods": ["GET"], "description": "Get metadata consumer status"},
                {"path": "/metadata/diagnostics", "methods": ["GET"], "description": "Get detailed metadata consumer diagnostics"}
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

@app.get("/metadata/diagnostics")
async def metadata_diagnostics():
    """Get detailed diagnostics information about the metadata consumer"""
    try:
        # Import the health check utility
        from infrastructure.messaging.kafka_health_check import check_kafka_health
        
        # Get basic consumer status
        status = {
            "consumer_status": get_consumer_status(metadata_consumer.consumer),
            "bootstrap_servers": metadata_consumer.bootstrap_servers,
            "topic": metadata_consumer.topic,
            "consumer_group_id": metadata_consumer.consumer_group_id,
            "processed_count": metadata_consumer.processed_count,
            "failed_count": metadata_consumer.failed_count
        }
        
        # Get detailed debug status from the consumer
        consumer_debug = await metadata_consumer.debug_status()
        status["consumer_debug"] = consumer_debug
        
        # Run Kafka diagnosis with the standard diagnostics
        kafka_status = await diagnose_kafka_connection(
            bootstrap_servers=metadata_consumer.bootstrap_servers,
            topic=metadata_consumer.topic
        )
        status["kafka_diagnosis"] = kafka_status
        
        # Run enhanced health check
        health_check = await check_kafka_health(metadata_consumer.bootstrap_servers)
        status["kafka_health"] = health_check
        
        return status
    except Exception as e:
        logger.error(f"Error getting metadata diagnostics: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Error getting diagnostics: {str(e)}"}
        )

@app.post("/metadata/fix")
async def fix_metadata_consumer():
    """Attempt to fix the metadata consumer issues"""
    try:
        # Import the fix utility
        from infrastructure.messaging.kafka_health_check import fix_consumer_issues
        
        # Stop the current consumer
        logger.info("Stopping the current consumer for repair...")
        await metadata_consumer.stop()
        
        # Attempt to fix issues
        fix_results = await fix_consumer_issues(
            bootstrap_servers=metadata_consumer.bootstrap_servers,
            topic=metadata_consumer.topic,
            consumer_group=metadata_consumer.consumer_group_id
        )
        
        # Reinitialize and restart the consumer
        logger.info("Reinitializing the consumer...")
        await metadata_consumer.initialize()
        
        logger.info("Restarting the consumer...")
        await metadata_consumer.start()
        
        return {
            "status": "repair_attempted",
            "fix_results": fix_results,
            "consumer_restarted": True
        }
    except Exception as e:
        logger.error(f"Error fixing metadata consumer: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Error fixing consumer: {str(e)}"}
        )

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
        "app.main:app",  # Changed from "main:app"
        host="0.0.0.0",
        port=8002, # Changed from 8001
        reload=os.getenv("DEBUG", "False").lower() == "true"
    )

"""
Kafka Utility Service
-------------------
This microservice provides reusable Kafka producers and consumers:
- Consumer patterns for document events, queries, and metadata
- Producer patterns for various services
- Message transformation and routing
"""

import asyncio
import os
import logging
import uvicorn
import socket
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import json
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define service name and version
SERVICE_NAME = "KafkaUtilityService"
SERVICE_VERSION = "1.0.0"

# API configuration
class ApiConfig:
    # Kafka configuration
    KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    
    # Service URLs
    DOCUMENT_SERVICE_URL = os.getenv("DOCUMENT_SERVICE_URL", "http://document-service:8000")
    QUERY_SERVICE_URL = os.getenv("QUERY_SERVICE_URL", "http://query-service:8000")
    LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://llm-service:8000")
    
    # API root path
    ROOT_PATH = os.getenv("ROOT_PATH", "")

# Initialize configuration
config = ApiConfig()

# Create the FastAPI app instance
app = FastAPI(
    title="Kafka Utility Service",
    description="Kafka consumers and producers for the RAG system",
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

# Import and initialize all consumers and producers
# This will be implemented in the next steps

# Dictionary to store active consumer tasks
active_consumers = {}

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint to verify API is running"""
    return {"status": "ok", "message": "Kafka Utility Service API is operational"}

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for service discovery"""
    return {"status": "healthy", "active_consumers": list(active_consumers.keys())}

# Service information endpoint
@app.get("/service-info")
async def service_info(request: Request):
    """Service information endpoint for service registry"""
    hostname = socket.gethostname()
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "hostname": hostname,
        "consumers": list(active_consumers.keys()),
        "topics": [
            "document-created",
            "document-processed",
            "document-chunks-created",
            "rag-queries",
            "query-results",
            "embedding-requests",
            "metadata-enrichment"
        ]
    }

# Consumer control endpoints will be added here
# ...

# Start all consumers on application startup
@app.on_event("startup")
async def startup_event():
    """Start all consumers when the application starts"""
    # This will be implemented in the next steps
    pass

# Stop all consumers on application shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Stop all consumers when the application shuts down"""
    # This will be implemented in the next steps
    pass

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

"""
Document Service
---------------
This microservice handles document operations:
- Upload, download, list and delete documents
- Document chunking 
- Integration with document processor for format conversions
- PDF creation
"""

from fastapi import FastAPI, UploadFile, BackgroundTasks, Form, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional, Union, Any
import asyncio
import io
import os
import sys
import logging
import uvicorn
import socket
from bson import ObjectId
from bson.errors import InvalidId
import uuid
import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import application services
try:
    from application.services.document_service import DocumentService, DocumentDTO
    from domain.services.document_processing_service import DocumentProcessingService
    from domain.services.chunking_service import ChunkingService
    from infrastructure.blob.blob_store import BlobStore
    from infrastructure.persistence.mongodb_document_repository import MongoDBDocumentRepository
    from infrastructure.messaging.kafka_client import KafkaClient
except ImportError:
    # Try alternative import paths
    from app.application.services.document_service import DocumentService, DocumentDTO
    from app.domain.services.document_processing_service import DocumentProcessingService
    from app.domain.services.chunking_service import ChunkingService
    from app.infrastructure.blob.blob_store import BlobStore
    from app.infrastructure.persistence.mongodb_document_repository import MongoDBDocumentRepository
    from app.infrastructure.messaging.kafka_client import KafkaClient

# Define service name and version
SERVICE_NAME = "DocumentService"
SERVICE_VERSION = "1.0.0"

# API configuration
class ApiConfig:
    # MongoDB connection
    MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://user:password@mongodb:27017/rag_db?authSource=admin&replicaSet=rs0&retryWrites=true")
    MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "rag_db")
    
    # MinIO configuration
    MINIO_URL = os.getenv("MINIO_URL", "localhost:9000")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    
    # Document processor URL
    DOCUMENT_PROCESSOR_URL = os.getenv("DOCUMENT_PROCESSOR_URL", "http://document-processor:8080")
    
    # Kafka configuration
    KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    
    # API root path
    ROOT_PATH = os.getenv("ROOT_PATH", "")

# Initialize configuration
config = ApiConfig()

# Create the FastAPI app instance
app = FastAPI(
    title="Document Service",
    description="Document upload, processing, and management API",
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

# Initialize infrastructure components
blob_store = BlobStore(
    endpoint=config.MINIO_URL,
    access_key=config.MINIO_ACCESS_KEY,
    secret_key=config.MINIO_SECRET_KEY
)

document_repository = MongoDBDocumentRepository(
    connection_string=config.MONGODB_URL,
    db_name=config.MONGODB_DB_NAME
)

kafka_client = KafkaClient(bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS)

# Initialize domain services
document_processor = DocumentProcessingService(document_processor_url=config.DOCUMENT_PROCESSOR_URL)
chunking_service = ChunkingService()

# Initialize application services
document_service = DocumentService(
    document_repository=document_repository,
    document_processor=document_processor,
    blob_store=blob_store,
    chunking_service=chunking_service,
    kafka_client=kafka_client
)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint to verify API is running"""
    return {"status": "ok", "message": "Document Service API is operational"}

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for service discovery"""
    return {"status": "healthy"}

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
            {"path": "/api/documents", "methods": ["GET", "POST"], "description": "Document operations"},
            {"path": "/api/documents/{document_id}", "methods": ["GET", "DELETE"], "description": "Document details and deletion"},
            {"path": "/api/documents/{document_id}/download", "methods": ["GET"], "description": "Download document"},
            {"path": "/api/documents/{document_id}/chunks", "methods": ["GET"], "description": "Get document chunks"},
            {"path": "/api/documents/convert", "methods": ["POST"], "description": "Convert document to PDF"},
        ]
    }

# Document endpoints
@app.post("/api/documents", response_model=DocumentDTO)
async def create_document(
    file: UploadFile,
    user_id: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None)
):
    """Upload a new document"""
    # Parse metadata if provided
    parsed_metadata = {}
    if metadata:
        try:
            parsed_metadata = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid metadata format")
    
    # Upload document
    return await document_service.upload_document(
        file=file,
        user_id=user_id,
        metadata=parsed_metadata
    )

@app.get("/api/documents", response_model=Dict[str, Any])
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    processed: Optional[bool] = None,
    chunked: Optional[bool] = None
):
    """List documents with optional filtering"""
    # Build query filter
    query_filter = {}
    
    if status:
        query_filter["processing_status"] = status
        
    if processed is not None:
        query_filter["is_processed"] = processed
        
    if chunked is not None:
        query_filter["is_chunked"] = chunked
    
    # Get documents
    documents, total = await document_service.list_documents(
        skip=skip,
        limit=limit,
        query_filter=query_filter
    )
    
    # Return with pagination info
    return {
        "documents": documents,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@app.get("/api/documents/{document_id}", response_model=DocumentDTO)
async def get_document(document_id: str):
    """Get document metadata"""
    return await document_service.get_document(document_id)

@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document"""
    result = await document_service.delete_document(document_id)
    if result:
        return {"status": "success", "message": "Document deleted"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete document")

@app.get("/api/documents/{document_id}/download")
async def download_document(document_id: str):
    """Download document file"""
    file_content, filename, content_type = await document_service.download_document(document_id)
    
    # Create streaming response
    return StreamingResponse(
        iter([file_content.getvalue()]),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/documents/{document_id}/chunks")
async def get_document_chunks(document_id: str):
    """Get chunks for a document"""
    chunks = await document_service.get_document_chunks(document_id)
    return {"chunks": chunks, "count": len(chunks)}

@app.post("/api/documents/convert")
async def convert_to_pdf(file: UploadFile):
    """Convert a document to PDF"""
    pdf_content, pdf_filename = await document_service.convert_to_pdf(file)
    
    # Create streaming response
    return StreamingResponse(
        iter([pdf_content]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={pdf_filename}"}
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

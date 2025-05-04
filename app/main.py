from fastapi import FastAPI, UploadFile, BackgroundTasks, Form, Body, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional
import asyncio
import io
import os
import sys
import logging
import uvicorn
import socket
import platform

# Set up logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Fix imports by getting the absolute paths
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)
    logger.debug(f"Added {parent_dir} to sys.path")

try:
    # First try relative imports if running as a package
    from .application.services.document_service import DocumentService, DocumentDTO
    from .application.services.query_service import QueryService
    from .domain.services.document_processing_service import DocumentProcessingService
    from .infrastructure.persistence.mongodb_document_repository import MongoDBDocumentRepository
    from .infrastructure.llm.llm_manager import LLMManager
    from .infrastructure.blob.blob_store import BlobStore
    from .infrastructure.messaging.kafka_consumer import KafkaConsumerService
    logger.debug("Imported modules using relative imports")
except ImportError as e:
    logger.debug(f"Relative import failed: {e}, trying absolute imports")
    # Fall back to absolute imports if running directly
    from app.application.services.document_service import DocumentService, DocumentDTO
    from app.application.services.query_service import QueryService
    from app.domain.services.document_processing_service import DocumentProcessingService
    from app.infrastructure.persistence.mongodb_document_repository import MongoDBDocumentRepository
    from app.infrastructure.llm.llm_manager import LLMManager
    from app.infrastructure.blob.blob_store import BlobStore
    from app.infrastructure.messaging.kafka_consumer import KafkaConsumerService
    logger.debug("Imported modules using absolute imports")

from pydantic import BaseModel

# Define a query request model
class QueryRequest(BaseModel):
    query: str

# Define service constants
SERVICE_NAME = "rag-api"
SERVICE_VERSION = "1.0.0"

# Create the FastAPI app instance
app = FastAPI(
    title="RAG API Service",
    description="Retrieval-Augmented Generation API",
    version=SERVICE_VERSION
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Initialize all dependencies
document_repository = MongoDBDocumentRepository()
document_processor = DocumentProcessingService()
llm_manager = LLMManager()
blob_store = BlobStore()

# Initialize application services
document_service = DocumentService(document_repository, document_processor)
query_service = QueryService(document_service, llm_manager)

# Initialize Kafka consumer
kafka_consumer = KafkaConsumerService(query_service)

# Add a root endpoint for API health check
@app.get("/")
async def root():
    """Root endpoint to verify API is running"""
    logger.info("Root endpoint called")
    return {"status": "ok", "message": "RAG API is operational"}

# Service registry endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint for service discovery"""
    return {"status": "healthy"}

@app.get("/service-info")
async def service_info(request: Request):
    """Service information endpoint for service registry"""
    hostname = socket.gethostname()
    
    # Get base URL from environment or request
    base_url = os.getenv("BASE_PATH", "")
    
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "hostname": hostname,
        "platform": platform.platform(),
        "endpoints": [
            f"{base_url}/documents/upload",
            f"{base_url}/document/upload",
            f"{base_url}/query/async",
            f"{base_url}/query/sync",
            f"{base_url}/documents/list",
            f"{base_url}/diagnostics/vector-index"
        ]
    }

@app.on_event("startup")
async def startup_event():
    """Initialize repository and start Kafka consumer when application starts"""
    logger.info("Starting application services...")
    
    # Initialize MongoDB repository with proper async initialization
    try:
        await document_repository.initialize()
        logger.info("MongoDB repository initialized successfully")
        
        # Check if LLM service is available
        await llm_manager.check_availability()
        logger.info("LLM service availability checked")
        
        # Start Kafka consumer - this will throw an exception if Kafka is not available
        logger.info("Starting Kafka consumer...")
        # Create a task but also await its initial setup to catch immediate errors
        consumer_task = asyncio.create_task(kafka_consumer.start_consuming())
        # Give it a short time to initialize and potentially throw errors
        await asyncio.sleep(1)  
        
        # Quick check to see if the task failed immediately
        if consumer_task.done() and consumer_task.exception() is not None:
            raise RuntimeError(f"Kafka consumer failed to start: {consumer_task.exception()}")
            
        logger.info("Application startup completed successfully")
    except Exception as e:
        logger.error(f"Critical error during startup: {e}")
        # Re-raise the exception to prevent the application from starting with partial services
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Stop Kafka consumer when application shuts down"""
    await kafka_consumer.stop()

@app.post("/documents/upload")
async def upload_documents(files: List[UploadFile]):
    results = []
    for file in files:
        # Store in blob storage
        blob_path = await blob_store.upload_file(file)
        
        # Read file content as bytes
        content_bytes = await file.read()
        
        # Create document DTO with bytes content
        doc_dto = DocumentDTO(
            title=file.filename,
            content=content_bytes, # Pass bytes directly
            metadata={
                'file_type': file.content_type,
                'blob_path': blob_path,
                'source_type': 'file' # Use a more generic source type initially
            }
        )
        
        # Process and store document (ensure service handles bytes)
        document_id = await document_service.process_and_store_document(doc_dto)
        
        results.append({
            "file": file.filename,
            "document_id": document_id,
            "blob_path": blob_path
        })
    
    return results

@app.post("/document/upload")
async def upload_document(file: UploadFile):
    """Endpoint to upload a single document"""
    # Store in blob storage
    blob_path = await blob_store.upload_file(file)
    
    # Read file content as bytes
    content_bytes = await file.read()
    
    # Create document DTO with bytes content
    doc_dto = DocumentDTO(
        title=file.filename,
        content=content_bytes, # Pass bytes directly
        metadata={
            'file_type': file.content_type,
            'blob_path': blob_path,
            'source_type': 'file'
        }
    )
    
    # Process and store document
    document_id = await document_service.process_and_store_document(doc_dto)
    
    return {
        "file": file.filename,
        "document_id": document_id,
        "blob_path": blob_path
    }

@app.post("/query/async")
async def async_query(query_req: QueryRequest, background_tasks: BackgroundTasks = None):
    query_id = await query_service.query_async(query_req.query)
    return {"query_id": query_id, "status": "processing"}

@app.get("/query/async/{query_id}")
async def get_async_result(query_id: str):
    result = await query_service.get_query_result(query_id)
    if result is None:
        return {"status": "processing"}
    return {
        "status": result.status,
        "answer": result.answer,
        "sources": [
            {
                "content": chunk.content,
                "source": chunk.source,
                "metadata": chunk.metadata
            }
            for chunk in result.source_chunks
        ]
    }

@app.post("/query/sync")
async def sync_query(query_req: QueryRequest):
    async def generate_results():
        async for token in query_service.query_sync(query_req.query):
            yield token

    return StreamingResponse(generate_results(), media_type="text/plain")

@app.get("/diagnostics/vector-index")
async def check_vector_index():
    """Diagnostic endpoint to check vector index status"""
    status = await document_repository.check_vector_index_status()
    return status

@app.get("/documents/list")
async def list_documents():
    docs = await document_repository.documents.find().to_list(100)
    return [{"id": str(doc.get("_id")), "title": doc.get("title")} for doc in docs]

@app.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and its associated chunks"""
    try:
        # Get document metadata to find the blob path
        doc = await document_repository.documents.find_one({"_id": document_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Extract blob path from metadata if available
        blob_path = None
        if doc.get("metadata") and doc["metadata"].get("blob_path"):
            blob_path = doc["metadata"]["blob_path"]
        
        # Delete document from MongoDB
        delete_result = await document_repository.documents.delete_one({"_id": document_id})
        if (delete_result.deleted_count == 0):
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete associated chunks
        await document_repository.chunks.delete_many({"metadata.document_id": document_id})
        
        # Delete from blob storage if path exists
        if blob_path:
            await blob_store.delete_file(blob_path)
            
        return {"success": True, "message": "Document and associated data deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")

@app.get("/documents/{document_id}/download")
async def download_document(document_id: str):
    """Download a document from blob storage"""
    try:
        # Get document metadata to find the blob path
        doc = await document_repository.documents.find_one({"_id": document_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
            
        # Get blob path from metadata
        if not doc.get("metadata") or not doc["metadata"].get("blob_path"):
            raise HTTPException(status_code=404, detail="Document blob path not found")
            
        blob_path = doc["metadata"]["blob_path"]
        
        # Get file from blob storage
        file_content = await blob_store.get_file(blob_path)
        if not file_content:
            raise HTTPException(status_code=404, detail="File not found in storage")
            
        # Determine content type
        content_type = doc["metadata"].get("file_type", "application/octet-stream")
        
        # Use the original filename or fallback to a generic name
        filename = doc.get("title", f"document-{document_id}")
        
        # Return file as downloadable response
        return StreamingResponse(
            file_content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading document: {str(e)}")

@app.get("/query/completed")
async def get_completed_queries():
    """Get a list of completed queries"""
    completed_queries = await query_service.get_completed_queries()
    return completed_queries

# Modified run block for direct execution
if __name__ == "__main__":
    logger.info("Starting FastAPI application directly")
    import uvicorn
    # If running directly, use the filename instead of module path
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
from fastapi import FastAPI, UploadFile, BackgroundTasks, Form, Body, HTTPException, Request, Query
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional, Tuple, Union
import asyncio
import io
import os
import sys
import logging
import uvicorn
import socket
import platform
import aiohttp
import tempfile
from pathlib import Path
import mimetypes
from bson import ObjectId
from bson.errors import InvalidId

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure OpenTelemetry Logging
OTEL_SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "rag-app")
OTEL_EXPORTER_OTLP_LOGS_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "http://otel-collector:4317")
OTEL_PYTHON_LOG_LEVEL_STR = os.environ.get("OTEL_PYTHON_LOG_LEVEL", "INFO").upper()
otel_log_level = getattr(logging, OTEL_PYTHON_LOG_LEVEL_STR, logging.INFO)

from opentelemetry.exporter.otlp.proto.grpc.log_exporter import OTLPLogExporter
from opentelemetry.sdk.logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk.logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

logger_provider = LoggerProvider(
    resource=Resource.create({"service.name": OTEL_SERVICE_NAME})
)
otlp_log_exporter = OTLPLogExporter(endpoint=OTEL_EXPORTER_OTLP_LOGS_ENDPOINT, insecure=True)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_log_exporter))
logging.getLogger().addHandler(LoggingHandler(level=otel_log_level, logger_provider=logger_provider))
# logging.getLogger().setLevel(otel_log_level) # Keep existing basicConfig level for now

# Fix imports by getting the absolute paths
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if (parent_dir not in sys.path):
    sys.path.append(parent_dir)
    logger.debug(f"Added {parent_dir} to sys.path")

try:
    # First try relative imports if running as a package
    from .application.services.document_service import DocumentService, DocumentDTO
    from .application.services.query_service import QueryService
    from .domain.services.document_processing_service import DocumentProcessingService
    from .domain.services.query_preprocessor import QueryPreprocessor
    from .domain.services.advanced_chunking_service import AdvancedChunkingService
    from .domain.services.query_enhancer import QueryEnhancer
    from .infrastructure.persistence.mongodb_document_repository import MongoDBDocumentRepository
    from .infrastructure.llm.llm_manager import LLMManager
    from .infrastructure.blob.blob_store import BlobStore
    from .infrastructure.messaging.kafka_consumer import KafkaConsumerService
    from .infrastructure.messaging.metadata_consumer import MetadataConsumerService
    from .infrastructure.reranking.cross_encoder_reranker import CrossEncoderReRanker
    from .infrastructure.query_enhancement.advanced_query_enhancer import AdvancedQueryEnhancer
    from .infrastructure.query_enhancement.query_enhancer_pipeline import QueryEnhancerPipeline
    from .domain.value_objects.embedding import Embedding # Added import
    logger.debug("Imported modules using relative imports")
except ImportError as e:
    logger.debug(f"Relative import failed: {e}, trying absolute imports")
    # Fall back to absolute imports if running directly
    from app.application.services.document_service import DocumentService, DocumentDTO
    from app.application.services.query_service import QueryService
    from app.domain.services.document_processing_service import DocumentProcessingService
    from app.domain.services.query_preprocessor import QueryPreprocessor
    from app.domain.services.advanced_chunking_service import AdvancedChunkingService
    from app.domain.services.query_enhancer import QueryEnhancer
    from app.infrastructure.persistence.mongodb_document_repository import MongoDBDocumentRepository
    from app.infrastructure.llm.llm_manager import LLMManager
    from app.infrastructure.blob.blob_store import BlobStore
    from app.infrastructure.messaging.kafka_consumer import KafkaConsumerService
    from app.infrastructure.messaging.metadata_consumer import MetadataConsumerService
    from app.infrastructure.reranking.cross_encoder_reranker import CrossEncoderReRanker
    from app.infrastructure.query_enhancement.advanced_query_enhancer import AdvancedQueryEnhancer
    from app.infrastructure.query_enhancement.query_enhancer_pipeline import QueryEnhancerPipeline
    from app.domain.value_objects.embedding import Embedding # Added import
    logger.debug("Imported modules using absolute imports")

from pydantic import BaseModel

# Define a query request model
class QueryRequest(BaseModel):
    query: str

# Define service constants
SERVICE_NAME = "rag-api"
SERVICE_VERSION = "1.0.0"
# Document processor service URL - will default to localhost if not set
DOCUMENT_PROCESSOR_URL = os.getenv("DOCUMENT_PROCESSOR_URL", "http://localhost:8080")

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

# Initialize precision-enhancing components
query_preprocessor = QueryPreprocessor()
advanced_chunking = AdvancedChunkingService() 
cross_encoder_reranker = CrossEncoderReRanker()

# Initialize query enhancer components
advanced_query_enhancer = AdvancedQueryEnhancer(llm_manager=llm_manager)

# Set up the query enhancer pipeline
query_enhancer_pipeline = QueryEnhancerPipeline(
    enhancers=[
        advanced_query_enhancer
        # Add more enhancers here if needed
    ]
)

# Initialize application services with enhanced components
document_service = DocumentService(
    document_repository, 
    document_processor,
    llm_manager=llm_manager,  # Pass LLM manager for metadata enrichment
    query_preprocessor=query_preprocessor,
    reranker=cross_encoder_reranker,
    query_enhancer=query_enhancer_pipeline,
    kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
)
query_service = QueryService(document_service, llm_manager)

# Initialize Kafka consumers
kafka_consumer = KafkaConsumerService(query_service)
metadata_consumer = MetadataConsumerService(
    document_repository=document_repository,
    llm_manager=llm_manager,
    kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
)

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
    """Initialize repository and start Kafka consumers when application starts"""
    logger.info("Starting application services...")
    
    # Initialize MongoDB repository with proper async initialization
    try:
        await document_repository.initialize()
        logger.info("MongoDB repository initialized successfully")
        
        # Check if LLM service is available
        await llm_manager.check_availability()
        logger.info("LLM service availability checked")
        
        # Start Kafka query consumer - this will throw an exception if Kafka is not available
        logger.info("Starting Kafka query consumer...")
        # Create a task but also await its initial setup to catch immediate errors
        consumer_task = asyncio.create_task(kafka_consumer.start_consuming())
        
        # Start Kafka metadata enrichment consumer
        logger.info("Starting metadata enrichment consumer...")
        metadata_consumer_task = asyncio.create_task(metadata_consumer.start())
        
        # Give them a short time to initialize and potentially throw errors
        await asyncio.sleep(1)  
        
        # Quick check to see if the tasks failed immediately
        if consumer_task.done() and consumer_task.exception() is not None:
            raise RuntimeError(f"Kafka query consumer failed to start: {consumer_task.exception()}")
            
        if metadata_consumer_task.done() and metadata_consumer_task.exception() is not None:
            raise RuntimeError(f"Metadata consumer failed to start: {metadata_consumer_task.exception()}")
            
        logger.info("Application startup completed successfully")
    except Exception as e:
        logger.error(f"Critical error during startup: {e}")
        # Re-raise the exception to prevent the application from starting with partial services
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Stop Kafka consumers when application shuts down"""
    logger.info("Application is shutting down, stopping services...")
    
    # Create a list of shutdown tasks
    shutdown_tasks = []
    
    # Add Kafka consumer shutdown tasks with timeouts
    if hasattr(kafka_consumer, 'stop'):
        logger.info("Stopping Kafka query consumer...")
        shutdown_tasks.append(kafka_consumer.stop())
    
    if hasattr(metadata_consumer, 'stop'):
        logger.info("Stopping metadata consumer...")
        shutdown_tasks.append(metadata_consumer.stop())
    
    # Wait for all shutdown tasks to complete with a timeout
    if shutdown_tasks:
        try:
            # Use asyncio.wait with a timeout to ensure we don't hang indefinitely
            done, pending = await asyncio.wait(
                shutdown_tasks,
                timeout=5.0,  # 5 seconds max wait time
                return_when=asyncio.ALL_COMPLETED
            )
            
            # Log any pending tasks that didn't complete in time
            if pending:
                logger.warning(f"{len(pending)} shutdown tasks didn't complete in time")
            
            logger.info("All Kafka consumers stopped during shutdown")
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")
    else:
        logger.info("No services to stop during shutdown")
    
    # Add a small delay to allow final cleanup
    await asyncio.sleep(0.5)
    logger.info("Application shutdown complete")

@app.post("/documents/upload")
async def upload_documents(files: List[UploadFile]):
    """Endpoint to upload multiple documents"""
    results = []
    for file in files:
        try:
            result = await process_document_upload(file)
            results.append(result)
        except Exception as e:
            logger.error(f"Error processing document upload: {file.filename}: {str(e)}")
            results.append({
                "file": file.filename,
                "error": str(e),
                "status": "failed"
            })
    
    return results

@app.post("/document/upload")
async def upload_document(file: UploadFile):
    """Endpoint to upload a single document"""
    try:
        result = await process_document_upload(file)
        return result
    except Exception as e:
        logger.error(f"Error processing document upload: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing document upload: {str(e)}"
        )

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
        # Convert string ID to ObjectId
        try:
            obj_id = ObjectId(document_id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="Invalid document ID format")

        # Get document metadata to find the blob path
        doc = await document_repository.documents.find_one({"_id": obj_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        blob_path = doc["metadata"].get("blob_path")

        # Delete document from MongoDB using ObjectId
        delete_result = await document_repository.documents.delete_one({"_id": obj_id})
        if (delete_result.deleted_count == 0):
            # This case should ideally be covered by the find_one check above,
            # but kept for robustness.
            raise HTTPException(status_code=404, detail="Document not found during deletion")

        # Delete associated chunks - ensure metadata.document_id is stored consistently (string or ObjectId)
        await document_repository.chunks.delete_many({"metadata.document_id": document_id})

        # Delete from blob storage if path exists
        if blob_path:
            try:
                await blob_store.delete_file(blob_path)
            except Exception as e:
                logger.error(f"Error deleting blob at {blob_path}: {str(e)}")
                # Continue with the operation even if blob deletion fails
        
        return {"status": "success", "message": "Document and associated data deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")

@app.get("/documents/{document_id}/download")
async def download_document(document_id: str):
    """Download a document from blob storage"""
    try:
        # Convert string ID to ObjectId
        try:
            obj_id = ObjectId(document_id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="Invalid document ID format")

        # Get document metadata to find the blob path
        doc = await document_repository.documents.find_one({"_id": obj_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Get blob path from metadata
        if not doc.get("metadata") or not doc["metadata"].get("blob_path"):
            raise HTTPException(status_code=404, detail="Document blob path not found")
            
        blob_path = doc["metadata"]["blob_path"]
        print(f"Blob path: {blob_path}")
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

@app.get("/diagnostics/vector-search-threshold")
async def check_vector_search_threshold(query: str = Query("", description="Optional test query to see scores")):
    """Diagnostic endpoint to check vector similarity threshold and test its effect"""
    try:
        # Get current threshold from document repository
        threshold = document_repository.similarity_threshold
        
        results = {
            "current_similarity_threshold": threshold,
            "vector_search_available": document_repository.vector_search_available,
            "vector_index_type": document_repository.vector_index_type
        }
        
        # If a query is provided, test it with the current threshold
        if query:
            # Get a few more results than normal for analysis
            limit = 10
            
            # Generate embedding for the query
            query_embedding = document_processor.encoder.encode(query)
            embedding = Embedding.create(query_embedding.tolist())
            
            # Perform search without filtering to see raw scores
            # This is a direct search that bypasses the threshold for diagnostic purposes
            pipeline = []
            
            if document_repository.vector_index_type == 'atlas':
                pipeline = [
                    {
                        "$search": {
                            "index": document_repository.vector_index_name,
                            "knnBeta": {
                                "vector": embedding.vector,
                                "path": "embedding.vector",
                                "k": limit
                            }
                        }
                    },
                    {
                        "$project": {
                            "_id": 1,
                            "content": 1, 
                            "metadata": 1,
                            "source": 1,
                            "score": { "$meta": "searchScore" }
                        }
                    }
                ]
            elif document_repository.vector_index_type == 'native':
                pipeline = [
                    {
                        "$vectorSearch": {
                            "index": document_repository.vector_index_name,
                            "path": "embedding.vector",
                            "queryVector": embedding.vector,
                            "numCandidates": limit * 10,
                            "limit": limit
                        }
                    },
                    {
                        "$project": {
                            "_id": 1,
                            "content": 1,
                            "metadata": 1, 
                            "source": 1,
                            "score": { "$meta": "vectorSearchScore" }
                        }
                    }
                ]
            
            cursor = document_repository.chunks.aggregate(pipeline)
            test_results = await cursor.to_list(length=limit)
            
            # Format the results for easy analysis
            query_results = []
            for doc in test_results:
                score = doc.get("score", 0)
                metadata = doc.get("metadata", {})
                source = doc.get("source", "Unknown")
                meets_threshold = score >= threshold
                
                query_results.append({
                    "content_snippet": doc.get("content", "")[:100] + "...",
                    "source": source,
                    "score": score,
                    "meets_threshold": meets_threshold,
                    "metadata": metadata
                })
            
            results["query"] = query
            results["results"] = query_results
            results["filtered_results_count"] = sum(1 for r in query_results if r["meets_threshold"])
            
        return results
    except Exception as e:
        logger.error(f"Error checking vector search threshold: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error checking vector search threshold: {str(e)}")

@app.get("/vector/similarity-scores")
async def get_similarity_scores(query: str = Query(..., description="Query to calculate similarity scores for")):
    """
    Get similarity scores between a query and documents in the vector store.
    This endpoint focuses specifically on printing the vector similarity scores.
    """
    try:
        logger.info(f"Calculating similarity scores for query: {query}")
        
        # Maximum number of results to return
        limit = 20
        
        # Generate embedding for the query using document processor
        query_embedding = document_processor.encoder.encode(query)
        
        # Assuming Embedding is imported from domain.value_objects.embedding
        try:
            from app.domain.value_objects.embedding import Embedding
        except ImportError:
            from domain.value_objects.embedding import Embedding
            
        embedding = Embedding.create(query_embedding.tolist())
        
        # Prepare the search pipeline based on vector index type
        pipeline = []
        
        if document_repository.vector_index_type == 'atlas':
            pipeline = [
                {
                    "$search": {
                        "index": document_repository.vector_index_name,
                        "knnBeta": {
                            "vector": embedding.vector,
                            "path": "embedding.vector",
                            "k": limit
                        }
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "content": 1, 
                        "source": 1,
                        "metadata": 1,
                        "score": { "$meta": "searchScore" }
                    }
                }
            ]
        elif document_repository.vector_index_type == 'native':
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": document_repository.vector_index_name,
                        "path": "embedding.vector",
                        "queryVector": embedding.vector,
                        "numCandidates": limit * 10,
                        "limit": limit
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "content": 1,
                        "source": 1,
                        "metadata": 1,
                        "score": { "$meta": "vectorSearchScore" }
                    }
                }
            ]
        else:
            return {"error": "Vector search not available or properly configured"}
        
        # Execute the search
        cursor = document_repository.chunks.aggregate(pipeline)
        results = await cursor.to_list(length=limit)
        
        # Format results to emphasize similarity scores
        formatted_results = []
        for doc in results:
            score = doc.get("score", 0)
            source = doc.get("source", "Unknown")
            doc_id = str(doc.get("_id", "Unknown"))
            
            # Get a snippet of content for context
            content_snippet = doc.get("content", "")[:150] + "..." if len(doc.get("content", "")) > 150 else doc.get("content", "")
            
            formatted_results.append({
                "score": score,
                "document_id": doc_id,
                "source": source,
                "content_preview": content_snippet
            })
        
        # Sort by similarity score (highest first)
        formatted_results.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "query": query,
            "vector_search_type": document_repository.vector_index_type,
            "similarity_scores": formatted_results
        }
        
    except Exception as e:
        logger.error(f"Error calculating similarity scores: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error calculating similarity scores: {str(e)}")

# Helper function to convert documents to PDF
async def convert_to_pdf(file: UploadFile) -> Tuple[bytes, str]:
    """
    Converts a document to PDF format using the document-processor service
    
    Args:
        file: The uploaded file to convert
        
    Returns:
        Tuple containing (pdf_content_bytes, original_filename_with_pdf_extension)
    """
    logger.info(f"Converting document to PDF format: {file.filename}")
    
    # Check if the file is already a PDF (check by content type and extension)
    is_pdf_content_type = file.content_type == "application/pdf"
    is_pdf_extension = file.filename.lower().endswith('.pdf')
    
    if (is_pdf_content_type or is_pdf_extension):
        logger.info(f"File '{file.filename}' is detected as PDF (content_type: {file.content_type}), skipping conversion")
        content = await file.read()
        # Reset file pointer for further use
        await file.seek(0)
        return content, file.filename
    
    # Read file content
    content = await file.read()
    
    try:
        # Improve content type detection
        content_type = file.content_type
        if not content_type or content_type == "application/octet-stream":
            # Try to determine content type from file extension
            content_type = mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
            logger.debug(f"Updated content type for {file.filename}: {content_type}")
        
        # Get file extension for format detection
        file_extension = os.path.splitext(file.filename)[1].lower().lstrip('.')
        if not file_extension:
            file_extension = "txt"  # Default to txt if no extension is found
        
        logger.debug(f"File extension extracted: '{file_extension}'")
        
        # Create form data for the document-processor service
        form_data = aiohttp.FormData()
        form_data.add_field('file', 
                          io.BytesIO(content),
                          filename=file.filename,
                          content_type=content_type)
        
        # Explicitly add format field based on file extension
        form_data.add_field('format', file_extension)
        
        logger.debug(f"Sending file to conversion service: filename={file.filename}, content_type={content_type}, format={file_extension}, size={len(content)} bytes")
        
        # Send request to document-processor service
        # Make sure the endpoint path is correct - make sure we're using /api/convert
        convert_url = f"{DOCUMENT_PROCESSOR_URL}/api/convert"
        logger.info(f"Sending document to conversion service: {convert_url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(convert_url, data=form_data) as response:
                if (response.status != 200):
                    # For error responses, try to get text content
                    try:
                        error_text = await response.text(errors='replace')
                        logger.error(f"Failed to convert document: {error_text}")
                        raise HTTPException(
                            status_code=500, 
                            detail=f"Failed to convert document to PDF: {error_text}"
                        )
                    except Exception as text_err:
                        logger.error(f"Failed to convert document and couldn't read error text: {text_err}")
                        raise HTTPException(
                            status_code=500,
                            detail="Failed to convert document to PDF"
                        )
                
                # For successful responses, get binary content directly
                pdf_content = await response.read()
                logger.debug(f"Received PDF conversion response, size: {len(pdf_content)} bytes")
        
        # Get filename without extension and add PDF extension
        filename_base = Path(file.filename).stem
        pdf_filename = f"{filename_base}.pdf"
        
        logger.info(f"Successfully converted document to PDF: {pdf_filename}")
        return pdf_content, pdf_filename
        
    except Exception as e:
        logger.error(f"Error converting document to PDF: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error converting document to PDF: {str(e)}"
        )
    finally:
        # Reset file pointer for further use
        await file.seek(0)

async def process_document_upload(file: UploadFile) -> Dict:
    """
    Process a single document upload, including PDF conversion, checksum verification, and storage.
    Prevents duplicate document uploads by checking content checksums.
    
    Args:
        file: The uploaded file to process
        
    Returns:
        Dict containing the document details and duplicate status
    """
    # Convert document to PDF 
    pdf_content, pdf_filename = await convert_to_pdf(file)
    
    # Store the converted PDF in blob storage
    blob_path = await blob_store.upload_binary(pdf_content, pdf_filename)
    
    # Create document DTO with PDF content
    doc_dto = DocumentDTO(
        title=pdf_filename,
        content=pdf_content,
        metadata={
            'file_type': 'application/pdf',
            'blob_path': blob_path,
            'source_type': 'file',
            'original_filename': file.filename,
            'original_content_type': file.content_type
        }
    )
    
    # Process and store document with checksum verification
    result = await document_service.process_and_store_document_with_checksum(doc_dto)
    
    # Handle duplicate case
    if result['is_duplicate']:
        logger.info(f"Document '{pdf_filename}' is a duplicate with checksum: {result['checksum']}")
        return {
            "file": pdf_filename,
            "original_file": file.filename,
            "document_id": result['document_id'],
            "is_duplicate": True,
            "checksum": result['checksum'],
            "blob_path": blob_path,
            "content_type": "application/pdf",
            "message": "Document already exists in the database, skipped processing."
        }
    
    # Handle new document case
    logger.info(f"Added new document '{pdf_filename}' with checksum: {result['checksum']}")
    return {
        "file": pdf_filename,
        "original_file": file.filename,
        "document_id": result['document_id'],
        "is_duplicate": False,
        "checksum": result['checksum'],
        "blob_path": blob_path,
        "content_type": "application/pdf"
    }

# Modified run block for direct execution
if __name__ == "__main__":
    logger.info("Starting FastAPI application directly")
    import uvicorn
    # If running directly, use the filename instead of module path
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
from fastapi import FastAPI, UploadFile, BackgroundTasks, Form
from fastapi.responses import StreamingResponse
from typing import List, Dict
import asyncio
from .application.services.document_service import DocumentService, DocumentDTO
from .application.services.query_service import QueryService
from .domain.services.document_processing_service import DocumentProcessingService
from .infrastructure.persistence.mongodb_document_repository import MongoDBDocumentRepository
from .infrastructure.llm.llm_manager import LLMManager
from .infrastructure.blob.blob_store import BlobStore
from .infrastructure.messaging.kafka_consumer import KafkaConsumerService

app = FastAPI()

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

@app.on_event("startup")
async def startup_event():
    """Initialize repository and start Kafka consumer when application starts"""
    # Initialize MongoDB repository with proper async initialization
    await document_repository.initialize()
    
    # Check if LLM service is available
    await llm_manager.check_availability()
    
    # Start Kafka consumer
    asyncio.create_task(kafka_consumer.start_consuming())

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
async def async_query(query: str = Form(...), background_tasks: BackgroundTasks = None):
    query_id = await query_service.query_async(query)
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
async def sync_query(query: str = Form(...)):
    async def generate_results():
        async for token in query_service.query_sync(query):
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
"""
Document Service
--------------
Application service for document operations, connecting domain logic with infrastructure.
"""

import logging
import os
import mimetypes
import tempfile
import asyncio
import json
from typing import List, Dict, Optional, Any, BinaryIO, Tuple, Union
from dataclasses import dataclass
from fastapi import UploadFile, HTTPException
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource

from domain.entities.document import Document, DocumentChunk
from domain.repositories.document_repository import DocumentRepository
from domain.services.document_processing_service import DocumentProcessingService
from domain.services.chunking_service import ChunkingService
from infrastructure.blob.blob_store import BlobStore
from infrastructure.messaging.kafka_client import KafkaClient

# Configure OpenTelemetry
resource = Resource.create({"service.name": "document-service"})
trace.set_tracer_provider(TracerProvider(resource=resource))
otlp_exporter = OTLPSpanExporter(endpoint="otel-collector:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
tracer = trace.get_tracer(__name__)

# Configure structured logging
class StructuredLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.service_name = "document-service"
    
    def _log(self, level, message, **kwargs):
        span_context = trace.get_current_span().get_span_context()
        log_data = {
            "message": message,
            "service": self.service_name,
            "trace_id": format(span_context.trace_id, "032x"),
            "span_id": format(span_context.span_id, "016x"),
            **kwargs
        }
        self.logger.log(level, json.dumps(log_data))
    
    def info(self, message, **kwargs):
        self._log(logging.INFO, message, **kwargs)
        
    def error(self, message, **kwargs):
        self._log(logging.ERROR, message, **kwargs)
        
    def warning(self, message, **kwargs):
        self._log(logging.WARNING, message, **kwargs)
        
    def debug(self, message, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)

logger = StructuredLogger(__name__)

@dataclass
class DocumentDTO:
    """Data transfer object for document metadata"""
    id: str
    name: str
    file_type: str
    file_size: int
    content_type: str
    created_at: str
    updated_at: str
    is_processed: bool
    is_chunked: bool
    processing_status: str
    processing_error: Optional[str] = None
    chunk_count: int = 0
    metadata: Dict[str, Any] = None

@dataclass
class ChunkDTO:
    """Data transfer object for document chunk"""
    id: str
    document_id: str
    chunk_index: int
    text: str
    metadata: Dict[str, Any] = None


class DocumentService:
    """Application service for document operations"""
    
    def __init__(
        self,
        document_repository: DocumentRepository,
        document_processor: DocumentProcessingService,
        blob_store: BlobStore,
        chunking_service: ChunkingService,
        kafka_client: KafkaClient
    ):
        """
        Initialize the document service
        
        Args:
            document_repository: Repository for document storage
            document_processor: Service for document processing
            blob_store: Storage for document files
            chunking_service: Service for chunking documents
            kafka_client: Client for Kafka messaging
        """
        self.document_repository = document_repository
        self.document_processor = document_processor
        self.blob_store = blob_store
        self.chunking_service = chunking_service
        self.kafka_client = kafka_client
        
        logger.info("Document service initialized")
        
    async def upload_document(
        self,
        file: UploadFile,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DocumentDTO:
        """
        Upload a new document
        
        Args:
            file: The uploaded file
            user_id: ID of the uploading user
            metadata: Additional document metadata
            
        Returns:
            Document DTO
        """
        with tracer.start_as_current_span("upload_document") as span:
            span.set_attribute("file.name", file.filename)
            span.set_attribute("file.size", file.size if hasattr(file, 'size') else 0)
            span.set_attribute("user.id", user_id or "anonymous")
            
            try:
                # Read file content
                file_content = await file.read()
                
                # Create a document entity
                document = Document(
                    name=file.filename,
                    file_type=os.path.splitext(file.filename)[1].lower().lstrip("."),
                    file_size=len(file_content),
                    content_type=file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream",
                    created_by=user_id,
                    metadata=metadata or {}
                )
                
                with tracer.start_span("save_document_to_repository") as save_span:
                    # Save document to repository
                    document = await self.document_repository.save_document(document)
                    save_span.set_attribute("document.id", document.id)
                
                with tracer.start_span("save_to_blob_storage") as blob_span:
                    # Save file to blob storage
                    blob_path = await self.blob_store.save_file(
                        file_content=file.file,
                        file_name=file.filename,
                        content_type=document.content_type
                    )
                    blob_span.set_attribute("blob.path", blob_path)
                
                # Update document with blob path
                document.blob_path = blob_path
                document = await self.document_repository.update_document(document)
                
                with tracer.start_span("send_document_created_event") as event_span:
                    # Send document created event
                    await self.kafka_client.send_document_created_event(
                        document_id=document.id,
                        metadata={
                            "name": document.name,
                            "file_type": document.file_type,
                            "file_size": document.file_size,
                            "content_type": document.content_type
                        }
                    )
                
                # Start processing document asynchronously
                asyncio.create_task(self._process_document(document.id))
                
                span.set_status(Status(StatusCode.OK))
                logger.info("Document uploaded successfully", 
                           document_id=document.id,
                           file_name=document.name,
                           file_size=document.file_size)
                
                # Convert to DTO
                return self._document_to_dto(document)
                
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR), str(e))
                logger.error("Error uploading document",
                           error=str(e),
                           file_name=file.filename)
                raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")
                
    async def _process_document(self, document_id: str):
        """
        Process document asynchronously
        
        Args:
            document_id: ID of document to process
        """
        with tracer.start_as_current_span("process_document") as span:
            span.set_attribute("document.id", document_id)
            
            try:
                # Get document
                document = await self.document_repository.get_document_by_id(document_id)
                if not document:
                    logger.error("Document not found for processing",
                               document_id=document_id)
                    span.set_status(Status(StatusCode.ERROR), "Document not found")
                    return
                
                # Update processing status
                document.update_processing_status("processing")
                await self.document_repository.update_document(document)
                
                with tracer.start_span("extract_text") as extract_span:
                    # Get file from blob storage
                    file_content, _ = await self.blob_store.get_file(document.blob_path)
                    
                    # Extract text from document
                    text, error = await self.document_processor.extract_text(
                        file_content=file_content.getvalue(),
                        file_extension=f".{document.file_type}"
                    )
                    
                    if error:
                        logger.error("Error extracting text from document",
                                   document_id=document_id,
                                   error=error)
                        extract_span.set_status(Status(StatusCode.ERROR), error)
                        document.update_processing_status("failed", error)
                        await self.document_repository.update_document(document)
                        await self.kafka_client.send_document_processed_event(
                            document_id=document_id,
                            status="failed",
                            metadata={"error": error}
                        )
                        return
                
                with tracer.start_span("request_metadata_extraction") as metadata_span:
                    # Request metadata extraction in parallel
                    metadata_task = asyncio.create_task(self.kafka_client.send_metadata_extraction_request(
                        document_id=document_id,
                        document_path=document.blob_path,
                        file_type=document.file_type
                    ))
                
                # Continue with text processing
                # Update document with extracted text
                document.text_content = text
                document = await self.document_repository.update_document(document)
                
                # Wait for metadata extraction request to complete
                try:
                    await metadata_task
                    logger.info("Metadata extraction requested",
                              document_id=document_id)
                except Exception as e:
                    logger.error("Failed to request metadata extraction",
                               document_id=document_id,
                               error=str(e))
                    # Continue processing even if metadata extraction request fails
                
                # Process successful
                document.update_processing_status("completed")
                await self.document_repository.update_document(document)
                
                # Send document processed event
                await self.kafka_client.send_document_processed_event(
                    document_id=document_id,
                    status="completed"
                )
                
                # Chunk the document
                await self._chunk_document(document_id, text)
                
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                logger.error("Error processing document",
                           document_id=document_id,
                           error=str(e))
                span.set_status(Status(StatusCode.ERROR), str(e))
                
                # Update document with error
                try:
                    document = await self.document_repository.get_document_by_id(document_id)
                    if document:
                        document.update_processing_status("failed", str(e))
                        await self.document_repository.update_document(document)
                except Exception as update_error:
                    logger.error("Error updating document with error",
                               document_id=document_id,
                               error=str(update_error))
                
                # Send document processed event with error
                await self.kafka_client.send_document_processed_event(
                    document_id=document_id,
                    status="failed",
                    error=str(e)
                )
            
    async def _chunk_document(self, document_id: str, text: str):
        """
        Chunk document text and save chunks
        
        Args:
            document_id: ID of the document
            text: Document text
        """
        try:
            # Get document
            document = await self.document_repository.get_document_by_id(document_id)
            if not document:
                logger.error(f"Document not found for chunking: {document_id}")
                return
                
            # Delete any existing chunks
            await self.document_repository.delete_chunks_by_document_id(document_id)
            
            # Chunk document with semantic boundaries
            try:
                chunks = self.chunking_service.chunk_with_semantic_boundaries(
                    text=text,
                    metadata={
                        "document_id": document_id,
                        "document_name": document.name,
                        "document_type": document.file_type
                    }
                )
            except Exception as e:
                logger.error(f"Error during document chunking: {e}")
                return
            
            if not chunks:
                logger.warning(f"No chunks created for document: {document_id}")
                return
                
            # Save chunks with retry logic
            failed_chunks = []
            for i, chunk in enumerate(chunks):
                try:
                    document_chunk = DocumentChunk(
                        document_id=document_id,
                        chunk_index=i,
                        text=chunk["text"],
                        metadata=chunk.get("metadata", {})
                    )
                    await self.document_repository.save_chunk(document_chunk)
                    logger.debug(f"Saved chunk {i} for document {document_id}")
                except Exception as e:
                    logger.error(f"Failed to save chunk {i} for document {document_id}: {e}")
                    failed_chunks.append(i)
            
            if failed_chunks:
                logger.warning(f"Failed to save {len(failed_chunks)} chunks for document {document_id}")
            else:
                logger.info(f"Successfully processed and saved {len(chunks)} chunks for document {document_id}")
                
            # Update document status
            await self.document_repository.update_document_status(
                document_id=document_id,
                is_chunked=True,
                chunk_count=len(chunks) - len(failed_chunks)
            )
            
        except Exception as e:
            logger.error(f"Error in chunking document {document_id}: {e}")
            # Update document status to indicate failure
            await self.document_repository.update_document_status(
                document_id=document_id,
                is_chunked=False,
                processing_error=str(e)
            )
            
    async def get_document(self, document_id: str) -> DocumentDTO:
        """
        Get document metadata
        
        Args:
            document_id: ID of the document
            
        Returns:
            Document DTO
        """
        try:
            document = await self.document_repository.get_document_by_id(document_id)
            if not document:
                raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
                
            return self._document_to_dto(document)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting document {document_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error retrieving document: {str(e)}")
            
    async def list_documents(
        self,
        skip: int = 0,
        limit: int = 100,
        query_filter: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[DocumentDTO], int]:
        """
        List documents with pagination and filtering
        
        Args:
            skip: Number of documents to skip
            limit: Maximum number of documents to return
            query_filter: Filter criteria
            
        Returns:
            Tuple of (list of document DTOs, total count)
        """
        try:
            documents, total = await self.document_repository.list_documents(
                skip=skip,
                limit=limit,
                query_filter=query_filter
            )
            
            return [self._document_to_dto(doc) for doc in documents], total
            
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")
            
    async def delete_document(self, document_id: str) -> bool:
        """
        Delete document and all associated data
        
        Args:
            document_id: ID of the document to delete
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            # Get document
            document = await self.document_repository.get_document_by_id(document_id)
            if not document:
                raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
                
            # Delete file from blob storage if it exists
            if document.blob_path:
                await self.blob_store.delete_file(document.blob_path)
                
            # Delete all chunks
            await self.document_repository.delete_chunks_by_document_id(document_id)
            
            # Delete document
            result = await self.document_repository.delete_document(document_id)
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")
            
    async def download_document(self, document_id: str) -> Tuple[BinaryIO, str, str]:
        """
        Download document file
        
        Args:
            document_id: ID of the document
            
        Returns:
            Tuple of (file content, filename, content type)
        """
        try:
            # Get document
            document = await self.document_repository.get_document_by_id(document_id)
            if not document:
                raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
                
            # Get file from blob storage
            if not document.blob_path:
                raise HTTPException(status_code=404, detail=f"File not found for document: {document_id}")
                
            file_content, original_filename = await self.blob_store.get_file(document.blob_path)
            
            return file_content, document.name, document.content_type
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error downloading document {document_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error downloading document: {str(e)}")
            
    async def get_document_chunks(self, document_id: str) -> List[ChunkDTO]:
        """
        Get all chunks for a document
        
        Args:
            document_id: ID of the document
            
        Returns:
            List of chunk DTOs
        """
        try:
            # Verify document exists
            document = await self.document_repository.get_document_by_id(document_id)
            if not document:
                raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
                
            # Get chunks
            chunks = await self.document_repository.get_chunks_by_document_id(document_id)
            
            # Convert to DTOs
            return [
                ChunkDTO(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    metadata=chunk.metadata
                )
                for chunk in chunks
            ]
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting chunks for document {document_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error retrieving document chunks: {str(e)}")
            
    async def convert_to_pdf(self, file: UploadFile) -> Tuple[bytes, str]:
        """
        Convert a document to PDF
        
        Args:
            file: The uploaded file
            
        Returns:
            Tuple of (PDF content, PDF filename)
        """
        try:
            # Read file content
            file_content = await file.read()
            
            # Convert to PDF
            pdf_content, error = await self.document_processor.convert_to_pdf(
                file_content=file.file,
                file_name=file.filename
            )
            
            if error:
                raise HTTPException(status_code=400, detail=f"Error converting to PDF: {error}")
                
            # Generate PDF filename
            pdf_filename = os.path.splitext(file.filename)[0] + ".pdf"
            
            return pdf_content, pdf_filename
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error converting to PDF: {e}")
            raise HTTPException(status_code=500, detail=f"Error converting to PDF: {str(e)}")
    
    def _document_to_dto(self, document: Document) -> DocumentDTO:
        """
        Convert document entity to DTO
        
        Args:
            document: Document entity
            
        Returns:
            Document DTO
        """
        return DocumentDTO(
            id=document.id,
            name=document.name,
            file_type=document.file_type,
            file_size=document.file_size,
            content_type=document.content_type,
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat(),
            is_processed=document.is_processed,
            is_chunked=document.is_chunked,
            processing_status=document.processing_status,
            processing_error=document.processing_error,
            chunk_count=document.chunk_count,
            metadata=document.metadata
        )

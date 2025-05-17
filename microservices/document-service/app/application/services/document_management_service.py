\
import asyncio
import io
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, BinaryIO

from fastapi import HTTPException, UploadFile # Added UploadFile and HTTPException
from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode

# Corrected absolute imports from 'app'
from app.domain.entities.document import Document
from app.application.dtos.document_dto import DocumentDTO, ChunkDTO
from app.domain.repositories.document_repository import DocumentRepository
try:
    from app.domain.services.document_processing_service import DocumentProcessingService
except ImportError:
    from app.application.services.document_processing_service import DocumentProcessingService
from app.application.services.background_document_processor import BackgroundDocumentProcessor
from app.infrastructure.blob.blob_store import BlobStore
from app.infrastructure.messaging.kafka_client import KafkaClient


logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class DocumentManagementService:
    """Manages primary document operations like upload, retrieval, deletion."""
    def __init__(
        self,
        document_repository: DocumentRepository, 
        document_processor: DocumentProcessingService, 
        blob_store: BlobStore,          
        kafka_client: KafkaClient,        
        background_processor: BackgroundDocumentProcessor 
    ):
        self.document_repository = document_repository
        self.document_processor = document_processor 
        self.blob_store = blob_store
        self.kafka_client = kafka_client
        self.background_processor = background_processor
        logger.info("DocumentManagementService initialized")

    async def upload_document(
        self,
        file: UploadFile, 
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DocumentDTO: 
        """Uploads a new document, converts to PDF if necessary, and schedules background processing."""
        with tracer.start_as_current_span("upload_document_management") as span:
            span.set_attribute("file.name", file.filename)
            span.set_attribute("file.size", file.size if hasattr(file, 'size') else 0)
            span.set_attribute("user.id", user_id or "anonymous")
            
            try:
                is_pdf = os.path.splitext(file.filename)[1].lower() == ".pdf"
                span.set_attribute("file.is_pdf", is_pdf)
                
                with tracer.start_as_current_span("convert_to_pdf_management") as convert_span:
                    pdf_content, pdf_filename = await self._convert_to_pdf_internal(file)
                    convert_span.set_attribute("pdf.filename", pdf_filename)
                    convert_span.set_attribute("pdf.size", len(pdf_content))
                    convert_span.set_attribute("conversion_performed", not is_pdf)
                
                document = Document( 
                    name=pdf_filename, file_type="pdf", file_size=len(pdf_content),
                    content_type="application/pdf", created_by=user_id, metadata=metadata or {}
                )
                
                with tracer.start_as_current_span("save_document_to_repository_management") as save_span:
                    document = await self.document_repository.save_document(document)
                    save_span.set_attribute("document.id", document.id)
                
                pdf_file = io.BytesIO(pdf_content)
                with tracer.start_as_current_span("save_to_blob_storage_management") as blob_span:
                    blob_path = await self.blob_store.save_file(
                        file_content=pdf_file, file_name=pdf_filename, content_type="application/pdf"
                    )
                    blob_span.set_attribute("blob.path", blob_path)
                
                document.blob_path = blob_path
                document = await self.document_repository.update_document(document)
                
                with tracer.start_as_current_span("send_document_created_event_management") as event_span:
                    await self.kafka_client.send_document_created_event(
                        document_id=document.id,
                        metadata={
                            "name": document.name, "file_type": document.file_type,
                            "file_size": document.file_size, "content_type": document.content_type,
                            "converted": not is_pdf
                        }
                    )
                
                asyncio.create_task(self.background_processor.process_document_background(document.id))
                span.set_status(Status(StatusCode.OK))
                log_message = "PDF document uploaded successfully" if is_pdf else "Document converted to PDF and uploaded successfully"
                logger.info(f"{log_message} - document_id: {document.id}, file_name: {document.name}, file_size: {document.file_size}, " +
                            (f"original_name: {file.filename}" if not is_pdf else ""))
                
                return self._document_to_dto_internal(document) 
                
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR), str(e))
                logger.error(f"Error uploading document in management service - error: {str(e)}, file_name: {file.filename}")
                raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")

    async def _convert_to_pdf_internal(self, file: UploadFile) -> Tuple[bytes, str]: 
        """Converts an uploaded file to PDF if it's not already one."""
        try:
            file_extension = os.path.splitext(file.filename)[1].lower()
            if file_extension == ".pdf":
                logger.info(f"File '{file.filename}' is already a PDF. No conversion needed.")
                content = await file.read()
                await file.seek(0) # Reset cursor for potential re-reads by other parts of the system
                return content, file.filename
            
            logger.info(f"Converting file '{file.filename}' (type: {file_extension}) to PDF.")
            file_content = await file.read()
            await file.seek(0) # Reset cursor
            
            pdf_content, error = await self.document_processor.convert_to_pdf(
                file_content=file_content,
                file_name=file.filename
            )
            
            if error:
                logger.error(f"Error converting file '{file.filename}' to PDF: {error}")
                raise HTTPException(status_code=500, detail=f"Error converting file to PDF: {error}")
            
            pdf_filename = f"{os.path.splitext(file.filename)[0]}.pdf"
            logger.info(f"File '{file.filename}' converted to '{pdf_filename}' successfully.")
            return pdf_content, pdf_filename
            
        except HTTPException: # Re-raise HTTP exceptions directly
            raise
        except Exception as e:
            logger.error(f"Unexpected error during PDF conversion for '{file.filename}': {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Unexpected error converting file to PDF: {str(e)}")

    async def get_document_metadata(self, document_id: str) -> DocumentDTO: 
        """Retrieves document metadata by ID."""
        try:
            document = await self.document_repository.get_document_by_id(document_id)
            if not document:
                logger.warning(f"Document metadata not found for ID: {document_id}")
                raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
            return self._document_to_dto_internal(document) 
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting document metadata for {document_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error retrieving document metadata: {str(e)}")
            
    async def list_documents_metadata(
        self,
        skip: int = 0,
        limit: int = 100,
        query_filter: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[DocumentDTO], int]: 
        """Lists document metadata with pagination and filtering."""
        try:
            documents, total = await self.document_repository.list_documents(
                skip=skip, limit=limit, query_filter=query_filter
            )
            return [self._document_to_dto_internal(doc) for doc in documents], total 
        except Exception as e:
            logger.error(f"Error listing documents metadata: {e}")
            raise HTTPException(status_code=500, detail=f"Error listing documents metadata: {str(e)}")
            
    async def delete_document_and_data(self, document_id: str) -> bool:
        """Deletes a document, its blob, and all associated chunks."""
        try:
            document = await self.document_repository.get_document_by_id(document_id)
            if not document:
                logger.warning(f"Document not found for deletion: {document_id}")
                raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
                
            if document.blob_path:
                await self.blob_store.delete_file(document.blob_path)
                logger.info(f"Blob deleted for document {document_id} at path: {document.blob_path}")
            
            await self.document_repository.delete_chunks_by_document_id(document_id)
            logger.info(f"Chunks deleted for document {document_id}")
            
            result = await self.document_repository.delete_document(document_id)
            if result:
                logger.info(f"Document record deleted successfully: {document_id}")
            else:
                logger.warning(f"Document record deletion reported as unsuccessful for: {document_id}")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting document and data for {document_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")
            
    async def download_document_file(self, document_id: str) -> Tuple[BinaryIO, str, str]:
        """Downloads the actual file content of a document."""
        try:
            document = await self.document_repository.get_document_by_id(document_id)
            if not document:
                logger.warning(f"Document not found for download: {document_id}")
                raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
                
            if not document.blob_path:
                logger.error(f"Blob path not found for document {document_id}, cannot download.")
                raise HTTPException(status_code=404, detail=f"File not found for document: {document_id}")
                
            file_content_stream, _ = await self.blob_store.get_file(document.blob_path)
            logger.info(f"File retrieved from blob storage for document {document_id}")
            return file_content_stream, document.name, document.content_type
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error downloading document file for {document_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error downloading document file: {str(e)}")
            
    async def get_document_chunks_data(self, document_id: str) -> List[ChunkDTO]: 
        """Retrieves all chunks associated with a document."""
        try:
            document = await self.document_repository.get_document_by_id(document_id)
            if not document:
                logger.warning(f"Document not found when trying to get chunks: {document_id}")
                raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
                
            chunks = await self.document_repository.get_chunks_by_document_id(document_id)
            logger.info(f"Retrieved {len(chunks)} chunks for document {document_id}")
            
            return [
                ChunkDTO( 
                    id=chunk.id, document_id=chunk.document_id, chunk_index=chunk.chunk_index,
                    text=chunk.text, metadata=chunk.metadata
                )
                for chunk in chunks # Corrected this line
            ]
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting chunks data for document {document_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error retrieving document chunks data: {str(e)}")

    def _document_to_dto_internal(self, document: Document) -> DocumentDTO: 
        """Converts a document domain model to its DTO representation."""
        return DocumentDTO( 
            id=document.id,
            name=document.name,
            file_type=document.file_type,
            file_size=document.file_size,
            content_type=document.content_type,
            created_at=document.created_at.isoformat(), # Assumes datetime object
            updated_at=document.updated_at.isoformat(), # Assumes datetime object
            is_processed=document.is_processed,
            is_chunked=document.is_chunked,
            processing_status=document.processing_status,
            processing_error=document.processing_error,
            chunk_count=document.chunk_count,
            metadata=document.metadata
        )

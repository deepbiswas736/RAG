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
from typing import List, Dict, Optional, Any, BinaryIO, Tuple, Union
from dataclasses import dataclass
from fastapi import UploadFile, HTTPException

from domain.entities.document import Document, DocumentChunk
from domain.repositories.document_repository import DocumentRepository
from domain.services.document_processing_service import DocumentProcessingService
from domain.services.chunking_service import ChunkingService
from infrastructure.blob.blob_store import BlobStore
from infrastructure.messaging.kafka_client import KafkaClient

# Configure logging
logger = logging.getLogger(__name__)

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
            
            # Save document to repository
            document = await self.document_repository.save_document(document)
            
            # Save file to blob storage
            blob_path = await self.blob_store.save_file(
                file_content=file.file,
                file_name=file.filename,
                content_type=document.content_type
            )
            
            # Update document with blob path
            document.blob_path = blob_path
            document = await self.document_repository.update_document(document)
            
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
            
            # Convert to DTO
            return self._document_to_dto(document)
            
        except Exception as e:
            logger.error(f"Error uploading document: {e}")
            raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")
            
    async def _process_document(self, document_id: str):
        """
        Process document asynchronously
        
        Args:
            document_id: ID of document to process
        """
        try:
            # Get document
            document = await self.document_repository.get_document_by_id(document_id)
            if not document:
                logger.error(f"Document not found for processing: {document_id}")
                return
                
            # Update processing status
            document.update_processing_status("processing")
            await self.document_repository.update_document(document)
            
            # Get file from blob storage
            file_content, _ = await self.blob_store.get_file(document.blob_path)
            
            # Extract text from document
            text, error = await self.document_processor.extract_text(
                file_content=file_content.getvalue(),
                file_extension=f".{document.file_type}"
            )
            
            if error:
                logger.error(f"Error extracting text from document {document_id}: {error}")
                document.update_processing_status("failed", error)
                await self.document_repository.update_document(document)
                await self.kafka_client.send_document_processed_event(
                    document_id=document_id,
                    status="failed",
                    metadata={"error": error}
                )
                return
                
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
                logger.info(f"Metadata extraction requested for document {document_id}")
            except Exception as e:
                logger.error(f"Failed to request metadata extraction for document {document_id}: {e}")
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
            
        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}")
            
            # Update document with error
            try:
                document = await self.document_repository.get_document_by_id(document_id)
                if document:
                    document.update_processing_status("failed", str(e))
                    await self.document_repository.update_document(document)
            except Exception as update_error:
                logger.error(f"Error updating document with error: {update_error}")
                
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
            chunks = self.chunking_service.chunk_with_semantic_boundaries(
                text=text,
                metadata={
                    "document_id": document_id,
                    "document_name": document.name,
                    "document_type": document.file_type
                }
            )
            
            # Save chunks
            for i, chunk in enumerate(chunks):
                document_chunk = DocumentChunk(
                    document_id=document_id,
                    chunk_index=i,
                    text=chunk["text"],
                    metadata=chunk["metadata"]
                )
                
                # Save chunk
                document_chunk = await self.document_repository.save_chunk(document_chunk)
                
                # Request embedding for the chunk
                await self.kafka_client.send_embedding_request(
                    document_id=document_id,
                    chunk_id=document_chunk.id,
                    text=document_chunk.text
                )
                
            # Update document with chunk information
            document.update_chunking_status(True, len(chunks))
            await self.document_repository.update_document(document)
            
            # Send document chunks created event
            await self.kafka_client.send_document_chunks_created_event(
                document_id=document_id,
                chunk_count=len(chunks)
            )
            
            logger.info(f"Document {document_id} chunked into {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Error chunking document {document_id}: {e}")
            
            # Update document status
            try:
                document = await self.document_repository.get_document_by_id(document_id)
                if document:
                    document.update_chunking_status(False)
                    await self.document_repository.update_document(document)
            except Exception as update_error:
                logger.error(f"Error updating document chunking status: {update_error}")
            
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

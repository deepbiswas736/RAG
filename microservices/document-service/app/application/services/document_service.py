"""
Document Service
--------------
Application service for document operations, connecting domain logic with infrastructure.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple, BinaryIO

from fastapi import HTTPException, UploadFile
from opentelemetry import trace

# Import the DTOs to make them available to importers of this module
from app.domain.entities.document import Document
from app.application.dtos.document_dto import DocumentDTO, ChunkDTO

# Export the DTO classes for backward compatibility
__all__ = ["DocumentService", "DocumentDTO", "ChunkDTO"]

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class DocumentService:
    """Orchestrates document-related operations by delegating to specialized services."""
    
    def __init__(
        self,
        document_management_service: Any, # Actual type: DocumentManagementService
        # Other specialized services can be injected here if needed in the future
        # For example, a service specifically for advanced search or analytics if those grow complex.
    ):
        """
        Initialize the main DocumentService with specialized service handlers.
        
        Args:
            document_management_service: Service for core document CRUD and lifecycle.
        """
        self.document_management_service = document_management_service
        # Note: The original dependencies like document_repository, document_processor (for text extraction),
        # blob_store, chunking_service, kafka_client are now primarily managed by 
        # DocumentManagementService and BackgroundDocumentProcessor.
        # This DocumentService acts as a facade or a higher-level orchestrator.
        
        logger.info("Main DocumentService (orchestrator) initialized")
        
    async def upload_document(
        self,
        file: Any, # Actual type: UploadFile
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Any: # Actual type: DocumentDTO
        """Delegates document upload to the DocumentManagementService."""
        # TODO: Ensure 'UploadFile' and 'DocumentDTO' types are correctly imported/defined if this service
        # is directly exposed to FastAPI routes or similar that use these types.
        return await self.document_management_service.upload_document(file, user_id, metadata)
                
    async def get_document_metadata(self, document_id: str) -> Any: # Actual type: DocumentDTO
        """Delegates fetching document metadata to the DocumentManagementService."""
        return await self.document_management_service.get_document_metadata(document_id)
            
    async def list_documents_metadata(
        self,
        skip: int = 0,
        limit: int = 100,
        query_filter: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Any], int]: # Actual type: List[DocumentDTO]
        """Delegates listing document metadata to the DocumentManagementService."""
        return await self.document_management_service.list_documents_metadata(skip, limit, query_filter)
            
    async def delete_document_and_data(self, document_id: str) -> bool:
        """Delegates document deletion to the DocumentManagementService."""
        return await self.document_management_service.delete_document_and_data(document_id)
            
    async def download_document_file(self, document_id: str) -> Tuple[BinaryIO, str, str]:
        """Delegates document file download to the DocumentManagementService."""
        return await self.document_management_service.download_document_file(document_id)
            
    async def get_document_chunks_data(self, document_id: str) -> List[Any]: # Actual type: List[ChunkDTO]
        """Delegates fetching document chunks to the DocumentManagementService."""
        return await self.document_management_service.get_document_chunks_data(document_id)

    # Note: _process_document, _chunk_document, convert_to_pdf, and _document_to_dto
    # have been moved to BackgroundDocumentProcessor or DocumentManagementService (as internal methods).
    # The main DocumentService no longer directly implements these low-level details.
    # If there are other high-level orchestration tasks that don't fit into DocumentManagementService
    # or BackgroundDocumentProcessor, they could reside here.

"""
Document Repository Interface
---------------------------
Defines the interface for document storage and retrieval operations.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Tuple

from domain.entities.document import Document, DocumentChunk


class DocumentRepository(ABC):
    """Abstract base class for document repository implementations"""
    
    @abstractmethod
    async def save_document(self, document: Document) -> Document:
        """Save a document to the repository"""
        pass
    
    @abstractmethod
    async def get_document_by_id(self, document_id: str) -> Optional[Document]:
        """Retrieve a document by its ID"""
        pass
    
    @abstractmethod
    async def delete_document(self, document_id: str) -> bool:
        """Delete a document from the repository"""
        pass
    
    @abstractmethod
    async def update_document(self, document: Document) -> Document:
        """Update an existing document"""
        pass
    
    @abstractmethod
    async def list_documents(self, skip: int = 0, limit: int = 100, 
                         query_filter: Optional[Dict[str, Any]] = None) -> Tuple[List[Document], int]:
        """
        List documents with pagination and filtering
        Returns tuple of (documents, total_count)
        """
        pass
    
    @abstractmethod
    async def save_chunk(self, chunk: DocumentChunk) -> DocumentChunk:
        """Save a document chunk"""
        pass
    
    @abstractmethod
    async def get_chunks_by_document_id(self, document_id: str) -> List[DocumentChunk]:
        """Get all chunks for a document"""
        pass
    
    @abstractmethod
    async def delete_chunks_by_document_id(self, document_id: str) -> bool:
        """Delete all chunks for a document"""
        pass
    
    @abstractmethod
    async def search_chunks_by_embedding(self, embedding: List[float], limit: int = 5) -> List[DocumentChunk]:
        """Search for chunks by embedding similarity"""
        pass

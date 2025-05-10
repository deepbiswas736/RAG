from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from ..entities.document import Document, Chunk
from ..value_objects.embedding import Embedding
from ..value_objects.metadata import DocumentMetadata

class DocumentRepository(ABC):
    @abstractmethod
    async def save(self, document: Document) -> str:
        """Save a document and return its ID"""
        pass

    @abstractmethod
    async def find_by_id(self, document_id: str) -> Optional[Document]:
        """Find a document by its ID"""
        pass
        
    @abstractmethod
    async def find_by_checksum(self, checksum: str) -> Optional[Document]:
        """Find a document by its content checksum"""
        pass

    @abstractmethod
    async def save_chunks(self, chunks: List[Chunk]) -> List[str]:
        """Save document chunks and return their IDs"""
        pass

    @abstractmethod
    async def search_similar(self, embedding: Embedding, limit: int = 5, metadata_filters: Optional[Dict] = None) -> List[Chunk]:
        """
        Find chunks similar to the given embedding with optional metadata filtering.
        
        Args:
            embedding: The query embedding to compare against
            limit: Maximum number of results to return
            metadata_filters: Dictionary of metadata key-value pairs to filter chunks
                            (e.g., {"person_name": "John Doe"})
        
        Returns:
            List of chunks matching the query
        """
        pass
        
    @abstractmethod
    async def filter_then_search(self, 
                                embedding: Embedding, 
                                metadata_filters: Dict,
                                limit: int = 5,
                                pre_filter_limit: int = 100) -> List[Chunk]:
        """
        Two-step retrieval: First filter by metadata, then find semantically similar chunks.
        
        Args:
            embedding: The query embedding to compare against
            metadata_filters: Dictionary of metadata key-value pairs for filtering
                            (e.g., {"person_name": "John Doe", "topics": ["Machine Learning"]})
            limit: Maximum number of final results to return
            pre_filter_limit: Maximum number of chunks to retrieve in the initial metadata filtering
            
        Returns:
            List of chunks matching both metadata filters and semantic similarity
        """
        pass

    @abstractmethod
    async def find_chunks_by_document_id(self, document_id: str) -> List[Chunk]:
        """Find all chunks belonging to a document"""
        pass
        
    @abstractmethod
    async def update_metadata(self, document_id: str, metadata: DocumentMetadata) -> bool:
        """
        Update metadata for a document.
        
        Args:
            document_id: Document ID to update
            metadata: New metadata to set
            
        Returns:
            True if update succeeded, False otherwise
        """
        pass

    @abstractmethod
    async def semantic_metadata_search(self, 
                                query: str, 
                                embedding: Embedding,
                                limit: int = 100) -> List[str]:
        """
        Perform semantic search on metadata fields to find relevant document IDs.
        
        Args:
            query: The search query text
            embedding: The query embedding for semantic comparison
            limit: Maximum number of document IDs to return
            
        Returns:
            List of document_ids that have semantically similar metadata
        """
        pass
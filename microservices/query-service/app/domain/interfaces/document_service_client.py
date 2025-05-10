"""
Document Service Client Interface
-------------------------------
Interface for communicating with the Document Service microservice
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class DocumentServiceClient(ABC):
    """Client interface for Document Service"""
    
    @abstractmethod
    async def search_documents(self, 
                             query_text: str,
                             limit: int = 5,
                             filters: Optional[Dict[str, Any]] = None,
                             similarity_threshold: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Search for documents using vector similarity
        
        Args:
            query_text: The query text to search for
            limit: Maximum number of documents to return
            filters: Optional filters to apply to the search
            similarity_threshold: Optional minimum similarity threshold
            
        Returns:
            List of matching document chunks with metadata and content
        """
        pass
    
    @abstractmethod
    async def search_documents_with_embeddings(self, 
                                            query_text: str,
                                            query_embedding: List[float],
                                            limit: int = 5,
                                            filters: Optional[Dict[str, Any]] = None,
                                            similarity_threshold: Optional[float] = None,
                                            include_metadata_search: bool = True) -> List[Dict[str, Any]]:
        """
        Advanced search for documents using both text and embedding vectors
        
        Args:
            query_text: The query text to search for
            query_embedding: The embedding vector of the query
            limit: Maximum number of documents to return
            filters: Optional filters to apply to the search
            similarity_threshold: Optional minimum similarity threshold
            include_metadata_search: Whether to search in document metadata embeddings
            
        Returns:
            List of matching document chunks with metadata and content
        """
        pass
    
    @abstractmethod
    async def vector_search_with_ranking(self,
                                       query_text: str,
                                       query_embedding: List[float],
                                       limit: int = 10,
                                       filters: Optional[Dict[str, Any]] = None,
                                       similarity_threshold: float = 0.65,
                                       ranking_method: str = "hybrid") -> List[Dict[str, Any]]:
        """
        Search for documents using client-side vector ranking
        
        Args:
            query_text: The query text to search for
            query_embedding: The embedding vector of the query
            limit: Maximum number of documents to return
            filters: Optional filters to apply to the search
            similarity_threshold: Minimum similarity threshold 
            ranking_method: Ranking method (hybrid, vector_only, keyword_boost)
            
        Returns:
            List of matching document chunks with metadata and content, ranked by relevance
        """
        pass
    
    @abstractmethod
    async def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a document by ID
        
        Args:
            document_id: ID of the document to retrieve
            
        Returns:
            Document information if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def get_document_chunks(self, 
                                document_id: str,
                                limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get chunks for a specific document
        
        Args:
            document_id: ID of the document to retrieve chunks for
            limit: Optional maximum number of chunks to return
            
        Returns:
            List of document chunks with metadata and content
        """
        pass
    
    @abstractmethod
    async def check_health(self) -> Dict[str, Any]:
        """
        Check the health of the Document Service
        
        Returns:
            Health status information
        """
        pass

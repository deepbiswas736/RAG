"""
HTTP Document Service Client
-------------------------
Implementation of the Document Service client using HTTP
"""

import os
import logging
import httpx
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from domain.interfaces.document_service_client import DocumentServiceClient

logger = logging.getLogger(__name__)


class HttpDocumentServiceClient(DocumentServiceClient):
    """HTTP client for the Document Service"""
    
    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize the Document Service client
        
        Args:
            base_url: Optional base URL for the Document Service (default: environment variable)
        """
        self.base_url = base_url or os.environ.get("DOCUMENT_SERVICE_URL", "http://document-service:8000")
        self.timeout = float(os.environ.get("DOCUMENT_SERVICE_TIMEOUT", "30.0"))
        logger.info(f"Initialized Document Service client with URL: {self.base_url}")
    
    async def search_documents(self, 
                             query_text: str,
                             limit: int = 5,
                             filters: Optional[Dict[str, Any]] = None,
                             similarity_threshold: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Search for documents using vector similarity
        """
        payload = {
            "query": query_text,
            "limit": limit
        }
        
        if filters is not None:
            payload["filters"] = filters
            
        if similarity_threshold is not None:
            payload["similarity_threshold"] = similarity_threshold
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/documents/search",
                    json=payload,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    error_message = f"Document Service error: {response.status_code} - {response.text}"
                    logger.error(error_message)
                    raise Exception(error_message)
        except Exception as e:
            logger.error(f"Error communicating with Document Service: {str(e)}")
            raise
            
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
        payload = {
            "query": query_text,
            "embedding": query_embedding,
            "limit": limit
        }
        
        if filters is not None:
            payload["filters"] = filters
            
        if similarity_threshold is not None:
            payload["similarity_threshold"] = similarity_threshold
            
        payload["include_metadata"] = include_metadata_search
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/documents/search/hybrid",
                    json=payload,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    error_message = f"Document Service error: {response.status_code} - {response.text}"
                    logger.error(error_message)
                    raise Exception(error_message)
        except Exception as e:
            logger.error(f"Error in hybrid search with Document Service: {str(e)}")
            # Fallback to standard search
            return await self.search_documents(query_text, limit, filters, similarity_threshold)
    
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
        # Get more candidates than requested for better ranking
        search_limit = min(limit * 3, 30)  # Get 3x candidates but cap at 30
        
        # 1. Get candidate documents from Document Service
        try:
            # Try advanced search with embeddings first
            try:
                candidates = await self.search_documents_with_embeddings(
                    query_text=query_text,
                    query_embedding=query_embedding,
                    limit=search_limit,
                    filters=filters,
                    similarity_threshold=similarity_threshold,
                    include_metadata_search=True
                )
                logger.info(f"Using search_documents_with_embeddings for query: {query_text}")
            except Exception as e:
                logger.warning(f"Error in search_documents_with_embeddings, falling back to standard search: {str(e)}")
                # Fallback to standard vector search from Document Service
                candidates = await self.search_documents(
                    query_text=query_text,
                    limit=search_limit,
                    filters=filters,
                    similarity_threshold=similarity_threshold
                )
            
            if not candidates:
                logger.info(f"No candidates found for query: {query_text}")
                return []
                
            logger.info(f"Found {len(candidates)} candidate documents for ranking")
            
            # 2. Apply client-side re-ranking
            ranked_results = await self._rank_documents(
                candidates=candidates,
                query_text=query_text,
                query_embedding=query_embedding,
                ranking_method=ranking_method
            )
            
            # 3. Return only the requested number of documents
            return ranked_results[:limit]
            
        except Exception as e:
            logger.error(f"Error in vector search with client-side ranking: {str(e)}")
            # Fallback to standard search
            return await self.search_documents(
                query_text=query_text, 
                limit=limit,
                filters=filters, 
                similarity_threshold=similarity_threshold
            )
    
    async def _rank_documents(self, 
                           candidates: List[Dict[str, Any]], 
                           query_text: str, 
                           query_embedding: List[float],
                           ranking_method: str = "hybrid") -> List[Dict[str, Any]]:
        """
        Rank document candidates based on selected method
        
        Args:
            candidates: List of candidate documents
            query_text: The original query text
            query_embedding: The query embedding vector
            ranking_method: Ranking method to use
            
        Returns:
            Reranked list of document chunks
        """
        if ranking_method == "vector_only":
            # Just sort by vector similarity if that's all we want
            return sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)
        
        # For hybrid or keyword_boost methods, we need to compute additional scores
        for doc in candidates:
            # Start with vector similarity score from server
            base_score = doc.get("score", 0)
            
            # Get metadata matching score if available
            metadata_score = doc.get("metadata_score", 0)
            
            # Apply keyword matching boost as a secondary signal
            content = doc.get("content", "").lower()
            query_terms = query_text.lower().split()
            
            # Calculate keyword overlap
            keyword_matches = sum(1 for term in query_terms if term in content)
            keyword_score = keyword_matches / len(query_terms) if query_terms else 0
            
            # Optional: calculate position score (terms closer to start get higher score)
            position_score = 0
            if keyword_matches > 0:
                first_pos = min((content.find(term) for term in query_terms if term in content), default=len(content))
                position_score = 1.0 - (first_pos / min(len(content), 1000))  # Normalize to first 1000 chars
            
            # Calculate final score based on method
            if ranking_method == "hybrid":
                # Balanced approach: 60% vector similarity, 15% keyword matches, 10% position, 15% metadata
                final_score = (base_score * 0.6) + (keyword_score * 0.15) + (position_score * 0.10) + (metadata_score * 0.15)
            elif ranking_method == "keyword_boost":
                # Vector similarity with stronger keyword influence
                final_score = (base_score * 0.4) + (keyword_score * 0.3) + (position_score * 0.1) + (metadata_score * 0.2)
            elif ranking_method == "metadata_focus":
                # Focus more on metadata matching for topic-driven queries
                final_score = (base_score * 0.4) + (keyword_score * 0.15) + (position_score * 0.05) + (metadata_score * 0.4)
            else:
                # Default to vector similarity
                final_score = base_score
                
            # Store all scores for debugging and transparency
            doc["original_score"] = base_score
            doc["score"] = final_score
            doc["score_components"] = {
                "vector_similarity": base_score,
                "keyword_match": keyword_score,
                "position_score": position_score,
                "metadata_score": metadata_score
            }
            
        # Sort by final score (descending)
        return sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)
    
    async def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a document by ID
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/documents/{document_id}",
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    return None
                else:
                    error_message = f"Document Service error: {response.status_code} - {response.text}"
                    logger.error(error_message)
                    raise Exception(error_message)
        except Exception as e:
            logger.error(f"Error communicating with Document Service: {str(e)}")
            raise
    
    async def get_document_chunks(self, 
                                document_id: str,
                                limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get chunks for a specific document
        """
        params = {}
        if limit is not None:
            params["limit"] = limit
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/documents/{document_id}/chunks",
                    params=params,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    return []
                else:
                    error_message = f"Document Service error: {response.status_code} - {response.text}"
                    logger.error(error_message)
                    raise Exception(error_message)
        except Exception as e:
            logger.error(f"Error communicating with Document Service: {str(e)}")
            raise
    
    async def check_health(self) -> Dict[str, Any]:
        """
        Check the health of the Document Service
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    timeout=5.0  # Short timeout for health checks
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"status": "unhealthy", "message": f"Status code: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error checking Document Service health: {str(e)}")
            return {"status": "unhealthy", "message": str(e)}

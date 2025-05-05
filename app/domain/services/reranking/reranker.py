from abc import ABC, abstractmethod
from typing import List, Dict, Tuple

from ....domain.entities.document import Chunk


class ReRanker(ABC):
    """Abstract interface for re-ranking retrieved chunks for better precision"""
    
    @abstractmethod
    async def rerank(
        self, 
        query: str, 
        chunks: List[Chunk], 
        top_k: int = None
    ) -> List[Tuple[Chunk, float]]:
        """
        Re-ranks the chunks based on relevance to the query.
        
        Args:
            query: User query
            chunks: List of chunks to rerank
            top_k: Number of top chunks to return (None = return all reranked)
            
        Returns:
            List of tuples containing (chunk, score) sorted by relevance
        """
        pass
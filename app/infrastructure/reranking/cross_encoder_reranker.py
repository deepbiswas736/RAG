import os
import logging
from typing import List, Tuple, Dict
import numpy as np

from ...domain.services.reranking.reranker import ReRanker
from ...domain.entities.document import Chunk

logger = logging.getLogger(__name__)

class CrossEncoderReRanker(ReRanker):
    """
    Implements reranking using a cross-encoder model for high precision
    relevance scoring between query and document chunks.
    """
    
    def __init__(self, model_name: str = None):
        """
        Initialize the cross-encoder reranker.
        
        Args:
            model_name: Name of the cross-encoder model to use
        """
        self.model_name = model_name or os.getenv(
            "CROSS_ENCODER_MODEL", 
            "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        logger.info(f"Initializing CrossEncoderReRanker with model: {self.model_name}")
        
        try:
            # Lazy import to avoid startup dependencies if not used
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(self.model_name)
            logger.info("Successfully loaded cross-encoder model")
        except Exception as e:
            logger.error(f"Error loading cross-encoder model: {e}")
            # Keep reference to error to check in rerank method
            self.initialization_error = e
            self.model = None

    async def rerank(
        self, 
        query: str, 
        chunks: List[Chunk], 
        top_k: int = None
    ) -> List[Tuple[Chunk, float]]:
        """
        Re-ranks chunks based on cross-encoder relevance scoring.
        
        Args:
            query: User query
            chunks: List of chunks to rerank
            top_k: Number of top chunks to return
            
        Returns:
            List of (chunk, score) tuples sorted by relevance score
        """
        if not chunks:
            logger.warning("No chunks provided for reranking")
            return []
            
        if self.model is None:
            logger.error("Cross-encoder model not initialized, skipping reranking")
            # Return original chunks with zero scores as fallback
            return [(chunk, 0.0) for chunk in chunks]
            
        try:
            # Prepare pairs of (query, chunk_content) for scoring
            pairs = [(query, chunk.content) for chunk in chunks]
            
            # Get relevance scores from cross-encoder
            scores = self.model.predict(pairs)
            
            # Combine chunks with their scores and sort by decreasing score
            chunk_scores = list(zip(chunks, scores))
            chunk_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Return top_k results if specified
            if top_k is not None and top_k < len(chunk_scores):
                return chunk_scores[:top_k]
                
            return chunk_scores
            
        except Exception as e:
            logger.error(f"Error during reranking: {e}")
            # Return original chunks with zero scores as fallback
            return [(chunk, 0.0) for chunk in chunks]
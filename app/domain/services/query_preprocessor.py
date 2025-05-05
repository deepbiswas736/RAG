import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class QueryPreprocessor:
    """
    Preprocesses queries to improve retrieval quality by:
    - Extracting key entities and concepts
    - Removing noise words
    - Expanding queries with related terms
    - Applying query rewriting techniques
    """
    
    def __init__(self):
        # Common stop words to filter out when necessary
        self.stop_words = {
            'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 
            'what', 'which', 'this', 'that', 'these', 'those', 'then',
            'just', 'so', 'than', 'such', 'both', 'through', 'about', 
            'for', 'is', 'of', 'while', 'during', 'to'
        }
        
    async def preprocess(self, query: str) -> Dict[str, Any]:
        """
        Preprocesses the query to improve retrieval quality.
        
        Args:
            query: Raw user query
            
        Returns:
            Dict containing processed query and metadata:
            - processed_query: The main query to use for retrieval
            - keywords: Extracted keywords
            - entities: Extracted entities (if any)
            - original_query: Original raw query
        """
        if not query or not query.strip():
            return {"processed_query": "", "keywords": [], "original_query": ""}
        
        # Clean and normalize query
        cleaned_query = self._clean_query(query)
        
        # Extract keywords from the query
        keywords = self._extract_keywords(cleaned_query)
        
        # For now, use the cleaned query as the processed query
        # In a more advanced implementation, you could implement query expansion,
        # entity extraction, or other NLP techniques here
        
        return {
            "processed_query": cleaned_query,
            "keywords": keywords,
            "original_query": query
        }
    
    def _clean_query(self, query: str) -> str:
        """Cleans and normalizes the query text"""
        # Convert to lowercase
        query = query.lower()
        
        # Remove special characters but keep spaces and meaningful punctuation
        query = re.sub(r'[^\w\s\?\.]', ' ', query)
        
        # Normalize whitespace
        query = re.sub(r'\s+', ' ', query).strip()
        
        return query
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extracts important keywords from the query"""
        # Simple keyword extraction (remove stop words)
        words = query.split()
        keywords = [word for word in words if word not in self.stop_words]
        
        return keywords
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class QueryEnhancer(ABC):
    """
    Interface defining the contract for enhancing queries to improve retrieval quality.
    Query enhancers can transform or expand queries to better match relevant documents.
    """
    
    @abstractmethod
    async def enhance(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Enhance a query to improve retrieval performance.
        
        Args:
            query: Original user query
            **kwargs: Additional parameters for enhancement
            
        Returns:
            Dictionary containing enhanced query information:
            - enhanced_query: The enhanced query string
            - original_query: Original query for reference
            - technique: Name of enhancement technique used
            - expansion_terms: Any expansion terms added (optional)
            - metadata: Additional enhancement metadata (optional)
        """
        pass
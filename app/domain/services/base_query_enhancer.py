import logging
from typing import Dict, Any, List, Optional
from .query_enhancer import QueryEnhancer

logger = logging.getLogger(__name__)


class BaseQueryEnhancer(QueryEnhancer):
    """
    Base implementation of the QueryEnhancer interface with common functionality.
    Concrete enhancers should extend this class.
    """
    
    def __init__(self, name: str = "base"):
        """
        Initialize the base query enhancer.
        
        Args:
            name: Name of the enhancer technique
        """
        self.name = name
        
    async def enhance(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Base implementation that returns the query unchanged.
        Override this in concrete implementations.
        
        Args:
            query: Original user query
            **kwargs: Additional parameters for enhancement
            
        Returns:
            Dictionary containing enhanced query information
        """
        if not query or not query.strip():
            return {
                "enhanced_query": "",
                "original_query": query,
                "technique": self.name,
                "metadata": {}
            }
        
        try:
            # This is where concrete implementations will add their enhancement logic
            enhanced_query = await self._process_query(query, **kwargs)
            
            result = {
                "enhanced_query": enhanced_query,
                "original_query": query,
                "technique": self.name,
                "metadata": {}
            }
            
            # Optional metadata that concrete implementations might add
            if hasattr(self, 'last_expansion_terms'):
                result["expansion_terms"] = self.last_expansion_terms
                
            return result
            
        except Exception as e:
            logger.error(f"Error in query enhancement ({self.name}): {e}")
            # On error, return original query
            return {
                "enhanced_query": query,
                "original_query": query,
                "technique": f"{self.name} (failed)",
                "error": str(e),
                "metadata": {"error_occurred": True}
            }
    
    async def _process_query(self, query: str, **kwargs) -> str:
        """
        Process the query to enhance it. Override this method in concrete enhancers.
        
        Args:
            query: Original user query
            **kwargs: Additional parameters for enhancement
            
        Returns:
            Enhanced query string
        """
        # Base implementation returns the query unchanged
        return query
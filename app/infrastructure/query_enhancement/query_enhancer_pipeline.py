import logging
from typing import List, Dict, Any

from ...domain.services.query_enhancer import QueryEnhancer

logger = logging.getLogger(__name__)

class QueryEnhancerPipeline(QueryEnhancer):
    """
    Composable pipeline that chains multiple query enhancers.
    This allows combining different enhancement techniques in sequence.
    """
    
    def __init__(self, enhancers: List[QueryEnhancer] = None):
        """
        Initialize the pipeline with a list of enhancers.
        
        Args:
            enhancers: List of QueryEnhancer instances to apply in sequence
        """
        self.enhancers = enhancers or []
        
    async def enhance(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Enhance a query by applying each enhancer in sequence.
        
        Args:
            query: Original user query
            **kwargs: Additional parameters for enhancement
            
        Returns:
            Dictionary containing enhanced query information
        """
        if not self.enhancers:
            return {
                "enhanced_query": query,
                "original_query": query,
                "technique": "empty-pipeline",
                "metadata": {}
            }
            
        current_query = query
        enhancement_results = []
        
        # Apply each enhancer in sequence
        for enhancer in self.enhancers:
            try:
                result = await enhancer.enhance(current_query, **kwargs)
                enhancement_results.append(result)
                
                # Use the enhanced query for the next enhancer
                if "enhanced_query" in result:
                    current_query = result["enhanced_query"]
                    
            except Exception as e:
                logger.error(f"Error in enhancer {enhancer.__class__.__name__}: {e}")
                # Continue with the current query if an enhancer fails
        
        # Combine metadata from all enhancers
        combined_metadata = {}
        for result in enhancement_results:
            if "metadata" in result and isinstance(result["metadata"], dict):
                combined_metadata.update(result["metadata"])
                
        # Collect all expansion terms
        expansion_terms = []
        for result in enhancement_results:
            if "expansion_terms" in result:
                expansion_terms.extend(result["expansion_terms"])
                
        # Create the final result
        final_result = {
            "enhanced_query": current_query,
            "original_query": query,
            "technique": "pipeline",
            "metadata": combined_metadata,
            "enhancement_steps": [
                {
                    "technique": result.get("technique", "unknown"),
                    "query": result.get("enhanced_query", "")
                }
                for result in enhancement_results
            ]
        }
        
        if expansion_terms:
            final_result["expansion_terms"] = expansion_terms
            
        return final_result
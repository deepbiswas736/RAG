"""
Vector Search Testing Script
-------------------------
Script to test the vector search with client-side ranking
"""

import asyncio
import os
import sys
import json
import logging
from typing import List, Dict, Any, Optional

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.infrastructure.adapters.http_document_service_client import HttpDocumentServiceClient
from app.infrastructure.adapters.http_llm_service_client import HttpLLMServiceClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set up environment variables if needed (for local testing)
os.environ.setdefault("DOCUMENT_SERVICE_URL", "http://localhost:8000")
os.environ.setdefault("LLM_SERVICE_URL", "http://localhost:8001")
os.environ.setdefault("DOCUMENT_SERVICE_TIMEOUT", "30.0")
os.environ.setdefault("LLM_SERVICE_TIMEOUT", "30.0")

async def test_vector_search_with_ranking():
    """Test the vector search with client-side ranking"""
    document_client = HttpDocumentServiceClient()
    llm_client = HttpLLMServiceClient()
    
    # Test query
    query_text = "How does vector search improve RAG applications?"
    
    # Check if services are available
    try:
        doc_health = await document_client.check_health()
        llm_health = await llm_client.check_health()
        
        logger.info(f"Document Service health: {doc_health}")
        logger.info(f"LLM Service health: {llm_health}")
        
        if doc_health.get("status") != "healthy" or llm_health.get("status") != "healthy":
            logger.error("One or more services are unhealthy. Aborting test.")
            return
    except Exception as e:
        logger.error(f"Error checking service health: {e}")
        return
    
    try:
        # Generate embedding for the query
        logger.info(f"Generating embedding for query: {query_text}")
        embedding_response = await llm_client.generate_embeddings(query_text)
        query_embedding = embedding_response.get("embedding", [])
        
        if not query_embedding:
            logger.error("Failed to generate query embedding")
            return
            
        # Test with different ranking methods
        ranking_methods = ["hybrid", "vector_only", "keyword_boost"]
        
        for method in ranking_methods:
            logger.info(f"Testing vector search with ranking method: {method}")
            
            results = await document_client.vector_search_with_ranking(
                query_text=query_text,
                query_embedding=query_embedding,
                limit=5,
                ranking_method=method
            )
            
            logger.info(f"Received {len(results)} results using {method} ranking")
            
            # Display the top results with scores
            for i, result in enumerate(results[:3]):  # Show top 3
                logger.info(f"Result {i+1} - Score: {result.get('score')}")
                logger.info(f"Content preview: {result.get('content', '')[:100]}...")
                
                # Show score components if available
                if "score_components" in result:
                    components = result["score_components"]
                    logger.info(f"Score components: {json.dumps(components, indent=2)}")
                
                logger.info("-" * 40)
    
    except Exception as e:
        logger.error(f"Error in vector search test: {e}")

if __name__ == "__main__":
    asyncio.run(test_vector_search_with_ranking())

"""
Vector Search Validation Script
------------------------------
This script tests the vector search capabilities of the Query Service
with different query types to verify ranking method selection and accuracy.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, Any, List

# Add the RAG directory to the path
# __file__ is RAG/testing/vector_search_validation.py
# os.path.dirname(__file__) is RAG/testing/
# os.path.join(os.path.dirname(__file__), "..") is RAG/
rag_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if rag_dir not in sys.path:
    sys.path.insert(0, rag_dir)

# Import the necessary modules
from microservices.query_service.app.infrastructure.adapters.http_document_service_client import HttpDocumentServiceClient
from microservices.query_service.app.infrastructure.adapters.http_llm_service_client import HttpLLMServiceClient
from microservices.query_service.app.application.services.query_processor import QueryProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("vector_search_validation")

# Define test query sets by category
TEST_QUERIES = {
    "hybrid": [
        "Machine learning applications",
        "Neural networks in image processing", 
        "GPT-4 capabilities",
        "Compare CNN and RNN architectures"
    ],
    "keyword_boost": [
        "What is machine learning?",
        "Define reinforcement learning",
        "Explain how transformers work",
        "Steps to implement a neural network"
    ],
    "metadata_focus": [
        "Find articles about machine learning",
        "Show documents written by John Smith",
        "What's the summary of reinforcement learning paper?",
        "List papers related to the topic of natural language processing"
    ]
}

# Test environment configuration
DOCUMENT_SERVICE_URL = os.environ.get("DOCUMENT_SERVICE_URL", "http://localhost:8000")
LLM_SERVICE_URL = os.environ.get("LLM_SERVICE_URL", "http://localhost:8001")
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "vector_search_results.json")


async def test_vector_search():
    """Test vector search with different query types"""
    logger.info("Initializing clients...")
    
    # Create Document and LLM service clients
    document_client = HttpDocumentServiceClient(DOCUMENT_SERVICE_URL)
    llm_client = HttpLLMServiceClient(LLM_SERVICE_URL)
    
    # Create query processor without repository (not needed for this test)
    query_processor = QueryProcessor(
        llm_service_client=llm_client,
        document_service_client=document_client,
        query_repository=None
    )
    
    # Create results structure
    results = {"query_results": []}
    
    # Process each query type
    for query_type, queries in TEST_QUERIES.items():
        logger.info(f"Testing {query_type} queries...")
        
        for query_text in queries:
            logger.info(f"Processing query: {query_text}")
            
            # Determine ranking method
            ranking_method = query_processor._determine_ranking_method(query_text)
            logger.info(f"Selected ranking method: {ranking_method}")
            
            # Generate query embedding
            embed_response = await llm_client.generate_embeddings(query_text)
            query_embedding = embed_response.get("embedding", [])
            
            # Search for documents
            docs = await document_client.vector_search_with_ranking(
                query_text=query_text,
                query_embedding=query_embedding,
                limit=5,
                ranking_method=ranking_method
            )
            
            # Store results
            query_result = {
                "query_text": query_text,
                "expected_type": query_type,
                "detected_type": ranking_method,
                "match": query_type == ranking_method,
                "document_count": len(docs),
                "top_document": docs[0] if docs else None,
                "score_components": docs[0].get("score_components") if docs else None
            }
            
            results["query_results"].append(query_result)
            
            logger.info(f"Query type match: {query_result['match']}")
            
            # Display top result if available
            if docs:
                top_doc = docs[0]
                logger.info(f"Top document: {top_doc['id']}, score: {top_doc['score']}")
                if "score_components" in top_doc:
                    components = top_doc["score_components"]
                    logger.info(f"Score components: vector={components.get('vector_similarity', 0):.3f}, "
                           f"keyword={components.get('keyword_match', 0):.3f}, "
                           f"metadata={components.get('metadata_score', 0):.3f}")
    
    # Write results to file
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Results written to {OUTPUT_FILE}")
    
    # Summary statistics
    correct_matches = sum(1 for r in results["query_results"] if r["match"])
    total_queries = len(results["query_results"])
    
    logger.info(f"Query type detection accuracy: {correct_matches}/{total_queries} "
               f"({correct_matches/total_queries*100:.1f}%)")


async def validate_metadata_scoring():
    """Test metadata scoring functionality specifically"""
    logger.info("Testing metadata scoring functionality...")
    
    # Create Document and LLM service clients
    document_client = HttpDocumentServiceClient(DOCUMENT_SERVICE_URL)
    llm_client = HttpLLMServiceClient(LLM_SERVICE_URL)
    
    # Create query processor
    query_processor = QueryProcessor(
        llm_service_client=llm_client,
        document_service_client=document_client,
        query_repository=None
    )
    
    # Test query specifically looking for metadata matches
    query_text = "machine learning papers by John Smith about neural networks"
    
    # Generate query embedding
    embed_response = await llm_client.generate_embeddings(query_text)
    query_embedding = embed_response.get("embedding", [])
    
    # Search using metadata focus
    metadata_results = await document_client.vector_search_with_ranking(
        query_text=query_text,
        query_embedding=query_embedding,
        limit=5,
        ranking_method="metadata_focus"
    )
    
    # Search using hybrid for comparison
    hybrid_results = await document_client.vector_search_with_ranking(
        query_text=query_text,
        query_embedding=query_embedding,
        limit=5,
        ranking_method="hybrid"
    )
    
    # Compare results
    logger.info(f"Retrieved {len(metadata_results)} documents with metadata_focus ranking")
    logger.info(f"Retrieved {len(hybrid_results)} documents with hybrid ranking")
    
    # Check if ordering is different
    metadata_ids = [doc["id"] for doc in metadata_results]
    hybrid_ids = [doc["id"] for doc in hybrid_results]
    
    order_different = metadata_ids != hybrid_ids
    logger.info(f"Ranking methods produced different document ordering: {order_different}")
    
    # Check score component differences
    if metadata_results and hybrid_results:
        metadata_components = metadata_results[0].get("score_components", {})
        hybrid_components = hybrid_results[0].get("score_components", {})
        
        logger.info("Score component comparison (metadata_focus vs hybrid):")
        logger.info(f"Vector similarity: {metadata_components.get('vector_similarity', 0):.3f} vs "
                   f"{hybrid_components.get('vector_similarity', 0):.3f}")
        logger.info(f"Keyword match: {metadata_components.get('keyword_match', 0):.3f} vs "
                   f"{hybrid_components.get('keyword_match', 0):.3f}")
        logger.info(f"Metadata score: {metadata_components.get('metadata_score', 0):.3f} vs "
                   f"{hybrid_components.get('metadata_score', 0):.3f}")
    

async def main():
    """Main function to run the tests"""
    logger.info("Starting vector search validation...")
    
    # Run the vector search tests
    await test_vector_search()
    
    # Run the metadata scoring validation
    await validate_metadata_scoring()
    
    logger.info("Validation complete")


if __name__ == "__main__":
    asyncio.run(main())

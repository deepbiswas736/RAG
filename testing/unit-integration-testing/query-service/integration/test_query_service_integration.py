"""
Integration Tests for Query Service
---------------------------------
End-to-end tests for the Query Service with Document Service and LLM Service
"""

import pytest
import asyncio
import os
import httpx
import sys
from typing import Dict, Any, List

# Adjust path to import from app modules
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../microservices/query-service"))

# Set environment variables for test
os.environ['DOCUMENT_SERVICE_URL'] = 'http://localhost:8000'
os.environ['LLM_SERVICE_URL'] = 'http://localhost:8001'
os.environ['MONGODB_URL'] = 'mongodb://user:password@mongodb:27017'
os.environ['ENABLE_METADATA_SEARCH'] = 'True'


@pytest.mark.integration
@pytest.mark.skipif('INTEGRATION_TESTS' not in os.environ, reason="Integration tests disabled")
class TestQueryServiceIntegration:
    """Integration tests for the Query Service"""
    
    @classmethod
    def setup_class(cls):
        """Setup test class - verify services are available"""
        cls.document_service_url = os.environ.get('DOCUMENT_SERVICE_URL')
        cls.llm_service_url = os.environ.get('LLM_SERVICE_URL')
        cls.query_service_url = os.environ.get('QUERY_SERVICE_URL', 'http://localhost:8002')
        
        # Verify services are running
        async def check_services():
            try:
                async with httpx.AsyncClient() as client:
                    # Check Document Service
                    doc_response = await client.get(f"{cls.document_service_url}/health", timeout=5)
                    assert doc_response.status_code == 200
                    
                    # Check LLM Service
                    llm_response = await client.get(f"{cls.llm_service_url}/health", timeout=5)
                    assert llm_response.status_code == 200
                    
                    # Check Query Service
                    query_response = await client.get(f"{cls.query_service_url}/health", timeout=5)
                    assert query_response.status_code == 200
                    
                return True
            except Exception as e:
                pytest.skip(f"Services not available for integration testing: {str(e)}")
                return False
        
        # Run the service check
        loop = asyncio.get_event_loop()
        services_available = loop.run_until_complete(check_services())
        if not services_available:
            pytest.skip("Integration test environment not available")
    
    @pytest.mark.asyncio
    async def test_query_processing_flow(self):
        """Test the complete query processing flow"""
        # Create test query
        test_query = {
            "text": "Explain machine learning algorithms",
            "metadata": {
                "user_id": "test-user",
                "session_id": "test-session"
            }
        }
        
        # Submit query to service
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.query_service_url}/api/v1/queries",
                json=test_query,
                timeout=30  # Give it some time as this is an end-to-end flow
            )
            
            # Verify response
            assert response.status_code == 200, f"Failed with response: {response.text}"
            result = response.json()
            
            # Validate response structure
            assert "id" in result
            assert "text" in result
            assert "references" in result
            assert len(result["references"]) > 0
            
            # Verify query completion
            query_id = result["id"]
            status_response = await client.get(
                f"{self.query_service_url}/api/v1/queries/{query_id}"
            )
            
            assert status_response.status_code == 200
            status_data = status_response.json()
            assert status_data["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_vector_search_with_metadata(self):
        """Test vector search capabilities with metadata"""
        # Create a query that should benefit from metadata search
        test_query = {
            "text": "Find documents about machine learning written by John Smith",
            "metadata": {
                "search_type": "advanced",
                "ranking_method": "metadata_focus"
            }
        }
        
        # Submit query to service
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.query_service_url}/api/v1/queries/search",
                json=test_query,
                timeout=15
            )
            
            # Verify response
            assert response.status_code == 200
            result = response.json()
            
            # Validate search results
            assert "results" in result
            assert len(result["results"]) > 0
            
            # Check for score components
            if len(result["results"]) > 0:
                assert "score_components" in result["results"][0]
                assert "metadata_score" in result["results"][0]["score_components"]
    
    @pytest.mark.asyncio
    async def test_different_ranking_methods(self):
        """Test different ranking methods produce different results"""
        # Define the query
        query_text = "machine learning algorithms"
        
        # Test with different ranking methods
        ranking_methods = ["hybrid", "keyword_boost", "metadata_focus"]
        results = {}
        
        async with httpx.AsyncClient() as client:
            for method in ranking_methods:
                response = await client.post(
                    f"{self.query_service_url}/api/v1/queries/search",
                    json={
                        "text": query_text,
                        "metadata": {
                            "ranking_method": method
                        }
                    },
                    timeout=15
                )
                
                assert response.status_code == 200
                results[method] = response.json()["results"]
        
        # Verify that different methods give different rankings
        # This is a simple check that the order of results varies
        if len(results["hybrid"]) > 1 and len(results["metadata_focus"]) > 1:
            hybrid_ids = [doc["id"] for doc in results["hybrid"]]
            metadata_ids = [doc["id"] for doc in results["metadata_focus"]]
            
            # At least some variation should exist in ordering or scores
            assert (hybrid_ids != metadata_ids) or \
                   any(results["hybrid"][i]["score"] != results["metadata_focus"][i]["score"] 
                       for i in range(min(len(hybrid_ids), len(metadata_ids))))

"""
Tests for LLM Service API endpoints
"""

import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from app.main import app
from tests.conftest import configure_mock_text_generation, configure_mock_embedding_service


@pytest.fixture
def client():
    """TestClient fixture for FastAPI app testing"""
    with TestClient(app) as client:
        yield client


class TestLLMServiceAPI:
    """Test cases for LLM service API endpoints"""
    
    @patch("app.main.llm_service")
    def test_health_check(self, mock_llm_service, client):
        """Test health check endpoint"""
        mock_llm_service.text_generation_service.check_availability = AsyncMock(return_value=True)
        mock_llm_service.embedding_service.check_availability = AsyncMock(return_value=True)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "healthy"
        assert result["text_generation"] is True
        assert result["embedding"] is True
    
    @patch("app.main.llm_service")
    def test_health_check_service_down(self, mock_llm_service, client):
        """Test health check when services are down"""
        mock_llm_service.text_generation_service.check_availability = AsyncMock(return_value=False)
        mock_llm_service.embedding_service.check_availability = AsyncMock(return_value=False)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "degraded"
        assert result["text_generation"] is False
        assert result["embedding"] is False
    
    @patch("app.main.llm_service")
    def test_generate_text(self, mock_llm_service, client):
        """Test generate text endpoint"""
        # Configure mock
        mock_llm_service.generate_text = AsyncMock(
            return_value={
                "text": "This is a test response",
                "model": "test-model",
                "input": "Test prompt",
                "tokens": {
                    "prompt": 10,
                    "completion": 5,
                    "total": 15
                },
                "elapsed_time": 0.5
            }
        )
        
        # Make request
        response = client.post(
            "/llm/generate",
            json={"prompt": "Test prompt"}
        )
        
        # Check response
        assert response.status_code == 200
        result = response.json()
        assert result["text"] == "This is a test response"
        assert result["model"] == "test-model"
        assert result["input"] == "Test prompt"
        
        # Verify mock was called correctly
        mock_llm_service.generate_text.assert_called_once_with(
            "Test prompt", None, None, None, None, None
        )
    
    @patch("app.main.llm_service")
    def test_generate_text_with_context(self, mock_llm_service, client):
        """Test generate text with context"""
        # Configure mock
        mock_llm_service.generate_text = AsyncMock(
            return_value={
                "text": "Paris has a population of 2.1 million people.",
                "model": "test-model",
                "input": "What is the population of Paris?",
                "tokens": {
                    "prompt": 15,
                    "completion": 10,
                    "total": 25
                },
                "elapsed_time": 0.5
            }
        )
        
        # Make request with context
        response = client.post(
            "/llm/generate",
            json={
                "prompt": "What is the population of Paris?",
                "context": [
                    {"content": "Paris has 2.1 million people.", "source": "wiki/paris.txt"}
                ],
                "model": "llama2",
                "temperature": 0.7,
                "max_tokens": 100,
                "system_message": "You are a helpful assistant."
            }
        )
        
        # Check response
        assert response.status_code == 200
        result = response.json()
        assert "Paris" in result["text"]
        
        # Verify mock was called with all parameters
        mock_llm_service.generate_text.assert_called_once()
        call_args = mock_llm_service.generate_text.call_args[0]
        call_kwargs = mock_llm_service.generate_text.call_args[1]
        assert call_args[0] == "What is the population of Paris?"
        assert isinstance(call_args[1], list)  # Context
        assert call_kwargs.get("model") == "llama2"
        assert call_kwargs.get("temperature") == 0.7
        assert call_kwargs.get("max_tokens") == 100
        assert call_kwargs.get("system_message") == "You are a helpful assistant."
    
    @patch("app.main.llm_service")
    def test_create_embedding(self, mock_llm_service, client):
        """Test create embedding endpoint"""
        # Configure mock
        mock_llm_service.create_embedding = AsyncMock(
            return_value={
                "embedding": [0.1, 0.2, 0.3],
                "dimension": 3,
                "model": "test-embedding-model"
            }
        )
        
        # Make request
        response = client.post(
            "/llm/embeddings",
            json={"text": "Test text for embedding"}
        )
        
        # Check response
        assert response.status_code == 200
        result = response.json()
        assert "embedding" in result
        assert result["embedding"] == [0.1, 0.2, 0.3]
        assert result["dimension"] == 3
        assert result["model"] == "test-embedding-model"
        
        # Verify mock was called correctly
        mock_llm_service.create_embedding.assert_called_once_with(
            "Test text for embedding", None
        )
    
    @patch("app.main.llm_service")
    def test_create_batch_embeddings(self, mock_llm_service, client):
        """Test batch embeddings endpoint"""
        # Configure mock
        mock_llm_service.create_batch_embeddings = AsyncMock(
            return_value=[
                {
                    "embedding": [0.1, 0.2, 0.3],
                    "dimension": 3,
                    "model": "test-embedding-model"
                },
                {
                    "embedding": [0.4, 0.5, 0.6],
                    "dimension": 3,
                    "model": "test-embedding-model"
                }
            ]
        )
        
        # Make request
        response = client.post(
            "/llm/batch_embeddings",
            json={"texts": ["First text", "Second text"]}
        )
        
        # Check response
        assert response.status_code == 200
        result = response.json()
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["embedding"] == [0.1, 0.2, 0.3]
        assert result[1]["embedding"] == [0.4, 0.5, 0.6]
        
        # Verify mock was called correctly
        mock_llm_service.create_batch_embeddings.assert_called_once_with(
            ["First text", "Second text"], None
        )

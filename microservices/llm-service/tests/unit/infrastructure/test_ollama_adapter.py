"""
Tests for Ollama adapters in the infrastructure layer
"""

import pytest
import os
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from app.infrastructure.llm.ollama_adapter import OllamaTextGeneration, OllamaEmbedding
from app.domain.models.generation import GenerationResponse, StreamingChunk
from app.domain.models.embedding import Embedding
from app.infrastructure.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError


class TestOllamaTextGeneration:
    """Test cases for OllamaTextGeneration adapter"""
    
    @pytest.fixture
    def text_generation(self):
        """Create an instance of OllamaTextGeneration with mocked dependencies"""
        with patch('app.infrastructure.resilience.circuit_breaker.CircuitBreaker') as mock_circuit_breaker:
            service = OllamaTextGeneration()
            service.circuit_breaker = mock_circuit_breaker.return_value
            service.circuit_breaker.execute = AsyncMock()
            return service
    
    @pytest.fixture
    def httpx_client_mock(self):
        """Mock for httpx.AsyncClient"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "response": "This is a test response",
                "model": "llama2",
                "prompt_eval_count": 10,
                "eval_count": 5
            }
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            yield mock_client
    
    @patch('httpx.AsyncClient')
    async def test_check_availability_success(self, mock_client, text_generation):
        """Test successful availability check"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama2"}, {"name": "mistral"}]}
        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
        
        result = await text_generation.check_availability()
        
        assert result is True
        assert text_generation.fallback_mode is False
        mock_client.return_value.__aenter__.return_value.get.assert_called_once()
    
    @patch('httpx.AsyncClient')
    async def test_check_availability_failure(self, mock_client, text_generation):
        """Test failed availability check"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
        
        result = await text_generation.check_availability()
        
        assert result is False
        assert text_generation.fallback_mode is True
    
    @patch('httpx.AsyncClient')
    async def test_check_availability_exception(self, mock_client, text_generation):
        """Test exception during availability check"""
        mock_client.return_value.__aenter__.return_value.get.side_effect = Exception("Connection error")
        
        result = await text_generation.check_availability()
        
        assert result is False
        assert text_generation.fallback_mode is True
    
    async def test_generate_text_success(self, text_generation, httpx_client_mock):
        """Test successful text generation"""
        # Setup the mock to return a proper response via the circuit breaker
        mock_response = GenerationResponse(
            text="This is a test response",
            model="llama2",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            elapsed_time=0.5
        )
        text_generation.circuit_breaker.execute.return_value = mock_response
        
        # Call the method
        prompt = "Generate a test response"
        result = await text_generation.generate_text(prompt)
        
        # Verify the result
        assert result.text == "This is a test response"
        assert result.model == "llama2"
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 5
        assert result.total_tokens == 15
        
        # Verify the circuit breaker was used with the correct internal method
        text_generation.circuit_breaker.execute.assert_called_once()
        assert text_generation.circuit_breaker.execute.call_args[0][0].__name__ == "_generate_text_internal"
    
    async def test_generate_text_fallback_mode(self, text_generation):
        """Test text generation in fallback mode"""
        # Set the fallback mode
        text_generation.fallback_mode = True
        
        # Call the method
        prompt = "Generate a test response"
        result = await text_generation.generate_text(prompt)
        
        # Verify fallback response
        assert "unavailable" in result.text.lower()
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
    
    async def test_generate_text_circuit_breaker_open(self, text_generation):
        """Test text generation when circuit breaker is open"""
        # Setup the circuit breaker to raise an exception
        text_generation.circuit_breaker.execute.side_effect = CircuitBreakerOpenError("Circuit is open")
        
        # Call the method
        prompt = "Generate a test response"
        result = await text_generation.generate_text(prompt)
        
        # Verify fallback response is returned
        assert "unavailable" in result.text.lower()
    
    @patch('httpx.AsyncClient')
    async def test_generate_streaming_success(self, mock_client, text_generation):
        """Test successful streaming text generation"""
        # Setup streaming response mock
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_lines = [
            json.dumps({"response": "Hello", "done": False}),
            json.dumps({"response": " world", "done": False}),
            json.dumps({"response": "!", "done": True})
        ]
        
        # Create a mock streaming context
        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__.return_value = mock_response
        mock_client.return_value.stream.return_value = mock_stream_ctx
        
        # Setup aiter_lines to yield our mock lines
        async def mock_aiter_lines():
            for line in mock_lines:
                yield line
                
        mock_response.aiter_lines = mock_aiter_lines
        
        # Call the streaming method
        prompt = "Generate a streaming response"
        results = []
        async for chunk in text_generation.generate_streaming(prompt):
            results.append(chunk)
        
        # Verify the results
        assert len(results) == 3
        assert results[0].text == "Hello"
        assert results[0].is_final is False
        assert results[1].text == " world"
        assert results[1].is_final is False
        assert results[2].text == "!"
        assert results[2].is_final is True
    
    @patch('httpx.AsyncClient')
    async def test_generate_streaming_error(self, mock_client, text_generation):
        """Test streaming with error response"""
        # Setup streaming response mock with error
        mock_response = AsyncMock()
        mock_response.status_code = 500
        
        # Create a mock streaming context
        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__.return_value = mock_response
        mock_client.return_value.stream.return_value = mock_stream_ctx
        
        # Setup aiter_lines (won't be called due to error status)
        mock_response.aiter_lines = AsyncMock()
        
        # Call the streaming method
        prompt = "Generate a streaming response"
        results = []
        async for chunk in text_generation.generate_streaming(prompt):
            results.append(chunk)
        
        # Verify the error result
        assert len(results) == 1
        assert "Error:" in results[0].text
        assert results[0].is_final is True
    
    async def test_generate_streaming_fallback_mode(self, text_generation):
        """Test streaming text generation in fallback mode"""
        # Set the fallback mode
        text_generation.fallback_mode = True
        
        # Call the streaming method
        prompt = "Generate a streaming response"
        results = []
        async for chunk in text_generation.generate_streaming(prompt):
            results.append(chunk)
        
        # Verify the fallback result
        assert len(results) == 1
        assert "unavailable" in results[0].text.lower()
        assert results[0].is_final is True


class TestOllamaEmbedding:
    """Test cases for OllamaEmbedding adapter"""
    
    @pytest.fixture
    def embedding_service(self):
        """Create an instance of OllamaEmbedding with mocked dependencies"""
        with patch('app.infrastructure.resilience.circuit_breaker.CircuitBreaker') as mock_circuit_breaker:
            service = OllamaEmbedding()
            service.circuit_breaker = mock_circuit_breaker.return_value
            service.circuit_breaker.execute = AsyncMock()
            return service
    
    @pytest.fixture
    def httpx_client_mock(self):
        """Mock for httpx.AsyncClient"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "embedding": [0.1, 0.2, 0.3]
            }
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            yield mock_client
    
    @patch('httpx.AsyncClient')
    async def test_check_availability_success(self, mock_client, embedding_service):
        """Test successful availability check"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
        
        result = await embedding_service.check_availability()
        
        assert result is True
        assert embedding_service.fallback_mode is False
    
    @patch('httpx.AsyncClient')
    async def test_check_availability_failure(self, mock_client, embedding_service):
        """Test failed availability check"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
        
        result = await embedding_service.check_availability()
        
        assert result is False
        assert embedding_service.fallback_mode is True
    
    async def test_create_embedding_success(self, embedding_service, httpx_client_mock):
        """Test successful embedding creation"""
        # Setup the mock embedding
        mock_embedding = Embedding.create(
            vector=[0.1, 0.2, 0.3],
            model="nomic-embed-text"
        )
        embedding_service.circuit_breaker.execute.return_value = mock_embedding
        
        # Call the method
        text = "Test text for embedding"
        result = await embedding_service.create_embedding(text)
        
        # Verify the result
        assert result.vector == [0.1, 0.2, 0.3]
        assert result.model == "nomic-embed-text"
        assert result.dimension == 3
        
        # Verify the circuit breaker was used
        embedding_service.circuit_breaker.execute.assert_called_once()
    
    async def test_create_embedding_fallback_mode(self, embedding_service):
        """Test embedding creation in fallback mode"""
        # Set the fallback mode
        embedding_service.fallback_mode = True
        
        # Call the method and expect an exception
        with pytest.raises(Exception, match="Embedding service is not available"):
            await embedding_service.create_embedding("Test text")
    
    async def test_create_embedding_circuit_breaker_open(self, embedding_service):
        """Test embedding creation when circuit breaker is open"""
        # Setup the circuit breaker to raise an exception
        embedding_service.circuit_breaker.execute.side_effect = CircuitBreakerOpenError("Circuit is open")
        
        # Call the method and expect the exception to be propagated
        with pytest.raises(Exception):
            await embedding_service.create_embedding("Test text")
    
    async def test_create_batch_embeddings_success(self, embedding_service):
        """Test successful batch embedding creation"""
        # Setup mock for create_embedding
        mock_embeddings = [
            Embedding.create(vector=[0.1, 0.2, 0.3], model="nomic-embed-text"),
            Embedding.create(vector=[0.4, 0.5, 0.6], model="nomic-embed-text")
        ]
        
        # Patch the create_embedding method to return our mock embeddings
        with patch.object(embedding_service, 'create_embedding', AsyncMock()) as mock_create:
            mock_create.side_effect = mock_embeddings
            
            # Call the batch method
            texts = ["First text", "Second text"]
            results = await embedding_service.create_batch_embeddings(texts)
            
            # Verify the results
            assert len(results) == 2
            assert results[0].vector == [0.1, 0.2, 0.3]
            assert results[1].vector == [0.4, 0.5, 0.6]
            
            # Verify create_embedding was called for each text
            assert mock_create.call_count == 2
    
    async def test_create_batch_embeddings_partial_failure(self, embedding_service):
        """Test batch embedding creation with some failures"""
        # Setup mock to succeed for first text but fail for second
        async def mock_create_embedding_side_effect(text, model=None):
            if text == "First text":
                return Embedding.create(vector=[0.1, 0.2, 0.3], model="nomic-embed-text")
            else:
                raise Exception("Failed to create embedding")
        
        # Patch the create_embedding method
        with patch.object(embedding_service, 'create_embedding', AsyncMock()) as mock_create:
            mock_create.side_effect = mock_create_embedding_side_effect
            
            # Call the batch method
            texts = ["First text", "Second text"]
            results = await embedding_service.create_batch_embeddings(texts)
            
            # Verify the results
            assert len(results) == 2
            assert results[0].vector == [0.1, 0.2, 0.3]
            assert results[1] is None

"""
Tests for LLM Service application layer
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any
from app.application.services.llm_service import LLMService
from app.domain.models.embedding import Embedding
from app.domain.models.generation import GenerationResponse, StreamingChunk


class TestLLMService:
    """Test cases for LLM Service"""
    
    @pytest.fixture
    def text_generation_service(self):
        """Mock text generation service"""
        service = AsyncMock()
        service.generate_text = AsyncMock()
        service.generate_streaming = AsyncMock()
        return service
    
    @pytest.fixture
    def embedding_service(self):
        """Mock embedding service"""
        service = AsyncMock()
        service.create_embedding = AsyncMock()
        service.create_batch_embeddings = AsyncMock()
        return service
    
    @pytest.fixture
    def llm_service(self, text_generation_service, embedding_service):
        """LLM service instance with mock dependencies"""
        return LLMService(
            text_generation_service=text_generation_service,
            embedding_service=embedding_service
        )
    
    async def test_generate_text_without_context(self, llm_service, text_generation_service):
        """Test generating text without context"""
        # Arrange
        prompt = "What is the capital of France?"
        mock_response = GenerationResponse(
            text="The capital of France is Paris.",
            model="test-model",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            elapsed_time=0.5
        )
        text_generation_service.generate_text.return_value = mock_response
        
        # Act
        result = await llm_service.generate_text(prompt)
        
        # Assert
        text_generation_service.generate_text.assert_called_once_with(
            prompt=prompt,
            model=None,
            temperature=None,
            max_tokens=None,
            system_message=None
        )
        assert result["text"] == "The capital of France is Paris."
        assert result["model"] == "test-model"
        assert result["input"] == prompt
    
    async def test_generate_text_with_context(self, llm_service, text_generation_service):
        """Test generating text with context"""
        # Arrange
        prompt = "What is the population?"
        context = [
            {"content": "Paris has a population of 2.1 million.", "source": "wiki/paris.txt"}
        ]
        mock_response = GenerationResponse(
            text="Paris has a population of 2.1 million people.",
            model="test-model",
            prompt_tokens=20,
            completion_tokens=10,
            total_tokens=30,
            elapsed_time=0.7
        )
        text_generation_service.generate_text.return_value = mock_response
        
        # Act
        result = await llm_service.generate_text(prompt, context)
        
        # Assert
        assert "Paris" in result["text"]
        assert "2.1 million" in result["text"]
        # Verify prompt was formatted with context
        expected_context = "CONTENT: Paris has a population of 2.1 million.\nSOURCE: wiki/paris.txt"
        assert expected_context in text_generation_service.generate_text.call_args[1]["prompt"]
    
    async def test_generate_streaming(self, llm_service, text_generation_service):
        """Test generating streaming text"""
        # Arrange
        prompt = "Count from 1 to 3"
        
        # Mock a streaming response as an async generator
        async def mock_streaming():
            chunks = [
                StreamingChunk(text="1", model="test-model"),
                StreamingChunk(text="2", model="test-model"),
                StreamingChunk(text="3", model="test-model", is_final=True)
            ]
            for chunk in chunks:
                yield chunk
                
        text_generation_service.generate_streaming.return_value = mock_streaming()
        
        # Act
        results = []
        async for chunk in llm_service.generate_streaming(prompt):
            results.append(chunk)
        
        # Assert
        assert len(results) == 3
        assert results[0]["text"] == "1"
        assert results[1]["text"] == "2"
        assert results[2]["text"] == "3"
        assert results[2]["is_final"] is True
        
    async def test_create_embedding(self, llm_service, embedding_service):
        """Test creating an embedding"""
        # Arrange
        text = "Sample text for embedding"
        mock_embedding = Embedding.create(
            vector=[0.1, 0.2, 0.3],
            model="test-embedding-model"
        )
        embedding_service.create_embedding.return_value = mock_embedding
        
        # Act
        result = await llm_service.create_embedding(text)
        
        # Assert
        embedding_service.create_embedding.assert_called_once_with(text, None)
        assert result["embedding"] == [0.1, 0.2, 0.3]
        assert result["dimension"] == 3
        assert result["model"] == "test-embedding-model"
        
    async def test_create_batch_embeddings(self, llm_service, embedding_service):
        """Test creating batch embeddings"""
        # Arrange
        texts = ["First text", "Second text"]
        mock_embeddings = [
            Embedding.create(vector=[0.1, 0.2, 0.3], model="test-model"),
            Embedding.create(vector=[0.4, 0.5, 0.6], model="test-model")
        ]
        embedding_service.create_batch_embeddings.return_value = mock_embeddings
        
        # Act
        results = await llm_service.create_batch_embeddings(texts)
        
        # Assert
        embedding_service.create_batch_embeddings.assert_called_once_with(texts, None)
        assert len(results) == 2
        assert results[0]["embedding"] == [0.1, 0.2, 0.3]
        assert results[1]["embedding"] == [0.4, 0.5, 0.6]
    
    def test_format_context(self, llm_service):
        """Test formatting context items"""
        # Arrange
        context = [
            {"content": "Paris is the capital of France.", "source": "wiki/france.txt"},
            {"content": "Paris has many museums.", "source": "wiki/paris.txt"}
        ]
        
        # Act
        result = llm_service._format_context(context)
        
        # Assert
        expected = (
            "CONTENT: Paris is the capital of France.\n"
            "SOURCE: wiki/france.txt\n\n"
            "CONTENT: Paris has many museums.\n"
            "SOURCE: wiki/paris.txt"
        )
        assert result == expected
    
    def test_create_prompt_with_context(self, llm_service):
        """Test creating a prompt with context"""
        # Arrange
        query = "What museums are in Paris?"
        context = "CONTENT: Paris has the Louvre and Orsay museums.\nSOURCE: wiki/paris.txt"
        
        # Act
        result = llm_service._create_prompt_with_context(query, context)
        
        # Assert
        assert "CONTEXT:" in result
        assert context in result
        assert "QUESTION: What museums are in Paris?" in result
        assert "ANSWER:" in result

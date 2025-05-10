"""
Pytest configuration and shared fixtures for LLM service tests
"""

import pytest
import os
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

from app.domain.interfaces.llm_services import TextGenerationService, EmbeddingService
from app.domain.models.generation import GenerationResponse, StreamingChunk
from app.domain.models.embedding import Embedding


class MockTextGenerationService(TextGenerationService):
    """Mock implementation of TextGenerationService for testing"""
    
    def __init__(self):
        self.generate_text_mock = AsyncMock()
        self.generate_streaming_mock = AsyncMock()
        self.check_availability_mock = AsyncMock(return_value=True)
    
    async def check_availability(self) -> bool:
        return await self.check_availability_mock()
    
    async def generate_text(self, 
                          prompt: str, 
                          model: Optional[str] = None,
                          temperature: Optional[float] = None,
                          max_tokens: Optional[int] = None,
                          system_message: Optional[str] = None) -> GenerationResponse:
        return await self.generate_text_mock(prompt, model, temperature, max_tokens, system_message)
    
    async def generate_streaming(self, 
                               prompt: str,
                               model: Optional[str] = None,
                               temperature: Optional[float] = None,
                               max_tokens: Optional[int] = None,
                               system_message: Optional[str] = None) -> AsyncGenerator[StreamingChunk, None]:
        return await self.generate_streaming_mock(prompt, model, temperature, max_tokens, system_message)


class MockEmbeddingService(EmbeddingService):
    """Mock implementation of EmbeddingService for testing"""
    
    def __init__(self):
        self.create_embedding_mock = AsyncMock()
        self.create_batch_embeddings_mock = AsyncMock()
        self.check_availability_mock = AsyncMock(return_value=True)
    
    async def check_availability(self) -> bool:
        return await self.check_availability_mock()
    
    async def create_embedding(self, text: str, model: Optional[str] = None) -> Embedding:
        return await self.create_embedding_mock(text, model)
    
    async def create_batch_embeddings(self, texts: List[str], model: Optional[str] = None) -> List[Embedding]:
        return await self.create_batch_embeddings_mock(texts, model)


@pytest.fixture
def mock_text_generation_service():
    """Fixture providing a mock text generation service"""
    return MockTextGenerationService()


@pytest.fixture
def mock_embedding_service():
    """Fixture providing a mock embedding service"""
    return MockEmbeddingService()


def configure_mock_text_generation(mock_service, response_text="Mock response"):
    """Configure a mock text generation service with default behaviors"""
    # Mock the generate_text method
    mock_service.generate_text_mock.reset_mock()
    mock_service.generate_text_mock.return_value = GenerationResponse(
        text=response_text,
        model="mock-model",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        elapsed_time=0.1
    )
    
    # Mock the generate_streaming method
    async def mock_streaming(*args, **kwargs):
        chunks = [
            StreamingChunk(text="Mock", model="mock-model"),
            StreamingChunk(text=" streaming", model="mock-model"),
            StreamingChunk(text=" response", model="mock-model", is_final=True)
        ]
        for chunk in chunks:
            yield chunk
    
    mock_service.generate_streaming_mock.reset_mock()
    mock_service.generate_streaming_mock.return_value = mock_streaming()
    
    return mock_service


def configure_mock_embedding_service(mock_service, vector=None):
    """Configure a mock embedding service with default behaviors"""
    if vector is None:
        vector = [0.1, 0.2, 0.3]
        
    # Mock the create_embedding method
    mock_service.create_embedding_mock.reset_mock()
    mock_service.create_embedding_mock.return_value = Embedding.create(
        vector=vector,
        model="mock-embedding-model"
    )
    
    # Mock the create_batch_embeddings method
    mock_service.create_batch_embeddings_mock.reset_mock()
    mock_service.create_batch_embeddings_mock.return_value = [
        Embedding.create(vector=vector, model="mock-embedding-model"),
        Embedding.create(vector=vector, model="mock-embedding-model")
    ]
    
    return mock_service

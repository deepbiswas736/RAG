"""
Integration tests for the LLM service with Ollama
"""

import pytest
import os
import asyncio
from app.infrastructure.llm.ollama_adapter import OllamaTextGeneration, OllamaEmbedding
from app.application.services.llm_service import LLMService
from app.domain.models.embedding import Embedding


# Skip these tests if OLLAMA_INTEGRATION_TESTS environment variable is not set to "true"
pytestmark = pytest.mark.skipif(
    os.environ.get("OLLAMA_INTEGRATION_TESTS", "false").lower() != "true",
    reason="Ollama integration tests are disabled. Set OLLAMA_INTEGRATION_TESTS=true to enable."
)


class TestOllamaIntegration:
    """Integration tests for Ollama service"""
    
    @pytest.fixture
    def ollama_base_url(self):
        """Get the Ollama base URL from environment or use default"""
        return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    
    @pytest.fixture
    def text_generation_service(self, ollama_base_url):
        """Create a real text generation service pointing to Ollama"""
        service = OllamaTextGeneration()
        service.base_url = ollama_base_url
        service.default_model = os.environ.get("OLLAMA_TEST_MODEL", "llama2")
        return service
    
    @pytest.fixture
    def embedding_service(self, ollama_base_url):
        """Create a real embedding service pointing to Ollama"""
        service = OllamaEmbedding()
        service.base_url = ollama_base_url
        service.default_model = os.environ.get("OLLAMA_EMBEDDING_TEST_MODEL", "nomic-embed-text")
        return service
    
    @pytest.fixture
    def llm_service(self, text_generation_service, embedding_service):
        """Create an LLM service with real dependencies"""
        return LLMService(
            text_generation_service=text_generation_service,
            embedding_service=embedding_service
        )
    
    @pytest.mark.asyncio
    async def test_check_availability(self, text_generation_service, embedding_service):
        """Test if Ollama service is available"""
        text_gen_available = await text_generation_service.check_availability()
        embedding_available = await embedding_service.check_availability()
        
        assert text_gen_available, "Ollama text generation service should be available"
        assert embedding_available, "Ollama embedding service should be available"
    
    @pytest.mark.asyncio
    async def test_generate_text(self, text_generation_service):
        """Test generating text with real Ollama service"""
        # Skip test if service is not available
        if not await text_generation_service.check_availability():
            pytest.skip("Ollama service is not available")
        
        prompt = "What is the capital of France?"
        response = await text_generation_service.generate_text(
            prompt=prompt,
            max_tokens=100  # Limit response size for faster tests
        )
        
        assert response.text, "Response should contain text"
        assert response.model == text_generation_service.default_model
        assert response.prompt_tokens > 0, "Prompt tokens should be greater than 0"
        assert response.completion_tokens > 0, "Completion tokens should be greater than 0"
        assert "Paris" in response.text, "Response should mention Paris as the capital of France"
    
    @pytest.mark.asyncio
    async def test_generate_streaming(self, text_generation_service):
        """Test streaming text generation with real Ollama service"""
        # Skip test if service is not available
        if not await text_generation_service.check_availability():
            pytest.skip("Ollama service is not available")
        
        prompt = "Count from 1 to 5"
        chunks = []
        
        async for chunk in text_generation_service.generate_streaming(
            prompt=prompt,
            max_tokens=50  # Limit response size for faster tests
        ):
            chunks.append(chunk)
            # Break early if we get more than 10 chunks to avoid long tests
            if len(chunks) >= 10:
                break
        
        assert chunks, "Should receive at least one chunk"
        assert any(chunk.text for chunk in chunks), "At least one chunk should contain text"
        
        # Check if we got a final chunk
        final_chunks = [chunk for chunk in chunks if chunk.is_final]
        if final_chunks:
            assert len(final_chunks) == 1, "Should have exactly one final chunk"
    
    @pytest.mark.asyncio
    async def test_create_embedding(self, embedding_service):
        """Test creating an embedding with real Ollama service"""
        # Skip test if service is not available
        if not await embedding_service.check_availability():
            pytest.skip("Ollama embedding service is not available")
        
        text = "This is a test text for embedding"
        embedding = await embedding_service.create_embedding(text)
        
        assert isinstance(embedding, Embedding), "Should return an Embedding instance"
        assert embedding.vector, "Embedding should have a vector"
        assert embedding.dimension > 0, "Embedding dimension should be greater than 0"
        assert embedding.model == embedding_service.default_model
    
    @pytest.mark.asyncio
    async def test_create_batch_embeddings(self, embedding_service):
        """Test creating batch embeddings with real Ollama service"""
        # Skip test if service is not available
        if not await embedding_service.check_availability():
            pytest.skip("Ollama embedding service is not available")
        
        texts = ["First test text", "Second test text", "Third test text"]
        embeddings = await embedding_service.create_batch_embeddings(texts)
        
        assert len(embeddings) == len(texts), "Should return as many embeddings as texts"
        assert all(isinstance(emb, Embedding) for emb in embeddings), "All results should be Embedding instances"
        assert all(emb.dimension == embeddings[0].dimension for emb in embeddings), "All embeddings should have the same dimension"
    
    @pytest.mark.asyncio
    async def test_llm_service_with_context(self, llm_service):
        """Test the full LLM service with context"""
        # Skip test if dependencies are not available
        if not await llm_service.text_generation_service.check_availability() or \
           not await llm_service.embedding_service.check_availability():
            pytest.skip("Ollama services are not available")
        
        prompt = "What is the population?"
        context = [
            {"content": "Paris has a population of 2.1 million people.", "source": "wiki/paris.txt"}
        ]
        
        response = await llm_service.generate_text(prompt, context)
        
        assert response["text"], "Response should contain text"
        assert "2.1 million" in response["text"], "Response should include information from the context"

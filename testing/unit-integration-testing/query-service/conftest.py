"""
Pytest configuration for Query Service tests
------------------------------------------
Shared fixtures and configuration for testing the Query Service
"""

import pytest
import asyncio
import sys
import os
from unittest.mock import AsyncMock
import numpy as np

# Adjust path to import from app modules
sys.path.append(os.path.join(os.path.dirname(__file__), "../../microservices/query-service"))

from app.infrastructure.adapters.http_document_service_client import HttpDocumentServiceClient
from app.infrastructure.adapters.http_llm_service_client import HttpLLMServiceClient
from app.application.services.query_processor import QueryProcessor


# Define event loop for pytest-asyncio
@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def document_service_client():
    """Create a mock document service client"""
    client = AsyncMock(spec=HttpDocumentServiceClient)
    
    # Add default mock responses for commonly used methods
    sample_docs = [
        {
            "id": "doc1",
            "content": "Introduction to machine learning concepts and algorithms",
            "metadata": {"title": "ML Intro", "author": "John Smith"},
            "score": 0.95,
            "metadata_score": 0.92
        },
        {
            "id": "doc2",
            "content": "Advanced deep learning techniques for natural language processing",
            "metadata": {"title": "Advanced NLP", "author": "Jane Doe"},
            "score": 0.92,
            "metadata_score": 0.85
        },
        {
            "id": "doc3",
            "content": "Reinforcement learning in robotics applications",
            "metadata": {"title": "RL in Robotics", "author": "Bob Johnson"},
            "score": 0.88,
            "metadata_score": 0.75
        }
    ]
    
    client.search_documents.return_value = sample_docs
    client.search_documents_with_embeddings.return_value = sample_docs
    client.vector_search_with_ranking.return_value = sample_docs
    
    return client


@pytest.fixture
def llm_service_client():
    """Create a mock LLM service client"""
    client = AsyncMock(spec=HttpLLMServiceClient)
    
    # Create sample embedding response
    async def mock_generate_embeddings(text, model=None):
        # Generate a deterministic pseudo-random embedding based on the text
        np.random.seed(hash(text) % 2**32)
        return {
            "embedding": np.random.rand(1536).tolist(),
            "model": "test-embedding-model",
            "text": text
        }
    
    client.generate_embeddings = mock_generate_embeddings
    
    # Create sample metadata embedding response
    async def mock_generate_metadata_embeddings(metadata, fields=None, model=None):
        # Generate metadata text
        if fields:
            metadata_text = " ".join(str(metadata.get(field, "")) for field in fields)
        else:
            metadata_text = " ".join(str(value) for value in metadata.values())
        
        # Generate a deterministic pseudo-random embedding based on the metadata text
        np.random.seed(hash(metadata_text) % 2**32)
        return {
            "embedding": np.random.rand(1536).tolist(),
            "model": "test-embedding-model",
            "text": metadata_text,
            "metadata_fields": fields or list(metadata.keys())
        }
    
    client.generate_metadata_embeddings = mock_generate_metadata_embeddings
    
    # Mock LLM response
    async def mock_generate_text(prompt, context=None, model=None, temperature=None, 
                              max_tokens=None, system_message=None):
        return {
            "text": f"Response to: {prompt}",
            "model": "test-llm-model",
            "tokens": {
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": 20,
                "total_tokens": len(prompt.split()) + 20
            }
        }
    
    client.generate_text = mock_generate_text
    
    return client


@pytest.fixture
def query_repository():
    """Create a mock query repository"""
    repo = AsyncMock()
    return repo


@pytest.fixture
def query_processor(document_service_client, llm_service_client, query_repository):
    """Create a QueryProcessor with mock dependencies"""
    processor = QueryProcessor(
        llm_service_client=llm_service_client,
        document_service_client=document_service_client,
        query_repository=query_repository
    )
    return processor


# Environment setup for integration tests
def pytest_configure(config):
    """Configure pytest environment variables"""
    # These are set only if not already defined
    os.environ.setdefault('DOCUMENT_SERVICE_URL', 'http://localhost:8000')
    os.environ.setdefault('LLM_SERVICE_URL', 'http://localhost:8001')
    os.environ.setdefault('QUERY_SERVICE_URL', 'http://localhost:8002')
    os.environ.setdefault('MONGODB_URL', 'mongodb://user:password@mongodb:27017')
    os.environ.setdefault('ENABLE_METADATA_SEARCH', 'True')

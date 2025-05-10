"""
Test Vector Search Functionality
-------------------------------
Test the vector search capabilities with client-side ranking
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np
from typing import List, Dict, Any
import sys
import os

# Adjust path to import from app modules
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../microservices/query-service"))

from app.infrastructure.adapters.http_document_service_client import HttpDocumentServiceClient
from app.infrastructure.adapters.http_llm_service_client import HttpLLMServiceClient
from app.application.services.query_processor import QueryProcessor


@pytest.fixture
def document_service_client():
    """Create a mock document service client"""
    client = AsyncMock(spec=HttpDocumentServiceClient)
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


@pytest.mark.asyncio
async def test_vector_search_with_ranking(document_service_client):
    """Test vector search with client-side ranking"""
    # Create sample documents
    sample_docs = [
        {
            "id": "doc1",
            "content": "Introduction to machine learning concepts and algorithms",
            "metadata": {"title": "ML Intro", "author": "John Smith"},
            "score": 0.95
        },
        {
            "id": "doc2",
            "content": "Advanced deep learning techniques for natural language processing",
            "metadata": {"title": "Advanced NLP", "author": "Jane Doe"},
            "score": 0.92
        },
        {
            "id": "doc3",
            "content": "Reinforcement learning in robotics applications",
            "metadata": {"title": "RL in Robotics", "author": "Bob Johnson"},
            "score": 0.88
        }
    ]
    
    document_service_client.vector_search_with_ranking.return_value = sample_docs
    
    # Initialize client
    client = HttpDocumentServiceClient("http://test-document-service:8000")
    client.search_documents = document_service_client.search_documents
    client.vector_search_with_ranking = document_service_client.vector_search_with_ranking
    
    # Test with hybrid ranking method
    query = "machine learning algorithms"
    query_embedding = [0.1] * 1536  # Dummy embedding
    results = await client.vector_search_with_ranking(
        query_text=query,
        query_embedding=query_embedding,
        ranking_method="hybrid"
    )
    
    # Verify the results
    assert len(results) == 3
    assert results[0]["id"] == "doc1"
    document_service_client.vector_search_with_ranking.assert_called_once()


@pytest.mark.asyncio
async def test_search_documents_with_embeddings(document_service_client):
    """Test search with document and metadata embeddings"""
    # Create sample documents with metadata scores
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
    
    document_service_client.search_documents_with_embeddings.return_value = sample_docs
    
    # Initialize client
    client = HttpDocumentServiceClient("http://test-document-service:8000")
    client.search_documents_with_embeddings = document_service_client.search_documents_with_embeddings
    
    # Test search with embeddings
    query = "machine learning by John Smith"
    query_embedding = [0.1] * 1536  # Dummy embedding
    results = await client.search_documents_with_embeddings(
        query_text=query,
        query_embedding=query_embedding,
        include_metadata_search=True
    )
    
    # Verify the results
    assert len(results) == 3
    assert results[0]["id"] == "doc1"
    assert "metadata_score" in results[0]
    document_service_client.search_documents_with_embeddings.assert_called_once()


@pytest.mark.asyncio
async def test_determine_ranking_method(query_processor):
    """Test dynamic ranking method selection"""
    # Test metadata-focused queries
    metadata_queries = [
        "Find articles about machine learning",
        "Show documents written by John Smith",
        "What's the summary of reinforcement learning paper?",
        "List papers related to the topic of natural language processing"
    ]
    
    for query in metadata_queries:
        method = query_processor._determine_ranking_method(query)
        assert method == "metadata_focus", f"Query '{query}' should use metadata_focus method"
    
    # Test keyword-focused queries
    keyword_queries = [
        "What is machine learning?",
        "Define reinforcement learning",
        "Explain how transformers work",
        "Steps to implement a neural network"
    ]
    
    for query in keyword_queries:
        method = query_processor._determine_ranking_method(query)
        assert method == "keyword_boost", f"Query '{query}' should use keyword_boost method"
    
    # Test general/hybrid queries
    hybrid_queries = [
        "Machine learning applications",
        "Neural networks in image processing",
        "GPT-4 capabilities",
        "Compare CNN and RNN architectures"
    ]
    
    for query in hybrid_queries:
        method = query_processor._determine_ranking_method(query)
        assert method == "hybrid", f"Query '{query}' should use hybrid method"


@pytest.mark.asyncio
async def test_calculate_metadata_score(query_processor):
    """Test metadata scoring function"""
    # Define test metadata
    metadata = {
        "title": "Introduction to Machine Learning",
        "author": "John Smith",
        "keywords": "ai, machine learning, algorithms, neural networks",
        "topic": "artificial intelligence",
        "summary": "An overview of machine learning concepts and algorithms"
    }
    
    # Test with matching query terms
    query_terms = ["machine", "learning", "algorithms"]
    score = query_processor._calculate_metadata_score(metadata, query_terms)
    assert 0 <= score <= 1, "Metadata score should be between 0 and 1"
    assert score > 0.5, "Score should be high for matching terms"
    
    # Test with non-matching query terms
    query_terms = ["quantum", "computing", "qubits"]
    score = query_processor._calculate_metadata_score(metadata, query_terms)
    assert 0 <= score <= 1, "Metadata score should be between 0 and 1"
    assert score < 0.3, "Score should be low for non-matching terms"
    
    # Test with empty metadata
    score = query_processor._calculate_metadata_score({}, query_terms)
    assert score == 0, "Score should be 0 for empty metadata"


@pytest.mark.asyncio
async def test_search_relevant_documents_integration(query_processor, document_service_client, llm_service_client):
    """Test the complete search relevant documents flow"""
    # Setup mock responses
    document_service_client.search_documents_with_embeddings.return_value = [
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
        }
    ]
    
    # Test the search flow
    query_text = "machine learning algorithms by John Smith"
    results = await query_processor.search_relevant_documents(
        query_text=query_text,
        limit=5,
        search_type="advanced"
    )
    
    # Verify results
    assert len(results) == 2
    assert results[0]["id"] == "doc1"
    assert "score_components" in results[0]
    
    # Verify the right methods were called
    assert llm_service_client.generate_embeddings.call_count == 1
    assert document_service_client.search_documents_with_embeddings.call_count == 1

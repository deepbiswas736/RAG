"""
Tests for Embedding model
"""

import pytest
import numpy as np
from app.domain.models.embedding import Embedding


class TestEmbedding:
    """Test cases for Embedding model"""
    
    def test_embedding_creation(self):
        """Test creating an embedding directly"""
        vector = [0.1, 0.2, 0.3]
        embedding = Embedding(vector=vector, dimension=3, model="test-model")
        
        assert embedding.vector == vector
        assert embedding.dimension == 3
        assert embedding.model == "test-model"
    
    def test_embedding_factory_method(self):
        """Test creating an embedding using factory method"""
        vector = [0.1, 0.2, 0.3]
        embedding = Embedding.create(vector=vector, model="test-model")
        
        assert embedding.vector == vector
        assert embedding.dimension == len(vector)
        assert embedding.model == "test-model"
    
    def test_embedding_immutable(self):
        """Test that embedding is immutable (frozen)"""
        vector = [0.1, 0.2, 0.3]
        embedding = Embedding.create(vector=vector, model="test-model")
        
        with pytest.raises(AttributeError):
            embedding.vector = [0.4, 0.5, 0.6]
    
    def test_cosine_similarity_same_vectors(self):
        """Test cosine similarity between identical vectors"""
        vector = [0.1, 0.2, 0.3]
        embedding1 = Embedding.create(vector=vector, model="test-model")
        embedding2 = Embedding.create(vector=vector, model="test-model")
        
        similarity = embedding1.cosine_similarity(embedding2)
        assert similarity == pytest.approx(1.0)
    
    def test_cosine_similarity_different_vectors(self):
        """Test cosine similarity between different vectors"""
        embedding1 = Embedding.create(vector=[1, 0, 0], model="test-model")
        embedding2 = Embedding.create(vector=[0, 1, 0], model="test-model")
        
        similarity = embedding1.cosine_similarity(embedding2)
        assert similarity == pytest.approx(0.0)
        
        embedding3 = Embedding.create(vector=[1, 1, 0], model="test-model")
        embedding4 = Embedding.create(vector=[1, 0, 1], model="test-model")
        
        similarity = embedding3.cosine_similarity(embedding4)
        assert similarity == pytest.approx(0.5)
    
    def test_cosine_similarity_different_dimensions(self):
        """Test cosine similarity raises error for different dimensions"""
        embedding1 = Embedding.create(vector=[0.1, 0.2, 0.3], model="test-model")
        embedding2 = Embedding.create(vector=[0.1, 0.2], model="test-model")
        
        with pytest.raises(ValueError):
            embedding1.cosine_similarity(embedding2)

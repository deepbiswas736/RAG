"""
Tests for Generation Response models
"""

import pytest
from datetime import datetime, timedelta
from app.domain.models.generation import GenerationResponse, StreamingChunk


class TestGenerationResponse:
    """Test cases for GenerationResponse model"""
    
    def test_generation_response_creation(self):
        """Test creating a generation response"""
        response = GenerationResponse(
            text="This is a test response",
            model="test-model",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            elapsed_time=0.5
        )
        
        assert response.text == "This is a test response"
        assert response.model == "test-model"
        assert response.prompt_tokens == 10
        assert response.completion_tokens == 5
        assert response.total_tokens == 15
        assert response.elapsed_time == 0.5
        assert isinstance(response.created_at, datetime)
    
    def test_generation_response_with_created_at(self):
        """Test creating a generation response with provided timestamp"""
        now = datetime.now()
        response = GenerationResponse(
            text="This is a test response",
            model="test-model",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            elapsed_time=0.5,
            created_at=now
        )
        
        assert response.created_at == now
    
    def test_generation_response_to_dict(self):
        """Test converting response to dictionary"""
        now = datetime.now()
        response = GenerationResponse(
            text="This is a test response",
            model="test-model",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            elapsed_time=0.5,
            created_at=now
        )
        
        response_dict = response.to_dict()
        
        assert response_dict["text"] == "This is a test response"
        assert response_dict["model"] == "test-model"
        assert response_dict["prompt_tokens"] == 10
        assert response_dict["completion_tokens"] == 5
        assert response_dict["total_tokens"] == 15
        assert response_dict["elapsed_time"] == 0.5
        assert response_dict["created_at"] == now.isoformat()
    
    def test_generation_response_from_dict(self):
        """Test creating response from dictionary"""
        now = datetime.now()
        response_dict = {
            "text": "This is a test response",
            "model": "test-model",
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "elapsed_time": 0.5,
            "created_at": now.isoformat()
        }
        
        response = GenerationResponse.from_dict(response_dict)
        
        assert response.text == "This is a test response"
        assert response.model == "test-model"
        assert response.prompt_tokens == 10
        assert response.completion_tokens == 5
        assert response.total_tokens == 15
        assert response.elapsed_time == 0.5
        assert response.created_at.isoformat() == now.isoformat()


class TestStreamingChunk:
    """Test cases for StreamingChunk model"""
    
    def test_streaming_chunk_creation(self):
        """Test creating a streaming chunk"""
        chunk = StreamingChunk(
            text="partial text",
            model="test-model"
        )
        
        assert chunk.text == "partial text"
        assert chunk.model == "test-model"
        assert chunk.is_final is False
    
    def test_streaming_chunk_with_final_flag(self):
        """Test creating a final streaming chunk"""
        chunk = StreamingChunk(
            text="final text",
            model="test-model",
            is_final=True
        )
        
        assert chunk.text == "final text"
        assert chunk.model == "test-model"
        assert chunk.is_final is True
    
    def test_streaming_chunk_to_dict(self):
        """Test converting streaming chunk to dictionary"""
        chunk = StreamingChunk(
            text="partial text",
            model="test-model",
            is_final=True
        )
        
        chunk_dict = chunk.to_dict()
        
        assert chunk_dict["text"] == "partial text"
        assert chunk_dict["model"] == "test-model"
        assert chunk_dict["is_final"] is True

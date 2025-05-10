"""
Unit tests for the document chunking service
"""

import pytest
import sys
import os
from typing import Dict, List, Any

from domain.services.chunking_service import ChunkingService


class TestChunkingService:
    """Tests for the ChunkingService"""
    
    @pytest.fixture
    def chunking_service(self):
        """Fixture for creating a chunking service"""
        return ChunkingService(
            default_chunk_size=1000,
            default_chunk_overlap=200,
            min_chunk_size=100,
            max_chunk_size=2000
        )
    
    @pytest.fixture
    def sample_text(self):
        """Fixture providing sample text for chunking"""
        return """
        # Introduction
        
        This is a test document that will be used for testing the chunking service.
        It contains multiple paragraphs and some structure.
        
        ## Section 1
        
        This is the first section of the document. It has several paragraphs
        that should be kept together when possible during the chunking process.
        
        This is another paragraph in the first section. It should be chunked
        appropriately based on the chunk size and overlap settings.
        
        ## Section 2
        
        This is the second section of the document. It also has multiple paragraphs
        that should be processed correctly.
        
        This is the final paragraph in our test document. The chunking service
        should preserve the semantic boundaries when possible.
        """
    
    def test_chunk_text_basic(self, chunking_service, sample_text):
        """Test basic text chunking without metadata"""
        chunks = chunking_service.chunk_text(
            text=sample_text,
            chunk_size=500,
            chunk_overlap=100
        )
        
        # Check that chunks were created
        assert len(chunks) > 0
        
        # Check structure of each chunk
        for chunk in chunks:
            assert "text" in chunk
            assert "metadata" in chunk
            assert isinstance(chunk["text"], str)
            assert isinstance(chunk["metadata"], dict)
            assert len(chunk["text"]) > 0
            assert "chunk_index" in chunk["metadata"]
            
        # Check content overlap
        if len(chunks) > 1:
            chunk1_text = chunks[0]["text"]
            chunk2_text = chunks[1]["text"]
            
            # There should be some overlap between adjacent chunks
            overlap_text = self._find_overlap(chunk1_text, chunk2_text)
            assert len(overlap_text) > 0
            
    def test_chunk_text_with_metadata(self, chunking_service, sample_text):
        """Test chunking with custom metadata"""
        custom_metadata = {
            "document_id": "12345",
            "document_name": "test.pdf",
            "author": "Test Author"
        }
        
        chunks = chunking_service.chunk_text(
            text=sample_text,
            chunk_size=500,
            chunk_overlap=100,
            metadata=custom_metadata
        )
        
        # Check that metadata was properly included
        for chunk in chunks:
            assert "metadata" in chunk
            assert chunk["metadata"]["document_id"] == "12345"
            assert chunk["metadata"]["document_name"] == "test.pdf"
            assert chunk["metadata"]["author"] == "Test Author"
            
    def test_chunk_size_limits(self, chunking_service):
        """Test that chunk size limits are enforced"""
        text = "This is a test " * 100  # Create a longer text
        
        # Test with chunk size below minimum
        chunks = chunking_service.chunk_text(
            text=text,
            chunk_size=50,  # Below minimum (100)
            chunk_overlap=10
        )
        
        # Should use minimum chunk size instead
        if chunks:
            for chunk in chunks:
                assert len(chunk["text"]) >= chunking_service.min_chunk_size
                
        # Test with chunk size above maximum
        chunks = chunking_service.chunk_text(
            text=text,
            chunk_size=3000,  # Above maximum (2000)
            chunk_overlap=200
        )
        
        # Should use maximum chunk size instead
        if chunks:
            for chunk in chunks:
                assert len(chunk["text"]) <= chunking_service.max_chunk_size + chunking_service.default_chunk_overlap
                
    def test_chunk_with_semantic_boundaries(self, chunking_service, sample_text):
        """Test semantic boundary chunking"""
        chunks = chunking_service.chunk_with_semantic_boundaries(
            text=sample_text,
            chunk_size=500,
            chunk_overlap=100
        )
        
        # Check that chunks were created
        assert len(chunks) > 0
        
        # Look for section headers in chunks
        section_headers = ["Introduction", "Section 1", "Section 2"]
        found_headers = []
        
        for chunk in chunks:
            for header in section_headers:
                if header in chunk["text"]:
                    found_headers.append(header)
        
        # Should have found at least some of the section headers
        assert len(found_headers) > 0
        
    def test_empty_text(self, chunking_service):
        """Test chunking with empty text"""
        chunks = chunking_service.chunk_text(
            text="",
            chunk_size=500,
            chunk_overlap=100
        )
        
        assert len(chunks) == 0
        
    def test_short_text(self, chunking_service):
        """Test chunking with text shorter than chunk size"""
        short_text = "This is a very short text."
        
        chunks = chunking_service.chunk_text(
            text=short_text,
            chunk_size=500,
            chunk_overlap=100
        )
        
        assert len(chunks) == 1
        assert chunks[0]["text"] == short_text
        
    def test_clean_text(self, chunking_service):
        """Test text cleaning functionality"""
        messy_text = "This text has   multiple    spaces and\n\n\n\nmultiple newlines."
        
        cleaned = chunking_service._clean_text(messy_text)
        
        assert "   multiple    spaces" not in cleaned
        assert "\n\n\n\n" not in cleaned
        assert "multiple newlines" in cleaned
        
    def _find_overlap(self, text1: str, text2: str) -> str:
        """Helper method to find overlap between two texts"""
        # Simple implementation - find the longest common suffix/prefix
        max_overlap = ""
        
        # Try different lengths of overlap
        for i in range(1, min(len(text1), len(text2)) + 1):
            if text1[-i:] == text2[:i]:
                max_overlap = text2[:i]
                
        return max_overlap

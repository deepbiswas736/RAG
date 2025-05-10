"""
Unit tests for the Document entity and related value objects
"""

import pytest
from datetime import datetime
from pathlib import Path
import sys
import os

# Add the microservices directory to the Python path
sys.path.append(os.path.abspath("microservices/document-service/app"))

from domain.entities.document import Document, DocumentChunk


class TestDocument:
    """Tests for Document entity"""

    def test_document_creation(self):
        """Test creating a document with default values"""
        doc = Document(name="test.pdf")
        
        assert doc.id is not None
        assert doc.name == "test.pdf"
        assert doc.file_type == ""
        assert doc.file_size == 0
        assert doc.is_processed is False
        assert doc.is_chunked is False
        assert doc.processing_status == "pending"
        
    def test_document_with_properties(self):
        """Test creating a document with specific properties"""
        doc = Document(
            name="test.pdf",
            file_type="pdf",
            file_size=1024,
            content_type="application/pdf",
            blob_path="documents/123_test.pdf",
            created_by="user123"
        )
        
        assert doc.name == "test.pdf"
        assert doc.file_type == "pdf"
        assert doc.file_size == 1024
        assert doc.content_type == "application/pdf"
        assert doc.blob_path == "documents/123_test.pdf"
        assert doc.created_by == "user123"
        assert isinstance(doc.created_at, datetime)
        
    def test_update_processing_status(self):
        """Test updating document processing status"""
        doc = Document(name="test.pdf")
        
        # Initial state
        assert doc.processing_status == "pending"
        assert doc.is_processed is False
        
        # Update to processing
        doc.update_processing_status("processing")
        assert doc.processing_status == "processing"
        assert doc.is_processed is False
        assert doc.processing_error is None
        
        # Update to completed
        doc.update_processing_status("completed")
        assert doc.processing_status == "completed"
        assert doc.is_processed is True
        assert doc.processing_error is None
        
        # Update to failed with error
        doc.update_processing_status("failed", "File corrupted")
        assert doc.processing_status == "failed"
        assert doc.is_processed is True  # Should preserve the previous state
        assert doc.processing_error == "File corrupted"
        
    def test_update_chunking_status(self):
        """Test updating document chunking status"""
        doc = Document(name="test.pdf")
        
        # Initial state
        assert doc.is_chunked is False
        assert doc.chunk_count == 0
        
        # Update chunking status
        doc.update_chunking_status(True, 5)
        assert doc.is_chunked is True
        assert doc.chunk_count == 5
        
        # Update to false state
        doc.update_chunking_status(False)
        assert doc.is_chunked is False
        assert doc.chunk_count == 0
        
    def test_is_ready_for_query(self):
        """Test document ready for querying status"""
        doc = Document(name="test.pdf")
        
        # Initial state - not ready
        assert doc.is_ready_for_query is False
        
        # Processed but not chunked - not ready
        doc.update_processing_status("completed")
        assert doc.is_processed is True
        assert doc.is_chunked is False
        assert doc.is_ready_for_query is False
        
        # Processed and chunked - ready
        doc.update_chunking_status(True, 5)
        assert doc.is_processed is True
        assert doc.is_chunked is True
        assert doc.is_ready_for_query is True
        
    def test_document_to_dict(self):
        """Test converting document to dictionary"""
        doc = Document(
            id="12345",
            name="test.pdf",
            file_type="pdf",
            file_size=1024
        )
        
        doc_dict = doc.to_dict()
        
        assert doc_dict["id"] == "12345"
        assert doc_dict["name"] == "test.pdf"
        assert doc_dict["file_type"] == "pdf"
        assert doc_dict["file_size"] == 1024
        assert isinstance(doc_dict["created_at"], str)
        assert isinstance(doc_dict["updated_at"], str)
        
    def test_document_from_dict(self):
        """Test creating document from dictionary"""
        timestamp = datetime.now().isoformat()
        doc_dict = {
            "id": "12345",
            "name": "test.pdf",
            "file_type": "pdf",
            "file_size": 1024,
            "content_type": "application/pdf",
            "blob_path": "documents/123_test.pdf",
            "created_at": timestamp,
            "updated_at": timestamp,
            "created_by": "user123",
            "metadata": {"author": "John Doe"},
            "is_processed": True,
            "is_chunked": True,
            "processing_status": "completed",
            "processing_error": None,
            "chunk_count": 5,
            "embedding_model": "text-embedding-ada-002"
        }
        
        doc = Document.from_dict(doc_dict)
        
        assert doc.id == "12345"
        assert doc.name == "test.pdf"
        assert doc.file_type == "pdf"
        assert doc.file_size == 1024
        assert doc.content_type == "application/pdf"
        assert doc.is_processed is True
        assert doc.is_chunked is True
        assert doc.processing_status == "completed"
        assert doc.chunk_count == 5
        assert doc.metadata["author"] == "John Doe"


class TestDocumentChunk:
    """Tests for DocumentChunk entity"""
    
    def test_chunk_creation(self):
        """Test creating a document chunk"""
        chunk = DocumentChunk(
            document_id="12345",
            chunk_index=0,
            text="This is a test chunk"
        )
        
        assert chunk.id is not None
        assert chunk.document_id == "12345"
        assert chunk.chunk_index == 0
        assert chunk.text == "This is a test chunk"
        assert chunk.embedding is None
        assert chunk.embedding_model is None
        assert isinstance(chunk.metadata, dict)
        assert len(chunk.metadata) == 0
        
    def test_chunk_with_properties(self):
        """Test creating a chunk with all properties"""
        chunk = DocumentChunk(
            id="chunk123",
            document_id="12345",
            chunk_index=0,
            text="This is a test chunk",
            embedding=[0.1, 0.2, 0.3],
            embedding_model="text-embedding-ada-002",
            metadata={"position": "beginning"}
        )
        
        assert chunk.id == "chunk123"
        assert chunk.document_id == "12345"
        assert chunk.chunk_index == 0
        assert chunk.text == "This is a test chunk"
        assert chunk.embedding == [0.1, 0.2, 0.3]
        assert chunk.embedding_model == "text-embedding-ada-002"
        assert chunk.metadata["position"] == "beginning"
        
    def test_chunk_to_dict(self):
        """Test converting chunk to dictionary"""
        chunk = DocumentChunk(
            id="chunk123",
            document_id="12345",
            chunk_index=0,
            text="This is a test chunk",
            embedding=[0.1, 0.2, 0.3],
            embedding_model="text-embedding-ada-002"
        )
        
        chunk_dict = chunk.to_dict()
        
        assert chunk_dict["id"] == "chunk123"
        assert chunk_dict["document_id"] == "12345"
        assert chunk_dict["chunk_index"] == 0
        assert chunk_dict["text"] == "This is a test chunk"
        assert chunk_dict["embedding"] == [0.1, 0.2, 0.3]
        assert chunk_dict["embedding_model"] == "text-embedding-ada-002"
        
    def test_chunk_from_dict(self):
        """Test creating chunk from dictionary"""
        chunk_dict = {
            "id": "chunk123",
            "document_id": "12345",
            "chunk_index": 0,
            "text": "This is a test chunk",
            "embedding": [0.1, 0.2, 0.3],
            "embedding_model": "text-embedding-ada-002",
            "metadata": {"position": "beginning"}
        }
        
        chunk = DocumentChunk.from_dict(chunk_dict)
        
        assert chunk.id == "chunk123"
        assert chunk.document_id == "12345"
        assert chunk.chunk_index == 0
        assert chunk.text == "This is a test chunk"
        assert chunk.embedding == [0.1, 0.2, 0.3]
        assert chunk.embedding_model == "text-embedding-ada-002"
        assert chunk.metadata["position"] == "beginning"

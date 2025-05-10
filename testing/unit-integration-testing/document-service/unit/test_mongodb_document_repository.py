"""
Unit tests for MongoDB Document Repository
"""

import pytest
import sys
import os
import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

# Add the microservices directory to the Python path
sys.path.append(os.path.abspath("microservices/document-service/app"))

from domain.entities.document import Document, DocumentChunk
from infrastructure.persistence.mongodb_document_repository import MongoDBDocumentRepository


class TestMongoDBDocumentRepository:
    """Tests for MongoDBDocumentRepository"""
    
    @pytest.fixture
    def mock_mongodb_client(self):
        """Fixture for mocking MongoDB client"""
        with patch("infrastructure.persistence.mongodb_document_repository.MongoClient") as mock_client:
            # Setup mock collections
            mock_documents_collection = MagicMock()
            mock_chunks_collection = MagicMock()
            
            # Setup mock database
            mock_db = MagicMock()
            mock_db.__getitem__.side_effect = lambda x: {
                "documents": mock_documents_collection,
                "document_chunks": mock_chunks_collection
            }[x]
            
            # Setup mock client
            mock_client_instance = MagicMock()
            mock_client_instance.__getitem__.return_value = mock_db
            mock_client.return_value = mock_client_instance
            
            yield {
                "client": mock_client,
                "documents_collection": mock_documents_collection,
                "chunks_collection": mock_chunks_collection
            }
    
    @pytest.fixture
    def repository(self, mock_mongodb_client):
        """Fixture for creating a repository with mocked MongoDB client"""
        return MongoDBDocumentRepository(
            connection_string="mongodb://mock:27017",
            db_name="test_db"
        )
    
    @pytest.fixture
    def sample_document(self):
        """Fixture for creating a sample document"""
        return Document(
            id="12345",
            name="test.pdf",
            file_type="pdf",
            file_size=1024,
            content_type="application/pdf",
            blob_path="documents/123_test.pdf"
        )
    
    @pytest.fixture
    def sample_chunk(self):
        """Fixture for creating a sample document chunk"""
        return DocumentChunk(
            id="chunk123",
            document_id="12345",
            chunk_index=0,
            text="This is a test chunk"
        )
    
    @pytest.mark.asyncio
    async def test_save_document(self, repository, mock_mongodb_client, sample_document):
        """Test saving a document"""
        # Setup mock insert response
        mock_mongodb_client["documents_collection"].insert_one.return_value = MagicMock(
            inserted_id="12345"
        )
        
        # Call the repository method
        result = await repository.save_document(sample_document)
        
        # Verify result
        assert result.id == "12345"
        assert result.name == "test.pdf"
        
        # Verify the mock was called correctly
        mock_mongodb_client["documents_collection"].insert_one.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_get_document_by_id(self, repository, mock_mongodb_client, sample_document):
        """Test retrieving a document by ID"""
        # Setup mock find_one response
        mock_mongodb_client["documents_collection"].find_one.return_value = sample_document.to_dict()
        
        # Call the repository method
        result = await repository.get_document_by_id("12345")
        
        # Verify result
        assert result is not None
        assert result.id == "12345"
        assert result.name == "test.pdf"
        
        # Verify the mock was called correctly
        mock_mongodb_client["documents_collection"].find_one.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_get_document_by_id_not_found(self, repository, mock_mongodb_client):
        """Test retrieving a non-existent document"""
        # Setup mock find_one response
        mock_mongodb_client["documents_collection"].find_one.return_value = None
        
        # Call the repository method
        result = await repository.get_document_by_id("nonexistent")
        
        # Verify result
        assert result is None
        
        # Verify the mock was called correctly
        mock_mongodb_client["documents_collection"].find_one.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_update_document(self, repository, mock_mongodb_client, sample_document):
        """Test updating a document"""
        # Setup mock replace_one response
        mock_mongodb_client["documents_collection"].replace_one.return_value = MagicMock(
            matched_count=1
        )
        
        # Call the repository method
        result = await repository.update_document(sample_document)
        
        # Verify result
        assert result.id == "12345"
        assert result.name == "test.pdf"
        
        # Verify the mock was called correctly
        mock_mongodb_client["documents_collection"].replace_one.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_delete_document(self, repository, mock_mongodb_client):
        """Test deleting a document"""
        # Setup mock delete_one response
        mock_mongodb_client["documents_collection"].delete_one.return_value = MagicMock(
            deleted_count=1
        )
        
        # Setup mock delete_many response for chunks
        mock_mongodb_client["chunks_collection"].delete_many.return_value = MagicMock(
            deleted_count=5
        )
        
        # Call the repository method
        result = await repository.delete_document("12345")
        
        # Verify result
        assert result is True
        
        # Verify the mocks were called correctly
        mock_mongodb_client["documents_collection"].delete_one.assert_called_once()
        mock_mongodb_client["chunks_collection"].delete_many.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_delete_document_not_found(self, repository, mock_mongodb_client):
        """Test deleting a non-existent document"""
        # Setup mock delete_one response
        mock_mongodb_client["documents_collection"].delete_one.return_value = MagicMock(
            deleted_count=0
        )
        
        # Call the repository method
        result = await repository.delete_document("nonexistent")
        
        # Verify result
        assert result is False
        
        # Verify the mock was called correctly
        mock_mongodb_client["documents_collection"].delete_one.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_list_documents(self, repository, mock_mongodb_client, sample_document):
        """Test listing documents"""
        # Setup mock count_documents response
        mock_mongodb_client["documents_collection"].count_documents.return_value = 1
        
        # Setup mock find response
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.__iter__.return_value = [sample_document.to_dict()]
        mock_mongodb_client["documents_collection"].find.return_value = mock_cursor
        
        # Call the repository method
        documents, total = await repository.list_documents(skip=0, limit=10)
        
        # Verify results
        assert total == 1
        assert len(documents) == 1
        assert documents[0].id == "12345"
        assert documents[0].name == "test.pdf"
        
        # Verify the mocks were called correctly
        mock_mongodb_client["documents_collection"].count_documents.assert_called_once()
        mock_mongodb_client["documents_collection"].find.assert_called_once()
        mock_cursor.sort.assert_called_once()
        mock_cursor.skip.assert_called_once()
        mock_cursor.limit.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_save_chunk(self, repository, mock_mongodb_client, sample_chunk):
        """Test saving a document chunk"""
        # Setup mock insert response
        mock_mongodb_client["chunks_collection"].insert_one.return_value = MagicMock(
            inserted_id="chunk123"
        )
        
        # Call the repository method
        result = await repository.save_chunk(sample_chunk)
        
        # Verify result
        assert result.id == "chunk123"
        assert result.document_id == "12345"
        assert result.text == "This is a test chunk"
        
        # Verify the mock was called correctly
        mock_mongodb_client["chunks_collection"].insert_one.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_get_chunks_by_document_id(self, repository, mock_mongodb_client, sample_chunk):
        """Test retrieving chunks by document ID"""
        # Setup mock find response
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.__iter__.return_value = [sample_chunk.to_dict()]
        mock_mongodb_client["chunks_collection"].find.return_value = mock_cursor
        
        # Call the repository method
        result = await repository.get_chunks_by_document_id("12345")
        
        # Verify result
        assert len(result) == 1
        assert result[0].id == "chunk123"
        assert result[0].document_id == "12345"
        
        # Verify the mock was called correctly
        mock_mongodb_client["chunks_collection"].find.assert_called_once()
        mock_cursor.sort.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_delete_chunks_by_document_id(self, repository, mock_mongodb_client):
        """Test deleting chunks by document ID"""
        # Setup mock delete_many response
        mock_mongodb_client["chunks_collection"].delete_many.return_value = MagicMock(
            deleted_count=5
        )
        
        # Call the repository method
        result = await repository.delete_chunks_by_document_id("12345")
        
        # Verify result
        assert result is True
        
        # Verify the mock was called correctly
        mock_mongodb_client["chunks_collection"].delete_many.assert_called_once_with({"document_id": "12345"})

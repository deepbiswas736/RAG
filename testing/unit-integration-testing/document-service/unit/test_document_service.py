"""
Unit tests for Document Service application layer
"""

import pytest
import sys
import os
import asyncio
import io
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import UploadFile, HTTPException
from typing import Dict, Any, Optional

# Add the microservices directory to the Python path
sys.path.append(os.path.abspath("microservices/document-service/app"))

from application.services.document_service import DocumentService, DocumentDTO, ChunkDTO
from domain.entities.document import Document, DocumentChunk
from domain.repositories.document_repository import DocumentRepository
from domain.services.document_processing_service import DocumentProcessingService
from domain.services.chunking_service import ChunkingService
from infrastructure.blob.blob_store import BlobStore
from infrastructure.messaging.kafka_client import KafkaClient


class TestDocumentService:
    """Tests for DocumentService application service"""
    
    @pytest.fixture
    def mock_document_repository(self):
        """Fixture for mocking document repository"""
        repo = AsyncMock(spec=DocumentRepository)
        return repo
    
    @pytest.fixture
    def mock_document_processor(self):
        """Fixture for mocking document processor"""
        processor = AsyncMock(spec=DocumentProcessingService)
        return processor
    
    @pytest.fixture
    def mock_blob_store(self):
        """Fixture for mocking blob store"""
        blob_store = AsyncMock(spec=BlobStore)
        return blob_store
    
    @pytest.fixture
    def mock_chunking_service(self):
        """Fixture for mocking chunking service"""
        chunker = MagicMock(spec=ChunkingService)
        return chunker
    
    @pytest.fixture
    def mock_kafka_client(self):
        """Fixture for mocking Kafka client"""
        client = AsyncMock(spec=KafkaClient)
        return client
    
    @pytest.fixture
    def service(self, mock_document_repository, mock_document_processor, 
                mock_blob_store, mock_chunking_service, mock_kafka_client):
        """Fixture for creating document service with mocked dependencies"""
        return DocumentService(
            document_repository=mock_document_repository,
            document_processor=mock_document_processor,
            blob_store=mock_blob_store,
            chunking_service=mock_chunking_service,
            kafka_client=mock_kafka_client
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
    
    @pytest.fixture
    def mock_upload_file(self):
        """Fixture for creating a mock UploadFile"""
        file = AsyncMock(spec=UploadFile)
        file.filename = "test.pdf"
        file.content_type = "application/pdf"
        file.file = io.BytesIO(b"Test file content")
        return file
    
    @patch("application.services.document_service.asyncio.create_task")
    @pytest.mark.asyncio
    async def test_upload_document(self, mock_create_task, service, mock_document_repository, 
                                 mock_blob_store, mock_kafka_client, mock_upload_file, sample_document):
        """Test uploading a document"""
        # Setup mocks
        mock_document_repository.save_document.return_value = sample_document
        mock_document_repository.update_document.return_value = sample_document
        mock_blob_store.save_file.return_value = "documents/123_test.pdf"
        mock_upload_file.read = AsyncMock(return_value=b"Test file content")
        
        # Call the service method
        result = await service.upload_document(
            file=mock_upload_file,
            user_id="user123",
            metadata={"source": "test"}
        )
        
        # Verify result
        assert isinstance(result, DocumentDTO)
        assert result.id == "12345"
        assert result.name == "test.pdf"
        
        # Verify mocks were called correctly
        mock_document_repository.save_document.assert_called_once()
        mock_blob_store.save_file.assert_called_once()
        mock_document_repository.update_document.assert_called_once()
        mock_kafka_client.send_document_created_event.assert_called_once()
        mock_create_task.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_get_document(self, service, mock_document_repository, sample_document):
        """Test getting a document"""
        # Setup mock
        mock_document_repository.get_document_by_id.return_value = sample_document
        
        # Call the service method
        result = await service.get_document("12345")
        
        # Verify result
        assert isinstance(result, DocumentDTO)
        assert result.id == "12345"
        assert result.name == "test.pdf"
        
        # Verify mock was called correctly
        mock_document_repository.get_document_by_id.assert_called_once_with("12345")
        
    @pytest.mark.asyncio
    async def test_get_document_not_found(self, service, mock_document_repository):
        """Test getting a non-existent document"""
        # Setup mock
        mock_document_repository.get_document_by_id.return_value = None
        
        # Verify exception is raised
        with pytest.raises(HTTPException) as excinfo:
            await service.get_document("nonexistent")
        
        assert excinfo.value.status_code == 404
        
        # Verify mock was called correctly
        mock_document_repository.get_document_by_id.assert_called_once_with("nonexistent")
        
    @pytest.mark.asyncio
    async def test_list_documents(self, service, mock_document_repository, sample_document):
        """Test listing documents"""
        # Setup mock
        mock_document_repository.list_documents.return_value = ([sample_document], 1)
        
        # Call the service method
        documents, total = await service.list_documents(skip=0, limit=10)
        
        # Verify result
        assert len(documents) == 1
        assert isinstance(documents[0], DocumentDTO)
        assert documents[0].id == "12345"
        assert total == 1
        
        # Verify mock was called correctly
        mock_document_repository.list_documents.assert_called_once_with(
            skip=0, limit=10, query_filter=None
        )
        
    @pytest.mark.asyncio
    async def test_delete_document(self, service, mock_document_repository, 
                                  mock_blob_store, sample_document):
        """Test deleting a document"""
        # Setup mocks
        mock_document_repository.get_document_by_id.return_value = sample_document
        mock_blob_store.delete_file.return_value = True
        mock_document_repository.delete_chunks_by_document_id.return_value = True
        mock_document_repository.delete_document.return_value = True
        
        # Call the service method
        result = await service.delete_document("12345")
        
        # Verify result
        assert result is True
        
        # Verify mocks were called correctly
        mock_document_repository.get_document_by_id.assert_called_once_with("12345")
        mock_blob_store.delete_file.assert_called_once_with("documents/123_test.pdf")
        mock_document_repository.delete_chunks_by_document_id.assert_called_once_with("12345")
        mock_document_repository.delete_document.assert_called_once_with("12345")
        
    @pytest.mark.asyncio
    async def test_delete_document_not_found(self, service, mock_document_repository):
        """Test deleting a non-existent document"""
        # Setup mock
        mock_document_repository.get_document_by_id.return_value = None
        
        # Verify exception is raised
        with pytest.raises(HTTPException) as excinfo:
            await service.delete_document("nonexistent")
        
        assert excinfo.value.status_code == 404
        
        # Verify mock was called correctly
        mock_document_repository.get_document_by_id.assert_called_once_with("nonexistent")
        
    @pytest.mark.asyncio
    async def test_download_document(self, service, mock_document_repository, 
                                    mock_blob_store, sample_document):
        """Test downloading a document"""
        # Setup mocks
        mock_document_repository.get_document_by_id.return_value = sample_document
        mock_blob_store.get_file.return_value = (io.BytesIO(b"Test file content"), "test.pdf")
        
        # Call the service method
        file_content, filename, content_type = await service.download_document("12345")
        
        # Verify result
        assert file_content.getvalue() == b"Test file content"
        assert filename == "test.pdf"
        assert content_type == "application/pdf"
        
        # Verify mocks were called correctly
        mock_document_repository.get_document_by_id.assert_called_once_with("12345")
        mock_blob_store.get_file.assert_called_once_with("documents/123_test.pdf")
        
    @pytest.mark.asyncio
    async def test_get_document_chunks(self, service, mock_document_repository, 
                                      sample_document, sample_chunk):
        """Test getting document chunks"""
        # Setup mocks
        mock_document_repository.get_document_by_id.return_value = sample_document
        mock_document_repository.get_chunks_by_document_id.return_value = [sample_chunk]
        
        # Call the service method
        chunks = await service.get_document_chunks("12345")
        
        # Verify result
        assert len(chunks) == 1
        assert isinstance(chunks[0], ChunkDTO)
        assert chunks[0].id == "chunk123"
        assert chunks[0].document_id == "12345"
        assert chunks[0].text == "This is a test chunk"
        
        # Verify mocks were called correctly
        mock_document_repository.get_document_by_id.assert_called_once_with("12345")
        mock_document_repository.get_chunks_by_document_id.assert_called_once_with("12345")
        
    @pytest.mark.asyncio
    async def test_convert_to_pdf(self, service, mock_document_processor, mock_upload_file):
        """Test converting a document to PDF"""
        # Setup mocks
        mock_upload_file.read = AsyncMock(return_value=b"Test file content")
        mock_document_processor.convert_to_pdf.return_value = (b"PDF content", None)
        
        # Call the service method
        pdf_content, pdf_filename = await service.convert_to_pdf(mock_upload_file)
        
        # Verify result
        assert pdf_content == b"PDF content"
        assert pdf_filename == "test.pdf"
        
        # Verify mocks were called correctly
        mock_upload_file.read.assert_called_once()
        mock_document_processor.convert_to_pdf.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_convert_to_pdf_error(self, service, mock_document_processor, mock_upload_file):
        """Test error during PDF conversion"""
        # Setup mocks
        mock_upload_file.read = AsyncMock(return_value=b"Test file content")
        mock_document_processor.convert_to_pdf.return_value = (None, "Conversion failed")
        
        # Verify exception is raised
        with pytest.raises(HTTPException) as excinfo:
            await service.convert_to_pdf(mock_upload_file)
        
        assert excinfo.value.status_code == 400
        assert "Conversion failed" in str(excinfo.value.detail)
        
        # Verify mocks were called correctly
        mock_upload_file.read.assert_called_once()
        mock_document_processor.convert_to_pdf.assert_called_once()

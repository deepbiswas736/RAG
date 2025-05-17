"""
Integration tests for Document Service
"""

import pytest
import sys
import os
import io
import json
from unittest import mock
import asyncio
import httpx
import pytest_asyncio

# Add the microservices directory to the Python path
sys.path.append(os.path.abspath("microservices/document-service/app"))

from fastapi import FastAPI
from fastapi.testclient import TestClient
import motor.motor_asyncio
from minio import Minio

# Import application
from main import app, get_document_service
from application.services.document_service import DocumentService
from domain.repositories.document_repository import DocumentRepository
from infrastructure.persistence.mongodb_document_repository import MongoDBDocumentRepository
from infrastructure.blob.blob_store import BlobStore
from infrastructure.messaging.kafka_client import KafkaClient
from domain.services.chunking_service import ChunkingService
from domain.services.document_processing_service import DocumentProcessingService


class TestDocumentServiceIntegration:
    """Integration tests for Document Service"""
    
    @pytest_asyncio.fixture
    async def mock_mongodb_client(self):
        """Fixture for creating a mock MongoDB client"""
        # Use mock MongoDB client for integration tests
        from mongomock_motor import AsyncMongoMockClient
        
        client = AsyncMongoMockClient()
        db = client["test_db"]
        
        # Create test collections
        await db.create_collection("documents")
        await db.create_collection("document_chunks")
        
        return client
    
    @pytest.fixture
    def mock_minio_client(self):
        """Fixture for creating a mock MinIO client"""
        with mock.patch("minio.Minio") as mock_client:
            mock_instance = mock.MagicMock()
            mock_client.return_value = mock_instance
            
            # Mock methods
            mock_instance.bucket_exists.return_value = True
            mock_instance.put_object.return_value = None
            mock_instance.get_object.return_value = io.BytesIO(b"test document content")
            mock_instance.remove_object.return_value = None
            
            yield mock_instance
    
    @pytest.fixture
    def mock_kafka_client(self):
        """Fixture for creating a mock Kafka client"""
        with mock.patch("infrastructure.messaging.kafka_client.KafkaClient") as mock_client:
            mock_instance = mock.AsyncMock()
            mock_client.return_value = mock_instance
            
            # Mock methods
            mock_instance.send_document_created_event.return_value = None
            mock_instance.send_document_processed_event.return_value = None
            mock_instance.send_document_chunked_event.return_value = None
            mock_instance.send_document_deleted_event.return_value = None
            
            yield mock_instance
    
    @pytest.fixture
    def test_client(self, mock_mongodb_client, mock_minio_client, mock_kafka_client):
        """Fixture for creating a FastAPI test client with mocked dependencies"""
        # Override the dependency injection
        async def override_get_document_service():
            # Create repository
            document_repository = MongoDBDocumentRepository(
                connection_string="mongodb://mongodb:27017",
                db_name="test_db",
                client=mock_mongodb_client
            )
            
            # Create blob store with mock client
            blob_store = BlobStore(
                endpoint="localhost:9000",
                access_key="test_access_key",
                secret_key="test_secret_key",
                secure=False
            )
            blob_store.client = mock_minio_client
            
            # Create document processing service
            document_processor = DocumentProcessingService()
            
            # Create chunking service
            chunking_service = ChunkingService()
            
            # Create kafka client
            kafka_client = mock_kafka_client
            
            # Create document service
            document_service = DocumentService(
                document_repository=document_repository,
                document_processor=document_processor,
                blob_store=blob_store,
                chunking_service=chunking_service,
                kafka_client=kafka_client
            )
            
            return document_service
        
        # Override dependency in FastAPI app
        app.dependency_overrides[get_document_service] = override_get_document_service
        
        # Create test client
        client = TestClient(app)
        
        yield client
        
        # Clean up
        app.dependency_overrides = {}
    
    async def upload_test_document(self, test_client):
        """Helper function to upload a test document"""
        # Create test file
        test_content = b"This is a test document"
        test_file = io.BytesIO(test_content)
        test_file.name = "test.txt"
        
        # Upload document
        response = test_client.post(
            "/api/v1/documents",
            files={"file": ("test.txt", test_file, "text/plain")},
            data={"metadata": json.dumps({"source": "test"})}
        )
        
        return response.json()
    
    def test_health_check(self, test_client):
        """Test health check endpoint"""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_upload_document(self, test_client):
        """Test uploading a document"""
        # Create test file
        test_content = b"This is a test document"
        test_file = io.BytesIO(test_content)
        
        # Upload document
        response = test_client.post(
            "/api/v1/documents",
            files={"file": ("test.txt", test_file, "text/plain")},
            data={"metadata": json.dumps({"source": "test"})}
        )
        
        # Check response
        assert response.status_code == 201
        
        data = response.json()
        assert "id" in data
        assert data["name"] == "test.txt"
        assert data["file_type"] == "txt"
        assert data["processing_status"] == "pending"
        assert data["is_processed"] is False
        assert data["is_chunked"] is False
        assert "blob_path" in data
        assert data["metadata"]["source"] == "test"
    
    def test_get_document(self, test_client):
        """Test getting a document"""
        # First upload a document
        doc = asyncio.run(self.upload_test_document(test_client))
        
        # Get the document
        response = test_client.get(f"/api/v1/documents/{doc['id']}")
        
        # Check response
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == doc["id"]
        assert data["name"] == "test.txt"
    
    def test_get_document_not_found(self, test_client):
        """Test getting a non-existent document"""
        response = test_client.get("/api/v1/documents/nonexistent")
        
        # Check response
        assert response.status_code == 404
    
    def test_list_documents(self, test_client):
        """Test listing documents"""
        # First upload a document
        doc = asyncio.run(self.upload_test_document(test_client))
        
        # List documents
        response = test_client.get("/api/v1/documents")
        
        # Check response
        assert response.status_code == 200
        
        data = response.json()
        assert "documents" in data
        assert "total" in data
        assert data["total"] == 1
        assert len(data["documents"]) == 1
        assert data["documents"][0]["id"] == doc["id"]
    
    def test_delete_document(self, test_client):
        """Test deleting a document"""
        # First upload a document
        doc = asyncio.run(self.upload_test_document(test_client))
        
        # Delete the document
        response = test_client.delete(f"/api/v1/documents/{doc['id']}")
        
        # Check response
        assert response.status_code == 200
        assert response.json() == {"success": True}
        
        # Verify document is deleted
        get_response = test_client.get(f"/api/v1/documents/{doc['id']}")
        assert get_response.status_code == 404
    
    def test_download_document(self, test_client, mock_minio_client):
        """Test downloading a document"""
        # First upload a document
        doc = asyncio.run(self.upload_test_document(test_client))
        
        # Mock the get_object response
        mock_minio_client.get_object.return_value = io.BytesIO(b"test document content")
        
        # Download the document
        response = test_client.get(f"/api/v1/documents/{doc['id']}/download")
        
        # Check response
        assert response.status_code == 200
        assert response.content == b"test document content"
        assert response.headers["content-type"] == "text/plain"
        
    def test_convert_to_pdf(self, test_client):
        """Test converting a document to PDF"""
        # Create test file
        test_content = b"This is a test document"
        test_file = io.BytesIO(test_content)
        
        # Mock PDF conversion
        with mock.patch("domain.services.document_processing_service.DocumentProcessingService.convert_to_pdf") as mock_convert:
            mock_convert.return_value = (b"%PDF-1.7\nTest PDF content", None)
            
            # Convert document
            response = test_client.post(
                "/api/v1/documents/convert-to-pdf",
                files={"file": ("test.txt", test_file, "text/plain")}
            )
            
            # Check response
            assert response.status_code == 200
            assert response.content.startswith(b"%PDF-1.7")
            assert response.headers["content-type"] == "application/pdf"
            assert "attachment; filename=test.pdf" in response.headers["content-disposition"]

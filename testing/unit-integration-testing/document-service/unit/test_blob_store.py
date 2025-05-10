"""
Unit tests for BlobStore
"""

import pytest
import sys
import os
import io
from unittest.mock import patch, MagicMock

# Add the microservices directory to the Python path
sys.path.append(os.path.abspath("microservices/document-service/app"))

from infrastructure.blob.blob_store import BlobStore


class TestBlobStore:
    """Tests for BlobStore"""
    
    @pytest.fixture
    def mock_minio_client(self):
        """Fixture for mocking MinIO client"""
        with patch("minio.Minio") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            # Mock methods
            mock_instance.bucket_exists.return_value = True
            mock_instance.put_object.return_value = None
            mock_instance.get_object.return_value = io.BytesIO(b"test content")
            mock_instance.remove_object.return_value = None
            mock_instance.presigned_get_object.return_value = "https://test-presigned-url.com"
            
            yield mock_instance
    
    @pytest.fixture
    def blob_store(self, mock_minio_client):
        """Fixture for creating a blob store with mocked MinIO client"""
        store = BlobStore(
            endpoint="localhost:9000",
            access_key="test_access_key",
            secret_key="test_secret_key",
            secure=False,
            bucket_name="test-bucket"
        )
        store.client = mock_minio_client
        return store
    
    @pytest.mark.asyncio
    async def test_init(self, blob_store, mock_minio_client):
        """Test initialization"""
        # Check bucket creation
        mock_minio_client.bucket_exists.assert_called_once_with("test-bucket")
        mock_minio_client.make_bucket.assert_not_called()  # Bucket exists, so no need to create
        
    @pytest.mark.asyncio
    async def test_init_create_bucket(self, mock_minio_client):
        """Test initialization with bucket creation"""
        # Setup mock bucket_exists to return False
        mock_minio_client.bucket_exists.return_value = False
        
        # Create blob store, should create bucket
        store = BlobStore(
            endpoint="localhost:9000",
            access_key="test_access_key",
            secret_key="test_secret_key",
            secure=False,
            bucket_name="test-bucket"
        )
        store.client = mock_minio_client
        
        # Check bucket creation
        mock_minio_client.bucket_exists.assert_called_once_with("test-bucket")
        mock_minio_client.make_bucket.assert_called_once_with("test-bucket")
        
    @pytest.mark.asyncio
    async def test_save_file(self, blob_store, mock_minio_client):
        """Test saving a file"""
        # Test data
        file_data = b"test content"
        file_obj = io.BytesIO(file_data)
        file_name = "test.txt"
        content_type = "text/plain"
        
        # Call save_file
        result = await blob_store.save_file(
            file_obj=file_obj,
            file_name=file_name,
            content_type=content_type
        )
        
        # Check result (should be a path)
        assert result is not None
        assert file_name in result
        assert result.startswith("documents/")
        
        # Check that put_object was called
        mock_minio_client.put_object.assert_called_once()
        call_args = mock_minio_client.put_object.call_args
        assert call_args[0][0] == "test-bucket"  # bucket name
        assert call_args[0][2] == len(file_data)  # file size
        assert call_args[1]["content_type"] == content_type
        
    @pytest.mark.asyncio
    async def test_get_file(self, blob_store, mock_minio_client):
        """Test getting a file"""
        # Test data
        file_path = "documents/test.txt"
        
        # Call get_file
        file_obj, file_name = await blob_store.get_file(file_path)
        
        # Check results
        assert file_obj is not None
        assert file_obj.read() == b"test content"
        assert file_name == "test.txt"
        
        # Check that get_object was called
        mock_minio_client.get_object.assert_called_once_with(
            "test-bucket", file_path
        )
        
    @pytest.mark.asyncio
    async def test_delete_file(self, blob_store, mock_minio_client):
        """Test deleting a file"""
        # Test data
        file_path = "documents/test.txt"
        
        # Call delete_file
        result = await blob_store.delete_file(file_path)
        
        # Check result
        assert result is True
        
        # Check that remove_object was called
        mock_minio_client.remove_object.assert_called_once_with(
            "test-bucket", file_path
        )
        
    @pytest.mark.asyncio
    async def test_delete_file_exception(self, blob_store, mock_minio_client):
        """Test error handling during file deletion"""
        # Test data
        file_path = "documents/test.txt"
        
        # Setup mock to raise exception
        mock_minio_client.remove_object.side_effect = Exception("Delete failed")
        
        # Call delete_file
        result = await blob_store.delete_file(file_path)
        
        # Check result
        assert result is False
        
    @pytest.mark.asyncio
    async def test_get_presigned_url(self, blob_store, mock_minio_client):
        """Test getting a presigned URL"""
        # Test data
        file_path = "documents/test.txt"
        
        # Call get_presigned_url
        url = await blob_store.get_presigned_url(file_path, expires=3600)
        
        # Check result
        assert url == "https://test-presigned-url.com"
        
        # Check that presigned_get_object was called
        mock_minio_client.presigned_get_object.assert_called_once_with(
            "test-bucket", file_path, expires=3600
        )

"""
Blob Store
---------
Handles storage and retrieval of document files using MinIO.
"""
import logging
import os
import io
from typing import Optional, Tuple, BinaryIO
from minio import Minio
from minio.error import S3Error
import uuid

# Configure logging
logger = logging.getLogger(__name__)

class BlobStore:
    """Storage service for document files using MinIO"""
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        secure: bool = False,
        bucket_name: str = "documents"
    ):
        """
        Initialize the blob store
        
        Args:
            endpoint: MinIO endpoint URL
            access_key: MinIO access key
            secret_key: MinIO secret key
            secure: Use HTTPS if True
            bucket_name: Name of the bucket to use
        """
        self.endpoint = endpoint or os.getenv("MINIO_URL", "localhost:9000")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.secure = secure
        self.bucket_name = bucket_name
        
        # Initialize MinIO client
        self._client = Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
        
        logger.info(f"Blob store initialized with endpoint: {self.endpoint}, bucket: {self.bucket_name}")
        
    def _ensure_bucket_exists(self):
        """Ensure that the bucket exists, create it if not"""
        try:
            # Check if bucket exists
            if not self._client.bucket_exists(self.bucket_name):
                # Create bucket if it doesn't exist
                self._client.make_bucket(self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")
            else:
                logger.info(f"Bucket already exists: {self.bucket_name}")
                
        except S3Error as e:
            logger.error(f"Error ensuring bucket exists: {e}")
            raise
            
    async def save_file(
        self,
        file_content: BinaryIO,
        file_name: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> str:
        """
        Save file to blob storage
        
        Args:
            file_content: File content as binary data
            file_name: Original file name
            content_type: MIME type of the file
            
        Returns:
            Path to the stored file
        """
        try:
            # Generate a unique object name if file_name is not provided
            if not file_name:
                file_name = f"document_{uuid.uuid4()}"
                
            # Use UUID to avoid name collisions
            object_name = f"{uuid.uuid4()}_{file_name}"
            
            # Get file size
            file_content.seek(0, os.SEEK_END)
            file_size = file_content.tell()
            file_content.seek(0)
            
            # Save file to MinIO
            self._client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_content,
                length=file_size,
                content_type=content_type
            )
            
            logger.info(f"File saved to blob storage: {object_name}")
            return object_name
            
        except S3Error as e:
            logger.error(f"Error saving file to blob storage: {e}")
            raise
            
    async def get_file(self, blob_path: str) -> Tuple[io.BytesIO, str]:
        """
        Retrieve file from blob storage
        
        Args:
            blob_path: Path to the file in blob storage
            
        Returns:
            Tuple of (file content as BytesIO, original file name)
        """
        try:
            # Extract original file name from blob path
            original_file_name = blob_path.split('_', 1)[1] if '_' in blob_path else blob_path
            
            # Get file from MinIO
            response = self._client.get_object(
                bucket_name=self.bucket_name,
                object_name=blob_path
            )
            
            # Read file content into BytesIO
            file_content = io.BytesIO(response.read())
            
            # Close response to avoid resource leak
            response.close()
            response.release_conn()
            
            logger.info(f"File retrieved from blob storage: {blob_path}")
            return file_content, original_file_name
            
        except S3Error as e:
            logger.error(f"Error retrieving file from blob storage: {e}")
            raise
            
    async def delete_file(self, blob_path: str) -> bool:
        """
        Delete file from blob storage
        
        Args:
            blob_path: Path to the file in blob storage
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            # Remove the object
            self._client.remove_object(
                bucket_name=self.bucket_name,
                object_name=blob_path
            )
            
            logger.info(f"File deleted from blob storage: {blob_path}")
            return True
            
        except S3Error as e:
            logger.error(f"Error deleting file from blob storage: {e}")
            return False
            
    async def get_file_metadata(self, blob_path: str) -> dict:
        """
        Get file metadata from blob storage
        
        Args:
            blob_path: Path to the file in blob storage
            
        Returns:
            Dictionary of metadata
        """
        try:
            # Stat the object to get metadata
            stat = self._client.stat_object(
                bucket_name=self.bucket_name,
                object_name=blob_path
            )
            
            # Extract relevant metadata
            metadata = {
                "size": stat.size,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified
            }
            
            return metadata
            
        except S3Error as e:
            logger.error(f"Error getting file metadata from blob storage: {e}")
            raise

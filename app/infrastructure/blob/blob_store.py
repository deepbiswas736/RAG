from minio import Minio
from fastapi import UploadFile
import os
import io
from typing import Optional, BinaryIO

class BlobStore:
    def __init__(self):
        self.client = Minio(
            os.getenv("MINIO_URL", "localhost:9000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            secure=False
        )
        self.bucket_name = "documents"
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except Exception as e:
            print(f"Error ensuring bucket exists: {e}")

    async def upload_file(self, file: UploadFile) -> str:
        """Upload a file to blob storage and return its path"""
        try:
            content = await file.read()
            content_stream = io.BytesIO(content)
            # Reset file pointer for future reads
            await file.seek(0)
            
            # Generate a unique object name
            object_name = f"{file.filename}"
            
            # Upload to MinIO
            self.client.put_object(
                self.bucket_name,
                object_name,
                content_stream,
                length=len(content),
                content_type=file.content_type
            )
            
            return f"{self.bucket_name}/{object_name}"
        except Exception as e:
            print(f"Error uploading file: {e}")
            raise

    async def upload_binary(self, content: bytes, filename: str) -> str:
        """Upload binary content to blob storage and return its path"""
        try:
            content_stream = io.BytesIO(content)
            
            # Generate a unique object name based on the filename
            object_name = filename
            
            # Determine content type based on filename
            content_type = "application/pdf"  # Default to PDF since we're converting everything to PDF
            
            # Upload to MinIO
            self.client.put_object(
                self.bucket_name,
                object_name,
                content_stream,
                length=len(content),
                content_type=content_type
            )
            
            return f"{self.bucket_name}/{object_name}"
        except Exception as e:
            print(f"Error uploading binary content: {e}")
            raise

    async def get_file(self, file_path: str) -> Optional[BinaryIO]:
        """Retrieve a file from blob storage"""
        try:
            # Extract bucket and object name from path
            _, object_name = file_path.split('/', 1)
            
            # Get object data
            response = self.client.get_object(self.bucket_name, object_name)
            return response
        except Exception as e:
            print(f"Error retrieving file: {e}")
            return None

    async def delete_file(self, file_path: str) -> bool:
        """Delete a file from blob storage"""
        try:
            # Extract bucket and object name from path
            _, object_name = file_path.split('/', 1)
            
            # Remove object
            self.client.remove_object(self.bucket_name, object_name)
            return True
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False
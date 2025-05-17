from typing import Tuple, Any, Optional

class BlobStore:
    """Service for storing and retrieving document files"""
    
    async def get_file(self, blob_path: str) -> Tuple[Any, Optional[str]]:
        """
        Retrieve a file from blob storage
        Returns: (file_content, error)
        """
        raise NotImplementedError
        
    async def save_file(self, file_content: bytes, blob_path: str) -> Optional[str]:
        """
        Save a file to blob storage
        Returns: error if any
        """
        raise NotImplementedError
        
    async def delete_file(self, blob_path: str) -> Optional[str]:
        """
        Delete a file from blob storage
        Returns: error if any
        """
        raise NotImplementedError

import hashlib
import logging
from typing import Union, Optional

logger = logging.getLogger(__name__)

class ChecksumUtil:
    """
    Utility class for generating and validating document checksums.
    Used to identify duplicate documents during upload.
    """
    
    @staticmethod
    def generate_checksum(content: Union[str, bytes], algorithm: str = 'sha256') -> str:
        """
        Generate a checksum hash for document content.
        
        Args:
            content: Document content as string or bytes
            algorithm: Hash algorithm to use (default: sha256)
            
        Returns:
            Hexadecimal string representation of the hash
        """
        if not content:
            logger.warning("Empty content provided for checksum generation")
            return ""
            
        try:
            if isinstance(content, str):
                content = content.encode('utf-8')
                
            if algorithm.lower() == 'sha256':
                return hashlib.sha256(content).hexdigest()
            elif algorithm.lower() == 'md5':
                return hashlib.md5(content).hexdigest()
            else:
                logger.warning(f"Unsupported hash algorithm: {algorithm}, using sha256")
                return hashlib.sha256(content).hexdigest()
                
        except Exception as e:
            logger.error(f"Error generating checksum: {str(e)}")
            return ""
    
    @staticmethod
    def validate_checksum(content: Union[str, bytes], expected_checksum: str, algorithm: str = 'sha256') -> bool:
        """
        Validate if content matches the expected checksum.
        
        Args:
            content: Document content to validate
            expected_checksum: Expected checksum to compare against
            algorithm: Hash algorithm used for the checksum
            
        Returns:
            True if checksums match, False otherwise
        """
        if not expected_checksum:
            return False
            
        actual_checksum = ChecksumUtil.generate_checksum(content, algorithm)
        return actual_checksum == expected_checksum
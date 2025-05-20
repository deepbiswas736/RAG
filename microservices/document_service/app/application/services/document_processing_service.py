from typing import Tuple, Dict, Any, Optional

class DocumentProcessingService:
    """Service for processing document content"""
    
    async def extract_text(self, file_content: bytes, file_extension: str) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Extract text from document content
        Returns: (structured_content, error)
        """
        raise NotImplementedError

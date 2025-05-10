"""
Document Processing Service
------------------------
Handles document processing operations such as conversion and metadata extraction.
"""
import os
import aiohttp
import logging
import asyncio
import tempfile
import json
from typing import Dict, Any, Optional, BinaryIO, Tuple

# Configure logging
logger = logging.getLogger(__name__)


class DocumentProcessingService:
    """Handles operations related to processing documents"""
    
    def __init__(self, document_processor_url: str = None):
        """
        Initialize the document processing service
        
        Args:
            document_processor_url: URL of the document processor service
        """
        self.document_processor_url = document_processor_url or os.getenv(
            "DOCUMENT_PROCESSOR_URL", "http://document-processor:8080"
        )
        logger.info(f"Document processor URL: {self.document_processor_url}")

    async def convert_to_pdf(self, file_content: BinaryIO, file_name: str) -> Tuple[bytes, Optional[str]]:
        """
        Convert a document to PDF using the document processor service
        
        Args:
            file_content: Binary file content
            file_name: Name of the file
            
        Returns:
            Tuple of (pdf_content, error_message)
        """
        try:
            # Prepare the file upload
            data = aiohttp.FormData()
            data.add_field('file',
                          file_content,
                          filename=file_name,
                          content_type='application/octet-stream')
            
            # API endpoint for document conversion
            url = f"{self.document_processor_url}/api/convert"
            
            # Create a timeout for the request
            timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes timeout
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                logger.info(f"Sending conversion request for {file_name} to {url}")
                
                async with session.post(url, data=data) as response:
                    if response.status == 200:
                        logger.info(f"Successfully converted {file_name} to PDF")
                        return await response.read(), None
                    else:
                        error_msg = await response.text()
                        logger.error(f"Failed to convert {file_name} to PDF: {error_msg}")
                        return None, f"Conversion failed: {error_msg}"
                        
        except Exception as e:
            logger.exception(f"Error converting {file_name} to PDF: {e}")
            return None, f"Conversion error: {str(e)}"
            
    async def extract_text(self, file_content: bytes, file_extension: str) -> Tuple[str, Optional[str]]:
        """
        Extract text from a document
        
        Args:
            file_content: Binary file content
            file_extension: File extension to determine processing method
            
        Returns:
            Tuple of (extracted_text, error_message)
        """
        try:
            # Create a temporary file to store the content
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                temp_file.write(file_content)
                temp_path = temp_file.name
                
            # Prepare the file upload
            data = aiohttp.FormData()
            data.add_field('file',
                           open(temp_path, 'rb'),
                           filename=f'document{file_extension}',
                           content_type='application/octet-stream')
            
            # API endpoint for text extraction
            url = f"{self.document_processor_url}/api/extract-text"
            
            # Create a timeout for the request
            timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes timeout
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                logger.info(f"Sending text extraction request to {url}")
                
                async with session.post(url, data=data) as response:
                    # Clean up temporary file
                    os.unlink(temp_path)
                    
                    if response.status == 200:
                        text_content = await response.text()
                        logger.info(f"Successfully extracted text ({len(text_content)} chars)")
                        return text_content, None
                    else:
                        error_msg = await response.text()
                        logger.error(f"Failed to extract text: {error_msg}")
                        return "", f"Text extraction failed: {error_msg}"
        
        except Exception as e:
            logger.exception(f"Error extracting text: {e}")
            return "", f"Text extraction error: {str(e)}"
            
    async def extract_metadata(self, file_content: bytes, file_extension: str) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Extract metadata from a document
        
        Args:
            file_content: Binary file content
            file_extension: File extension to determine processing method
            
        Returns:
            Tuple of (metadata_dict, error_message)
        """
        try:
            # Create a temporary file to store the content
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                temp_file.write(file_content)
                temp_path = temp_file.name
                
            # Prepare the file upload
            data = aiohttp.FormData()
            data.add_field('file',
                           open(temp_path, 'rb'),
                           filename=f'document{file_extension}',
                           content_type='application/octet-stream')
            
            # API endpoint for metadata extraction
            url = f"{self.document_processor_url}/api/extract-metadata"
            
            # Create a timeout for the request
            timeout = aiohttp.ClientTimeout(total=60)  # 1 minute timeout
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                logger.info(f"Sending metadata extraction request to {url}")
                
                async with session.post(url, data=data) as response:
                    # Clean up temporary file
                    os.unlink(temp_path)
                    
                    if response.status == 200:
                        metadata = await response.json()
                        logger.info(f"Successfully extracted metadata: {metadata}")
                        return metadata, None
                    else:
                        error_msg = await response.text()
                        logger.error(f"Failed to extract metadata: {error_msg}")
                        return {}, f"Metadata extraction failed: {error_msg}"
        
        except Exception as e:
            logger.exception(f"Error extracting metadata: {e}")
            return {}, f"Metadata extraction error: {str(e)}"

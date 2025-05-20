\
"""
Metadata Extraction Utilities
-----------------------------
Utility functions for extracting metadata from documents.
"""
import os
import logging
import tempfile
import aiohttp
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

async def extract_metadata_service(file_content: bytes, file_extension: str, document_processor_url: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Extract metadata from a document using the document processor service.
    """
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_file.write(file_content)
            temp_path = temp_file.name

        data = aiohttp.FormData()
        data.add_field('file',
                       open(temp_path, 'rb'),
                       filename=f'document{file_extension}',
                       content_type='application/octet-stream')

        url = f"{document_processor_url}/api/extract-metadata"
        timeout = aiohttp.ClientTimeout(total=60)  # 1 minute timeout

        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.info(f"Sending metadata extraction request to {url}")
            async with session.post(url, data=data) as response:
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

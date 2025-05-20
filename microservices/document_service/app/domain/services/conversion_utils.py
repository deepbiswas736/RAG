\
"""
File Conversion Utilities
-------------------------
Utility functions for file conversion operations.
"""
import logging
import aiohttp
from typing import BinaryIO, Tuple, Optional

logger = logging.getLogger(__name__)

async def convert_to_pdf_service(file_content: BinaryIO, file_name: str, document_processor_url: str) -> Tuple[bytes, Optional[str]]:
    """
    Convert a document to PDF using the document processor service.
    """
    try:
        data = aiohttp.FormData()
        data.add_field('file',
                       file_content,
                       filename=file_name,
                       content_type='application/octet-stream')

        url = f"{document_processor_url}/api/convert"
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

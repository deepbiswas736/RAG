"""
Document Processing Service
------------------------
Domain service for handling document processing operations 
with locally installed Poppler and Tesseract services.
"""
import os
import aiohttp
import logging
import asyncio
import tempfile
import json
import io
import uuid
import subprocess
import shlex
import pytesseract
from pdf2image import convert_from_bytes
from typing import Dict, Any, Optional, BinaryIO, Tuple, List
from PyPDF2 import PdfReader
from PIL import Image

# Configure logging
logger = logging.getLogger(__name__)


class PageContent:
    """Domain value object representing extracted page content"""
    
    def __init__(self, page_num: int, text: str, extraction_method: str):
        self.page_num = page_num
        self.text = text
        self.extraction_method = extraction_method  # 'pdf_extract' or 'ocr'
        
    @property
    def has_content(self) -> bool:
        """Check if the page has meaningful text content"""
        return bool(self.text and not self.text.isspace())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'page': self.page_num,
            'text': self.text,
            'method': self.extraction_method
        }


class DocumentProcessingService:
    """
    Domain service that handles document processing operations.
    
    This service is responsible for extracting text content from PDF documents
    using a combination of direct PDF text extraction and OCR when needed,
    leveraging locally installed Poppler and Tesseract tools.
    """
    
    def __init__(self, document_processor_url: str = None):
        """
        Initialize the document processing service
        
        Args:
            document_processor_url: URL of the document processor service
        """
        # External service configuration
        self.document_processor_url = document_processor_url or os.getenv(
            "DOCUMENT_PROCESSOR_URL", "http://document-processor:8080"
        )
        
        # Setup temporary directories for processing
        self.pdf_processing_dir = os.environ.get('PDF_PROCESSING_DIR', os.path.abspath('./data/pdf_processing'))
        self.ocr_processing_dir = os.environ.get('OCR_PROCESSING_DIR', os.path.abspath('./data/ocr_processing'))
        
        # Ensure directories exist
        os.makedirs(self.pdf_processing_dir, exist_ok=True)
        os.makedirs(self.ocr_processing_dir, exist_ok=True)
        
        # Configure OCR parameters
        self.ocr_language = os.environ.get('OCR_LANGUAGE', 'eng')  # Default to English
        self.pdf_dpi = int(os.environ.get('PDF_DPI', '300'))  # Default DPI for PDF conversion
          # Verify tools are installed
        self._verify_tools_installed()
        
        # Log configuration
        logger.info(f"Document processor URL: {self.document_processor_url}")
        logger.info(f"Using local Poppler and Tesseract for document processing")
        logger.info(f"PDF processing directory: {self.pdf_processing_dir}")
        logger.info(f"OCR processing directory: {self.ocr_processing_dir}")
        
    def _verify_tools_installed(self):
        """Verify that required tools are installed and available"""
        try:
            # Check Poppler (pdftoppm) availability
            result = subprocess.run(
                ["pdftoppm", "-v"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            if result.returncode == 0:
                logger.info("Poppler tools (pdftoppm) is available")
            else:
                logger.warning("Poppler tools may not be properly installed")
                
            # Check Tesseract availability
            result = subprocess.run(
                ["tesseract", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            if result.returncode == 0:
                logger.info("Tesseract OCR is available")
            else:
                logger.warning("Tesseract OCR may not be properly installed")
                
        except Exception as e:
            logger.error(f"Error verifying tools: {e}")
            logger.warning("Document processing may be limited due to missing tools")

    async def extract_text(self, file_content: bytes, file_extension: str) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Extract text from a document using Poppler and Tesseract for OCR if needed.
        Only processes PDF files.
        
        Args:
            file_content: Binary file content
            file_extension: File extension to determine processing method
            
        Returns:
            Tuple of (structured_content, error_message)
            structured_content is a dictionary containing:
                - document_text: Combined text with page markers (str)
                - pages: Dictionary of page objects, each containing page text and metadata
        """
        try:
            # Domain rule: Only PDF files are handled by our specialized extraction pipeline
            if file_extension.lower() == '.pdf':
                logger.info(f"Processing PDF document with specialized extraction pipeline")
                return await self._extract_text_from_pdf(file_content)
            else:
                logger.warning(f"File with extension {file_extension} is not supported for text extraction")
                return {"document_text": "", "pages": {}}, f"Unsupported file type: {file_extension}. Only PDF files are supported."
        
        except Exception as e:
            logger.exception(f"Error extracting text: {e}")
            return {"document_text": "", "pages": {}}, f"Text extraction error: {str(e)}"
    
    async def _extract_text_from_pdf(self, pdf_content: bytes) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Extract text from a PDF using a two-phase approach:
        1. Try direct text extraction from PDF
        2. Fall back to OCR for pages without extractable text
        
        Args:
            pdf_content: PDF binary content
            
        Returns:
            Tuple of (structured_content, error_message)
            structured_content is a dictionary containing:
                - document_text: Combined text with page markers (str)
                - pages: Dictionary of page objects, each containing page text and metadata
        """
        try:
            # First extract text using PyPDF2 (direct PDF text extraction)
            pdf_file = io.BytesIO(pdf_content)
            reader = PdfReader(pdf_file)
            num_pages = len(reader.pages)
            logger.info(f"PDF has {num_pages} pages")
            
            # Collection of page contents (domain objects)
            page_contents = {}
            
            # Convert PDF to images using local Poppler for potential OCR
            logger.info(f"Converting PDF pages to images using local Poppler tools (DPI: {self.pdf_dpi})...")
            try:
                images = await self._convert_pdf_to_images(pdf_content)
                if images:
                    logger.info(f"Successfully extracted {len(images)} images from PDF via Poppler")
                else:
                    logger.warning("Poppler failed to convert PDF to images. OCR will not be available.")
            except Exception as img_err:
                logger.error(f"Error converting PDF to images: {img_err}")
                images = []
            
            # Domain process: Extract text from each page using two-phase approach
            for i, page in enumerate(reader.pages):
                page_num = i + 1
                page_text = ""
                extraction_method = "pdf_extract"
                
                # Phase 1: Try to extract text directly from PDF with PyPDF2
                try:
                    page_text = page.extract_text()
                    if page_text and not page_text.isspace():
                        logger.info(f"Extracted text from page {page_num} using PyPDF2: {len(page_text)} chars")
                    else:
                        page_text = ""
                        logger.info(f"No text extracted from page {page_num} using PyPDF2")
                except Exception as text_err:
                    logger.error(f"Error extracting text from page {page_num}: {text_err}", exc_info=True)
                    page_text = ""
                
                # Phase 2: If direct extraction failed and we have an image, try OCR with Tesseract
                if (not page_text) and i < len(images):
                    logger.info(f"Page {page_num}: No text via PyPDF2, attempting OCR with Tesseract")
                    
                    # Use local Tesseract for OCR
                    page_text = await self._process_with_tesseract(images[i])
                    if page_text and not page_text.isspace():
                        logger.info(f"OCR extracted {len(page_text)} characters from page {page_num}")
                        extraction_method = "ocr"
                    else:
                        logger.warning(f"OCR returned empty or whitespace text for page {page_num}")
                        page_text = ""
                elif not page_text:
                    # Log why OCR wasn't attempted if text is missing
                    if i >= len(images):
                        logger.warning(f"Page {page_num}: No text via PyPDF2 and no corresponding image available for OCR")
                  # Store the page content if we have text
                if page_text:
                    # Create domain object
                    page_contents[page_num] = PageContent(
                        page_num=page_num,
                        text=page_text,
                        extraction_method=extraction_method
                    )
            
            # Format output: Combine all page texts into a single document with page markers
            combined_text = ""
            for page_num in sorted(page_contents.keys()):
                combined_text += f"\n\n=== PAGE {page_num} ===\n\n"
                combined_text += page_contents[page_num].text
            
            # Create structured page content representation
            structured_content = {
                'document_text': combined_text.strip() if combined_text else "",
                'pages': {page_num: page_contents[page_num].to_dict() for page_num in sorted(page_contents.keys())}
            }
            
            if combined_text:
                logger.info(f"Successfully extracted text from {len(page_contents)} pages")
                return structured_content, None
            else:
                error_msg = "No text could be extracted from any page"
                logger.warning(error_msg)
                return {"document_text": "", "pages": {}}, error_msg
                
        except Exception as e:
            logger.exception(f"Error extracting text from PDF: {e}")
            return {"document_text": "", "pages": {}}, f"PDF text extraction error: {str(e)}"
    
    async def _process_with_tesseract(self, image: Image.Image) -> str:
        """
        Process an image with the local Tesseract installation for OCR.
        
        Args:
            image: The PIL Image object to process
            
        Returns:
            Extracted text from the image
        """
        try:
            # Generate a unique identifier for this processing request
            unique_id = str(uuid.uuid4())
            image_filename = f"image_{unique_id}.jpg"
            
            # Create a path for temporary image storage
            image_path = os.path.join(self.ocr_processing_dir, image_filename)
            
            # Save the image for OCR processing
            image.save(image_path, "JPEG")
            logger.info(f"Saved image to {image_path} for OCR processing")
            
            # Process the image with pytesseract (running in the same process)
            # Running in a thread to avoid blocking the event loop
            ocr_text = await asyncio.to_thread(
                pytesseract.image_to_string,
                image,
                lang=self.ocr_language,
                config='--psm 1'  # Automatic page segmentation with OSD
            )
            
            if ocr_text and not ocr_text.isspace():
                logger.info(f"OCR extracted {len(ocr_text)} characters")
            else:
                logger.warning("OCR returned empty or whitespace text")
                ocr_text = ""
            
            # Clean up the temporary image file
            try:
                if os.path.exists(image_path):
                    os.remove(image_path)
            except Exception as e:
                logger.warning(f"Cleanup error: {e}")
            
            return ocr_text
            
        except Exception as e:
            logger.error(f"Error using Tesseract OCR: {e}", exc_info=True)
            # Attempt cleanup even on general error
            try:
                if 'image_path' in locals() and os.path.exists(image_path):
                    os.remove(image_path)
            except Exception as cleanup_err:
                logger.warning(f"Cleanup error during exception handling: {cleanup_err}")
            return ""
    
    async def _convert_pdf_to_images(self, pdf_content: bytes) -> List[Image.Image]:
        """
        Convert PDF pages to images using local Poppler (pdf2image).
        
        Args:
            pdf_content: PDF binary content
            
        Returns:
            List of PIL Image objects, one per page
        """
        try:
            # Use python-based pdf2image which uses poppler under the hood
            # Run in a thread to avoid blocking the event loop
            logger.info(f"Converting PDF to images with DPI: {self.pdf_dpi}")
            
            # Convert directly from bytes to images
            images = await asyncio.to_thread(
                convert_from_bytes,
                pdf_content,
                dpi=self.pdf_dpi,
                fmt='jpeg'
            )
            
            logger.info(f"Successfully converted PDF to {len(images)} images")
            return images
            
        except Exception as e:
            logger.exception(f"Error converting PDF to images: {e}")
            return []
    
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

\
"""
PDF Processing Utilities
------------------------
Utility functions for PDF processi        for page_num in sorted(page_contents_dict.keys()):
            combined_text += f"\\n\\n=== PAGE {page_num} ===\\n\\n"
            combined_text += page_contents_dict[page_num].text
            
        structured_content = {
            'document_text': combined_text.strip() if combined_text else "",
            'pages': {str(page_num): pc.to_dict() for page_num, pc in page_contents_dict.items()}
        }cluding text extraction and conversion.
"""
import io
import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from PyPDF2 import PdfReader
from PIL import Image
from pdf2image import convert_from_bytes
from .page_content import PageContent # Assuming PageContent is in the same directory

logger = logging.getLogger(__name__)

async def extract_text_from_pdf_page(page, page_num: int, image: Optional[Image.Image], ocr_processing_dir: str, ocr_language: str, process_with_tesseract_func) -> Optional[PageContent]:
    """
    Extracts text from a single PDF page, trying direct extraction first, then OCR.
    """
    page_text = ""
    extraction_method = "pdf_extract"

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

    if (not page_text) and image:
        logger.info(f"Page {page_num}: No text via PyPDF2, attempting OCR with Tesseract")
        page_text = await process_with_tesseract_func(image, ocr_processing_dir, ocr_language)
        if page_text and not page_text.isspace():
            logger.info(f"OCR extracted {len(page_text)} characters from page {page_num}")
            extraction_method = "ocr"
        else:
            logger.warning(f"OCR returned empty or whitespace text for page {page_num}")
            page_text = ""
    elif not page_text:
        if not image:
            logger.warning(f"Page {page_num}: No text via PyPDF2 and no corresponding image available for OCR")

    if page_text:
        return PageContent(
            page_num=page_num,
            text=page_text,
            extraction_method=extraction_method
        )
    return None

async def extract_text_from_pdf_content(pdf_content: bytes, pdf_dpi: int, ocr_processing_dir: str, ocr_language: str, convert_pdf_to_images_func, process_with_tesseract_func) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Extract text from a PDF using a two-phase approach:
    1. Try direct text extraction from PDF
    2. Fall back to OCR for pages without extractable text
    """
    try:
        pdf_file = io.BytesIO(pdf_content)
        reader = PdfReader(pdf_file)
        num_pages = len(reader.pages)
        logger.info(f"PDF has {num_pages} pages")

        page_contents_dict = {}

        logger.info(f"Converting PDF pages to images using local Poppler tools (DPI: {pdf_dpi})...")
        try:
            images = await convert_pdf_to_images_func(pdf_content, pdf_dpi)
            if images:
                logger.info(f"Successfully extracted {len(images)} images from PDF via Poppler")
            else:
                logger.warning("Poppler failed to convert PDF to images. OCR will not be available.")
        except Exception as img_err:
            logger.error(f"Error converting PDF to images: {img_err}")
            images = []

        tasks = []
        for i, page in enumerate(reader.pages):
            page_num = i + 1
            image = images[i] if i < len(images) else None
            tasks.append(extract_text_from_pdf_page(page, page_num, image, ocr_processing_dir, ocr_language, process_with_tesseract_func))
        
        extracted_pages = await asyncio.gather(*tasks)

        for pc in extracted_pages:
            if pc:
                page_contents_dict[pc.page_num] = pc
        combined_text = ""
        for page_num in sorted(page_contents_dict.keys()):
            combined_text += f"\n\n=== PAGE {page_num} ===\n\n"
            combined_text += page_contents_dict[page_num].text
        
        structured_content = {
            'document_text': combined_text.strip() if combined_text else "",
            'pages': {str(page_num): pc.to_dict() for page_num, pc in page_contents_dict.items()}
        }

        if combined_text:
            logger.info(f"Successfully extracted text from {len(page_contents_dict)} pages")
            return structured_content, None
        else:
            error_msg = "No text could be extracted from any page"
            logger.warning(error_msg)
            return {"document_text": "", "pages": {}}, error_msg

    except Exception as e:
        logger.exception(f"Error extracting text from PDF: {e}")
        return {"document_text": "", "pages": {}}, f"PDF text extraction error: {str(e)}"

async def convert_pdf_to_images_local(pdf_content: bytes, pdf_dpi: int) -> List[Image.Image]:
    """
    Convert PDF pages to images using local Poppler (pdf2image).
    """
    try:
        logger.info(f"Converting PDF to images with DPI: {pdf_dpi}")
        images = await asyncio.to_thread(
            convert_from_bytes,
            pdf_content,
            dpi=pdf_dpi,
            fmt='jpeg'
        )
        logger.info(f"Successfully converted PDF to {len(images)} images")
        return images
    except Exception as e:
        logger.exception(f"Error converting PDF to images: {e}")
        return []

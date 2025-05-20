\
"""
OCR Processing Utilities
------------------------
Utility functions for OCR processing using Tesseract.
"""
import os
import logging
import asyncio
import uuid
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

async def process_with_tesseract_local(image: Image.Image, ocr_processing_dir: str, ocr_language: str) -> str:
    """
    Process an image with the local Tesseract installation for OCR.
    """
    try:
        unique_id = str(uuid.uuid4())
        image_filename = f"image_{unique_id}.jpg"
        image_path = os.path.join(ocr_processing_dir, image_filename)

        image.save(image_path, "JPEG")
        logger.info(f"Saved image to {image_path} for OCR processing")

        ocr_text = await asyncio.to_thread(
            pytesseract.image_to_string,
            image,
            lang=ocr_language,
            config='--psm 1'  # Automatic page segmentation with OSD
        )

        if ocr_text and not ocr_text.isspace():
            logger.info(f"OCR extracted {len(ocr_text)} characters")
        else:
            logger.warning("OCR returned empty or whitespace text")
            ocr_text = ""

        try:
            if os.path.exists(image_path):
                os.remove(image_path)
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")

        return ocr_text

    except Exception as e:
        logger.error(f"Error using Tesseract OCR: {e}", exc_info=True)
        try:
            if 'image_path' in locals() and os.path.exists(image_path):
                os.remove(image_path)
        except Exception as cleanup_err:
            logger.warning(f"Cleanup error during exception handling: {cleanup_err}")
        return ""

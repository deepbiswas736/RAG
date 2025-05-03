import logging
import io
import os
import subprocess
import tempfile
import uuid
import asyncio
from typing import List, Dict
from pdf2image import convert_from_bytes, pdfinfo_from_bytes # Import pdfinfo_from_bytes
from PyPDF2 import PdfReader
from PIL import Image
import pytesseract  # Added for OCR capabilities
import shlex
import hashlib

from ..entities.document import Document, Chunk
from ..value_objects.embedding import Embedding
from ..value_objects.metadata import DocumentMetadata
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_container_name(service_name: str) -> str:
    """Try to get the actual running container name for a given service name using 'docker ps'."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            encoding="utf-8"
        )
        container_names = result.stdout.splitlines()
        # Try exact match first
        for name in container_names:
            if name == service_name:
                return name
        # Try partial match (e.g., rag-poppler-1 for poppler)
        for name in container_names:
            if service_name in name:
                return name
        # Fallback to original service name
        return service_name
    except Exception as e:
        logger.warning(f"Could not resolve container name for {service_name}: {e}")
        return service_name

class DocumentProcessingService:
    def __init__(self):
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        # Text chunking parameters (for non-PDFs)
        self.chunk_size = 1000
        self.chunk_overlap = 200

        # Check for Docker services
        self.poppler_service = os.environ.get('POPPLER_SERVICE')
        self.tesseract_service = os.environ.get('TESSERACT_SERVICE')
        # Resolve actual container names if running on Windows
        if self.poppler_service:
            self.poppler_service = get_container_name(self.poppler_service)
        if self.tesseract_service:
            self.tesseract_service = get_container_name(self.tesseract_service)

        # Check local availability ONLY if Docker services are not specified
        # Availability is TRUE if the service is specified, otherwise check locally.
        self.poppler_available = bool(self.poppler_service) or self._check_poppler_availability()
        self.ocr_available = bool(self.tesseract_service) or self._check_ocr_availability()

        # Logging service status
        if self.poppler_service:
            logger.info(f"Using dedicated Poppler service: {self.poppler_service}")
        elif self.poppler_available:
            logger.info("Using local Poppler installation")
        else:
            logger.warning("Poppler utilities (service or local) not available. PDF image extraction will be disabled.")

        if self.tesseract_service:
            logger.info(f"Using dedicated Tesseract service: {self.tesseract_service}")
        elif self.ocr_available:
            logger.info("Using local Tesseract installation")
        else:
            logger.warning("Tesseract OCR (service or local) not available. OCR will be disabled.")

    def _check_poppler_availability(self):
        """Check if poppler utils are likely available in the current environment."""
        try:
            # Common paths where poppler binaries might be located
            common_paths = [
                "/usr/bin/pdftoppm",  # Linux
                "/usr/local/bin/pdftoppm",  # macOS with brew
                "C:\\Program Files\\poppler\\bin\\pdftoppm.exe",  # Windows
            ]
            
            # Check if any of these paths exist
            for path in common_paths:
                if os.path.exists(path):
                    logger.info(f"Found Poppler at: {path}")
                    return True
                    
            # Try to run pdftoppm with subprocess to check if it's in PATH
            try:
                subprocess.run(["pdftoppm", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                logger.info("Poppler is available in PATH")
                return True
            except (subprocess.SubprocessError, FileNotFoundError):
                logger.warning("Poppler not found in PATH")
                return False
        except Exception as e:
            logger.warning(f"Poppler check failed: {e}")
            return False

    def _check_ocr_availability(self):
        """Check if Tesseract OCR is available in the current environment."""
        try:
            # Check for environment variable with Tesseract path
            tesseract_path = os.environ.get('TESSERACT_PATH')
            
            if os.name == 'nt':  # Windows
                # Check common Windows Tesseract install locations if path not specified
                if not tesseract_path:
                    common_paths = [
                        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                        r"C:\Tesseract-OCR\tesseract.exe"
                    ]
                    for path in common_paths:
                        if os.path.exists(path):
                            tesseract_path = path
                            break
                
                if tesseract_path and os.path.exists(tesseract_path):
                    pytesseract.pytesseract.tesseract_cmd = tesseract_path
                    logger.info(f"Tesseract OCR found at {tesseract_path}")
                    return True
                else:
                    logger.warning(f"Tesseract OCR not found on Windows. Searched paths: {tesseract_path or 'default Windows paths'}")
                    return False
            else:  # Linux/Mac
                try:
                    # Test if tesseract is available
                    result = subprocess.run(["tesseract", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                    if result.returncode == 0:
                        logger.info("Tesseract OCR is available locally")
                        return True
                    else:
                        logger.warning(f"Tesseract test failed with code {result.returncode}")
                        return False
                except (subprocess.SubprocessError, FileNotFoundError) as e:
                    logger.warning(f"Tesseract OCR not found: {e}")
                    return False
        except Exception as e:
            logger.warning(f"Error checking for Tesseract: {e}")
            return False

    async def _process_with_docker_tesseract(self, image):
        """Process an image with the tesseractshadow/tesseract4re Docker service"""
        if not self.tesseract_service:
            logger.error("Attempted to use Docker Tesseract service, but TESSERACT_SERVICE env var is not set.")
            return ""
        try:
            # Save image to the shared volume
            unique_id = str(uuid.uuid4())
            image_filename = f"image_{unique_id}.jpg"
            output_filename = f"output_{unique_id}"

            # Create paths for the image and text output
            # Use absolute paths for Docker volume mounts (Windows host)
            ocr_dir = os.environ.get('OCR_PROCESSING_DIR', os.path.abspath('./data/ocr_processing'))
            os.makedirs(ocr_dir, exist_ok=True)

            image_path = os.path.join(ocr_dir, image_filename)

            # Save the image for OCR processing
            image.save(image_path, "JPEG")
            logger.info(f"Saved image to {image_path} for Docker OCR processing")

            # Wait a moment for file system sync (might be needed on some systems)
            await asyncio.sleep(0.5)

            # Execute tesseract in the Docker container
            # Note: The container has mounted the host's ./data/ocr_processing to /app/tesseractshadow
            container_name = self.tesseract_service # Use the service name from env var

            # Command to run inside Docker (paths are relative to the container's mount point)
            # Use absolute paths within the container's filesystem
            container_image_path = f"/app/tesseractshadow/{image_filename}"
            container_output_base = f"/app/tesseractshadow/{output_filename}"
            cmd = f"docker exec {container_name} tesseract {container_image_path} {container_output_base}"
            logger.info(f"Running OCR command: {cmd}")

            def run_shell_command(cmd):
                import shlex, subprocess
                return subprocess.run(
                    shlex.split(cmd),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False
                )
            process = await asyncio.to_thread(run_shell_command, cmd)
            stdout = process.stdout
            stderr = process.stderr

            if process.returncode != 0:
                logger.error(f"Docker OCR process failed with code {process.returncode}")
                logger.error(f"Stdout: {stdout.decode(errors='replace') if stdout else 'None'}")
                logger.error(f"Stderr: {stderr.decode(errors='replace') if stderr else 'None'}")
                # Clean up image even on failure
                try:
                    os.remove(image_path)
                except Exception as e:
                    logger.warning(f"Cleanup error after failed OCR: {e}")
                return ""

            # Wait for the OCR process to complete and check for the output txt file
            txt_path = os.path.join(ocr_dir, f"{output_filename}.txt") # Path on the host

            # Wait for the text file to appear
            max_attempts = 10
            ocr_text = ""
            for attempt in range(max_attempts):
                if os.path.exists(txt_path):
                    # Read the OCR result
                    try:
                        with open(txt_path, 'r', encoding='utf-8', errors='replace') as f:
                            ocr_text = f.read()
                        logger.info(f"Docker OCR extracted {len(ocr_text)} characters")
                        break # Exit loop on success
                    except Exception as read_err:
                        logger.error(f"Error reading OCR output file {txt_path}: {read_err}")
                        ocr_text = "" # Ensure text is empty on read error
                        break # Exit loop on read error

                logger.info(f"Waiting for OCR result file {txt_path} (attempt {attempt+1}/{max_attempts})")
                await asyncio.sleep(1)

            if not ocr_text:
                 logger.warning(f"Docker OCR did not produce a readable output file at {txt_path} after {max_attempts} attempts")

            # Clean up files
            try:
                if os.path.exists(image_path): os.remove(image_path)
                if os.path.exists(txt_path): os.remove(txt_path)
            except Exception as e:
                logger.warning(f"Cleanup error: {e}")

            return ocr_text

        except Exception as e:
            logger.error(f"Error using Docker Tesseract service: {e}", exc_info=True)
            # Attempt cleanup even on general error
            try:
                if 'image_path' in locals() and os.path.exists(image_path): os.remove(image_path)
                if 'txt_path' in locals() and os.path.exists(txt_path): os.remove(txt_path)
            except Exception as cleanup_err:
                 logger.warning(f"Cleanup error during exception handling: {cleanup_err}")
            return ""

    async def _convert_pdf_to_images_with_docker_poppler(self, pdf_content: bytes, title: str, dpi: int = 300) -> List[Image.Image]:
        """Convert PDF pages to images using the Poppler Docker service."""
        if not self.poppler_service:
            logger.error("Attempted to use Docker Poppler service, but POPPLER_SERVICE env var is not set.")
            return []

        images = []
        unique_id = str(uuid.uuid4())
        # For debugging: always use test.pdf and testpage as output prefix
        pdf_filename = "test.pdf"
        output_prefix = "testpage"

        # Use correct absolute paths for Docker volume mounts
        host_pdf_dir = os.environ.get('PDF_PROCESSING_DIR', os.path.abspath('./data/pdf_processing'))
        container_pdf_dir = '/data'
        # Output images will be written to pdf_processing (shared with Poppler)
        container_output_path_prefix = os.path.join(container_pdf_dir, output_prefix).replace("\\", "/")
        host_output_dir = host_pdf_dir

        os.makedirs(host_pdf_dir, exist_ok=True)

        host_pdf_path = os.path.join(host_pdf_dir, pdf_filename)
        # Ensure container paths use forward slashes for Linux compatibility
        container_pdf_path = os.path.join(container_pdf_dir, pdf_filename).replace("\\", "/")
        # Output images will be written to ocr_processing
        container_output_path_prefix = os.path.join(container_pdf_dir, output_prefix).replace("\\", "/")

        try:
            # 1. Write PDF to the shared volume (host side)
            with open(host_pdf_path, 'wb') as f:
                f.write(pdf_content)
            logger.info(f"Saved PDF to {host_pdf_path} for Docker Poppler processing")
            # Log file size and hash for debugging
            pdf_size = os.path.getsize(host_pdf_path)
            with open(host_pdf_path, 'rb') as f:
                pdf_hash = hashlib.md5(f.read()).hexdigest()
            logger.info(f"PDF file size: {pdf_size} bytes, MD5 hash: {pdf_hash}")

            # Add check to see if file exists on host before proceeding
            if not os.path.exists(host_pdf_path):
                logger.error(f"CRITICAL: PDF file {host_pdf_path} does not exist on host immediately after writing!")
                # This indicates a fundamental problem with file writing or the path
                return []
            else:
                logger.info(f"Confirmed PDF file exists at {host_pdf_path} before Docker exec.")

            # Increase sleep duration significantly to allow for filesystem sync
            sync_delay = 3.0 # Increased to 3 seconds
            logger.info(f"Waiting {sync_delay} seconds for filesystem sync before Docker exec...")
            await asyncio.sleep(sync_delay)

            # 2. Execute pdftoppm in the Docker container
            container_name = self.poppler_service # Use service name from env var
            # Command: pdftoppm [options] <PDF-file> <image-root>
            # We use -jpeg for output format. Output files will be <image-root>-<page_number>.jpg
            # Added -v for verbose error messages from pdftoppm
            cmd = f"docker exec {container_name} pdftoppm -jpeg -r {dpi} {container_pdf_path} {container_output_path_prefix}"
            logger.info(f"Running Poppler command: {cmd}")

            
            def run_shell_command(cmd):
                return subprocess.run(
                    shlex.split(cmd),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False
                )
            process = await asyncio.to_thread(run_shell_command, cmd)
            stdout = process.stdout
            stderr = process.stderr

            # Log stdout and stderr from docker exec
            stdout_decoded = stdout.decode(errors='replace') if stdout else 'None'
            stderr_decoded = stderr.decode(errors='replace') if stderr else 'None'
            logger.info(f"Docker Poppler stdout: {stdout_decoded}")
            logger.info(f"Docker Poppler stderr: {stderr_decoded}")


            if process.returncode != 0:
                logger.error(f"Docker Poppler process failed with code {process.returncode}")
                # Log stderr again specifically on error
                logger.error(f"Docker Poppler stderr on failure: {stderr_decoded}")
                # Clean up PDF even on failure
                try:
                    os.remove(host_pdf_path)
                except Exception as e:
                    logger.warning(f"Cleanup error after failed Poppler: {e}")
                return []

            logger.info("Docker Poppler process completed successfully (return code 0).")

            # After running Poppler, log the directory contents
            logger.info(f"Files in {host_output_dir} after Poppler: {os.listdir(host_output_dir)}")

            # 3. Find and load the generated images from the shared volume (host side)
            # Use PyPDF2 to get the number of pages (cross-platform, no poppler dependency)
            try:
                reader = PdfReader(io.BytesIO(pdf_content))
                num_pages = len(reader.pages)
                if num_pages == 0:
                    logger.warning("Could not determine number of pages from PyPDF2. Cannot load images.")
                    return []
                logger.info(f"PDF has {num_pages} pages. Looking for generated images.")
            except Exception as info_err:
                logger.error(f"Could not get PDF info to determine page count: {info_err}")
                return []

            max_wait_attempts = 15
            loaded_images = 0
            for i in range(1, num_pages + 1):
                expected_image_filename = f"{output_prefix}-{i}.jpg"
                host_image_path = os.path.join(host_output_dir, expected_image_filename).replace("\\", "/")
                logger.debug(f"Checking for image file on host: {host_image_path}") # Log path being checked

                image_found = False
                for attempt in range(max_wait_attempts):
                    if os.path.exists(host_image_path):
                        try:
                            img = Image.open(host_image_path)
                            images.append(img.copy()) # Append a copy
                            img.close() # Close the file handle
                            loaded_images += 1
                            logger.info(f"Loaded image: {host_image_path}")
                            image_found = True
                            break # Exit wait loop for this page
                        except Exception as img_err:
                            logger.error(f"Error loading image {host_image_path}: {img_err}")
                            # Don't break here, maybe it appears later? Or is corrupted?
                    if not image_found:
                         logger.debug(f"Waiting for image {host_image_path} (attempt {attempt+1}/{max_wait_attempts})")
                         await asyncio.sleep(1) # Wait before next check

                if not image_found:
                     logger.warning(f"Image file {host_image_path} not found or loaded after {max_wait_attempts} attempts.")
                     # Decide whether to continue or fail? Let's continue for now.

            logger.info(f"Successfully loaded {loaded_images}/{num_pages} images via Docker Poppler.")
            return images

        except Exception as e:
            logger.error(f"Error using Docker Poppler service: {e}", exc_info=True)
            images = [] # Ensure empty list on error
        finally:
            # 4. Clean up temporary files (PDF and any generated images on host)
            try:
                if os.path.exists(host_pdf_path):
                    os.remove(host_pdf_path)
                    logger.debug(f"Cleaned up PDF: {host_pdf_path}")
                # Clean up any image files matching the pattern
                for item in os.listdir(host_pdf_dir):
                    if item.startswith(output_prefix) and item.endswith(".jpg"):
                        item_path = os.path.join(host_pdf_dir, item)
                        try:
                            os.remove(item_path)
                            logger.debug(f"Cleaned up image: {item_path}")
                        except Exception as rm_err:
                            logger.warning(f"Error removing image file {item_path}: {rm_err}")
            except Exception as cleanup_err:
                logger.warning(f"Error during Poppler cleanup: {cleanup_err}")

        return images


    async def _process_pdf_with_poppler_service(self, document: Document) -> List[Chunk]:
        """Process PDF using the dedicated Poppler service with OCR fallback."""
        chunks = []

        # First analyze PDF structure to understand what we're dealing with
        # Pass availability flags to analysis
        await self._analyze_pdf_structure(document.content, document.title, self.poppler_available, self.ocr_available)

        try:
            # First extract text using PyPDF2 (this works without Poppler)
            pdf_file = io.BytesIO(document.content)
            reader = PdfReader(pdf_file)
            num_pages = len(reader.pages)
            logger.info(f"PDF has {num_pages} pages.")

            # Track if we have any text content across all pages
            has_text_content = False

            # If we have a dedicated poppler service OR local poppler, use it for image extraction
            images = []
            if self.poppler_service:
                logger.info("Attempting to convert PDF pages to images using Docker Poppler service...")
                images = await self._convert_pdf_to_images_with_docker_poppler(document.content, document.title)
                if images:
                     logger.info(f"Successfully extracted {len(images)} images from PDF via Docker Poppler")
                else:
                     logger.warning("Docker Poppler service failed to return images.")
            elif self.poppler_available: # Use local poppler via pdf2image
                 try:
                    logger.info("Attempting to convert PDF pages to images using local Poppler via pdf2image...")
                    # pdf2image might still need poppler path configured depending on OS/install
                    images = convert_from_bytes(document.content, dpi=300, fmt='jpeg')
                    logger.info(f"Successfully extracted {len(images)} images from PDF via local Poppler")
                 except Exception as img_err:
                    logger.error(f"Failed to extract images using local Poppler (pdf2image): {img_err}", exc_info=True)
                    images = [] # Ensure images is empty on failure
            else:
                logger.warning("Poppler service/local installation not available. Cannot extract images for OCR.")

            # Process text and images
            for i, page in enumerate(reader.pages):
                page_num = i + 1
                page_text = ""

                # Try to extract text with PyPDF2
                try:
                    page_text = page.extract_text()
                    if not page_text or page_text.isspace():
                        page_text = ""
                        logger.info(f"No text extracted from page {page_num} using PyPDF2")
                    else:
                        logger.info(f"Extracted text from page {page_num} using PyPDF2: {len(page_text)} chars")
                        has_text_content = True # Mark that we got *some* text directly
                except Exception as text_err:
                    logger.error(f"Error extracting text from page {page_num}: {text_err}", exc_info=True)
                    page_text = ""

                # If no text was extracted AND images were successfully extracted for this page, try OCR
                ocr_attempted = False
                if (not page_text or page_text.isspace()) and i < len(images):
                    logger.info(f"Page {page_num}: No text via PyPDF2, attempting OCR as image is available.")
                    ocr_attempted = True
                    if self.tesseract_service:
                        # Use our Docker Tesseract service
                        logger.info(f"Attempting OCR on page {page_num} using Docker Tesseract service...")
                        page_text = await self._process_with_docker_tesseract(images[i])
                        if page_text and not page_text.isspace():
                            logger.info(f"Docker OCR extracted {len(page_text)} characters from page {page_num}")
                        else:
                            logger.warning(f"Docker OCR returned empty or whitespace text for page {page_num}")
                            page_text = "" # Ensure it's empty string
                    elif self.ocr_available:
                        # Fall back to local OCR if Docker service is not available but local is
                        try:
                            logger.info(f"Attempting OCR on page {page_num} with local Tesseract via pytesseract...")
                            page_text = pytesseract.image_to_string(images[i])
                            if page_text and not page_text.isspace():
                                logger.info(f"Local OCR extracted {len(page_text)} characters from page {page_num}")
                            else:
                                logger.warning(f"Local OCR returned empty or whitespace text for page {page_num}")
                                page_text = "" # Ensure it's empty string
                        except Exception as ocr_err:
                            logger.error(f"Local OCR failed on page {page_num}: {ocr_err}", exc_info=True)
                            page_text = "" # Ensure it's empty string
                    else:
                        # This case should ideally not happen if self.ocr_available was checked, but log just in case
                        logger.warning(f"Page {page_num}: OCR needed but no OCR service (Docker or local) is available.")
                        page_text = ""
                elif not page_text or page_text.isspace():
                    # Log why OCR wasn't attempted if text is missing
                    if i >= len(images):
                         logger.warning(f"Page {page_num}: No text via PyPDF2 and no corresponding image available/extracted for OCR (image index {i} out of bounds for {len(images)} images).")
                    # else: no suitable space found, use the original 'end'

                # Create chunk for page text if text exists (either extracted or OCR'd)
                if page_text and not page_text.isspace():
                    try:
                        embedding_vector = self.encoder.encode(page_text)
                        # Determine extraction method for metadata
                        extraction_method = 'pdf_extract'
                        if ocr_attempted and not has_text_content: # If OCR was tried AND we never got text directly
                             extraction_method = 'ocr'
                        elif ocr_attempted and has_text_content: # If OCR was tried but we also got direct text (maybe earlier pages)
                             extraction_method = 'ocr_fallback' # Or maybe just 'ocr'? Clarify needed. Let's use 'ocr' if this specific page needed it.
                             if not page.extract_text() or page.extract_text().isspace(): # Check *this* page specifically
                                 extraction_method = 'ocr'

                        # Generate a unique ID for the chunk using UUID
                        chunk_id = str(uuid.uuid4())

                        chunk = Chunk(
                            id=chunk_id,  # Set a unique ID here
                            content=page_text,
                            embedding=Embedding.create(embedding_vector.tolist()),
                            metadata=DocumentMetadata.from_dict({
                                **document.metadata.__dict__,
                                'page_number': page_num,
                                'content_type': 'text',
                                'extraction_method': extraction_method
                            }),
                            source=f"{document.title} (Page {page_num})"
                        )
                        chunks.append(chunk)
                        logger.info(f"Created chunk for page {page_num} with {len(page_text)} chars (Method: {extraction_method}, ID: {chunk_id})")
                    except Exception as e:
                        logger.error(f"Failed to encode text chunk for page {page_num}: {e}", exc_info=True)

            # Log final results
            if not chunks:
                logger.warning(f"PDF processing complete but no chunks were created for {document.title}")
                logger.warning("This could be due to: 1) The PDF is image-only and OCR failed or is unavailable, "
                              "2) The PDF has content protection, 3) The PDF has no extractable text, "
                              "4) Errors during processing.")
            else:
                logger.info(f"Successfully created {len(chunks)} chunks for {document.title}")

        except Exception as e:
            logger.error(f"Failed to process PDF document {document.title}: {e}", exc_info=True)

        return chunks

    async def process_document(self, document: Document) -> Document:
        """Process a document based on its type and create chunks with embeddings"""
        # Correctly access the attribute, providing a default if None or missing
        file_type = getattr(document.metadata, 'file_type', 'unknown') or 'unknown'
        logger.info(f"Processing document: {document.title}, Type: {file_type}")

        if file_type == 'application/pdf':
            # Use the new method that can work with the Poppler service
            chunks = await self._process_pdf_with_poppler_service(document)
        elif file_type.startswith('text/'):
            chunks = self._process_text(document)
        else:
            logger.warning(f"Unsupported file type '{file_type}' for document {document.title}. Attempting text processing.")
            # Fallback to text processing, might fail or produce poor results
            chunks = self._process_text(document)

        document.chunks = chunks
        logger.info(f"Finished processing. Created {len(chunks)} chunks for document: {document.title}")
        return document

    async def _process_pdf(self, document: Document) -> List[Chunk]:
        """Legacy PDF processing method - now redirects to the new method"""
        return await self._process_pdf_with_poppler_service(document)

    def _process_text(self, document: Document) -> List[Chunk]:
        """Process plain text documents using fixed-size chunking."""
        chunks = []
        try:
            # Decode content bytes to string here, handling potential errors
            text_content = document.content.decode('utf-8', errors='replace')
            logger.info(f"Successfully decoded text content for document: {document.title}")
        except Exception as e:
            logger.error(f"Failed to decode content for document {document.title}: {e}")
            return [] # Return empty list if decoding fails

        if not text_content or text_content.isspace():
             return []

        # Use the existing text chunking logic (now moved here)
        start = 0
        text_len = len(text_content)
        while start < text_len:
            logger.debug(f"Loop start: start={start}, text_len={text_len}") # Add debug log

            # Calculate potential end, ensuring it doesn't exceed text length
            end = min(start + self.chunk_size, text_len)
            actual_end = end
            logger.debug(f"Calculated end={end}, actual_end={actual_end}") # Add debug log

            # Try to find a space to break cleanly, only if not at the very end
            if end < text_len:
                search_pos = end - 1 # Start searching from the character before potential cut
                while search_pos > start and not text_content[search_pos].isspace(): # Check isspace() correctly
                    search_pos -= 1
                
                # If a space was found after the start position, adjust the end
                if search_pos > start:
                    actual_end = search_pos + 1 # Cut after the space
                    logger.debug(f"Found space at {search_pos}, adjusted actual_end={actual_end}") # Add debug log
                # else: no suitable space found, use the original 'end'

            # Slice the text to get the chunk content
            chunk_text = text_content[start:actual_end]
            logger.debug(f"Sliced chunk_text from {start} to {actual_end}") # Add debug log

            # Avoid creating empty chunks
            if not chunk_text or chunk_text.isspace():
                logger.warning(f"Skipping empty chunk from {start} to {actual_end}") # Add warning log
                start = actual_end # Move start past the empty/whitespace chunk
                continue

            # Generate embedding
            try:
                embedding_vector = self.encoder.encode(chunk_text)
            except Exception as e:
                logger.error(f"Failed to encode text chunk for document {document.title}: {e}")
                # Advance start to avoid getting stuck on problematic chunk
                start = actual_end - self.chunk_overlap
                if start < 0: start = 0
                if start >= actual_end: start = actual_end # Ensure progress
                continue

            # Generate a unique ID for the chunk using UUID
            chunk_id = str(uuid.uuid4())

            chunk = Chunk(
                id=chunk_id,  # Set a unique ID here
                content=chunk_text,
                embedding=Embedding.create(embedding_vector.tolist()),
                metadata=DocumentMetadata.from_dict({
                    **document.metadata.__dict__,
                    'start_char': start,
                    'end_char': actual_end,
                    'content_type': 'text'
                }),
                source=document.title
            )
            chunks.append(chunk)
            logger.debug(f"Appended chunk. Current count: {len(chunks)}") # Add debug log
            
            # Move start for the next chunk, considering overlap
            next_start = actual_end - self.chunk_overlap
            # Ensure start doesn't become negative due to overlap
            if next_start < 0:
                next_start = 0
                
            # Prevent infinite loop if overlap is too large or chunk size too small
            if next_start >= actual_end:
                 logger.warning(f"Chunk overlap issue detected near position {actual_end} in {document.title}. Calculated next_start={next_start}. Moving start forward.")
                 start = actual_end # Ensures progress
            else:
                 start = next_start

            logger.debug(f"Updated start for next iteration: {start}") # Add debug log

        return chunks

    async def _analyze_pdf_structure(self, content: bytes, title: str, poppler_is_available: bool, ocr_is_available: bool):
        """Analyze PDF structure to determine characteristics"""
        try:
            pdf_file = io.BytesIO(content)
            reader = PdfReader(pdf_file)
            num_pages = len(reader.pages)
            logger.info(f"PDF '{title}' has {num_pages} pages")
            
            # Check for text on each page
            has_text = False
            text_pages = 0
            empty_pages = 0
            
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and not text.isspace():
                    has_text = True
                    text_pages += 1
                    logger.info(f"Page {i+1}: Contains text ({len(text)} chars)")
                else:
                    empty_pages += 1
                    logger.info(f"Page {i+1}: No extractable text")
            
            # Check if PDF has any form fields (interactive PDF)
            has_form = False
            try:
                if hasattr(reader, 'get_fields') and callable(reader.get_fields):
                    fields = reader.get_fields()
                    has_form = fields is not None and len(fields) > 0
                    if has_form:
                        logger.info(f"PDF contains {len(fields)} form fields - it's an interactive PDF")
            except Exception as e:
                logger.warning(f"Couldn't check for form fields: {e}")
            
            # Check if PDF has any images
            has_images = False # Default to False
            if poppler_is_available:
                try:
                    # This is a simplistic test - in reality, determining if a PDF has images
                    # requires parsing the PDF structure which is complex
                    images = convert_from_bytes(content, dpi=72, fmt='jpeg') # Low DPI for faster check
                    has_images = len(images) > 0
                    if has_images:
                        logger.info(f"PDF contains {len(images)} image-based pages (checked via Poppler)")
                    else:
                        logger.info("PDF does not appear to contain images (checked via Poppler)")
                except Exception as e:
                    logger.warning(f"Couldn't check for images using Poppler: {e}")
                    # Keep has_images as False if check fails
            else:
                logger.warning("Cannot check for images because Poppler is not available.")
                # When Poppler is unavailable, we cannot determine if there are images.
                # Set has_images to None to indicate uncertainty.
                has_images = None

            # Determine if likely scanned: No text AND (has images OR image check was not possible)
            likely_scanned = not has_text and (has_images is True or has_images is None)

            analysis = {
                "title": title,
                "num_pages": num_pages,
                "contains_text": has_text,
                "text_pages": text_pages,
                "empty_pages": empty_pages,
                "is_form": has_form,
                # "likely_scanned": not has_text and has_images, # Old logic
                "likely_scanned": likely_scanned, # Updated logic
                "ocr_available": ocr_is_available,
                "poppler_available": poppler_is_available
            }
            
            logger.info(f"PDF Analysis: {analysis}")
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing PDF structure: {e}")
            return {"error": str(e)}